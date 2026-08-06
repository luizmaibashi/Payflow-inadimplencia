"""Adaptadores reais do `ClienteLLM` (ADR-0003) — Gemini e Groq.

Implementam so o Protocol de app/agente_underwriting.py: recebem contexto +
ferramentas disponiveis, devolvem a proxima acao. Toda a logica de
orquestracao (teto de chamadas, cegueira ao score, groundedness) fica em
agente_underwriting.py — este modulo so traduz JSON <-> dataclasses.

Saida estruturada (nao texto livre + parser regex): cada provider tem um modo
de "JSON garantido" (Gemini response_mime_type, Groq response_format
json_object). Delegar a validacao de formato ao provider elimina a classe de
erro "modelo devolveu texto que quase e JSON" antes mesmo do parser rodar.
Decisao registrada em ADR (ver adr-generator).
"""
import json
import random
import re
import time

from pydantic import ValidationError

from app.agente_underwriting import AcaoChamarFerramenta, AcaoConcluir, ClienteLLM
from app.config import exigir_chave
from app.memo_credito import MemoCredito

# Mensagem de instalacao por adaptador. O SDK e importado LAZY (dentro do
# __init__, nao no topo): a suite dos 103 testes roda sem nenhum SDK, o que
# preserva o design da Camada 2 — ela foi construida e testada SEM LLM, com o
# cliente injetado. Import no topo faria o teste de cegueira ao score (o mais
# importante do projeto) depender de ter o SDK do Google instalado.
# O preco do lazy — falha so em runtime — e pago com a mensagem acionavel abaixo.
_INSTALACAO = "pip install -r requirements-llm.txt"

# Temperatura 0 por padrao. Regra de reprodutibilidade da base ("seeds fixos"):
# com temperatura alta, dois runs do MESMO caso dao memos diferentes, e ai um
# delta entre dois prompts pode ser so ruido de amostragem. O ADR-0004 ja avisa
# que delta de 4pp com n=100 e menos da metade do ruido — nao da para somar
# ruido de decodificacao em cima disso. NAO garante determinismo perfeito
# (provider nao promete), mas remove a fonte que esta sob nosso controle.
TEMPERATURA_PADRAO = 0.0


class RespostaLLMInvalida(Exception):
    """JSON do provider nao bateu com o contrato esperado (acao/memo)."""


class DependenciaAusente(RuntimeError):
    """SDK do provider nao instalado. Mensagem diz exatamente o que rodar."""


class FalhaProvider(RuntimeError):
    """Falha do provider que sobreviveu ao retry. Carrega quantas tentativas
    foram gastas para que o eval consiga separar 'o provider oscilou' de
    'o provider esta fora'."""

    def __init__(self, mensagem: str, tentativas: int):
        super().__init__(mensagem)
        self.tentativas = tentativas


# --- Retry: politica DERIVADA de medicao, nao de precaucao (debito #20) ---
#
# O debito #20 dizia "adaptador sem retry/timeout/controle de custo - decisao
# consciente de MEDIR ANTES". A medicao saiu no piloto de 2026-08-06:
#   - gemini-2.5-pro devolve 429 com `limit: 0` (nao tem free tier nenhum);
#   - gemini-2.5-flash atende ~1 caso e entra em 429 de RPM;
#   - o provider manda junto o quanto esperar ("Please retry in 39.6s").
#
# Duas decisoes que caem dessa medicao:
#
# 1. ESPERAR O QUE O PROVIDER MANDOU, quando ele manda. Backoff exponencial
#    cego ignoraria a informacao mais confiavel disponivel e chutaria por
#    cima ou por baixo.
# 2. NAO RETENTAR ERRO PERMANENTE. 429 e 5xx oscilam; 401/403 (chave errada)
#    e 400 (requisicao malformada) nao melhoram com espera - retentar so
#    multiplica o tempo ate a mensagem util aparecer.
#
# `RespostaLLMInvalida` tambem NAO e retentada, e isso e o ponto mais sutil:
# ela e o modelo devolvendo JSON fora do contrato, que e uma taxa que o eval
# PRECISA medir (ADR-0004). Retentar por baixo dos panos transformaria uma
# metrica de qualidade do gerador em ruido invisivel.
MAX_TENTATIVAS_PADRAO = 3
ESPERA_BASE_S = 2.0
ESPERA_MAXIMA_S = 45.0      # teto por espera individual
TETO_ESPERA_TOTAL_S = 120.0  # teto acumulado por chamada - controle de custo

