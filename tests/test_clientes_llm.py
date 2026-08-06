"""Testes dos adaptadores reais de LLM (app/clientes_llm.py).

Nenhum teste aqui faz chamada de rede: o que se testa e a TRADUCAO
JSON -> dataclasses e o comportamento diante de resposta malformada.
Qualidade de julgamento do modelo e objeto de eval (ADR-0004).
"""
import json
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agente_underwriting import AcaoChamarFerramenta, AcaoConcluir  # noqa: E402
from app.clientes_llm import (  # noqa: E402
    TETO_ESPERA_TOTAL_S,
    ClienteGemini,
    ClienteGroq,
    DependenciaAusente,
    FalhaProvider,
    RespostaLLMInvalida,
    _chamar_com_retry,
    _contabilizar_tokens,
    _delay_sugerido,
    _parse_resposta,
    _prompt_sistema,
)
from app.memo_credito import Peso, Recomendacao  # noqa: E402

FERRAMENTAS = {"consultar_bureau": "credito em outras instituicoes"}


def _memo_json(recomendacao="NEGAR", **extra):
    memo = {
        "cliente_id": "1",
        "recomendacao": recomendacao,
        "fatores_cliente": [
            {"fato": f"fato {i}", "fonte_tool": "consultar_bureau", "peso": "desfavoravel"}
            for i in range(3)
        ],
        "cenario_assumido": {"lgd": 0.78, "fonte": "BCB SGS 432"},
    }
    memo.update(extra)
    return memo


def test_parse_chamar_ferramenta():
    acao = _parse_resposta(json.dumps({
        "acao": "chamar_ferramenta",
        "ferramenta": "consultar_bureau",
        "argumentos": {"sk_id_curr": 1},
    }))
    assert isinstance(acao, AcaoChamarFerramenta)
    assert acao.ferramenta == "consultar_bureau"
    assert acao.argumentos == {"sk_id_curr": 1}


def test_parse_chamar_ferramenta_sem_argumentos_usa_dict_vazio():
    acao = _parse_resposta(json.dumps({
        "acao": "chamar_ferramenta", "ferramenta": "consultar_bureau",
    }))
    assert acao.argumentos == {}


def test_parse_concluir_devolve_memo_validado():
    acao = _parse_resposta(json.dumps({"acao": "concluir", "memo": _memo_json()}))
    assert isinstance(acao, AcaoConcluir)
    assert acao.memo.recomendacao is Recomendacao.NEGAR
    assert len(acao.memo.fatores_cliente) == 3
    assert acao.memo.fatores_cliente[0].peso is Peso.DESFAVORAVEL


def test_json_malformado_levanta_erro_claro():
    with pytest.raises(RespostaLLMInvalida, match="nao e JSON valido"):
        _parse_resposta("{acao: concluir")


def test_acao_desconhecida_levanta_erro():
    with pytest.raises(RespostaLLMInvalida, match="acao' desconhecido"):
        _parse_resposta(json.dumps({"acao": "pensar_mais"}))


def test_chamar_ferramenta_sem_nome_levanta_erro():
    with pytest.raises(RespostaLLMInvalida, match="campo obrigatorio"):
        _parse_resposta(json.dumps({"acao": "chamar_ferramenta", "argumentos": {}}))


def test_memo_que_viola_contrato_levanta_erro_em_vez_de_passar():
    """Menos de MIN_FATORES fatos tem que barrar no adaptador, nao virar memo
    invalido circulando pelo agente."""
    memo_curto = _memo_json()
    memo_curto["fatores_cliente"] = memo_curto["fatores_cliente"][:1]
    with pytest.raises(RespostaLLMInvalida, match="nao bateu com o contrato"):
        _parse_resposta(json.dumps({"acao": "concluir", "memo": memo_curto}))


def test_deferir_sem_informacao_faltante_barra_no_adaptador():
    with pytest.raises(RespostaLLMInvalida, match="nao bateu com o contrato"):
        _parse_resposta(json.dumps({
            "acao": "concluir", "memo": _memo_json(recomendacao="DEFERIR")}))


