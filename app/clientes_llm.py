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
        resposta = modelo.generate_content(contexto)
        return _parse_resposta(resposta.text)


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

    def proxima_acao(
        self, contexto: str, ferramentas: dict[str, str]
    ) -> AcaoChamarFerramenta | AcaoConcluir:
        resposta = self._client.chat.completions.create(
            model=self._modelo_nome,
            response_format={"type": "json_object"},
            temperature=self._temperatura,
            messages=[
                {"role": "system", "content": _prompt_sistema(ferramentas)},
                {"role": "user", "content": contexto},
            ],
        )
        return _parse_resposta(resposta.choices[0].message.content)


# Satisfaz o Protocol estruturalmente (typing.Protocol nao exige heranca
# explicita) — checagem estatica, nao roda em tempo de execucao.
_ADAPTADORES: tuple[type[ClienteLLM], ...] = (ClienteGemini, ClienteGroq)