# 4xx que nao melhoram com espera. 408 (timeout) e 429 (rate limit) ficam de
# fora de proposito: sao os 4xx que de fato oscilam.
_HTTP_PERMANENTES = frozenset({400, 401, 403, 404, 422})


def _status_http(erro: Exception) -> int | None:
    """Extrai o status HTTP da excecao do SDK, se houver.

    Os SDKs nao concordam no nome do atributo, entao tentamos os conhecidos em
    vez de depender de um. None = nao deu para saber; nesse caso tratamos como
    transitorio (melhor uma espera a mais que abortar um lote por engano)."""
    for attr in ("code", "status_code", "status"):
        valor = getattr(erro, attr, None)
        if isinstance(valor, int):
            return valor
    return None


def _delay_sugerido(erro: Exception) -> float | None:
    """Quanto o PROVIDER pediu para esperar. Preferido sobre qualquer backoff
    nosso: e a unica fonte que sabe quando a janela de quota reabre."""
    bruto = getattr(erro, "retry_delay", None)
    segundos = getattr(bruto, "seconds", bruto)
    if isinstance(segundos, (int, float)) and segundos > 0:
        return float(segundos)

    # Fallback: o texto do 429 do Gemini traz "Please retry in 39.639939506s."
    achado = re.search(r"retry in ([\d.]+)s", str(erro))
    return float(achado.group(1)) if achado else None


def _contabilizar_tokens(resposta) -> dict[str, int]:
    """Tokens que o PROVIDER diz ter cobrado - medicao, nao estimativa.

    Existe porque estimar por contagem de caracteres erra justamente onde
    doi: `thoughts_token_count` (o raciocinio interno dos modelos 2.5) e
    cobrado como output e NAO aparece no texto da resposta. Uma estimativa
    por chars nao tem como enxerga-lo, e ele costuma ser a maior parte da
    conta.

    Defensivo de proposito: SDK que nao reporta uso devolve zeros em vez de
    quebrar o lote. Zero aqui significa "nao medido", nao "de graca" - o
    relatorio precisa dizer isso, senao um lote sem telemetria vira "custo
    zero" no report.
    """
    uso = getattr(resposta, "usage_metadata", None) or getattr(resposta, "usage", None)
    if uso is None:
        return {"input": 0, "output": 0, "thinking": 0, "total": 0, "medido": 0}

    def _campo(*nomes) -> int:
        for nome in nomes:
            valor = getattr(uso, nome, None)
            if isinstance(valor, int):
                return valor
        return 0

    # 1o nome = Gemini, 2o = padrao OpenAI/Groq
    entrada = _campo("prompt_token_count", "prompt_tokens")
    saida = _campo("candidates_token_count", "completion_tokens")
    pensamento = _campo("thoughts_token_count", "reasoning_tokens")
    total = _campo("total_token_count", "total_tokens")
    return {
        "input": entrada,
        "output": saida,
        "thinking": pensamento,
        "total": total or (entrada + saida + pensamento),
        "medido": 1,
    }


def _chamar_com_retry(fn, max_tentativas: int):
    """Executa `fn` com backoff. Devolve (resultado, tentativas_gastas)."""
    espera_acumulada = 0.0
    ultimo: Exception | None = None

    for tentativa in range(1, max_tentativas + 1):
        try:
            return fn(), tentativa
        except RespostaLLMInvalida:
            raise  # contrato, nao transporte - sobe limpo para o eval contar
        except Exception as erro:  # noqa: BLE001 - SDKs nao expoem hierarquia util
            ultimo = erro
            status = _status_http(erro)
            if status in _HTTP_PERMANENTES:
                raise FalhaProvider(
                    f"erro permanente do provider (HTTP {status}): {erro}", tentativa
                ) from erro
            if tentativa == max_tentativas:
                break

            sugerido = _delay_sugerido(erro)
            if sugerido is None:
                sugerido = ESPERA_BASE_S * (2 ** (tentativa - 1))
            # Jitter: varias chamadas que levam 429 ao mesmo tempo nao podem
            # voltar todas no mesmo instante e derrubar a quota de novo.
            espera = min(sugerido, ESPERA_MAXIMA_S) * random.uniform(0.8, 1.2)

            if espera_acumulada + espera > TETO_ESPERA_TOTAL_S:
                raise FalhaProvider(
                    f"teto de espera de {TETO_ESPERA_TOTAL_S:.0f}s por chamada "
                    f"estourado apos {tentativa} tentativa(s): {erro}",
                    tentativa,
                ) from erro

            time.sleep(espera)
            espera_acumulada += espera

    raise FalhaProvider(
        f"provider falhou em {max_tentativas} tentativa(s): {ultimo}", max_tentativas
    ) from ultimo


