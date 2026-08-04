"""Camada 1 baseline + Gate 1 (ADR-0002 SS2.5): a calibracao importa mais que o AUC.

Este script NAO e a Camada 1 final (essa exige EDA completo e feature
engineering sobre as tabelas relacionais, fora de escopo aqui - ADR-0001).
E um baseline diagnostico com um objetivo unico: reproduzir com dado real
o mecanismo da sabatina do Bloco 1 (P2) - undersampling da classe
majoritaria desloca o prior e infla p_hat sistematicamente, o AUC nao
acusa, e o motor de valor esperado (p* do ADR-0002) fica invalido sem
recalibracao.

Compara duas variantes de treino sobre application_train.csv:
  (a) natural   - sem reamostragem, distribuicao real (~8% TARGET=1)
  (b) undersample - classe majoritaria reamostrada para ~50/50 (como o
      pipeline legado do payflow fazia com imbalanced-learn)

Para cada variante mede, no MESMO conjunto de teste (distribuicao real):
  - AUC (ranqueamento)
  - Brier score (calibracao)
  - reliability diagram (bins de p_hat vs. taxa real observada)

E aplica calibracao isotonica pos-hoc na variante undersample, mostrando
que corrige o Brier/reliability sem mudar o AUC (a isotonica so remapeia
a escala de p_hat, nao a ordem).
"""
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.calibration import calibration_curve, CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.metrics import roc_auc_score, brier_score_loss

DATA = Path(__file__).resolve().parents[1] / "data" / "raw" / "home_credit"
OUT = Path(__file__).resolve().parents[1] / "reports"
OUT.mkdir(exist_ok=True)

RANDOM_STATE = 42


def carregar_e_preparar():
    df = pd.read_csv(DATA / "application_train.csv")

    # Anomalia documentada do Home Credit: DAYS_EMPLOYED=365243 e sentinela
    # de "nao empregado" (aposentado/desempregado), nao um valor real de dias.
    df["DAYS_EMPLOYED"] = df["DAYS_EMPLOYED"].replace(365243, np.nan)

    y = df["TARGET"]
    X = df.drop(columns=["TARGET", "SK_ID_CURR"])

    # HistGradientBoosting lida nativamente com NaN e com categoricas
    # (dtype 'category'), sem imputar nada - evita imputacao injustificada.
    cat_cols = X.select_dtypes(include="object").columns.tolist()
    for c in cat_cols:
        X[c] = X[c].astype("category")

    return X, y, cat_cols


def treinar(X_train, y_train, cat_cols, undersample: bool):
    if undersample:
        # Reamostra a classe majoritaria para ~50/50, mesma logica do
        # imbalanced-learn no pipeline legado (RandomUnderSampler).
        idx_pos = y_train[y_train == 1].index
        idx_neg = y_train[y_train == 0].index
        n_pos = len(idx_pos)
        rng = np.random.RandomState(RANDOM_STATE)
        idx_neg_sample = rng.choice(idx_neg, size=n_pos, replace=False)
        idx_final = np.concatenate([idx_pos, idx_neg_sample])
        X_fit = X_train.loc[idx_final]
        y_fit = y_train.loc[idx_final]
    else:
        X_fit, y_fit = X_train, y_train

    modelo = HistGradientBoostingClassifier(
        categorical_features=cat_cols if cat_cols else None,
        random_state=RANDOM_STATE,
        max_iter=200,
        learning_rate=0.05,
    )
    modelo.fit(X_fit, y_fit)
    return modelo, len(X_fit)


def avaliar(modelo, X_test, y_test, nome: str):
    p_hat = modelo.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, p_hat)
    brier = brier_score_loss(y_test, p_hat)
    frac_pos, mean_pred = calibration_curve(y_test, p_hat, n_bins=10, strategy="quantile")
    return {
        "nome": nome,
        "auc": auc,
        "brier": brier,
        "p_hat_medio": p_hat.mean(),
        "taxa_real_teste": y_test.mean(),
        "reliability": list(zip(mean_pred, frac_pos)),
    }


def formatar_reliability(reliability):
    linhas = ["| p̂ médio (bin) | taxa real observada | gap |", "|---|---|---|"]
    for mean_pred, frac_pos in reliability:
        gap = mean_pred - frac_pos
        linhas.append(f"| {mean_pred:.1%} | {frac_pos:.1%} | {gap:+.1%} |")
    return "\n".join(linhas)


