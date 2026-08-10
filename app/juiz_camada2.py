"""Juiz da rubrica Task Completion (ADR-0004 SS2.2, debito #19).

Avalia se a `recomendacao` de um memo PRONTO e defensavel pelos
`fatores_cliente` que o proprio agente levantou. Contrato DIFERENTE do
gerador (app/clientes_llm.py): o gerador conduz multi-hop de ferramentas e
devolve um memo; o juiz recebe memo + trace e devolve um veredito, uma
pergunta por vez. `ClienteGroq.__doc__` em clientes_llm.py ja registrava essa
lacuna - este modulo a fecha.

Reproduz a MESMA rubrica aplicada nos 87 labels humanos
(data/labels/task_completion_labels.json): "recomendacao_ignora_fato" e a
categoria de falha que apareceu em 10/87 casos rotulados a mao.

Familia diferente do gerador de proposito (ADR-0004 SS2.3, mitigacao de
self-enhancement bias, Zheng et al. NeurIPS 2023): o gerador padrao e
Gemini (ClienteGemini), o juiz e Groq/Llama.

NAO e a rubrica de groundedness nem de trajetoria - essas sao mecanicas
(validar_groundedness, validar_trajetoria em agente_underwriting.py), sem
juiz LLM envolvido.
"""
import json
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from app.clientes_llm import (
    MAX_TENTATIVAS_PADRAO,
    TEMPERATURA_PADRAO,
    DependenciaAusente,
    FalhaProvider,
    RespostaLLMInvalida,
    _chamar_com_retry,
    _contabilizar_tokens,
)
from app.config import exigir_chave
from app.ferramentas_caso import ChamadaFerramenta
from app.memo_credito import MemoCredito

# Reusa a politica de retry/contagem de tokens do gerador (clientes_llm.py)
# em vez de duplicar: mesma decisao de engenharia (debito #20), duas
# interfaces diferentes (proxima_acao multi-hop vs perguntar pergunta unica).


class VeredictoTaskCompletion(str, Enum):
    OK = "OK"
    FALHA = "FALHA"


@dataclass
class ResultadoJuizTaskCompletion:
    veredito: VeredictoTaskCompletion
    evidencia: str
    categoria_falha: str = ""
    # Debito #33 / ADR-0012: sinal deterministico, NAO vem do LLM. Marca
    # quando a evidencia do juiz admite nao ter achado dado nenhum - esse
    # padrao especifico resistiu a correcao via prompt (validado empirico
    # 2026-08-10), entao a checagem roda no texto ja produzido em vez de
    # confiar em instrucao nova.
    suspeito_dado_ausente: bool = False


class JuizLLM(Protocol):
    """Contrato do juiz: uma pergunta, uma resposta - sem multi-hop de
    ferramentas. Diferente do ClienteLLM do gerador (agente_underwriting.py),
    que conduz varias idas e voltas ate concluir."""

    def perguntar(self, prompt_sistema: str, prompt_usuario: str) -> str:
        ...


class ClienteGroqJuiz:
    """Adaptador Groq para o PAPEL DE JUIZ.

    A chave (GROQ_API_KEY) e a mesma do gerador alternativo ClienteGroq em
    clientes_llm.py; a interface nao - aqui e uma pergunta e uma resposta,
    la e conduzir multi-hop. Ver aviso no docstring de ClienteGroq.
    """

    def __init__(
        self,
        modelo: str = "llama-3.3-70b-versatile",
        api_key: str | None = None,
        temperatura: float = TEMPERATURA_PADRAO,
        max_tentativas: int = MAX_TENTATIVAS_PADRAO,
    ):
        try:
            from groq import Groq  # type: ignore[import-not-found]
        except ImportError as e:
            raise DependenciaAusente(
                "SDK do Groq nao instalado. Rode: pip install -r requirements-llm.txt"
            ) from e

        chave = api_key or exigir_chave("GROQ_API_KEY")
        self._client = Groq(api_key=chave)
        self._modelo_nome = modelo
        self._temperatura = temperatura
        self._max_tentativas = max_tentativas
        self.n_chamadas = 0
        self.tentativas_gastas = 0
        self.tokens = {"input": 0, "output": 0, "thinking": 0, "total": 0, "medido": 0}

    def perguntar(self, prompt_sistema: str, prompt_usuario: str) -> str:
        def _pedir():
            return self._client.chat.completions.create(
                model=self._modelo_nome,
                response_format={"type": "json_object"},
                temperature=self._temperatura,
                messages=[
                    {"role": "system", "content": prompt_sistema},
                    {"role": "user", "content": prompt_usuario},
                ],
            )

        self.n_chamadas += 1
        try:
            resposta, tentativas = _chamar_com_retry(_pedir, self._max_tentativas)
        except FalhaProvider as e:
            self.tentativas_gastas += e.tentativas
            raise
        self.tentativas_gastas += tentativas
        for chave, valor in _contabilizar_tokens(resposta).items():
            self.tokens[chave] += valor
        return resposta.choices[0].message.content


