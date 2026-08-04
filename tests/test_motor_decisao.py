import numpy as np
import pandas as pd
import pytest

from app.motor_decisao import (
    LGD_CASH_LOAN,
    LGD_REVOLVING,
    calcular_p_estrela,
    classificar_decisao,
    classificar_decisao_por_limites,
    lgd_por_tipo_contrato,
    limites_p_estrela_por_incerteza_margem,
    margem_proxy_anuidade,
    margem_via_prazo_historico_cliente,
)


def test_calcular_p_estrela_caso_da_aula():
    # R$20.000, LGD 75%, margem 18% -> p* = 19,35% (sabatina do Bloco 1)
    p_estrela = calcular_p_estrela(margem=0.18, lgd=0.75)
    assert p_estrela == pytest.approx(0.1935, abs=1e-4)


def test_calcular_p_estrela_invariante_ao_valor_absoluto():
    # mesma razao m/l, valores absolutos diferentes -> mesmo p*
    p_20k = calcular_p_estrela(margem=3600 / 20000, lgd=15000 / 20000)
    p_2k = calcular_p_estrela(margem=360 / 2000, lgd=1500 / 2000)
    assert p_20k == pytest.approx(p_2k)


def test_margem_proxy_anuidade():
    amt_annuity = pd.Series([1000.0, 2000.0])
    amt_credit = pd.Series([20000.0, 40000.0])
    resultado = margem_proxy_anuidade(amt_annuity, amt_credit)
    assert resultado.tolist() == pytest.approx([0.05, 0.05])


def test_margem_via_prazo_historico_cliente_usa_prazo_real():
    amt_annuity = pd.Series([1000.0])
    amt_credit = pd.Series([12000.0])
    prazo = pd.Series([12.0])  # cliente com historico: prazo medio real de 12 meses
    resultado = margem_via_prazo_historico_cliente(amt_annuity, amt_credit, prazo)
    # m = (1000*12 - 12000) / 12000 = 0.0
    assert resultado.iloc[0] == pytest.approx(0.0)


def test_margem_via_prazo_historico_cliente_fallback_sem_historico():
    amt_annuity = pd.Series([1000.0])
    amt_credit = pd.Series([12000.0])
    prazo = pd.Series([np.nan])  # sem historico -> usa fallback (12 meses)
    resultado = margem_via_prazo_historico_cliente(amt_annuity, amt_credit, prazo)
    assert resultado.iloc[0] == pytest.approx(0.0)


def test_margem_via_prazo_historico_cliente_prazo_maior_da_mais_margem():
    amt_annuity = pd.Series([1000.0, 1000.0])
    amt_credit = pd.Series([12000.0, 12000.0])
    prazo = pd.Series([12.0, 24.0])
    resultado = margem_via_prazo_historico_cliente(amt_annuity, amt_credit, prazo)
    assert resultado.iloc[1] > resultado.iloc[0]


def test_lgd_por_tipo_contrato():
    tipos = pd.Series(["Cash loans", "Revolving loans", "Cash loans"])
    resultado = lgd_por_tipo_contrato(tipos)
    assert list(resultado) == [0.70, 0.85, 0.70]


def test_classificar_decisao_aprova_abaixo_da_banda():
    decisao = classificar_decisao(p_hat=0.10, p_estrela=0.20, banda=0.03)
    assert decisao.item() == "APROVAR"


def test_classificar_decisao_nega_acima_da_banda():
    decisao = classificar_decisao(p_hat=0.30, p_estrela=0.20, banda=0.03)
    assert decisao.item() == "NEGAR"


def test_classificar_decisao_zona_cinzenta_dentro_da_banda():
    decisao = classificar_decisao(p_hat=0.21, p_estrela=0.20, banda=0.03)
    assert decisao.item() == "ZONA_CINZENTA"


def test_classificar_decisao_bordas_da_banda_sao_zona_cinzenta():
    # limites inclusivos ficam do lado da zona cinzenta (favorece deferral
    # em caso de empate, nao aprovacao/negacao automatica)
    decisao_inf = classificar_decisao(p_hat=0.17, p_estrela=0.20, banda=0.03)
    decisao_sup = classificar_decisao(p_hat=0.23, p_estrela=0.20, banda=0.03)
    assert decisao_inf.item() == "ZONA_CINZENTA"
    assert decisao_sup.item() == "ZONA_CINZENTA"


def test_classificar_decisao_vetorizado():
    p_hat = np.array([0.05, 0.20, 0.50])
    p_estrela = np.array([0.20, 0.20, 0.20])
    decisao = classificar_decisao(p_hat, p_estrela, banda=0.03)
    assert list(decisao) == ["APROVAR", "ZONA_CINZENTA", "NEGAR"]


def test_limites_por_incerteza_margem_produz_faixa_larga_e_ordenada():
    inf, sup = limites_p_estrela_por_incerteza_margem(LGD_CASH_LOAN)
    # margem P25=26,2% e P75=65,1% com LGD 70% -> p* de ~27% a ~48%
    assert inf == pytest.approx(0.262 / (0.262 + 0.70), abs=1e-6)
    assert sup == pytest.approx(0.651 / (0.651 + 0.70), abs=1e-6)
    assert inf < sup
    # a faixa derivada e MUITO mais larga que os +-3pp arbitrarios antigos
    assert (sup - inf) > 0.15


def test_limites_por_incerteza_margem_lgd_maior_estreita_a_faixa():
    inf_cash, sup_cash = limites_p_estrela_por_incerteza_margem(LGD_CASH_LOAN)
    inf_rev, sup_rev = limites_p_estrela_por_incerteza_margem(LGD_REVOLVING)
    # LGD maior (pior recuperacao) empurra p* para baixo nos dois extremos
    assert inf_rev < inf_cash
    assert sup_rev < sup_cash


def test_classificar_decisao_por_limites_assimetricos():
    p_hat = np.array([0.10, 0.35, 0.60])
    decisao = classificar_decisao_por_limites(p_hat, 0.272, 0.482)
    assert list(decisao) == ["APROVAR", "ZONA_CINZENTA", "NEGAR"]


def test_classificar_decisao_por_limites_borda_defere():
    # empate exato nas bordas -> ZONA_CINZENTA (deferir, nao decidir sozinho)
    decisao = classificar_decisao_por_limites(np.array([0.272, 0.482]), 0.272, 0.482)
    assert list(decisao) == ["ZONA_CINZENTA", "ZONA_CINZENTA"]
