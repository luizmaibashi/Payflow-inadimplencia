"""Feature engineering da Camada 1 sobre o esquema relacional Home Credit.

Substitui app/utils.py::process_credit_features (esquema sintetico antigo,
ADR-0001). Cada funcao agrega UMA tabela relacional para o grao SK_ID_CURR
e e pura/deterministica - testavel isoladamente (tests/test_paridade.py).

Convencao de nulos (regra de dados, sem imputacao injustificada):
- Contagens (n_*): fillna(0) - ausencia de historico E um fato medido
  (o cliente nao tem contrato daquele tipo), nao uma estimativa.
- Fracoes/medias condicionadas a existir historico: ficam NaN quando
  n=0 - o HistGradientBoostingClassifier lida nativamente com NaN, e
  "sem dado para calcular a razao" e diferente de "razao = 0".
"""
import numpy as np
import pandas as pd

# Severidade da coluna STATUS de bureau_balance: 'C'=quitado, '0'=sem atraso,
# '1'..'5'=faixas crescentes de dias em atraso (documentacao HC).
#
# 'X' NAO ESTA AQUI de proposito (corrigido em 2026-08-05, EDA relacional).
# Antes ele valia 0, igual a "em dia" - mas 'X' significa SEM INFORMACAO, e
# sao 21% de todos os meses da tabela. Tratar mes desconhecido como mes bom
# subestima sistematicamente a severidade historica de quem tem buraco no
# registro. Fora do mapa, 'X' vira NaN e e ignorado por max()/sum(), que e a
# afirmacao correta: nao sabemos o que houve naquele mes.
_STATUS_SEVERIDADE = {"C": 0, "0": 0, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5}


def agregar_bureau(bureau: pd.DataFrame, bureau_balance: pd.DataFrame) -> pd.DataFrame:
    """Historico de credito em OUTRAS instituicoes (bureau externo)."""
    bb = bureau_balance.copy()
    # sem fillna(0): STATUS fora do mapa (isto e, 'X') tem que ficar NaN
    bb["severidade"] = bb["STATUS"].map(_STATUS_SEVERIDADE)
    bb["mes_sem_informacao"] = bb["severidade"].isna()
    bb_agg = bb.groupby("SK_ID_BUREAU").agg(
        bureau_balance_max_severidade=("severidade", "max"),
        bureau_balance_meses_em_atraso=("severidade", lambda s: (s > 0).sum()),
        bureau_balance_meses_sem_info=("mes_sem_informacao", "sum"),
    ).reset_index()

    b = bureau.merge(bb_agg, on="SK_ID_BUREAU", how="left")

    # Divida NEGATIVA (8.418 linhas, EDA relacional 2026-08-05) significa saldo
    # a favor do cliente, nao divida. Somada cru, ela ABATE a divida de outros
    # contratos e faz o cliente parecer menos endividado do que esta. Piso em
    # zero: para "quanto este cliente deve", credito a favor conta como zero,
    # nao como divida negativa.
    b["divida_nao_negativa"] = b["AMT_CREDIT_SUM_DEBT"].clip(lower=0)

    out = b.groupby("SK_ID_CURR").agg(
        n_bureau_contratos=("SK_ID_BUREAU", "count"),
        n_bureau_ativos=("CREDIT_ACTIVE", lambda s: (s == "Active").sum()),
        n_bureau_atrasados_hoje=("CREDIT_DAY_OVERDUE", lambda s: (s > 0).sum()),
        bureau_credit_sum_total=("AMT_CREDIT_SUM", "sum"),
        bureau_credit_sum_debt_total=("divida_nao_negativa", "sum"),
        bureau_max_severidade_historica=("bureau_balance_max_severidade", "max"),
        bureau_meses_em_atraso_total=("bureau_balance_meses_em_atraso", "sum"),
        n_bureau_meses_sem_info=("bureau_balance_meses_sem_info", "sum"),
    ).reset_index()

    out["frac_bureau_ativos"] = np.where(
        out["n_bureau_contratos"] > 0, out["n_bureau_ativos"] / out["n_bureau_contratos"], np.nan
    )
    out["bureau_divida_sobre_credito"] = np.where(
        out["bureau_credit_sum_total"] > 0,
        out["bureau_credit_sum_debt_total"] / out["bureau_credit_sum_total"],
        np.nan,
    )
    return out


def agregar_previous_application(prev: pd.DataFrame) -> pd.DataFrame:
    """Historico de propostas anteriores na propria Home Credit."""
    out = prev.groupby("SK_ID_CURR").agg(
        n_previous_aplicacoes=("SK_ID_PREV", "count"),
        n_previous_aprovadas=("NAME_CONTRACT_STATUS", lambda s: (s == "Approved").sum()),
        n_previous_recusadas=("NAME_CONTRACT_STATUS", lambda s: (s == "Refused").sum()),
        previous_amt_credit_mean=("AMT_CREDIT", "mean"),
        previous_amt_annuity_mean=("AMT_ANNUITY", "mean"),
        previous_cnt_payment_mean=("CNT_PAYMENT", "mean"),
    ).reset_index()

    out["frac_previous_aprovadas"] = np.where(
        out["n_previous_aplicacoes"] > 0, out["n_previous_aprovadas"] / out["n_previous_aplicacoes"], np.nan
    )
    out["frac_previous_recusadas"] = np.where(
        out["n_previous_aplicacoes"] > 0, out["n_previous_recusadas"] / out["n_previous_aplicacoes"], np.nan
    )
    return out