def _prompt_sistema_juiz() -> str:
    """Prompt do juiz. Os limiares vem do ADR-0011, nao de intuicao.

    A versao anterior mandava marcar FALHA quando a recomendacao
    "contraria o peso predominante dos fatores" - isso media a REDACAO do
    memo (o agente escolhe como rotular cada peso), nao os fatos do
    cliente, e qualquer proxy que tambem contasse pesos concordava com o
    juiz por construcao. Trocado por criterio sobre os campos brutos.
    """
    return (
        "Voce e um AUDITOR independente de decisoes de credito. Voce nao "
        "decide credito - avalia se uma recomendacao JA TOMADA por outro "
        "agente e DEFENSAVEL.\n\n"
        "Voce recebe um memo (recomendacao + fatores citados) e os dados "
        "brutos das ferramentas.\n\n"
        "CRITERIO (aplica-se apenas quando a recomendacao e NEGAR):\n\n"
        "NEGAR e DEFENSAVEL se houver 1 SINAL GRAVE ou 2+ AGRAVANTES.\n\n"
        "SINAIS GRAVES (qualquer um basta):\n"
        "  - utilizacao de credito no bureau >= 80%\n"
        "  - pior_atraso_dias nesta casa >= 30 dias\n\n"
        "AGRAVANTES (precisam de pelo menos dois):\n"
        "  - deficit_medio_pct >= 15% (paga sistematicamente a menor)\n"
        "  - n_em_atraso_hoje >= 1 no bureau\n"
        "  - pior_atraso_dias >= 15 E dias_desde_ultimo_atraso <= 90\n"
        "    (atraso relevante E recente - os dois juntos, nunca so um)\n\n"
        "Sem sinal grave e com no maximo 1 agravante, NEGAR e INDEFENSAVEL: "
        "marque FALHA com categoria_falha 'recomendacao_ignora_fato'.\n\n"
        "Dado indisponivel (None, 'nao disponivel', ou similar) NAO conta "
        "como sinal favoravel nem como ausencia de risco - e apenas "
        "incerteza. A falta de um numero, sozinha, NUNCA torna NEGAR "
        "indefensavel: avalie SOMENTE os sinais e agravantes que de fato "
        "estao presentes nos dados brutos, e ignore os que faltam ao "
        "aplicar o criterio acima.\n\n"
        "O CRITERIO ACIMA E O UNICO CRITERIO. Se 1 sinal grave ou 2+ "
        "agravantes estiverem presentes, o veredito e OK - pare ai. NAO "
        "pondere depois se 'o historico e bom demais para negar' ou se "
        "'o sinal grave parece questionavel' - isso reintroduz o "
        "julgamento implicito que o ADR-0011 existe para eliminar. Uma "
        "vez que voce confirmou o sinal/agravante nos dados brutos, o "
        "veredito esta decidido; nao existe segunda camada de analise.\n\n"
        "NAO conte quantos fatores sao favoraveis ou desfavoraveis - o "
        "agente escolhe esses rotulos, entao contar peso mede a redacao do "
        "memo, nao o risco do cliente. Leia os NUMEROS das ferramentas.\n\n"
        "Pagar a menor de forma cronica, sozinho, NAO justifica negar: "
        "cliente que nunca deixou de pagar e antecipa parcelas mas entrega "
        "menos e caso de LIMITE MENOR, nao de recusa.\n\n"
        "Se a recomendacao for APROVAR ou DEFERIR, marque OK - este "
        "criterio so cobre recusa.\n\n"
        "Responda SOMENTE com um objeto JSON, sem texto fora do JSON:\n"
        '{"veredito": "OK" ou "FALHA", '
        '"evidencia": "<numeros especificos e quais sinais faltaram>", '
        '"categoria_falha": "recomendacao_ignora_fato" ou ""}\n\n'
        "Em `evidencia`, cite os NUMEROS e diga quais sinais do criterio "
        "estavam presentes ou ausentes. 'parece bom pagador' NAO e "
        "evidencia aceitavel. Exemplo bom: 'utilizacao 47%, deficit 0%, "
        "pior atraso 4d - nenhum sinal grave e apenas 1 agravante "
        "(1 contrato em atraso no bureau), mas recomendacao foi NEGAR'."
    )


def _prompt_usuario_juiz(memo: MemoCredito, trace: list[ChamadaFerramenta]) -> str:
    fatos = "\n".join(
        f"  [{f.peso.value}] {f.fato} (fonte: {f.fonte_tool})"
        for f in memo.fatores_cliente
    )
    dados_brutos = "\n".join(
        f"  {c.ferramenta}({c.argumentos}) -> {c.retorno}" for c in trace
    ) or "  (nenhuma chamada na trace)"
    faltante = "\n".join(f"  - {i}" for i in memo.informacao_faltante) or "  (nenhuma)"

    return (
        f"RECOMENDACAO DO MEMO: {memo.recomendacao.value}\n\n"
        f"FATORES CITADOS NO MEMO:\n{fatos}\n\n"
        f"INFORMACAO FALTANTE DECLARADA:\n{faltante}\n\n"
        f"DADOS BRUTOS DAS FERRAMENTAS (confira se ha algo relevante que o "
        f"memo nao citou):\n{dados_brutos}\n"
    )


