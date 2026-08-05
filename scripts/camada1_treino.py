"""Treino da Camada 1 final (ADR-0001) sobre o dataset Home Credit com
engenharia de features relacional (bureau, previous_application,
installments, POS_CASH, credit_card - scripts/camada1_feature_engineering.py).

Diferenca para o baseline diagnostico do Gate 1
(camada1_baseline_e_gate1_calibracao.py): aqui a calibracao entra DENTRO
do pipeline de producao (o .pkl salvo ja calibra internamente), nao e so
uma demonstracao a parte.

Split em 3: treino (60%) / calibracao (20%) / teste (20%), estratificado
por TARGET, todos com a distribuicao real (nenhum reamostrado) - o
pipeline de producao usa a distribuicao real desde o inicio, sem a
armadilha do undersampling que o Gate 1 demonstrou.
"""
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.frozen import FrozenEstimator
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.limpeza_dados import limpar  # noqa: E402

PROCESSED = Path(__file__).resolve().parents[1] / "data" / "processed"
MODELS = Path(__file__).resolve().parents[1] / "models"
REPORTS = Path(__file__).resolve().parents[1] / "reports"
MODELS.mkdir(exist_ok=True)

RANDOM_STATE = 42
N_BOOTSTRAP = 1000


def carregar():
    df = pd.read_parquet(PROCESSED / "camada1_features_train.parquet")
    df, contagens = limpar(df)
    print(f"  limpeza EDA: {contagens}")

    y = df["TARGET"]
    X = df.drop(columns=["TARGET", "SK_ID_CURR"])

    cat_cols = X.select_dtypes(include="object").columns.tolist()
    for c in cat_cols:
        X[c] = X[c].astype("category")

    return X, y, cat_cols


def bootstrap_ic(y_true, y_pred, metrica_fn, n=N_BOOTSTRAP, seed=RANDOM_STATE):
    rng = np.random.RandomState(seed)
    idx = np.arange(len(y_true))
    valores = []
    y_true_arr = np.asarray(y_true)
    y_pred_arr = np.asarray(y_pred)
    for _ in range(n):
        sample = rng.choice(idx, size=len(idx), replace=True)
        if y_true_arr[sample].sum() == 0 or y_true_arr[sample].sum() == len(sample):
            continue
        valores.append(metrica_fn(y_true_arr[sample], y_pred_arr[sample]))
    valores = np.array(valores)
    return np.percentile(valores, 2.5), np.percentile(valores, 97.5)


