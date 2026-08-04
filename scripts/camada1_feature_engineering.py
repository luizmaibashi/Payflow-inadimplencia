"""Roda a engenharia de features da Camada 1 sobre as 5 tabelas relacionais
do Home Credit (ADR-0001) e salva a tabela processada em data/processed/.

Uso: python scripts/camada1_feature_engineering.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.feature_engineering_home_credit import (
    agregar_bureau,
    agregar_credit_card,
    agregar_installments,
    agregar_pos_cash,
    agregar_previous_application,
    montar_tabela_features,
)

RAW = Path(__file__).resolve().parents[1] / "data" / "raw" / "home_credit"
PROCESSED = Path(__file__).resolve().parents[1] / "data" / "processed"
PROCESSED.mkdir(exist_ok=True)


def main():
    print("Carregando tabelas relacionais...")
    bureau = pd.read_csv(RAW / "bureau.csv")
    bureau_balance = pd.read_csv(RAW / "bureau_balance.csv")
    previous_application = pd.read_csv(RAW / "previous_application.csv")
    installments = pd.read_csv(RAW / "installments_payments.csv")
    pos_cash = pd.read_csv(RAW / "POS_CASH_balance.csv")
    credit_card = pd.read_csv(RAW / "credit_card_balance.csv")

    print("Agregando bureau + bureau_balance...")
    agg_bureau = agregar_bureau(bureau, bureau_balance)
    print(f"  {len(agg_bureau):,} clientes com historico de bureau")

    print("Agregando previous_application...")
    agg_prev = agregar_previous_application(previous_application)
    print(f"  {len(agg_prev):,} clientes com propostas anteriores")

    print("Agregando installments_payments...")
    agg_inst = agregar_installments(installments)
    print(f"  {len(agg_inst):,} clientes com historico de parcelas")

    print("Agregando POS_CASH_balance...")
    agg_pos = agregar_pos_cash(pos_cash)
    print(f"  {len(agg_pos):,} clientes com historico POS/cash")

    print("Agregando credit_card_balance...")
    agg_cc = agregar_credit_card(credit_card)
    print(f"  {len(agg_cc):,} clientes com historico de cartao")

    agregados = {
        "bureau": agg_bureau,
        "previous_application": agg_prev,
        "installments": agg_inst,
        "pos_cash": agg_pos,
        "credit_card": agg_cc,
    }

    for nome, df_split in [("train", "application_train.csv"), ("test", "application_test.csv")]:
        print(f"\nMontando tabela final ({nome})...")
        application = pd.read_csv(RAW / df_split)
        tabela = montar_tabela_features(application, agregados)
        print(f"  shape final: {tabela.shape}")
        out_path = PROCESSED / f"camada1_features_{nome}.parquet"
        tabela.to_parquet(out_path, index=False)
        print(f"  salvo em {out_path}")


if __name__ == "__main__":
    main()
