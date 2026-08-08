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
    return (
        "Voce e um AUDITOR independente de decisoes de credito. Voce nao "
        "decide credito - avalia se uma recomendacao JA TOMADA por outro "
        "agente e DEFENSAVEL pelos fatos que ele mesmo levantou.\n\n"
        "Voce recebe um memo (recomendacao + fatores_cliente, cada um "
        "marcado como favoravel/desfavoravel/neutro) e os dados brutos das "
        "ferramentas que originaram esses fatos.\n\n"
        "Responda SOMENTE com um objeto JSON, sem texto fora do JSON:\n"
        '{"veredito": "OK" ou "FALHA", '
        '"evidencia": "<fato especifico, nunca generico>", '
        '"categoria_falha": "recomendacao_ignora_fato" ou ""}\n\n'
        "Marque FALHA quando a recomendacao contraria o peso predominante "
        "dos fatores listados no memo (ex.: memo recomenda NEGAR mas os "
        "fatores sao majoritariamente favoraveis, ou o oposto). Em "
        "`evidencia`, cite o FATO ESPECIFICO e o numero exato que a "
        "recomendacao ignorou - 'parece ser bom pagador' NAO e evidencia "
        "aceitavel, tem que nomear o dado (ex.: 'atraso medio de -11.6 dias "
        "e 0 parcelas nunca pagas, mas recomendacao foi NEGAR').\n\n"
        "Marque OK quando a recomendacao segue logicamente do peso dos "
        "fatores - mesmo que um analista mais cauteloso pedisse mais "
        "informacao antes de decidir (isso seria DEFERIR, nao e FALHA de "
        "Task Completion)."
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
    return _parse_resposta_juiz(resposta)
