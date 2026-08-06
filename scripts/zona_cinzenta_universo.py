"""Materializa em disco o universo da ZONA CINZENTA (insumo da Camada 2).

POR QUE ESTE SCRIPT EXISTE: ate agora a zona cinzenta so existia DENTRO de
scripts/motor_decisao_backtest.py - era calculada, reportada em agregado e
descartada quando o processo terminava. Nenhum arquivo diz QUAIS sao os casos.
Rodar o agente da Camada 2 contra eles exige a lista em disco, e exige o
SK_ID_CURR: as ferramentas de caso (app/ferramentas_caso.py) so aceitam id.

O SK_ID_CURR e o ponto delicado. recriar_split() devolve X_test JA SEM essa
coluna - ela e dropada junto com TARGET antes do split, exatamente para que o
modelo nunca a veja. A recuperacao e pelo INDICE: app/limpeza_dados.limpar()
so remove COLUNAS, nunca linhas e nunca reindexa, entao o indice de X_test
continua apontando para as linhas originais do parquet. Ha uma asercao abaixo
guardando essa premissa - se limpar() um dia passar a mexer em linhas, este
script quebra alto em vez de casar id errado com caso errado.

PARIDADE: o split e o p_hat vem de recriar_split() do proprio backtest, nao de
uma copia. Duas implementacoes do mesmo split divergem em silencio e o universo
deixaria de ser o mesmo que o relatorio do motor descreve.

Saida: data/processed/zona_cinzenta.parquet (gitignored, regeneravel).
"""
import sys
from pathlib import Path

import joblib
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from app.motor_decisao import (  # noqa: E402
    classificar_decisao_por_limites,
    lgd_por_tipo_contrato,
    limites_p_estrela_por_incerteza_margem,
)
from motor_decisao_backtest import recriar_split  # noqa: E402

PROCESSED = RAIZ / "data" / "processed"
MODELS = RAIZ / "models"
SAIDA = PROCESSED / "zona_cinzenta.parquet"

# ACHADO (2026-08-06): NAO da para estratificar p_hat em quartis. O modelo e
# CalibratedClassifierCV(method="isotonic"), e regressao isotonica devolve
# funcao ESCADA: sao 113 valores distintos de p_hat em 61.503 casos de teste,
# e apenas 15 dentro da zona cinzenta. Um unico valor (0,335337) concentra
# 40,6% da zona - mais que um quartil inteiro, entao pd.qcut(q=4) estoura com
# "Bin edges must be unique".
#
# Nao e bug: e o comportamento esperado da isotonica. Mas muda a estratificacao.
# O estrato honesto aqui e o PROPRIO PLATO de p_hat, porque essa e a resolucao
# real do modelo - casos no mesmo plato sao, para a Camada 1, indistinguiveis.
# Inventar faixas mais finas que o modelo produz seria precisao falsa.


def main():
    print("Recriando o split de teste (mesma funcao do backtest)...")
    X_test, y_test = recriar_split()
    print(f"  n_teste={len(X_test):,}")

    # PREMISSA GUARDADA: limpar() nao mexe em linhas, entao o indice de X_test
    # ainda enderecas as linhas originais do parquet. Se isso deixar de valer,
    # o merge abaixo casaria id errado com caso errado - silenciosamente.
    ids_originais = pd.read_parquet(
        PROCESSED / "camada1_features_train.parquet", columns=["SK_ID_CURR"]
    )
    faltantes = X_test.index.difference(ids_originais.index)
    if len(faltantes):
        raise RuntimeError(
            f"{len(faltantes)} indices de X_test nao existem no parquet original. "
            "limpar() passou a remover ou reindexar linhas - a recuperacao do "
            "SK_ID_CURR por indice nao vale mais. Ver docstring deste script."
        )
    sk_id = ids_originais.loc[X_test.index, "SK_ID_CURR"]

    print("Carregando modelo calibrado e pontuando...")
    modelo = joblib.load(MODELS / "camada1_home_credit_v1.pkl")
    p_hat = modelo.predict_proba(X_test)[:, 1]

    # Mesma derivacao do backtest: a banda vem da incerteza da premissa de
    # margem (ADR-0002 SS2.6), nao de uma largura escolhida a mao.
    lgd = lgd_por_tipo_contrato(X_test["NAME_CONTRACT_TYPE"])
    p_inf, p_sup = limites_p_estrela_por_incerteza_margem(lgd)
    decisao = classificar_decisao_por_limites(p_hat, p_inf, p_sup)

    universo = pd.DataFrame(
        {
            "SK_ID_CURR": sk_id.to_numpy(),
            "p_hat": p_hat,
            "TARGET": y_test.to_numpy(),
            "NAME_CONTRACT_TYPE": X_test["NAME_CONTRACT_TYPE"].astype(str).to_numpy(),
            "lgd": lgd,
            "p_estrela_inf": p_inf,
            "p_estrela_sup": p_sup,
            "decisao_motor": decisao,
        },
        index=X_test.index,
    )

    cinzenta = universo[universo["decisao_motor"] == "ZONA_CINZENTA"].copy()

    # Estrato = o PLATO de p_hat (ver nota sobre a isotonica no topo). Guardado
    # como categoria ordenada para a amostragem estratificada do passo D.
    #
    # NOTA: o bridge falava em estratificar por faixa de `p*`, mas p* aqui
    # assume so DOIS valores (a margem e constante global e a LGD tem duas
    # categorias) - estratificar por ele equivaleria a estratificar por tipo de
    # contrato. O que varia caso a caso e o p_hat. Tipo de contrato fica
    # gravado em coluna propria para quem quiser cruzar depois.
    platos = sorted(cinzenta["p_hat"].unique())
    cinzenta["plato_p_hat"] = pd.Categorical(
        cinzenta["p_hat"], categories=platos, ordered=True
    )

    PROCESSED.mkdir(parents=True, exist_ok=True)
    cinzenta.to_parquet(SAIDA)

    n = len(cinzenta)
    print(f"\nZona cinzenta: {n:,} casos ({n/len(X_test):.1%} do teste)")
    print(f"  taxa de default real: {cinzenta['TARGET'].mean():.1%} "
          f"(carteira: {universo['TARGET'].mean():.1%})")
    print(f"  p_hat: min={cinzenta['p_hat'].min():.3f} max={cinzenta['p_hat'].max():.3f} "
          f"em apenas {cinzenta['p_hat'].nunique()} platos distintos (isotonica)")
    print("\nEstratos (plato de p_hat x TARGET) - insumo do passo D:")
    tab = pd.crosstab(cinzenta["plato_p_hat"], cinzenta["TARGET"], margins=True)
    print(tab.to_string())
    print(f"\nSalvo em {SAIDA}")


if __name__ == "__main__":
    main()
