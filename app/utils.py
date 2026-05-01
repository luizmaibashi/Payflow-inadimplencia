"""
app/utils.py
----------------
Payflow — Central de Processamento
Centraliza o feature engineering e preparação de dados para garantir paridade treino-serventia.
"""
import pandas as pd

def process_credit_features(req_dict: dict, colunas: list) -> tuple[pd.DataFrame, float]:
    """
    Recebe um dicionário (com os campos raw) e a lista de colunas esperadas
    pelo modelo, executando o Feature Engineering e One-Hot Encoding manual.
    """
    is_autonomo = 1 if req_dict.get("autonomo") == "Sim" else 0
    has_avalista = 1 if req_dict.get("possui_avalista") == "Sim" else 0
    utilizacao_credito_dec = req_dict.get("utilizacao_credito_pct", 0) / 100.0
    
    features = {
        'idade': req_dict.get("idade"),
        'renda_mensal': req_dict.get("renda_mensal"),
        'tempo_emprego_anos': req_dict.get("tempo_emprego_anos"),
        'autonomo': is_autonomo,
        'score_credito': req_dict.get("score_credito"),
        'valor_solicitado': req_dict.get("valor_solicitado"),
        'prazo_meses': req_dict.get("prazo_meses", 1),
        'juros_mensal_pct': req_dict.get("juros_mensal_pct", 0),
        'qtde_cartoes': req_dict.get("qtde_cartoes", 0),
        'qtde_contratos_abertos': req_dict.get("qtde_contratos_abertos"),
        'utilizacao_credito': utilizacao_credito_dec,
        'inadimplencias_anteriores': req_dict.get("inadimplencias_anteriores"),
        'dias_atraso_max_12m': req_dict.get("dias_atraso_max_12m"),
        'reclamacoes_6m': req_dict.get("reclamacoes_6m"),
        'possui_avalista': has_avalista,
        
        'canal_aquisicao_app': 1 if req_dict.get("canal_aquisicao") == "App" else 0,
        'canal_aquisicao_loja': 1 if req_dict.get("canal_aquisicao") == "Loja" else 0,
        'canal_aquisicao_parceiro': 1 if req_dict.get("canal_aquisicao") == "Parceiro" else 0,
        'canal_aquisicao_site': 1 if req_dict.get("canal_aquisicao") == "Site" else 0,
        
        'regiao_Centro-Oeste': 1 if req_dict.get("regiao") == "Centro-Oeste" else 0,
        'regiao_Nordeste': 1 if req_dict.get("regiao") == "Nordeste" else 0,
        'regiao_Norte': 1 if req_dict.get("regiao") == "Norte" else 0,
        'regiao_Sudeste': 1 if req_dict.get("regiao") == "Sudeste" else 0,
        'regiao_Sul': 1 if req_dict.get("regiao") == "Sul" else 0,
        
        'tipo_produto_bnpl': 1 if req_dict.get("tipo_produto") == "BNPL" else 0,
        'tipo_produto_cartao': 1 if req_dict.get("tipo_produto") == "Cartão" else 0,
        'tipo_produto_emprestimo_pessoal': 1 if req_dict.get("tipo_produto") == "Empréstimo Pessoal" else 0,
    }

    # Feature Engineering Centralizado
    juros_decimal = req_dict.get("juros_mensal_pct", 0) / 100.0
    valor_solicitado = req_dict.get("valor_solicitado", 0)
    prazo_meses = req_dict.get("prazo_meses", 1)
    renda_mensal = req_dict.get("renda_mensal", 0)
    
    if juros_decimal > 0:
        parcela_estimada = valor_solicitado * juros_decimal / (1 - (1 + juros_decimal) ** (-prazo_meses))
    else:
        parcela_estimada = valor_solicitado / prazo_meses if prazo_meses > 0 else valor_solicitado

    comprometimento_renda = parcela_estimada / renda_mensal if renda_mensal > 0 else 0
    intensidade_credito = utilizacao_credito_dec * req_dict.get("qtde_cartoes", 0)

    features['parcela_estimada'] = parcela_estimada
    features['comprometimento_renda'] = comprometimento_renda
    features['intensidade_credito'] = intensidade_credito

    # Organizar DataFrame para o modelo
    df_novo = pd.DataFrame([features])
    for col in colunas:
        if col not in df_novo.columns:
            df_novo[col] = 0
            
    df_novo = df_novo[colunas]
    
    return df_novo, comprometimento_renda

import os

def get_decision_thresholds() -> dict:
    """
    Retorna os limites de risco, permitindo configuração via variáveis de ambiente.
    """
    return {
        "RISCO_BAIXO_MAX": float(os.environ.get("RISCO_BAIXO_MAX", 0.40)),
        "RISCO_MEDIO_MAX": float(os.environ.get("RISCO_MEDIO_MAX", 0.65))
    }
