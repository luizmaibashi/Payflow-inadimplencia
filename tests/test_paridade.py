import pytest
from app.utils import process_credit_features, get_decision_thresholds
from app.service import CreditScoringService
import pandas as pd
import numpy as np

def test_feature_engineering_parity():
    """
    Testa se o feature engineering no utilitário reproduz exatamente as 
    transformações esperadas e os tipos compatíveis com o modelo treinado.
    Isso previne o Training-Serving Skew.
    """
    # Dado um input de teste simulando a API
    req_dict = {
        "idade": 30,
        "renda_mensal": 5000.0,
        "tempo_emprego_anos": 5.0,
        "autonomo": "Não",
        "score_credito": 700,
        "valor_solicitado": 10000.0,
        "prazo_meses": 24,
        "juros_mensal_pct": 2.0,
        "qtde_cartoes": 2,
        "qtde_contratos_abertos": 1,
        "utilizacao_credito_pct": 30.0,
        "inadimplencias_anteriores": 0,
        "dias_atraso_max_12m": 0,
        "reclamacoes_6m": 0,
        "possui_avalista": "Não",
        "canal_aquisicao": "App",
        "regiao": "Sudeste",
        "tipo_produto": "Empréstimo Pessoal"
    }

    # As colunas esperadas pelo modelo
    # Simulamos algumas colunas baseadas no utils
    colunas_mock = ['idade', 'renda_mensal', 'tempo_emprego_anos', 'autonomo',
       'score_credito', 'valor_solicitado', 'prazo_meses', 'juros_mensal_pct',
       'qtde_cartoes', 'qtde_contratos_abertos', 'utilizacao_credito',
       'inadimplencias_anteriores', 'dias_atraso_max_12m', 'reclamacoes_6m',
       'possui_avalista', 'canal_aquisicao_app', 'canal_aquisicao_loja',
       'canal_aquisicao_parceiro', 'canal_aquisicao_site',
       'regiao_Centro-Oeste', 'regiao_Nordeste', 'regiao_Norte',
       'regiao_Sudeste', 'regiao_Sul', 'tipo_produto_bnpl',
       'tipo_produto_cartao', 'tipo_produto_emprestimo_pessoal',
       'parcela_estimada', 'comprometimento_renda', 'intensidade_credito']

    df_result, comprometimento = process_credit_features(req_dict, colunas_mock)

    # Verifica se os cálculos financeiros foram feitos corretamente
    juros_decimal = 0.02
    parcela_esperada = 10000.0 * juros_decimal / (1 - (1 + juros_decimal) ** (-24))
    
    assert df_result['parcela_estimada'].iloc[0] == pytest.approx(parcela_esperada)
    assert df_result['comprometimento_renda'].iloc[0] == pytest.approx(parcela_esperada / 5000.0)
    assert comprometimento == pytest.approx(parcela_esperada / 5000.0)
    assert df_result['intensidade_credito'].iloc[0] == pytest.approx(0.3 * 2)

    # Verifica codificação categórica
    assert df_result['canal_aquisicao_app'].iloc[0] == 1
    assert df_result['canal_aquisicao_loja'].iloc[0] == 0
    assert df_result['regiao_Sudeste'].iloc[0] == 1
    assert df_result['regiao_Norte'].iloc[0] == 0
    assert df_result['autonomo'].iloc[0] == 0

def test_decision_thresholds_env(monkeypatch):
    """
    Verifica se os thresholds de decisão podem ser sobrescritos por variáveis de ambiente.
    """
    # Testa os valores default
    monkeypatch.delenv("RISCO_BAIXO_MAX", raising=False)
    monkeypatch.delenv("RISCO_MEDIO_MAX", raising=False)
    thresholds_default = get_decision_thresholds()
    assert thresholds_default["RISCO_BAIXO_MAX"] == 0.40
    assert thresholds_default["RISCO_MEDIO_MAX"] == 0.65

    # Testa os valores sobrescritos
    monkeypatch.setenv("RISCO_BAIXO_MAX", "0.35")
    monkeypatch.setenv("RISCO_MEDIO_MAX", "0.60")
    thresholds_custom = get_decision_thresholds()
    assert thresholds_custom["RISCO_BAIXO_MAX"] == 0.35
    assert thresholds_custom["RISCO_MEDIO_MAX"] == 0.60
