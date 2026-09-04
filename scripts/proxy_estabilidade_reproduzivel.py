"""Executa o baseline canônico do proxy semântico no Stability."""

import argparse
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app.experimento_proxy_estabilidade import (  # noqa: E402
    FEATURES_PROXY,
    ConfiguracaoExperimentoProxy,
    executar_experimento_proxy,
    formatar_relatorio_markdown,
    montar_base_proxy,
)
from app.drift_features import PoliticaDrift  # noqa: E402
from app.politica_uso_modelo import PoliticaEvidencia  # noqa: E402


def argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reconstrói e mede o proxy temporal do PayFlow."
    )
    parser.add_argument("--data-referencia", required=True)
    parser.add_argument("--janela-dias", required=True, type=int)
    parser.add_argument("--bootstrap", type=int, default=200)
    parser.add_argument("--saida", type=Path)
    return parser.parse_args()


def carregar_dados() -> pd.DataFrame:
    raw = RAIZ / "data" / "raw" / "home_credit_stability"
    base = pd.read_csv(
        raw / "train_base.csv",
        usecols=["case_id", "date_decision", "target"],
    )
    colunas = ["case_id", *FEATURES_PROXY]
    particoes = [
        pd.read_parquet(raw / "train_static_0_0.parquet", columns=colunas),
        pd.read_parquet(raw / "train_static_0_1.parquet", columns=colunas),
    ]
    return montar_base_proxy(base, particoes)


def main() -> None:
    args = argumentos()
    configuracao = ConfiguracaoExperimentoProxy(
        data_referencia=args.data_referencia,
        janela_dias=args.janela_dias,
        amostras_bootstrap=args.bootstrap,
    )
    politica_case = PoliticaEvidencia(
        auc_referencia=0.6148,
        brier_referencia=0.0346,
        minimo_observacoes=1_000,
        minimo_inadimplentes=100,
        tolerancia_auc=0.03,
        tolerancia_brier=0.01,
        auc_ic_inferior_minimo=0.50,
    )
    resultado = executar_experimento_proxy(
        carregar_dados(),
        configuracao=configuracao,
        politica=politica_case,
        politica_drift=PoliticaDrift(
            minimo_nao_nulos=1_000,
            ks_alerta=0.10,
            ks_critico=0.20,
            ausencia_alerta=0.05,
            ausencia_critica=0.10,
        ),
    )
    relatorio = formatar_relatorio_markdown(resultado)
    if args.saida is None:
        print(relatorio)
        return
    args.saida.write_text(relatorio, encoding="utf-8")
    print(f"Relatório salvo em {args.saida}")


if __name__ == "__main__":
    main()