# Debito #33 / ADR-0012. Termos que o juiz usa quando conclui "nao ha
# dado" - vocabulario observado nos 11 casos reais do rerun de 2026-08-10
# (reports/calibracao_juiz.md). Heuristica de texto, mesma familia de
# validar_groundedness_numerica: se o vocabulario do juiz mudar, isto
# precisa ser revisto (mesma limitacao ja assumida no debito #26).
_TERMOS_DADO_AUSENTE = ("nao disponivel", "none", "nao disponiveis")

# Campos do criterio do ADR-0011 que, se vierem None, sao o gatilho do #33.
_CAMPOS_CRITERIO_ADR_0011 = (
    "utilizacao", "pior_atraso_dias", "deficit_medio_pct",
    "n_em_atraso_hoje", "dias_desde_ultimo_atraso",
)


def _evidencia_admite_dado_ausente(evidencia: str) -> bool:
    """A evidencia do juiz, em si, diz que nao achou dado nenhum?"""
    texto = evidencia.lower()
    return any(termo in texto for termo in _TERMOS_DADO_AUSENTE)


def _campos_criterio_estao_none(trace: list[ChamadaFerramenta]) -> bool:
    """Confirma contra os DADOS BRUTOS (nao contra a opiniao do juiz) que os
    campos do ADR-0011 realmente vieram None - sem isso, um FALHA legitimo
    que so MENCIONA a palavra "disponivel" de passagem seria marcado suspeito
    por engano."""
    valores = {}
    for c in trace:
        for campo in _CAMPOS_CRITERIO_ADR_0011:
            if campo in c.retorno:
                valores[campo] = c.retorno[campo]
    if not valores:
        return False
    return any(v is None for v in valores.values())


def suspeito_dado_ausente(
    resultado: ResultadoJuizTaskCompletion, trace: list[ChamadaFerramenta]
) -> bool:
    """Padrao do debito #33: veredito FALHA justificado so pela ausencia de
    dado, nao por sinal encontrado. NAO sobrescreve o veredito - so sinaliza,
    mesmo tratamento nao-eliminatorio do #26 (ADR-0012)."""
    if resultado.veredito != VeredictoTaskCompletion.FALHA:
        return False
    return (
        _evidencia_admite_dado_ausente(resultado.evidencia)
        and _campos_criterio_estao_none(trace)
    )


def _parse_resposta_juiz(bruto: str) -> ResultadoJuizTaskCompletion:
    try:
        dados = json.loads(bruto)
    except json.JSONDecodeError as e:
        raise RespostaLLMInvalida(
            f"juiz nao devolveu JSON valido: {e}\nbruto: {bruto[:500]}"
        ) from e

    veredito_bruto = dados.get("veredito")
    if veredito_bruto not in ("OK", "FALHA"):
        raise RespostaLLMInvalida(
            f"juiz devolveu veredito fora do contrato: {veredito_bruto!r}"
        )

    evidencia = (dados.get("evidencia") or "").strip()
    categoria = (dados.get("categoria_falha") or "").strip()
    # Mesmo padrao de rigor exigido do humano na rotulagem (debito #29):
    # FALHA sem fato nomeado nao e evidencia utilizavel para calibrar nada.
    if veredito_bruto == "FALHA" and not evidencia:
        raise RespostaLLMInvalida(
            "juiz marcou FALHA sem evidencia - contrato exige fato nomeado"
        )

    return ResultadoJuizTaskCompletion(
        veredito=VeredictoTaskCompletion(veredito_bruto),
        evidencia=evidencia,
        categoria_falha=categoria,
    )


def julgar_task_completion(
    memo: MemoCredito,
    trace: list[ChamadaFerramenta],
    cliente_juiz: JuizLLM,
) -> ResultadoJuizTaskCompletion:
    """Rubrica Task Completion do ADR-0004: a recomendacao e defensavel
    pelos fatos que o proprio memo levantou?

    Nao reavalia groundedness (mecanica, validar_groundedness) nem
    trajetoria (mecanica, validar_trajetoria) - so a rubrica que exige
    juizo, a mesma que voce aplicou a mao nos 87 labels.
    """
    resposta = cliente_juiz.perguntar(
        _prompt_sistema_juiz(), _prompt_usuario_juiz(memo, trace)
    )
    resultado = _parse_resposta_juiz(resposta)
    resultado.suspeito_dado_ausente = suspeito_dado_ausente(resultado, trace)
    return resultado

