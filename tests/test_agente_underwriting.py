"""Testes do agente de underwriting (ADR-0003, ADR-0007).

O LLM e substituido por um dublê com roteiro fixo. Isso e proposital: o que
se testa aqui e a ORQUESTRACAO (teto de chamadas, cegueira ao score,
groundedness), que e deterministica. Qualidade de julgamento do modelo e
objeto de eval (ADR-0004), nao de teste unitario.

O teste mais importante do arquivo e `test_contexto_do_agente_nao_contem_o_score`.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agente_underwriting import (  # noqa: E402
    AcaoChamarFerramenta,
    AcaoConcluir,
    AgenteUnderwriting,
    montar_contexto_inicial,
    preparar_lote,
    validar_groundedness,
)
from app.ferramenta_cenario import FerramentaCenario  # noqa: E402
from app.ferramentas_caso import FerramentasCaso  # noqa: E402
from app.memo_credito import (  # noqa: E402
    CenarioAssumido,
    FatorCliente,
    MemoCredito,
    Peso,
    Recomendacao,
)


@pytest.fixture
def cenario():
    return FerramentaCenario(buscador=lambda s: 12.5).consultar_cenario()


@pytest.fixture
def ferramentas(tmp_path):
    pd.DataFrame({
        "SK_ID_CURR": [1, 1], "SK_ID_BUREAU": [10, 11],
        "CREDIT_ACTIVE": ["Active", "Closed"], "CREDIT_DAY_OVERDUE": [0, 0],
        "AMT_CREDIT_SUM": [1000.0, 500.0], "AMT_CREDIT_SUM_DEBT": [300.0, 0.0],
    }).to_csv(tmp_path / "bureau.csv", index=False)
    pd.DataFrame({
        "SK_ID_BUREAU": [10, 10], "MONTHS_BALANCE": [-1, -2], "STATUS": ["0", "1"],
    }).to_csv(tmp_path / "bureau_balance.csv", index=False)
    pd.DataFrame({
        "SK_ID_CURR": [1, 1], "DAYS_INSTALMENT": [-60.0, -30.0],
        "DAYS_ENTRY_PAYMENT": [-62.0, -25.0],
        "AMT_INSTALMENT": [100.0, 100.0], "AMT_PAYMENT": [100.0, 100.0],
    }).to_csv(tmp_path / "installments_payments.csv", index=False)
    return FerramentasCaso(raw_dir=tmp_path)


def _memo(fontes=("consultar_bureau",), recomendacao=Recomendacao.NEGAR, **kw):
    fatores = [
        FatorCliente(fato=f"fato {i}", fonte_tool=f, peso=Peso.DESFAVORAVEL)
        for i, f in enumerate(fontes)
    ]
    while len(fatores) < 3:
        fatores.append(FatorCliente(
            fato=f"fato extra {len(fatores)}", fonte_tool=fontes[0], peso=Peso.NEUTRO))
    return MemoCredito(
        cliente_id="1", recomendacao=recomendacao, fatores_cliente=fatores,
        cenario_assumido=CenarioAssumido(lgd=0.78, fonte="BCB SGS 432"), **kw)


class LLMComRoteiro:
    """Dublê: devolve as acoes de um roteiro fixo, em ordem."""

    def __init__(self, roteiro):
        self.roteiro = list(roteiro)
        self.contextos_vistos = []

    def proxima_acao(self, contexto, ferramentas):
        self.contextos_vistos.append(contexto)
        return self.roteiro.pop(0) if self.roteiro else AcaoConcluir(memo=_memo())


# --- INVARIANTE CENTRAL: cegueira ao score (ADR-0003 SS2.1) ---

def test_contexto_do_agente_nao_contem_o_score(cenario):
    """Se este teste quebrar, NAO relaxe: o experimento inteiro perde sentido.

    Serializa tudo que o agente ve na abertura e procura qualquer rastro do
    modelo da Camada 1.
    """
    contexto = montar_contexto_inicial(sk_id_curr=100034, cenario=cenario)
    proibidos = ["p_default", "probabilidade de default", "score", "p_hat",
                 "camada 1", "modelo previu", "risco estimado"]
    for termo in proibidos:
        assert termo not in contexto.lower(), f"contexto vaza '{termo}'"


def test_montar_contexto_nao_aceita_parametro_de_score(cenario):
    """Prevencao ESTRUTURAL: nao existe por onde o score entrar."""
    with pytest.raises(TypeError):
        montar_contexto_inicial(sk_id_curr=1, cenario=cenario, p_default=0.42)


def test_contexto_marca_o_cenario_como_premissa_do_lote(cenario):
    """O macro nao pode ser lido como caracteristica do cliente (ADR-0008)."""
    contexto = montar_contexto_inicial(1, cenario).lower()
    assert "premissa da carteira" in contexto
    assert "nao caracteristica deste cliente" in contexto


def test_fila_e_embaralhada_para_nao_vazar_risco_pela_ordem():
    """Fila ordenada por risco faz a POSICAO carregar o score."""
    ordenada = list(range(100))
    assert preparar_lote(ordenada) != ordenada
    assert sorted(preparar_lote(ordenada)) == ordenada, "nao pode perder caso"


def test_embaralhamento_e_reprodutivel():
    assert preparar_lote([1, 2, 3, 4, 5], seed=7) == preparar_lote([1, 2, 3, 4, 5], seed=7)


# --- Groundedness verificada mecanicamente (ADR-0004, eliminatoria) ---

def test_fato_citando_ferramenta_nao_chamada_e_rejeitado(ferramentas, cenario):
    llm = LLMComRoteiro([AcaoConcluir(memo=_memo(fontes=("consultar_pagamentos",)))])
    r = AgenteUnderwriting(ferramentas, cenario, llm).analisar(1)

    assert r.memo is None, "memo com fonte inventada nao pode passar"
    assert "consultar_pagamentos" in r.erro


def test_fato_citando_ferramenta_chamada_e_aceito(ferramentas, cenario):
    llm = LLMComRoteiro([
        AcaoChamarFerramenta("consultar_bureau", {"sk_id_curr": 1}),
        AcaoConcluir(memo=_memo(fontes=("consultar_bureau",))),
    ])
    r = AgenteUnderwriting(ferramentas, cenario, llm).analisar(1)

    assert r.memo is not None and r.erro is None
    assert validar_groundedness(r.memo, r.trace) == []


# --- Multi-hop e teto de chamadas (ADR-0007) ---

def test_agente_encadeia_ferramentas_e_registra_a_sequencia(ferramentas, cenario):
    llm = LLMComRoteiro([
        AcaoChamarFerramenta("consultar_bureau", {"sk_id_curr": 1}),
        AcaoChamarFerramenta("consultar_historico_bureau", {"sk_id_curr": 1}),
        AcaoChamarFerramenta("consultar_pagamentos", {"sk_id_curr": 1}),
        AcaoConcluir(memo=_memo(fontes=(
            "consultar_bureau", "consultar_historico_bureau", "consultar_pagamentos"))),
    ])
    r = AgenteUnderwriting(ferramentas, cenario, llm).analisar(1)

    assert [c.ferramenta for c in r.trace] == [
        "consultar_bureau", "consultar_historico_bureau", "consultar_pagamentos"]


def test_retorno_da_ferramenta_entra_no_contexto_da_proxima_decisao(ferramentas, cenario):
    """E o que torna o multi-hop real: o 2o salto ve o resultado do 1o."""
    llm = LLMComRoteiro([
        AcaoChamarFerramenta("consultar_bureau", {"sk_id_curr": 1}),
        AcaoConcluir(memo=_memo()),
    ])
    AgenteUnderwriting(ferramentas, cenario, llm).analisar(1)

    assert "consultar_bureau" not in llm.contextos_vistos[0]
    assert "tem_historico_mensal" in llm.contextos_vistos[1]


def test_teto_de_chamadas_impede_loop_de_exploracao(ferramentas, cenario):
    llm = LLMComRoteiro(
        [AcaoChamarFerramenta("consultar_bureau", {"sk_id_curr": 1})] * 50)
    r = AgenteUnderwriting(ferramentas, cenario, llm, max_chamadas=4).analisar(1)

    assert r.atingiu_teto is True
    assert r.memo is None
    assert len(r.trace) == 4


def test_ferramenta_inexistente_nao_derruba_a_analise(ferramentas, cenario):
    """Modelo alucina nome de tool; isso vira erro no contexto, nao crash."""
    llm = LLMComRoteiro([
        AcaoChamarFerramenta("consultar_serasa", {"sk_id_curr": 1}),
        AcaoChamarFerramenta("consultar_bureau", {"sk_id_curr": 1}),
        AcaoConcluir(memo=_memo()),
    ])
    r = AgenteUnderwriting(ferramentas, cenario, llm).analisar(1)

    assert r.memo is not None
    assert "ERRO" in llm.contextos_vistos[1]


# --- Cenario e do lote, nao do cliente (ADR-0008) ---

def test_varios_clientes_do_lote_recebem_o_mesmo_cenario(ferramentas):
    f = FerramentaCenario(buscador=lambda s: 12.5)
    cen = f.consultar_cenario()
    for sk in (1, 2, 3):
        montar_contexto_inicial(sk, cen)
    assert f.n_buscas_externas == 1, "cenario nao pode ser buscado por cliente"