def _prompt_sistema(ferramentas: dict[str, str]) -> str:
    lista_ferramentas = "\n".join(f"  - {nome}: {desc}" for nome, desc in ferramentas.items())
    return (
        "Responda SOMENTE com um objeto JSON, sem texto fora do JSON.\n\n"
        "Duas formas validas de resposta:\n\n"
        '1) Chamar uma ferramenta:\n'
        '   {"acao": "chamar_ferramenta", "ferramenta": "<nome>", "argumentos": {}}\n\n'
        '2) Concluir com o parecer final:\n'
        '   {"acao": "concluir", "memo": {\n'
        '     "cliente_id": "<string>",\n'
        '     "recomendacao": "APROVAR" | "NEGAR" | "DEFERIR",\n'
        '     "fatores_cliente": [{"fato": "<string>", "fonte_tool": "<nome da ferramenta>", '
        '"peso": "favoravel" | "desfavoravel" | "neutro"}],\n'
        '     "cenario_assumido": {"lgd": <float 0-1>, "fonte": "<string>"},\n'
        '     "informacao_faltante": ["<string>"]\n'
        "   }}\n\n"
        "Ferramentas disponiveis:\n"
        f"{lista_ferramentas}\n"
    )


def _parse_resposta(bruto: str) -> AcaoChamarFerramenta | AcaoConcluir:
    try:
        dados = json.loads(bruto)
    except json.JSONDecodeError as e:
        raise RespostaLLMInvalida(f"resposta nao e JSON valido: {e}\nbruto: {bruto[:500]}") from e

    acao = dados.get("acao")
    if acao == "chamar_ferramenta":
        try:
            return AcaoChamarFerramenta(
                ferramenta=dados["ferramenta"], argumentos=dados.get("argumentos", {}))
        except KeyError as e:
            raise RespostaLLMInvalida(f"chamar_ferramenta sem campo obrigatorio: {e}") from e

    if acao == "concluir":
        try:
            memo = MemoCredito(**dados["memo"])
        except KeyError as e:
            raise RespostaLLMInvalida(f"concluir sem campo obrigatorio: {e}") from e
        # ESPECIFICA de proposito. `except Exception` capturaria tambem
        # AttributeError/TypeError — bugs DESTE modulo — e os disfarcaria de
        # "o modelo respondeu errado". Erro meu tem que estourar alto, nao
        # virar estatistica de resposta ruim do LLM.
        except ValidationError as e:
            raise RespostaLLMInvalida(f"memo nao bateu com o contrato: {e}") from e
        return AcaoConcluir(memo=memo)

    raise RespostaLLMInvalida(f"campo 'acao' desconhecido: {acao!r}")