def main():
    print("Carregando dados processados (com features relacionais)...")
    X, y, cat_cols = carregar()
    print(f"  {len(X):,} linhas, {X.shape[1]} colunas, TARGET=1 em {y.mean():.2%}")

    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.4, stratify=y, random_state=RANDOM_STATE
    )
    X_calib, X_test, y_calib, y_test = train_test_split(
        X_temp, y_temp, test_size=0.5, stratify=y_temp, random_state=RANDOM_STATE
    )
    print(f"  treino={len(X_train):,}  calibracao={len(X_calib):,}  teste={len(X_test):,}")

    print("\nTreinando modelo base (HistGradientBoostingClassifier)...")
    modelo_base = HistGradientBoostingClassifier(
        categorical_features=cat_cols if cat_cols else None,
        random_state=RANDOM_STATE,
        max_iter=300,
        learning_rate=0.05,
        l2_regularization=1.0,
    )
    modelo_base.fit(X_train, y_train)

    p_hat_bruto = modelo_base.predict_proba(X_test)[:, 1]
    auc_bruto = roc_auc_score(y_test, p_hat_bruto)
    brier_bruto = brier_score_loss(y_test, p_hat_bruto)

    print("Calibrando (isotonica, conjunto de calibracao separado)...")
    modelo_calibrado = CalibratedClassifierCV(FrozenEstimator(modelo_base), method="isotonic")
    modelo_calibrado.fit(X_calib, y_calib)

    p_hat_calibrado = modelo_calibrado.predict_proba(X_test)[:, 1]
    auc_calibrado = roc_auc_score(y_test, p_hat_calibrado)
    brier_calibrado = brier_score_loss(y_test, p_hat_calibrado)

    print("Calculando IC bootstrap (AUC e Brier, n=1000)...")
    auc_ic = bootstrap_ic(y_test, p_hat_calibrado, roc_auc_score)
    brier_ic = bootstrap_ic(y_test, p_hat_calibrado, brier_score_loss)

    frac_pos, mean_pred = calibration_curve(y_test, p_hat_calibrado, n_bins=10, strategy="quantile")

    # Comparacao contra o baseline do Gate 1 (so application_train, sem
    # features relacionais) - mesmo tipo de split, numeros nao sao
    # diretamente comparaveis por vir de amostras de teste diferentes,
    # mas a ordem de grandeza e informativa.
    AUC_BASELINE_GATE1 = 0.7589
    BRIER_BASELINE_GATE1 = 0.0678

    print("\nSalvando artefatos do modelo...")
    joblib.dump(modelo_calibrado, MODELS / "camada1_home_credit_v1.pkl")
    colunas_modelo = {"colunas": list(X.columns), "categoricas": cat_cols}
    joblib.dump(colunas_modelo, MODELS / "camada1_home_credit_v1_colunas.pkl")

    linhas = []
    linhas.append("# Camada 1 (final) — treino sobre Home Credit com features relacionais\n")
    linhas.append("**Gerado por:** `scripts/camada1_treino.py`  ")
    linhas.append(f"**Dados:** `data/processed/camada1_features_train.parquet` ({len(X):,} linhas, {X.shape[1]} colunas — 122 de `application_train` + 32 agregadas de bureau/previous_application/installments/POS_CASH/credit_card)")
    linhas.append(f"**Split:** treino {len(X_train):,} / calibração {len(X_calib):,} / teste {len(X_test):,} (estratificado, distribuição real preservada em todos — sem reamostragem)\n")

    linhas.append("## Resultado no conjunto de teste (n={:,})\n".format(len(y_test)))
    linhas.append("| Modelo | AUC | Brier |")
    linhas.append("|---|---|---|")
    linhas.append(f"| Base (sem calibração pós-hoc) | {auc_bruto:.4f} | {brier_bruto:.4f} |")
    linhas.append(f"| **Calibrado (isotônica, produção)** | **{auc_calibrado:.4f}** | **{brier_calibrado:.4f}** |")
    linhas.append(f"\n**IC bootstrap (n={N_BOOTSTRAP} reamostragens, sobre n={len(y_test):,} casos de teste):**")
    linhas.append(f"- AUC: {auc_calibrado:.4f} (IC95% {auc_ic[0]:.4f}–{auc_ic[1]:.4f})")
    linhas.append(f"- Brier: {brier_calibrado:.4f} (IC95% {brier_ic[0]:.4f}–{brier_ic[1]:.4f})\n")

    linhas.append("## Comparação com o baseline do Gate 1 (só `application_train`, sem features relacionais)\n")
    linhas.append("| | Baseline Gate 1 (natural) | Camada 1 final (com features relacionais) |")
    linhas.append("|---|---|---|")
    linhas.append(f"| AUC | {AUC_BASELINE_GATE1:.4f} | {auc_calibrado:.4f} |")
    linhas.append(f"| Brier | {BRIER_BASELINE_GATE1:.4f} | {brier_calibrado:.4f} |")
    delta_auc = auc_calibrado - AUC_BASELINE_GATE1
    linhas.append(f"\n**Ganho de AUC com as features relacionais: {delta_auc:+.4f}.** ")
    if delta_auc > 0.01:
        linhas.append("Ganho relevante — o histórico de bureau/pagamentos agrega sinal real além do formulário de aplicação.")
    else:
        linhas.append("Ganho pequeno — boa parte do sinal preditivo já estava no formulário de aplicação; as features relacionais têm valor de auditabilidade/narrativa para o agente (Camada 2) mesmo sem grande ganho de AUC.")
    linhas.append("\n> ⚠️ Amostras de teste diferentes entre os dois splits (Gate 1 não usava as colunas novas) — comparação é indicativa de ordem de grandeza, não um teste pareado formal.")

    linhas.append("\n## Reliability diagram (10 bins por quantil, modelo calibrado)\n")
    linhas.append("| p̂ médio (bin) | taxa real observada | gap |")
    linhas.append("|---|---|---|")
    for mp, fp in zip(mean_pred, frac_pos):
        linhas.append(f"| {mp:.1%} | {fp:.1%} | {mp - fp:+.1%} |")

    linhas.append("\n## Artefatos salvos\n")
    linhas.append("- `models/camada1_home_credit_v1.pkl` — modelo calibrado (produção)")
    linhas.append("- `models/camada1_home_credit_v1_colunas.pkl` — lista de colunas e categóricas esperadas (contrato de paridade treino-serving)")

    linhas.append("\n## O que este treino NÃO resolve (débitos que seguem abertos)\n")
    linhas.append("- Sem tuning de hiperparâmetros (valores padrão razoáveis, não otimizados)")
    linhas.append("- Sem seleção de features (todas as 152 features de entrada mantidas, sem remover redundância/colinearidade)")
    linhas.append("- Sem validação cruzada (só um split treino/calibração/teste)")
    linhas.append("- Calibração isotônica pode overfit em amostras pequenas por bin — vale revisitar com Platt scaling como alternativa mais suave")

    texto = "\n".join(linhas)
    out_path = REPORTS / "camada1_treino_final.md"
    out_path.write_text(texto, encoding="utf-8")
    print(f"\nRelatorio salvo em {out_path}")


if __name__ == "__main__":
    main()
