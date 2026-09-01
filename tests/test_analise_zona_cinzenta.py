"""Testes das funcoes puras dos dois scripts de analise do debito #34.

POR QUE ESTES TESTES EXISTEM: o debito #34 registrava "Sem teste automatizado
para backtest_camada2.py - validado manualmente, sem regressao automatica se
for alterado no futuro". Os scripts novos (auc_zona_cinzenta.py e
separacao_por_confianca.py) produzem os numeros que o README publica; nascer
sem teste repetiria o mesmo debito de propósito.

Escopo: funcoes puras e as guardas de contrato. main() de cada script le
disco e nao e testado aqui - o insumo dele (zona_cinzenta.parquet,
piloto_camada2_memos.jsonl) e versionado, entao rodar o script vale como
verificacao de ponta a ponta.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from auc_zona_cinzenta import (  # noqa: E402
    auc_com_ic,
    distancia_relativa_ao_centro,
)
from separacao_por_confianca import (  # noqa: E402
    assimetria_evidencia,
    separacao_com_ic,
)


# --------------------------------------------------------------------------
# auc_com_ic
# --------------------------------------------------------------------------

def test_auc_perfeito_tem_ic_colado_em_1():
    """Score que separa perfeitamente as classes deve dar AUC 1,0 e IC que
    nao desce - guarda contra bootstrap que reamostra errado."""
    y = np.array([0] * 50 + [1] * 50)
    score = np.concatenate([np.linspace(0, 0.4, 50), np.linspace(0.6, 1, 50)])
    res = auc_com_ic(y, score, n_bootstrap=200)
    assert res["auc"] == pytest.approx(1.0)
    assert res["ic_lo"] == pytest.approx(1.0)


def test_auc_de_score_aleatorio_tem_ic_que_contem_meio():
    """Score sem relacao com o alvo: o IC precisa conter 0,5. Se nao contiver,
    o bootstrap esta enviesado."""
    rng = np.random.RandomState(0)
    y = rng.randint(0, 2, 400)
    score = rng.rand(400)
    res = auc_com_ic(y, score, n_bootstrap=300)
    assert res["ic_lo"] < 0.5 < res["ic_hi"]


def test_alpha_menor_gera_intervalo_mais_largo():
    """O parametro alpha precisa de fato mudar a largura - a correcao de
    Bonferroni das sub-fatias depende disso. Se alpha fosse ignorado, os
    intervalos "corrigidos" seriam decorativos."""
    rng = np.random.RandomState(1)
    y = rng.randint(0, 2, 300)
    score = rng.rand(300) + y * 0.3
    largo = auc_com_ic(y, score, n_bootstrap=300, alpha=0.0167)
    normal = auc_com_ic(y, score, n_bootstrap=300, alpha=0.05)
    assert (largo["ic_hi"] - largo["ic_lo"]) > (normal["ic_hi"] - normal["ic_lo"])


def test_auc_com_uma_classe_so_levanta_em_vez_de_devolver_nan():
    y = np.ones(20, dtype=int)
    with pytest.raises(ValueError, match="uma classe so"):
        auc_com_ic(y, np.linspace(0, 1, 20))


def test_auc_com_tamanhos_diferentes_levanta():
    with pytest.raises(ValueError, match="tamanhos diferentes"):
        auc_com_ic(np.array([0, 1, 0]), np.array([0.1, 0.2]))


def test_alpha_fora_do_intervalo_levanta():
    y = np.array([0, 1] * 10)
    with pytest.raises(ValueError, match="alpha"):
        auc_com_ic(y, np.linspace(0, 1, 20), alpha=1.5)


def test_bootstrap_e_reprodutivel_com_a_mesma_seed():
    rng = np.random.RandomState(2)
    y = rng.randint(0, 2, 200)
    score = rng.rand(200)
    a = auc_com_ic(y, score, n_bootstrap=200, seed=7)
    b = auc_com_ic(y, score, n_bootstrap=200, seed=7)
    assert a["ic_lo"] == b["ic_lo"] and a["ic_hi"] == b["ic_hi"]


# --------------------------------------------------------------------------
# distancia_relativa_ao_centro
# --------------------------------------------------------------------------

def test_distancia_zero_no_centro_e_um_na_borda():
    df = pd.DataFrame({
        "p_hat": [0.30, 0.20, 0.40],          # centro, borda inf, borda sup
        "p_estrela_inf": [0.20, 0.20, 0.20],
        "p_estrela_sup": [0.40, 0.40, 0.40],
    })
    d = distancia_relativa_ao_centro(df)
    assert d.iloc[0] == pytest.approx(0.0)
    assert d.iloc[1] == pytest.approx(1.0)
    assert d.iloc[2] == pytest.approx(1.0)


def test_distancia_e_simetrica_nos_dois_lados_da_banda():
    """Caso acima e abaixo do centro, a mesma distancia absoluta - o teste
    de sub-fatia trata os dois lados como igualmente 'de borda'."""
    df = pd.DataFrame({
        "p_hat": [0.25, 0.35],
        "p_estrela_inf": [0.20, 0.20],
        "p_estrela_sup": [0.40, 0.40],
    })
    d = distancia_relativa_ao_centro(df)
    assert d.iloc[0] == pytest.approx(d.iloc[1])


def test_banda_degenerada_levanta_em_vez_de_dividir_por_zero():
    df = pd.DataFrame({
        "p_hat": [0.3], "p_estrela_inf": [0.3], "p_estrela_sup": [0.3],
    })
    with pytest.raises(ValueError, match="largura"):
        distancia_relativa_ao_centro(df)


def test_coluna_faltando_levanta_com_o_nome_da_coluna():
    df = pd.DataFrame({"p_hat": [0.3], "p_estrela_inf": [0.2]})
    with pytest.raises(ValueError, match="p_estrela_sup"):
        distancia_relativa_ao_centro(df)


# --------------------------------------------------------------------------
# assimetria_evidencia
# --------------------------------------------------------------------------

def _fatores(*pesos):
    return [{"fato": "x", "fonte_tool": "t", "peso": p} for p in pesos]


def test_assimetria_um_quando_evidencia_e_unanime():
    assim, fav, desf = assimetria_evidencia(_fatores("favoravel", "favoravel"))
    assert assim == pytest.approx(1.0)
    assert (fav, desf) == (2, 0)


def test_assimetria_zero_quando_lados_se_anulam():
    assim, fav, desf = assimetria_evidencia(
        _fatores("favoravel", "desfavoravel")
    )
    assert assim == pytest.approx(0.0)
    assert (fav, desf) == (1, 1)


def test_neutro_entra_no_denominador_e_derruba_a_assimetria():
    """A decisao de design documentada: memo com 1 fato favoravel e 3 neutros
    NAO e um memo confiante. Se `neutro` fosse excluido do denominador, isso
    daria 1,0 - o oposto do que a metrica quer medir."""
    assim, fav, desf = assimetria_evidencia(
        _fatores("favoravel", "neutro", "neutro", "neutro")
    )
    assert assim == pytest.approx(0.25)
    assert (fav, desf) == (1, 0)


def test_memo_todo_neutro_da_assimetria_zero():
    assim, _, _ = assimetria_evidencia(_fatores("neutro", "neutro"))
    assert assim == pytest.approx(0.0)


def test_peso_fora_do_contrato_levanta_em_vez_de_ser_ignorado():
    """Foi esta guarda que revelou que o contrato tem tres pesos, nao dois.
    Se ela virasse um `continue` silencioso, o denominador encolheria e a
    assimetria seria inflada sem ninguem notar."""
    with pytest.raises(ValueError, match="fora do contrato"):
        assimetria_evidencia(_fatores("favoravel", "muito_favoravel"))


def test_memo_sem_fatores_levanta():
    with pytest.raises(ValueError, match="sem fatores_cliente"):
        assimetria_evidencia([])


# --------------------------------------------------------------------------
# separacao_com_ic
# --------------------------------------------------------------------------

def test_separacao_detecta_diferenca_grande_e_real():
    """NEGAR com 90% de default e APROVAR com 10%: o IC precisa ficar
    inteiramente acima de zero."""
    df = pd.DataFrame({
        "recomendacao": ["NEGAR"] * 100 + ["APROVAR"] * 100,
        "TARGET": [1] * 90 + [0] * 10 + [1] * 10 + [0] * 90,
    })
    res = separacao_com_ic(df, n_bootstrap=300)
    assert res["delta"] == pytest.approx(0.8)
    assert res["ic_lo"] > 0


def test_separacao_de_grupos_identicos_tem_ic_que_contem_zero():
    df = pd.DataFrame({
        "recomendacao": ["NEGAR"] * 100 + ["APROVAR"] * 100,
        "TARGET": ([1] * 30 + [0] * 70) * 2,
    })
    res = separacao_com_ic(df, n_bootstrap=300)
    assert res["delta"] == pytest.approx(0.0)
    assert res["ic_lo"] < 0 < res["ic_hi"]


def test_grupo_vazio_devolve_none_em_vez_de_estourar():
    """Sub-grupo pode nao ter nenhum APROVAR. Isso e informacao a reportar
    ('grupo vazio de um lado'), nao erro - e nao pode virar 0,0 silencioso,
    que seria lido como 'nao separa'."""
    df = pd.DataFrame({"recomendacao": ["NEGAR"] * 10, "TARGET": [1] * 5 + [0] * 5})
    res = separacao_com_ic(df, n_bootstrap=50)
    assert res["delta"] is None and res["ic_lo"] is None
    assert res["n_negar"] == 10 and res["n_aprovar"] == 0


def test_deferir_nao_entra_em_nenhum_dos_dois_lados():
    """DEFERIR e encaminhamento a humano, nao aposta de risco - contamina a
    conta se for somado a qualquer um dos grupos (limitacao ja declarada em
    backtest_camada2.md)."""
    df = pd.DataFrame({
        "recomendacao": ["NEGAR"] * 10 + ["APROVAR"] * 10 + ["DEFERIR"] * 5,
        "TARGET": [1] * 10 + [0] * 10 + [1] * 5,
    })
    res = separacao_com_ic(df, n_bootstrap=50)
    assert res["n_negar"] == 10 and res["n_aprovar"] == 10


def test_alpha_corrigido_alarga_o_intervalo_da_separacao():
    """Mesma guarda do AUC: se alpha fosse ignorado aqui, a correcao de
    Bonferroni dos grupos de assimetria seria so texto no relatorio."""
    df = pd.DataFrame({
        "recomendacao": ["NEGAR"] * 80 + ["APROVAR"] * 80,
        "TARGET": [1] * 40 + [0] * 40 + [1] * 30 + [0] * 50,
    })
    largo = separacao_com_ic(df, n_bootstrap=300, alpha=0.0167)
    normal = separacao_com_ic(df, n_bootstrap=300, alpha=0.05)
    assert (largo["ic_hi"] - largo["ic_lo"]) > (normal["ic_hi"] - normal["ic_lo"])