def test_prompt_sistema_lista_as_ferramentas_recebidas():
    prompt = _prompt_sistema(FERRAMENTAS)
    assert "consultar_bureau" in prompt
    assert "credito em outras instituicoes" in prompt


@pytest.mark.parametrize("cliente,sdk", [
    (ClienteGemini, "google.generativeai"),
    (ClienteGroq, "groq"),
])
def test_sdk_ausente_da_mensagem_com_o_comando_de_instalacao(cliente, sdk, monkeypatch):
    """O preco do import lazy e falhar so em runtime. A mensagem tem que
    pagar esse preco: dizer o comando exato, nao 'No module named groq'."""
    monkeypatch.setitem(sys.modules, sdk, None)  # simula pacote ausente
    with pytest.raises(DependenciaAusente, match="requirements-llm.txt"):
        cliente()


def test_prompt_sistema_nao_menciona_score():
    """Cegueira ao score (ADR-0003 SS2.1): o adaptador nao pode reintroduzir
    o vocabulario do modelo no prompt."""
    prompt = _prompt_sistema(FERRAMENTAS).lower()
    for termo in ("p_default", "probabilidade de default", "camada1", "p_estrela"):
        assert termo not in prompt


# --- Retry (debito #20) ---
#
# Politica derivada da medicao do piloto de 2026-08-06, nao de precaucao.
# Nenhum teste aqui dorme de verdade: time.sleep e substituido por um registro
# das esperas pedidas, o que deixa a POLITICA visivel no assert.

class _Http(Exception):
    """Dublê de erro de SDK com status HTTP."""

    def __init__(self, code, mensagem="falhou"):
        super().__init__(mensagem)
        self.code = code


@pytest.fixture
def esperas(monkeypatch):
    registro = []
    monkeypatch.setattr("app.clientes_llm.time.sleep", registro.append)
    monkeypatch.setattr("app.clientes_llm.random.uniform", lambda a, b: 1.0)
    return registro


def test_sucesso_na_primeira_nao_espera(esperas):
    assert _chamar_com_retry(lambda: "ok", max_tentativas=3) == ("ok", 1)
    assert esperas == []


def test_erro_transitorio_e_retentado_ate_suceder(esperas):
    tentativas = []

    def instavel():
        tentativas.append(1)
        if len(tentativas) < 3:
            raise _Http(429, "rate limit")
        return "ok"

    assert _chamar_com_retry(instavel, max_tentativas=3) == ("ok", 3)
    assert len(esperas) == 2, "duas falhas, duas esperas"


def test_resposta_invalida_nao_e_retentada(esperas):
    """O ponto mais sutil da politica: JSON fora do contrato e QUALIDADE do
    gerador, metrica que o ADR-0004 quer medir. Retentar por baixo dos panos
    transformaria a metrica em ruido invisivel."""
    chamadas = []

    def sempre_invalida():
        chamadas.append(1)
        raise RespostaLLMInvalida("memo nao bateu com o contrato")

    with pytest.raises(RespostaLLMInvalida):
        _chamar_com_retry(sempre_invalida, max_tentativas=5)

    assert len(chamadas) == 1, "nao pode retentar erro de contrato"
    assert esperas == []


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
def test_erro_permanente_falha_rapido(status, esperas):
    """Chave errada nao melhora com espera - retentar so atrasa a mensagem util."""
    chamadas = []

    def permanente():
        chamadas.append(1)
        raise _Http(status)

    with pytest.raises(FalhaProvider, match="permanente"):
        _chamar_com_retry(permanente, max_tentativas=5)

    assert len(chamadas) == 1
    assert esperas == []


@pytest.mark.parametrize("status", [408, 429, 500, 503])
def test_status_que_oscila_e_retentado(status, esperas):
    with pytest.raises(FalhaProvider, match="2 tentativa"):
        _chamar_com_retry(lambda: (_ for _ in ()).throw(_Http(status)), max_tentativas=2)
    assert len(esperas) == 1


def test_espera_o_que_o_provider_mandou(esperas):
    """O 429 do Gemini traz 'Please retry in 39.6s'. Essa e a unica fonte que
    sabe quando a janela de quota reabre - backoff cego chutaria."""
    erro = _Http(429, "quota exceeded. Please retry in 12.5s. more text")
    with pytest.raises(FalhaProvider):
        _chamar_com_retry(lambda: (_ for _ in ()).throw(erro), max_tentativas=2)

    assert esperas == [12.5]


