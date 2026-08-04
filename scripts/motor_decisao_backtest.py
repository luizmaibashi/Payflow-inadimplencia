"""Backtest do motor de decisao (ADR-0002 SS5): motor de EV x threshold
fixo antigo (0.40/0.65), sobre o MESMO conjunto de teste da Camada 1
final (mesmo p_hat calibrado nas duas estrategias - isola o efeito do
motor de decisao, sem misturar com o efeito de trocar de modelo).

Usa outcome REAL (TARGET) para calcular valor realizado, nao esperado -
e por isso um backtest, nao uma simulacao teorica.

Comparacao PAREADA (mesmos casos nas duas estrategias, ver
wiki/concepts/01_data_and_mlops/Estatistica_de_Avaliacao.md): o delta
de valor entre motor e baseline e calculado so sobre os casos que AMBAS
as estrategias decidem automaticamente (nao deferem) - isso cancela a
dificuldade dos casos sorteados e da mais poder estatistico ao IC
bootstrap, com o mesmo n para as duas pontas.

Limitacoes declaradas (heranca do app/motor_decisao.py):
- margem = AMT_ANNUITY/AMT_CREDIT (proxy, nao a margem total sobre a
  vida do contrato - CNT_PAYMENT nao existe para a aplicacao corrente)
- LGD por NAME_CONTRACT_TYPE (Cash/Revolving) - unico proxy disponivel
  neste dataset, diferente do proxy Consumer/Cash do Gate 0
- valor realizado no caso de pagamento usa a MESMA margem proxy como
  fracao de AMT_CREDIT - aproximacao, nao o lucro contabil real do
  contrato (que dependeria do prazo/custo de funding, indisponiveis)
"""
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.motor_decisao import (
    calcular_p_estrela,
    classificar_decisao,
    lgd_por_tipo_contrato,
    margem_proxy_anuidade,
)

PROCESSED = Path(__file__).resolve().parents[1] / "data" / "processed"
MODELS = Path(__file__).resolve().parents[1] / "models"
REPORTS = Path(__file__).resolve().parents[1] / "reports"

RANDOM_STATE = 42
N_BOOTSTRAP = 1000

# Thresholds legados (app/utils.py::get_decision_thresholds, defaults)
RISCO_BAIXO_MAX = 0.40
RISCO_MEDIO_MAX = 0.65


def recriar_split():
    """Reproduz EXATAMENTE o split de scripts/camada1_treino.py (mesmo
    random_state, mesmos parametros) para obter o mesmo X_test/y_test
    sobre o qual o AUC/Brier da Camada 1 final foram reportados."""
    df = pd.read_parquet(PROCESSED / "camada1_features_train.parquet")
    df["DAYS_EMPLOYED"] = df["DAYS_EMPLOYED"].replace(365243, np.nan)

    y = df["TARGET"]
    X = df.drop(columns=["TARGET", "SK_ID_CURR"])
    cat_cols = X.select_dtypes(include="object").columns.tolist()
    for c in cat_cols:
        X[c] = X[c].astype("category")

    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.4, stratify=y, random_state=RANDOM_STATE
    )
    _, X_test, _, y_test = train_test_split(
        X_temp, y_temp, test_size=0.5, stratify=y_temp, random_state=RANDOM_STATE
    )
    return X_test, y_test


def classificar_baseline(p_hat):
    decisao = np.full(p_hat.shape, "REVISAR", dtype=object)
    decisao[p_hat < RISCO_BAIXO_MAX] = "APROVAR"
    decisao[p_hat > RISCO_MEDIO_MAX] = "NEGAR"
    return decisao


def valor_realizado(decisao, target, margem, lgd, amt_credit):
    """Valor realizado por caso, dado o outcome REAL (target):
    - APROVAR + default (target=1): perda = -lgd * amt_credit
    - APROVAR + pagou (target=0): ganho = +margem * amt_credit
    - NEGAR: 0 (baseline declarado, ADR-0002 SS2.2)
    - REVISAR/ZONA_CINZENTA: NaN (fora do calculo - decidido por humano)
    """
    valor = np.full(len(decisao), np.nan)
    aprovado = decisao == "APROVAR"
    negado = decisao == "NEGAR"

    aprovado_default = aprovado & (target == 1)
    aprovado_pagou = aprovado & (target == 0)

    valor[aprovado_default] = -lgd[aprovado_default] * amt_credit[aprovado_default]
    valor[aprovado_pagou] = margem[aprovado_pagou] * amt_credit[aprovado_pagou]
    valor[negado] = 0.0
    return valor