class ClienteGemini:
    """GERADOR padrao da Camada 2: conduz o multi-hop e emite o memo.

    Modelo com raciocinio mais forte fica aqui de proposito — redigir parecer
    ponderando evidencia conflitante e a tarefa dificil da Camada 2.
    """

    def __init__(
        self,
        modelo: str = "gemini-2.5-pro",
        api_key: str | None = None,
        temperatura: float = TEMPERATURA_PADRAO,
        max_tentativas: int = MAX_TENTATIVAS_PADRAO,
    ):
        try:
            import google.generativeai as genai  # type: ignore[import-not-found]
        except ImportError as e:
            raise DependenciaAusente(
                f"SDK do Gemini nao instalado. Rode: {_INSTALACAO}") from e

        chave = api_key or exigir_chave("GEMINI_API_KEY")
        genai.configure(api_key=chave)
        self._genai = genai
        self._modelo_nome = modelo
        self._temperatura = temperatura
        self._max_tentativas = max_tentativas
        # Contadores para o eval separar "quantas vezes perguntei" de "quantas
        # idas ao provider isso custou". A diferenca e o retry, e sem ela a
        # taxa de falha bruta some por baixo do backoff.
        self.n_chamadas = 0
        self.tentativas_gastas = 0
        # Uso REPORTADO pelo provider, acumulado. `medido` conta quantas
        # respostas trouxeram telemetria: sem ele, um lote inteiro sem uso
        # reportado seria indistinguivel de um lote de graca.
        self.tokens = {"input": 0, "output": 0, "thinking": 0, "total": 0, "medido": 0}

    def proxima_acao(
        self, contexto: str, ferramentas: dict[str, str]
    ) -> AcaoChamarFerramenta | AcaoConcluir:
        modelo = self._genai.GenerativeModel(
            self._modelo_nome,
            system_instruction=_prompt_sistema(ferramentas),
            generation_config={
                "response_mime_type": "application/json",
                "temperature": self._temperatura,
            },
        )
        self.n_chamadas += 1
        # A contagem tem que subir TAMBEM quando a chamada morre - senao
        # `tentativas_gastas` fica menor que `n_chamadas` e a conta de retries
        # da negativa (bug visto no piloto de 2026-08-06: "-1 retries").
        try:
            resposta, tentativas = _chamar_com_retry(
                lambda: modelo.generate_content(contexto), self._max_tentativas
            )
        except FalhaProvider as e:
            self.tentativas_gastas += e.tentativas
            raise
        self.tentativas_gastas += tentativas
        self._somar_tokens(resposta)
        # Fora do retry DE PROPOSITO: JSON fora do contrato e qualidade do
        # gerador, metrica que o ADR-0004 quer medir - nao falha de transporte.
        return _parse_resposta(resposta.text)

    def _somar_tokens(self, resposta):
        for chave, valor in _contabilizar_tokens(resposta).items():
            self.tokens[chave] += valor


class ClienteGroq:
    """GERADOR alternativo — familia diferente (Llama) para comparar contra o
    Gemini na mesma tarefa.

    ⚠️ ISTO NAO E O JUIZ DO ADR-0004, apesar de a chave Groq ter sido criada
    para esse fim. O juiz avalia rubricas BINARIAS sobre um memo ja pronto
    (groundedness, task completion) — assinatura tipo `julgar(memo, trace) ->
    veredito`. Aqui a assinatura e `proxima_acao`, que e o contrato do
    GERADOR: conduzir multi-hop e emitir memo. Sao contratos diferentes.

    O juiz ainda nao existe no codigo. Quando existir, mora em modulo proprio
    e reusa `exigir_chave("GROQ_API_KEY")` — a chave serve aos dois papeis, a
    interface nao. Manter Llama como gerador alternativo tem valor separado:
    permite medir se o resultado depende do modelo ou do desenho.
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
                f"SDK do Groq nao instalado. Rode: {_INSTALACAO}") from e

        chave = api_key or exigir_chave("GROQ_API_KEY")
        self._client = Groq(api_key=chave)
        self._modelo_nome = modelo
        self._temperatura = temperatura
        self._max_tentativas = max_tentativas
        self.n_chamadas = 0
        self.tentativas_gastas = 0
        # Uso REPORTADO pelo provider, acumulado. `medido` conta quantas
        # respostas trouxeram telemetria: sem ele, um lote inteiro sem uso
        # reportado seria indistinguivel de um lote de graca.
        self.tokens = {"input": 0, "output": 0, "thinking": 0, "total": 0, "medido": 0}

    def proxima_acao(
        self, contexto: str, ferramentas: dict[str, str]
    ) -> AcaoChamarFerramenta | AcaoConcluir:
        def _pedir():
            return self._client.chat.completions.create(
                model=self._modelo_nome,
                response_format={"type": "json_object"},
                temperature=self._temperatura,
                messages=[
                    {"role": "system", "content": _prompt_sistema(ferramentas)},
                    {"role": "user", "content": contexto},
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
        return _parse_resposta(resposta.choices[0].message.content)


# Satisfaz o Protocol estruturalmente (typing.Protocol nao exige heranca
# explicita) — checagem estatica, nao roda em tempo de execucao.
_ADAPTADORES: tuple[type[ClienteLLM], ...] = (ClienteGemini, ClienteGroq)