def test_delay_sugerido_le_atributo_estruturado_antes_do_texto():
    class ComRetryDelay(Exception):
        retry_delay = type("D", (), {"seconds": 39})()

    assert _delay_sugerido(ComRetryDelay()) == 39.0
    assert _delay_sugerido(Exception("sem dica nenhuma")) is None


def test_contador_de_tentativas_nunca_fica_menor_que_chamadas(monkeypatch, esperas):
    """Regressao do bug visto no piloto de 2026-08-06.

    `n_chamadas` subia antes da chamada e `tentativas_gastas` so depois, entao
    chamada que MORRIA incrementava um e nao o outro - o relatorio imprimia
    "-1 retries". Numero negativo denuncia; o perigoso e que com uma mistura
    diferente de sucesso e falha a conta ficaria positiva e ERRADA, sem nada
    apontando para o problema.
    """
    class _Modelo:
        def generate_content(self, contexto):
            raise _Http(429, "Please retry in 1s.")

    class _FakeGenAI:
        @staticmethod
        def configure(**kw):
            pass

        @staticmethod
        def GenerativeModel(*a, **kw):
            return _Modelo()

    # `import google.generativeai as genai` precisa das DUAS coisas: a entrada
    # em sys.modules e o atributo no pacote pai.
    pacote_google = types.ModuleType("google")
    pacote_google.generativeai = _FakeGenAI
    monkeypatch.setitem(sys.modules, "google", pacote_google)
    monkeypatch.setitem(sys.modules, "google.generativeai", _FakeGenAI)

    cliente = ClienteGemini(api_key="chave-de-teste", max_tentativas=2)
    with pytest.raises(FalhaProvider):
        cliente.proxima_acao("contexto", FERRAMENTAS)

    assert cliente.n_chamadas == 1
    assert cliente.tentativas_gastas == 2
    assert cliente.tentativas_gastas >= cliente.n_chamadas, "retries nao pode dar negativo"


# --- Contabilidade de tokens (custo medido, nao estimado) ---

def test_conta_thinking_separado_da_saida_visivel():
    """`thoughts_token_count` e cobrado como output e NAO aparece no texto.
    Estimativa por contagem de caracteres nao tem como enxerga-lo."""
    uso = types.SimpleNamespace(
        prompt_token_count=500, candidates_token_count=200,
        thoughts_token_count=1500, total_token_count=2200)
    tokens = _contabilizar_tokens(types.SimpleNamespace(usage_metadata=uso))

    assert tokens == {"input": 500, "output": 200, "thinking": 1500,
                      "total": 2200, "medido": 1}


def test_resposta_sem_telemetria_marca_nao_medido():
    """O erro perigoso: lote sem uso reportado virar 'custo zero' no relatorio.
    `medido=0` e o que permite o report dizer NAO MEDIDO em vez de R$ 0,00."""
    tokens = _contabilizar_tokens(types.SimpleNamespace())

    assert tokens["total"] == 0
    assert tokens["medido"] == 0, "sem isso, ausencia de dado vira ausencia de custo"


def test_le_o_formato_do_groq_tambem():
    """Groq/OpenAI usam prompt_tokens/completion_tokens."""
    uso = types.SimpleNamespace(prompt_tokens=300, completion_tokens=120)
    tokens = _contabilizar_tokens(types.SimpleNamespace(usage=uso))

    assert (tokens["input"], tokens["output"]) == (300, 120)
    assert tokens["total"] == 420, "sem total_tokens, soma os componentes"


def test_teto_de_espera_total_e_controle_de_custo(esperas):
    """Sem teto, um provider em quota zerada prenderia o lote indefinidamente."""
    erro = _Http(429, "Please retry in 45s.")
    with pytest.raises(FalhaProvider, match="teto de espera"):
        _chamar_com_retry(lambda: (_ for _ in ()).throw(erro), max_tentativas=10)

    assert sum(esperas) <= TETO_ESPERA_TOTAL_S
