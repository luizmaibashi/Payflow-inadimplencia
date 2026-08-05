"""Limpeza do dado bruto, vinda da EDA sistematica (reports/eda_application.md).

Mora em app/ e nao em scripts/ por causa de PARIDADE TREINO-SERVING: antes
disto a limpeza estava COPIADA em camada1_treino.py e em
motor_decisao_backtest.py. Logica copiada diverge em silencio - alguem
corrige um lado, esquece o outro, e o modelo passa a receber no eval um
dado diferente do que viu no treino. Nada quebra; o numero so fica errado.

Regra da casa (.claude/rules/dados.md): **erro implausivel vira NULO**, nao
teto nem exclusao. Nulo e a afirmacao honesta "este campo nao e confiavel
aqui": toca so as linhas ruins e preserva o resto da observacao.
"""
import numpy as np
import pandas as pd

# Sentinela de "nao empregado" (~1.000 anos). E o segmento de aposentados,
# 18,01% da base, com default de 5,40% contra 8,66% do resto - ou seja, o
# "ausente" marcava um grupo de MENOR risco. A informacao sobrevive em
# NAME_INCOME_TYPE e ORGANIZATION_TYPE (mesma populacao, divergencia zero),
# entao anular nao perde sinal.
SENTINELA_DIAS_EMPREGO = 365243

# Renda implausivel por criterio RELACIONAL, nao absoluto: "renda alta" e
# legitimo, "renda dezenas de vezes o valor pedido" nao - quem ganha isso
# nao toma emprestado. Pega exatamente 1 linha na base (renda declarada de
# 117 milhoes para credito de 562 mil; comprometimento de 0,00002% contra
# mediana de 16,3%). Teto no p99 alteraria 3.074 rendas legitimas para
# consertar esta uma.
RAZAO_RENDA_CREDITO_IMPLAUSIVEL = 50

# Colunas com >99,5% num unico valor - nao separam ninguem. FLAG_MOBIL e 1
# para 100% da base; FLAG_DOCUMENT_2/10/12 sao 0 para 100%. Arvore ja
# ignora, entao remover NAO muda AUC: e higiene e custo de treino.
COLUNAS_CONSTANTES = (
    "FLAG_MOBIL", "FLAG_CONT_MOBILE", "FLAG_DOCUMENT_2", "FLAG_DOCUMENT_4",
    "FLAG_DOCUMENT_7", "FLAG_DOCUMENT_9", "FLAG_DOCUMENT_10", "FLAG_DOCUMENT_11",
    "FLAG_DOCUMENT_12", "FLAG_DOCUMENT_13", "FLAG_DOCUMENT_14", "FLAG_DOCUMENT_15",
    "FLAG_DOCUMENT_17", "FLAG_DOCUMENT_19", "FLAG_DOCUMENT_20", "FLAG_DOCUMENT_21",
)


def limpar(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Aplica as correcoes da EDA e devolve o que foi tocado.

    Retorna contagens de proposito: limpeza silenciosa e equivalente a nao
    ter feito - sem o numero, ninguem audita depois.
    """
    df = df.copy()
    contagens = {}

    n = int((df["DAYS_EMPLOYED"] == SENTINELA_DIAS_EMPREGO).sum())
    df["DAYS_EMPLOYED"] = df["DAYS_EMPLOYED"].replace(SENTINELA_DIAS_EMPREGO, np.nan)
    contagens["dias_emprego_anulados"] = n

    implausivel = (
        df["AMT_INCOME_TOTAL"] > RAZAO_RENDA_CREDITO_IMPLAUSIVEL * df["AMT_CREDIT"]
    )
    df.loc[implausivel, "AMT_INCOME_TOTAL"] = np.nan
    contagens["renda_anulada"] = int(implausivel.sum())

    presentes = [c for c in COLUNAS_CONSTANTES if c in df.columns]
    df = df.drop(columns=presentes)
    contagens["colunas_constantes_removidas"] = len(presentes)

    return df, contagens