def agregar_installments(installments: pd.DataFrame) -> pd.DataFrame:
    """Comportamento real de pagamento de parcelas (contratos HC anteriores)."""
    df = installments.copy()
    df["atraso_dias"] = df["DAYS_ENTRY_PAYMENT"] - df["DAYS_INSTALMENT"]
    df["pagou_a_menor"] = df["AMT_PAYMENT"] < df["AMT_INSTALMENT"]

    # DEFEITO CORRIGIDO (EDA das tabelas relacionais, 2026-08-05): parcela SEM
    # data de pagamento e uma parcela NUNCA PAGA - o sinal mais forte de
    # inadimplencia que existe. Mas `atraso_dias` vira NaN, e `NaN > 0` e
    # False: ela sumia da contagem de atraso. Mesma coisa em `pagou_a_menor`
    # (`NaN < x` e False). Ou seja, quem nunca pagou era contado como quem
    # pagou em dia.
    #
    # Sao 2.905 parcelas em 1.249 clientes - poucos, mas com default de
    # 18,14% contra 8,04% do resto da base (2,26x mais arriscados).
    #
    # Vira feature PROPRIA em vez de virar "atraso muito grande": nunca pagar
    # e categoricamente diferente de pagar atrasado, e fundir os dois perderia
    # justamente a distincao que carrega o sinal.
    df["nunca_pagou"] = df["DAYS_ENTRY_PAYMENT"].isna()
    df["deficit_pct"] = np.where(
        df["AMT_INSTALMENT"] > 0,
        (df["AMT_INSTALMENT"] - df["AMT_PAYMENT"]) / df["AMT_INSTALMENT"],
        np.nan,
    )

    out = df.groupby("SK_ID_CURR").agg(
        n_parcelas_historico=("NUM_INSTALMENT_NUMBER", "count"),
        n_parcelas_atrasadas=("atraso_dias", lambda s: (s > 0).sum()),
        atraso_medio_dias=("atraso_dias", "mean"),
        atraso_max_dias=("atraso_dias", "max"),
        n_parcelas_pagas_a_menor=("pagou_a_menor", "sum"),
        deficit_pagamento_medio_pct=("deficit_pct", "mean"),
        n_parcelas_nunca_pagas=("nunca_pagou", "sum"),
    ).reset_index()

    out["frac_parcelas_nunca_pagas"] = np.where(
        out["n_parcelas_historico"] > 0,
        out["n_parcelas_nunca_pagas"] / out["n_parcelas_historico"],
        np.nan,
    )
    out["frac_parcelas_atrasadas"] = np.where(
        out["n_parcelas_historico"] > 0, out["n_parcelas_atrasadas"] / out["n_parcelas_historico"], np.nan
    )
    out["frac_parcelas_pagas_a_menor"] = np.where(
        out["n_parcelas_historico"] > 0, out["n_parcelas_pagas_a_menor"] / out["n_parcelas_historico"], np.nan
    )
    return out


def agregar_pos_cash(pos: pd.DataFrame) -> pd.DataFrame:
    """Historico de emprestimos parcelados/POS anteriores (status mensal)."""
    out = pos.groupby("SK_ID_CURR").agg(
        n_pos_contratos=("SK_ID_PREV", "nunique"),
        pos_max_dpd=("SK_DPD", "max"),
        pos_meses_em_atraso=("SK_DPD", lambda s: (s > 0).sum()),
    ).reset_index()
    return out


def agregar_credit_card(cc: pd.DataFrame) -> pd.DataFrame:
    """Historico de uso de cartao de credito Home Credit."""
    df = cc.copy()
    df["utilizacao"] = np.where(
        df["AMT_CREDIT_LIMIT_ACTUAL"] > 0, df["AMT_BALANCE"] / df["AMT_CREDIT_LIMIT_ACTUAL"], np.nan
    )

    out = df.groupby("SK_ID_CURR").agg(
        n_cc_contratos=("SK_ID_PREV", "nunique"),
        cc_utilizacao_media=("utilizacao", "mean"),
        cc_max_dpd=("SK_DPD", "max"),
        cc_meses_em_atraso=("SK_DPD", lambda s: (s > 0).sum()),
    ).reset_index()
    return out


def montar_tabela_features(application: pd.DataFrame, agregados: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Junta application_train/test com os agregados das 5 tabelas relacionais.

    `agregados` = {"bureau": df, "previous_application": df, "installments": df,
                   "pos_cash": df, "credit_card": df} - cada uma indexada por SK_ID_CURR.

    Contagens (n_*) recebem fillna(0): ausencia de historico e fato medido.
    Fracoes/medias ficam NaN quando nao ha historico - deixado para o
    HistGradientBoostingClassifier tratar nativamente.
    """
    out = application.copy()
    contagem_prefixos = ("n_",)
    for nome, agg in agregados.items():
        out = out.merge(agg, on="SK_ID_CURR", how="left")

    for col in out.columns:
        if col.startswith(contagem_prefixos):
            out[col] = out[col].fillna(0)

    return out