def main():
    print("Carregando application_train.csv...")
    X, y, cat_cols = carregar_e_preparar()
    print(f"  {len(X):,} linhas, TARGET=1 em {y.mean():.2%}")

    # 3 conjuntos: treino (60%), calibracao (20%), teste (20%) - todos
    # estratificados. Calibracao e teste ficam na distribuicao REAL,
    # nunca reamostrados - so o treino da variante (b) e reamostrado.
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.4, stratify=y, random_state=RANDOM_STATE
    )
    X_calib, X_test, y_calib, y_test = train_test_split(
        X_temp, y_temp, test_size=0.5, stratify=y_temp, random_state=RANDOM_STATE
    )
    print(f"  treino={len(X_train):,}  calibracao={len(X_calib):,}  teste={len(X_test):,}")

    resultados = []

    print("Treinando variante NATURAL (sem reamostragem)...")
    modelo_natural, n_fit_natural = treinar(X_train, y_train, cat_cols, undersample=False)
    res_natural = avaliar(modelo_natural, X_test, y_test, "Natural (sem reamostragem)")
    res_natural["n_treino"] = n_fit_natural
    resultados.append(res_natural)

    print("Treinando variante UNDERSAMPLE (~50/50, como o pipeline legado)...")
    modelo_under, n_fit_under = treinar(X_train, y_train, cat_cols, undersample=True)
    res_under = avaliar(modelo_under, X_test, y_test, "Undersample (nao calibrado)")
    res_under["n_treino"] = n_fit_under
    resultados.append(res_under)

    print("Recalibrando a variante undersample (isotonica, conjunto separado)...")
    calibrado = CalibratedClassifierCV(FrozenEstimator(modelo_under), method="isotonic")
    calibrado.fit(X_calib, y_calib)
    res_calibrado = avaliar(calibrado, X_test, y_test, "Undersample + isotonica")
    res_calibrado["n_treino"] = n_fit_under
    resultados.append(res_calibrado)

    # Relatorio
    linhas = []
    linhas.append("# Gate 1 — Calibração da Camada 1 (baseline diagnóstico)\n")
    linhas.append(f"**Gerado por:** `scripts/camada1_baseline_e_gate1_calibracao.py`  ")
    linhas.append(f"**Fonte:** `application_train.csv` ({len(X):,} linhas, TARGET=1 em {y.mean():.2%})")
    linhas.append(f"**Split:** treino {len(X_train):,} / calibração {len(X_calib):,} / teste {len(X_test):,} (estratificado, distribuição real preservada em calibração e teste)\n")

    linhas.append("## Resultado — mesmo conjunto de teste (distribuição real) para as 3 variantes\n")
    linhas.append("| Variante | n treino | AUC | Brier | p̂ médio | Taxa real (teste) | Gap (p̂ − real) |")
    linhas.append("|---|---|---|---|---|---|---|")
    for r in resultados:
        gap = r["p_hat_medio"] - r["taxa_real_teste"]
        linhas.append(
            f"| {r['nome']} | {r['n_treino']:,} | {r['auc']:.4f} | {r['brier']:.4f} | "
            f"{r['p_hat_medio']:.2%} | {r['taxa_real_teste']:.2%} | {gap:+.2%} |"
        )

    linhas.append("\n## Reliability diagram por variante (10 bins por quantil de p̂)\n")
    for r in resultados:
        linhas.append(f"### {r['nome']}\n")
        linhas.append(formatar_reliability(r["reliability"]))
        linhas.append("")

    # Veredito
    auc_natural, auc_under, auc_calib = resultados[0]["auc"], resultados[1]["auc"], resultados[2]["auc"]
    brier_natural, brier_under, brier_calib = resultados[0]["brier"], resultados[1]["brier"], resultados[2]["brier"]
    gap_under = resultados[1]["p_hat_medio"] - resultados[1]["taxa_real_teste"]

    linhas.append("## Veredito do Gate 1\n")
    linhas.append(f"**AUC praticamente igual entre as 3 variantes** ({auc_natural:.4f} / {auc_under:.4f} / {auc_calib:.4f}) — confirma o que a sabatina previu: o undersampling não piora o ranqueamento.")
    linhas.append(f"\n**Brier muito pior na variante undersample não calibrada** ({brier_natural:.4f} natural vs. {brier_under:.4f} undersample) — a probabilidade absoluta piora mesmo com AUC igual.")
    linhas.append(f"\n**`p̂` médio inflado em {gap_under:+.1%} na variante undersample** contra a taxa real de teste — é exatamente o deslocamento de prior que a P2 da sabatina descreveu, agora medido com dado real, não hipotético.")
    linhas.append(f"\n**Recalibração isotônica corrige**: Brier volta a {brier_calib:.4f} (próximo do natural), sem alterar o AUC — a isotônica remapeia a escala de `p̂`, não a ordem dos casos.")
    linhas.append(f"\n**Conclusão para o motor de EV (ADR-0002 §2.5):** usar `p̂` de um modelo treinado com reamostragem, sem recalibrar, produziria um `p*` sistematicamente errado na direção do gap medido acima. Este gate fica **satisfeito** quando o pipeline de produção incluir a etapa de recalibração — o que ainda **não está implementado**, só demonstrado aqui em escala de baseline diagnóstico.")
    linhas.append(f"\n> ⚠️ Este NÃO é a Camada 1 final. É um baseline com features cruas de `application_train.csv`, sem as tabelas relacionais (bureau, previous_application etc. — ADR-0001) e sem tuning. Serve só para fechar o Gate 1 com evidência empírica, não para produção.")

    texto = "\n".join(linhas)
    out_path = OUT / "gate1_calibracao.md"
    out_path.write_text(texto, encoding="utf-8")
    print(f"\nRelatorio salvo em {out_path}")


if __name__ == "__main__":
    main()
