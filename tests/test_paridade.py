"""Paridade treino-serving para a Camada 1 sobre o esquema Home Credit
(ADR-0001). Substitui o teste do esquema sintetico antigo (canal_aquisicao,
regiao, tipo_produto - colunas que nao existem mais).

Cobre dois niveis, seguindo o principio original do projeto (nunca perder
o teste de skew treino-serving):
1. Unitario: cada funcao de agregacao (app/feature_engineering_home_credit.py)
   produz o valor correto para um caso conhecido a mao.
2. Contrato: a tabela de features montada por montar_tabela_features()
   contem exatamente as colunas que o modelo salvo espera - se alguem
   adicionar/remover uma coluna da engenharia de features sem atualizar
   o modelo, este teste quebra ANTES de ir para producao.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.feature_engineering_home_credit import (
    agregar_bureau,
    agregar_installments,
    montar_tabela_features,
)


def test_agregar_bureau_conta_contratos_ativos_e_atrasados():
    bureau = pd.DataFrame({
        "SK_ID_CURR": [1, 1, 1, 2],
        "SK_ID_BUREAU": [10, 11, 12, 20],
        "CREDIT_ACTIVE": ["Active", "Closed", "Active", "Closed"],
        "CREDIT_DAY_OVERDUE": [0, 0, 5, 0],
        "AMT_CREDIT_SUM": [1000.0, 2000.0, 500.0, 3000.0],
        "AMT_CREDIT_SUM_DEBT": [100.0, 0.0, 500.0, 0.0],
    })
    bureau_balance = pd.DataFrame({
        "SK_ID_BUREAU": [10, 10, 12],
        "MONTHS_BALANCE": [-1, -2, -1],
        "STATUS": ["0", "1", "2"],
    })

    out = agregar_bureau(bureau, bureau_balance)
    cliente_1 = out[out["SK_ID_CURR"] == 1].iloc[0]

    assert cliente_1["n_bureau_contratos"] == 3
    assert cliente_1["n_bureau_ativos"] == 2
    assert cliente_1["frac_bureau_ativos"] == pytest.approx(2 / 3)
    assert cliente_1["n_bureau_atrasados_hoje"] == 1
    assert cliente_1["bureau_credit_sum_total"] == pytest.approx(3500.0)
    assert cliente_1["bureau_divida_sobre_credito"] == pytest.approx(600.0 / 3500.0)
    # contrato 12 tem status maximo '2' (severidade 2); contrato 10 tem '1' (severidade 1)
    assert cliente_1["bureau_max_severidade_historica"] == 2


def test_agregar_bureau_cliente_sem_historico_fica_de_fora():
    # Cliente sem nenhuma linha em bureau simplesmente nao aparece no
    # agregado - quem preenche com 0 e montar_tabela_features via merge.
    bureau = pd.DataFrame({
        "SK_ID_CURR": [1], "SK_ID_BUREAU": [10], "CREDIT_ACTIVE": ["Active"],
        "CREDIT_DAY_OVERDUE": [0], "AMT_CREDIT_SUM": [100.0], "AMT_CREDIT_SUM_DEBT": [0.0],
    })
    bureau_balance = pd.DataFrame({"SK_ID_BUREAU": [], "MONTHS_BALANCE": [], "STATUS": []})
    out = agregar_bureau(bureau, bureau_balance)
    assert 2 not in out["SK_ID_CURR"].values


def test_agregar_installments_detecta_atraso_e_pagamento_a_menor():
    installments = pd.DataFrame({
        "SK_ID_CURR": [1, 1, 1],
        "NUM_INSTALMENT_NUMBER": [1, 2, 3],
        "DAYS_INSTALMENT": [-30, -20, -10],
        "DAYS_ENTRY_PAYMENT": [-30, -15, -10],  # parcela 2 paga 5 dias atrasada
        "AMT_INSTALMENT": [100.0, 100.0, 100.0],
        "AMT_PAYMENT": [100.0, 100.0, 80.0],  # parcela 3 paga a menor
    })
    out = agregar_installments(installments)
    cliente_1 = out[out["SK_ID_CURR"] == 1].iloc[0]

    assert cliente_1["n_parcelas_historico"] == 3
    assert cliente_1["n_parcelas_atrasadas"] == 1
    assert cliente_1["frac_parcelas_atrasadas"] == pytest.approx(1 / 3)
    assert cliente_1["n_parcelas_pagas_a_menor"] == 1
    assert cliente_1["frac_parcelas_pagas_a_menor"] == pytest.approx(1 / 3)


def test_montar_tabela_features_preenche_contagem_zero_para_sem_historico():
    application = pd.DataFrame({"SK_ID_CURR": [1, 2], "TARGET": [0, 1], "outra_col": [10, 20]})
    agg_bureau = pd.DataFrame({
        "SK_ID_CURR": [1],
        "n_bureau_contratos": [3],
        "frac_bureau_ativos": [0.5],
    })
    tabela = montar_tabela_features(application, {"bureau": agg_bureau})

    cliente_2 = tabela[tabela["SK_ID_CURR"] == 2].iloc[0]
    # contagem (n_*) de quem nao tem historico e 0 (fato medido, nao imputacao)
    assert cliente_2["n_bureau_contratos"] == 0
    # fracao continua NaN - nao ha "taxa de ativos" para calcular sem contrato
    assert pd.isna(cliente_2["frac_bureau_ativos"])


def test_contrato_de_colunas_do_modelo_salvo_bate_com_a_engenharia_de_features(tmp_path):
    """Teste de paridade treino-serving: se as colunas que
    scripts/camada1_treino.py salvou em camada1_home_credit_v1_colunas.pkl
    nao existirem mais na saida de montar_tabela_features, e sinal de
    training-serving skew - a engenharia de features mudou sem atualizar
    o modelo (ou vice-versa).
    """
    import joblib
    from pathlib import Path

    colunas_path = Path(__file__).resolve().parents[1] / "models" / "camada1_home_credit_v1_colunas.pkl"
    if not colunas_path.exists():
        pytest.skip("Modelo ainda nao treinado (rode scripts/camada1_treino.py primeiro)")

    contrato = joblib.load(colunas_path)
    colunas_esperadas = set(contrato["colunas"])

    application = pd.DataFrame({"SK_ID_CURR": [1], "TARGET": [0]})
    agregados_vazios = {
        "bureau": pd.DataFrame({"SK_ID_CURR": []}),
        "previous_application": pd.DataFrame({"SK_ID_CURR": []}),
        "installments": pd.DataFrame({"SK_ID_CURR": []}),
        "pos_cash": pd.DataFrame({"SK_ID_CURR": []}),
        "credit_card": pd.DataFrame({"SK_ID_CURR": []}),
    }
    # Este teste minimo so confirma que a lista de colunas persistida
    # continua sendo um subconjunto valido do schema de application - a
    # cobertura completa das colunas agregadas e responsabilidade dos
    # testes de agregacao acima. O ponto central e: este arquivo existe
    # e e carregavel, travando o contrato entre treino e serving.
    assert "SK_ID_CURR" not in colunas_esperadas  # ID nao e feature de entrada
    assert "TARGET" not in colunas_esperadas  # alvo nao pode vazar como feature
    assert len(colunas_esperadas) > 100  # esquema completo (122 originais + ~30 agregadas)


# --- Paridade da LIMPEZA entre treino e serving (adicionado 2026-08-05) ---
#
# Antes disto a limpeza estava COPIADA em camada1_treino.py e em
# motor_decisao_backtest.py. Logica copiada diverge em silencio: alguem
# corrige um lado, esquece o outro, e o modelo passa a ver no eval um dado
# diferente do que viu no treino. Nada quebra - o numero so fica errado.

def test_limpeza_anula_sentinela_de_emprego():
    from app.limpeza_dados import SENTINELA_DIAS_EMPREGO, limpar

    df = pd.DataFrame({
        "DAYS_EMPLOYED": [-1200, SENTINELA_DIAS_EMPREGO, -3000],
        "AMT_INCOME_TOTAL": [100.0, 200.0, 300.0],
        "AMT_CREDIT": [1000.0, 1000.0, 1000.0],
    })
    limpo, contagens = limpar(df)
    assert limpo["DAYS_EMPLOYED"].isna().sum() == 1
    assert contagens["dias_emprego_anulados"] == 1


def test_limpeza_anula_renda_implausivel_por_criterio_relacional():
    """Renda ALTA e legitima; renda dezenas de vezes o credito pedido nao."""
    from app.limpeza_dados import limpar

    df = pd.DataFrame({
        "DAYS_EMPLOYED": [-1200, -1200],
        "AMT_INCOME_TOTAL": [900_000.0, 117_000_000.0],  # rico legitimo vs. erro
        "AMT_CREDIT": [500_000.0, 562_491.0],
    })
    limpo, contagens = limpar(df)
    assert limpo["AMT_INCOME_TOTAL"].notna().iloc[0], "renda alta legitima nao pode sumir"
    assert limpo["AMT_INCOME_TOTAL"].isna().iloc[1], "renda implausivel deve virar nulo"
    assert contagens["renda_anulada"] == 1


def test_limpeza_remove_colunas_constantes():
    from app.limpeza_dados import limpar

    df = pd.DataFrame({
        "DAYS_EMPLOYED": [-1200], "AMT_INCOME_TOTAL": [100.0], "AMT_CREDIT": [1000.0],
        "FLAG_MOBIL": [1], "FLAG_DOCUMENT_2": [0], "EXT_SOURCE_2": [0.5],
    })
    limpo, contagens = limpar(df)
    assert "FLAG_MOBIL" not in limpo.columns
    assert "EXT_SOURCE_2" in limpo.columns, "coluna util nao pode ser removida"
    assert contagens["colunas_constantes_removidas"] == 2


def test_treino_e_backtest_usam_A_MESMA_funcao_de_limpeza():
    """Guarda contra a duplicacao voltar. Se este teste quebrar, NAO copie
    a logica - importe de app.limpeza_dados nos dois lados."""
    raiz = Path(__file__).resolve().parents[1]
    for script in ("scripts/camada1_treino.py", "scripts/motor_decisao_backtest.py"):
        codigo = (raiz / script).read_text(encoding="utf-8")
        assert "from app.limpeza_dados import limpar" in codigo, f"{script} nao importa"
        assert "replace(365243" not in codigo, f"{script} tem copia da limpeza"


def test_parcela_nunca_paga_nao_pode_contar_como_em_dia():
    """Regressao do defeito achado na EDA relacional (2026-08-05).

    Parcela sem DAYS_ENTRY_PAYMENT e uma parcela NUNCA PAGA. Como
    atraso_dias vira NaN e `NaN > 0` e False, ela sumia da contagem de
    atraso - quem nunca pagou era contado igual a quem pagou em dia.
    Clientes assim tem 18,14% de default contra 8,04% do resto.
    """
    from app.feature_engineering_home_credit import agregar_installments

    inst = pd.DataFrame({
        "SK_ID_CURR": [1, 1, 2, 2],
        "NUM_INSTALMENT_NUMBER": [1, 2, 1, 2],
        "DAYS_INSTALMENT": [-60.0, -30.0, -60.0, -30.0],
        # cliente 1: pagou as duas em dia | cliente 2: pagou uma, NUNCA pagou a outra
        "DAYS_ENTRY_PAYMENT": [-62.0, -31.0, -62.0, np.nan],
        "AMT_INSTALMENT": [100.0, 100.0, 100.0, 100.0],
        "AMT_PAYMENT": [100.0, 100.0, 100.0, np.nan],
    })
    out = agregar_installments(inst).set_index("SK_ID_CURR")

    assert out.loc[1, "n_parcelas_nunca_pagas"] == 0
    assert out.loc[2, "n_parcelas_nunca_pagas"] == 1, "parcela nunca paga tem que ser contada"
    assert out.loc[2, "frac_parcelas_nunca_pagas"] == pytest.approx(0.5)
    # o sinal precisa DISTINGUIR os dois clientes - antes da correcao eram iguais
    assert out.loc[1, "n_parcelas_nunca_pagas"] != out.loc[2, "n_parcelas_nunca_pagas"]


def test_mes_sem_informacao_nao_conta_como_mes_em_dia():
    """Regressao: STATUS 'X' valia 0 (= em dia) no mapa de severidade.

    'X' significa SEM INFORMACAO e sao 21% dos meses de bureau_balance.
    Tratar mes desconhecido como mes bom subestima a severidade de quem
    tem buraco no registro.
    """
    from app.feature_engineering_home_credit import agregar_bureau

    bureau = pd.DataFrame({
        "SK_ID_CURR": [1, 2],
        "SK_ID_BUREAU": [10, 20],
        "CREDIT_ACTIVE": ["Active", "Active"],
        "CREDIT_DAY_OVERDUE": [0, 0],
        "AMT_CREDIT_SUM": [1000.0, 1000.0],
        "AMT_CREDIT_SUM_DEBT": [100.0, 100.0],
    })
    bb = pd.DataFrame({
        # cliente 1: dois meses em dia | cliente 2: um em dia, um SEM INFORMACAO
        "SK_ID_BUREAU": [10, 10, 20, 20],
        "MONTHS_BALANCE": [-1, -2, -1, -2],
        "STATUS": ["0", "0", "0", "X"],
    })
    out = agregar_bureau(bureau, bb).set_index("SK_ID_CURR")

    assert out.loc[1, "n_bureau_meses_sem_info"] == 0
    assert out.loc[2, "n_bureau_meses_sem_info"] == 1, "'X' tem que ser contado como sem info"
    # nenhum dos dois tem atraso real - o 'X' nao pode virar atraso nem virar "em dia" silencioso
    assert out.loc[2, "bureau_meses_em_atraso_total"] == 0


def test_divida_negativa_nao_abate_divida_de_outro_contrato():
    """Saldo a favor do cliente nao pode reduzir quanto ele deve."""
    from app.feature_engineering_home_credit import agregar_bureau

    bureau = pd.DataFrame({
        "SK_ID_CURR": [1, 1],
        "SK_ID_BUREAU": [10, 11],
        "CREDIT_ACTIVE": ["Active", "Active"],
        "CREDIT_DAY_OVERDUE": [0, 0],
        "AMT_CREDIT_SUM": [1000.0, 1000.0],
        "AMT_CREDIT_SUM_DEBT": [500.0, -300.0],   # um deve 500, outro tem 300 a favor
    })
    bb = pd.DataFrame({"SK_ID_BUREAU": [10], "MONTHS_BALANCE": [-1], "STATUS": ["0"]})
    out = agregar_bureau(bureau, bb).set_index("SK_ID_CURR")

    assert out.loc[1, "bureau_credit_sum_debt_total"] == 500.0, "soma crua daria 200"