def bootstrap_delta(valor_motor, valor_baseline, n=N_BOOTSTRAP, seed=RANDOM_STATE):
    """IC bootstrap do delta medio (motor - baseline) sobre os MESMOS
    casos (pareado) - reamostra indices em conjunto para os dois vetores."""
    rng = np.random.RandomState(seed)
    n_casos = len(valor_motor)
    deltas = []
    for _ in range(n):
        idx = rng.choice(n_casos, size=n_casos, replace=True)
        deltas.append(valor_motor[idx].mean() - valor_baseline[idx].mean())
    deltas = np.array(deltas)
    return deltas.mean(), np.percentile(deltas, 2.5), np.percentile(deltas, 97.5)


def main():
    print("Recriando split de teste da Camada 1 final...")
    X_test, y_test = recriar_split()
    y_test = y_test.reset_index(drop=True)
    X_test = X_test.reset_index(drop=True)
    print(f"  n_teste={len(X_test):,}")

    print("Carregando modelo calibrado...")
    modelo = joblib.load(MODELS / "camada1_home_credit_v1.pkl")
    p_hat = modelo.predict_proba(X_test)[:, 1]

    print("Aplicando motor de decisao (EV) e baseline (thresholds legados)...")
    margem = margem_proxy_anuidade(X_test["AMT_ANNUITY"], X_test["AMT_CREDIT"]).to_numpy()
    lgd = lgd_por_tipo_contrato(X_test["NAME_CONTRACT_TYPE"])
    p_estrela = calcular_p_estrela(margem, lgd)

    decisao_motor = classificar_decisao(p_hat, p_estrela)
    decisao_baseline = classificar_baseline(p_hat)

    amt_credit = X_test["AMT_CREDIT"].to_numpy()
    target = y_test.to_numpy()

    valor_motor = valor_realizado(decisao_motor, target, margem, lgd, amt_credit)
    valor_baseline = valor_realizado(decisao_baseline, target, margem, lgd, amt_credit)

    # Comparacao PAREADA: so os casos que AMBAS as estrategias decidem
    # automaticamente (nao caem em zona cinzenta/revisar em nenhuma delas)
    mask_pareado = ~np.isnan(valor_motor) & ~np.isnan(valor_baseline)
    n_pareado = mask_pareado.sum()
    print(f"  casos decididos por ambas as estrategias (pareado): {n_pareado:,} de {len(X_test):,}")

    delta_medio, ic_low, ic_high = bootstrap_delta(
        valor_motor[mask_pareado], valor_baseline[mask_pareado]
    )

    # Distribuicao de decisoes de cada estrategia (sobre o teste inteiro)
    dist_motor = pd.Series(decisao_motor).value_counts()
    dist_baseline = pd.Series(decisao_baseline).value_counts()

    linhas = []
    linhas.append("# Backtest do motor de decisão — EV × threshold legado\n")
    linhas.append(f"**Gerado por:** `scripts/motor_decisao_backtest.py`  ")
    linhas.append(f"**Modelo:** `models/camada1_home_credit_v1.pkl` (mesmo `p̂` nas duas estratégias — isola o efeito do motor, não do modelo)")
    linhas.append(f"**Teste:** n={len(X_test):,} (mesmo split de `camada1_treino.py`)\n")

    linhas.append("## Limitações declaradas (leia antes dos números)\n")
    linhas.append("- **Margem** = `AMT_ANNUITY/AMT_CREDIT` — proxy de intensidade de margem, **não** a margem total sobre a vida do contrato validada no Gate 0 (essa exige `CNT_PAYMENT`, indisponível para a aplicação corrente — o prazo é decidido junto com a aprovação, não é dado de entrada).")
    linhas.append("- **LGD** por `NAME_CONTRACT_TYPE` (`Cash loans`→70%, `Revolving loans`→85%) — único proxy disponível *neste* dataset; diferente do proxy `Consumer/Cash` usado no Gate 0 (que veio de `previous_application`, com categorias diferentes).")
    linhas.append("- **Valor realizado ao pagar** usa a mesma margem proxy como fração do crédito — aproximação do lucro, não o lucro contábil real (dependeria de prazo/custo de funding, indisponíveis).")
    linhas.append("- **Banda de indiferença fixa** (±3pp em torno de `p*`) — simplificação; não deriva da incerteza real da estimativa de PD (débito conhecido).\n")

    linhas.append("## Distribuição de decisões (teste completo, n={:,})\n".format(len(X_test)))
    linhas.append("| Estratégia | APROVAR | ZONA_CINZENTA / REVISAR | NEGAR |")
    linhas.append("|---|---|---|---|")
    linhas.append(
        f"| Motor (EV) | {dist_motor.get('APROVAR', 0):,} ({dist_motor.get('APROVAR', 0)/len(X_test):.1%}) | "
        f"{dist_motor.get('ZONA_CINZENTA', 0):,} ({dist_motor.get('ZONA_CINZENTA', 0)/len(X_test):.1%}) | "
        f"{dist_motor.get('NEGAR', 0):,} ({dist_motor.get('NEGAR', 0)/len(X_test):.1%}) |"
    )
    linhas.append(
        f"| Baseline (thresholds legados) | {dist_baseline.get('APROVAR', 0):,} ({dist_baseline.get('APROVAR', 0)/len(X_test):.1%}) | "
        f"{dist_baseline.get('REVISAR', 0):,} ({dist_baseline.get('REVISAR', 0)/len(X_test):.1%}) | "
        f"{dist_baseline.get('NEGAR', 0):,} ({dist_baseline.get('NEGAR', 0)/len(X_test):.1%}) |"
    )

    linhas.append(f"\n## Backtest pareado (n={n_pareado:,} — casos decididos automaticamente por AMBAS as estratégias)\n")
    valor_medio_motor = np.nanmean(valor_motor[mask_pareado])
    valor_medio_baseline = np.nanmean(valor_baseline[mask_pareado])
    linhas.append(f"- Valor médio realizado por caso — **Motor (EV):** R$ {valor_medio_motor:,.2f}")
    linhas.append(f"- Valor médio realizado por caso — **Baseline (thresholds legados):** R$ {valor_medio_baseline:,.2f}")
    linhas.append(f"\n**Delta médio (Motor − Baseline): R$ {delta_medio:,.2f} por caso, IC95% bootstrap [R$ {ic_low:,.2f}; R$ {ic_high:,.2f}] (n_bootstrap={N_BOOTSTRAP})**\n")

    if ic_low > 0:
        veredito = "O motor de EV supera o baseline com significância — o intervalo não cruza zero."
    elif ic_high < 0:
        veredito = "O baseline supera o motor de EV com significância — o intervalo não cruza zero."
    else:
        veredito = "O intervalo cruza zero — a diferença NÃO é estatisticamente significativa com este `n`. Não afirmar que uma estratégia é melhor que a outra a partir deste backtest."
    linhas.append(f"**Veredito:** {veredito}")

    frac_acima_040 = (p_hat > RISCO_BAIXO_MAX).mean()
    frac_acima_065 = (p_hat > RISCO_MEDIO_MAX).mean()
    linhas.append("\n## ⚠️ Por que o delta é tão grande — investigar antes de comemorar\n")
    linhas.append(
        f"Com `p̂` real calibrado (média {p_hat.mean():.1%}, batendo com a taxa real de default), "
        f"só **{frac_acima_040:.1%}** dos casos ultrapassam 0,40 e **{frac_acima_065:.2%}** ultrapassam 0,65 "
        f"— por isso o baseline aprova {dist_baseline.get('APROVAR', 0)/len(X_test):.0%} da carteira "
        f"quase sem negar ou revisar nada."
    )
    linhas.append(
        "\n**Isto não é 'o motor de EV venceu o threshold fixo' de forma limpa.** É evidência de que "
        "**os thresholds 0.40/0.65 foram calibrados contra a escala de `p̂` de um modelo diferente "
        "(provavelmente não calibrado/inflado — o mesmo mecanismo do Gate 1)**. Contra um `p̂` real e "
        "calibrado, um número fixo herdado de outra escala de probabilidade simplesmente para de fazer "
        "sentido — não é que o motor por EV seja necessariamente superior a qualquer corte único, é que "
        "**um corte numérico fixo é frágil a mudanças na calibração do modelo por trás dele**, e a fórmula "
        "`p* = m/(m+ℓ)` não é (ela se recalcula a partir de premissas de negócio, não de um número decorado)."
    )
    linhas.append(
        "\n**Comparação mais justa, não feita aqui:** um corte único **recalibrado** para esta mesma "
        "distribuição de `p̂` (ex: otimizado no conjunto de calibração, não no de teste, para evitar viés de "
        "otimismo) isolaria o efeito do **desenho do motor** (por observação vs. corte global) do efeito da "
        "**calibração desatualizada do baseline**. Sem esse terceiro braço, este backtest prova que "
        "'threshold fixo quebra quando o modelo muda de escala' — uma lição real e valiosa — mas não prova "
        "que 'decidir por observação bate um corte global bem calibrado'. Débito registrado no AGENTS.md."
    )

    texto = "\n".join(linhas)
    out_path = REPORTS / "motor_decisao_backtest.md"
    out_path.write_text(texto, encoding="utf-8")
    print(f"\nRelatorio salvo em {out_path}")


if __name__ == "__main__":
    main()
