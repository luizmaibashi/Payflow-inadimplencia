import numpy as np
import pandas as pd
import pytest

from app.motor_decisao import (
    calcular_p_estrela,
    classificar_decisao,
    lgd_por_tipo_contrato,
    margem_proxy_anuidade,
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
