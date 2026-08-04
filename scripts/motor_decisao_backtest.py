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
- margem = PREMISSA GLOBAL DECLARADA (mediana MEDIDA de Cash loans em
  previous_application, com a formula verdadeira do Gate 0). O prazo do
  contrato atual nao existe no momento da decisao, entao nao ha margem
  por observacao - problema estrutural, exposto como disclaimer em vez
  de medicao fingida. Substitui o proxy AMT_ANNUITY/AMT_CREDIT, que a
  auditoria de 2026-08-04 mostrou ter correlacao NEGATIVA com a margem
  real (ADR-0002 SS2.8).
- LGD por NAME_CONTRACT_TYPE (Cash/Revolving) - unica fonte de variacao
  de p* por observacao que restou.
- valor realizado no caso de pagamento usa a mesma margem como fracao
  de AMT_CREDIT - aproximacao, nao o lucro contabil real do contrato.
- valores em u.m. (unidades monetarias do dataset), nao em reais.
"""
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.motor_decisao import (
    MARGEM_MEDIANA_CASH,
    MARGEM_P25_CASH,
    MARGEM_P75_CASH,
    calcular_p_estrela,
    classificar_decisao_por_limites,
    lgd_por_tipo_contrato,
    limites_p_estrela_por_incerteza_margem,
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
    # NOTA (2026-08-04): tentamos usar margem_via_prazo_historico_cliente()
    # aqui - reconstruir a formula do Gate 0 com o prazo medio historico do
    # cliente. FALHOU e foi revertido: o prazo dos contratos ANTERIORES
    # (mediana 12 meses, emprestimos pequenos de varejo) e curto demais para
    # o credito ATUAL (que precisa de ~20 meses so para amortizar o
    # principal), gerando margem negativa em 77% dos casos - economicamente
    # absurdo. Sao populacoes de contrato diferentes; um nao estima o outro.
    # Ver ADR-0002 SS2.7 e AGENTS.md debito #12.
    # Margem: PREMISSA GLOBAL DECLARADA, medida com a formula verdadeira do
    # Gate 0 em previous_application (Cash loans, n=312.536). Substitui o
    # proxy AMT_ANNUITY/AMT_CREDIT, que a auditoria de 2026-08-04 mostrou ter
    # correlacao de Spearman NEGATIVA (-0,40) com a margem real.
    lgd = lgd_por_tipo_contrato(X_test["NAME_CONTRACT_TYPE"])
    margem = np.full(len(X_test), MARGEM_MEDIANA_CASH)
    p_estrela = calcular_p_estrela(margem, lgd)

    # Banda DERIVADA da incerteza da premissa (P25-P75 da margem), nao mais
    # +-3pp arbitrarios - implementa o ADR-0002 SS2.6.
    p_inf, p_sup = limites_p_estrela_por_incerteza_margem(lgd)

    decisao_motor = classificar_decisao_por_limites(p_hat, p_inf, p_sup)
    decisao_baseline = classificar_baseline(p_hat)

    amt_credit = X_test["AMT_CREDIT"].to_numpy()
    target = y_test.to_numpy()

    # CORRECAO METODOLOGICA (2026-08-04): a 1a versao comparava so os casos
    # que AMBAS as estrategias decidem automaticamente. Parecia pareamento
    # correto, mas as bandas sao ANINHADAS (a do motor cai dentro da do
    # baseline), entao o filtro removia EXATAMENTE os casos de discordancia -
    # o delta dava zero por construcao, nao por medicao. Comparacao correta
    # e sobre a carteira inteira, tratando a zona cinzenta explicitamente.
    def valor_carteira(decisao, grey_como):
        d = decisao.copy()
        d[(d == "ZONA_CINZENTA") | (d == "REVISAR")] = grey_como
        return valor_realizado(d, target, margem, lgd, amt_credit)

    # O desfecho dos casos deferidos a humano nao e observavel neste dataset,
    # entao reportamos dois cenarios-limite em vez de assumir um.
    valores, deltas = {}, {}
    for grey_como in ("NEGAR", "APROVAR"):
        vm = valor_carteira(decisao_motor, grey_como)
        vb = valor_carteira(decisao_baseline, grey_como)
        valores[grey_como] = (vm, vb)
        deltas[grey_como] = bootstrap_delta(vm, vb)

    # A fatia que de fato informa a comparacao: onde as estrategias discordam
    discordam = decisao_motor != decisao_baseline
    n_discordam = int(discordam.sum())
    taxa_default_discordancia = float(target[discordam].mean()) if n_discordam else float("nan")
    print(f"  casos em que as estrategias DISCORDAM: {n_discordam:,} de {len(X_test):,}")

    # Distribuicao de decisoes de cada estrategia (sobre o teste inteiro)
    dist_motor = pd.Series(decisao_motor).value_counts()
    dist_baseline = pd.Series(decisao_baseline).value_counts()

    linhas = []
    linhas.append("# Backtest do motor de decisão — EV × threshold legado\n")
    linhas.append(f"**Gerado por:** `scripts/motor_decisao_backtest.py`  ")
    linhas.append(f"**Modelo:** `models/camada1_home_credit_v1.pkl` (mesmo `p̂` nas duas estratégias — isola o efeito do motor, não do modelo)")
    linhas.append(f"**Teste:** n={len(X_test):,} (mesmo split de `camada1_treino.py`)\n")

    linhas.append("## Limitações declaradas (leia antes dos números)\n")
    linhas.append(
        f"- **Margem = premissa global declarada de {MARGEM_MEDIANA_CASH:.1%}** — mediana **medida** com a "
        f"fórmula verdadeira do Gate 0 (`(anuidade×prazo − crédito)/crédito`) sobre `Cash loans` aprovados em "
        f"`previous_application` (n=312.536), categoria que casa com ~90% de `application_train`. Aplicada como "
        f"constante porque o prazo do contrato atual **não existe** no momento da decisão (é definido junto com "
        f"a aprovação) — problema estrutural, exposto como disclaimer em vez de medição fingida (ADR-0006)."
    )
    linhas.append("- **LGD** por `NAME_CONTRACT_TYPE` (`Cash loans`→70%, `Revolving loans`→85%) — premissa declarada; é a única fonte de variação de `p*` **por observação** que restou.")
    linhas.append("- **Valor realizado ao pagar** usa a mesma margem como fração do crédito — aproximação do lucro, não o lucro contábil real (dependeria de custo de funding, indisponível).")
    linhas.append(
        f"- **Banda de indiferença derivada** da incerteza da premissa (margem P25={MARGEM_P25_CASH:.1%} a "
        f"P75={MARGEM_P75_CASH:.1%}), não mais ±3pp arbitrários — implementa o ADR-0002 §2.6: a zona cinzenta "
        f"é a região onde a decisão **inverte** conforme a premissa de margem adotada."
    )
    linhas.append("- **Valores em u.m. (unidades monetárias do dataset)**, não em reais — Home Credit é de mercados emergentes, moeda não identificada.\n")

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

    linhas.append(f"\n## Backtest sobre a carteira inteira (n={len(X_test):,})\n")
    linhas.append(
        "> **Correção metodológica (2026-08-04):** a 1ª versão comparava só os casos que **ambas** as "
        "estratégias decidem automaticamente. Parecia pareamento correto, mas as bandas são **aninhadas** "
        "(a do motor cai dentro da do baseline), então esse filtro removia **exatamente os casos em que as "
        "duas discordam** — o delta dava zero por construção, não por medição.\n"
    )
    linhas.append(
        "O desfecho dos casos deferidos a humano **não é observável** neste dataset, então o resultado vai "
        "em dois cenários-limite em vez de assumir um:\n"
    )
    linhas.append("| Zona cinzenta tratada como | Motor (u.m./caso) | Baseline (u.m./caso) | Delta | IC95% bootstrap |")
    linhas.append("|---|---|---|---|---|")
    for grey_como in ("NEGAR", "APROVAR"):
        vm, vb = valores[grey_como]
        d, lo, hi = deltas[grey_como]
        linhas.append(
            f"| {grey_como} | {np.nanmean(vm):,.0f} | {np.nanmean(vb):,.0f} | **{d:,.0f}** | [{lo:,.0f}; {hi:,.0f}] |"
        )

    linhas.append("\n### Onde as estratégias de fato discordam\n")
    linhas.append(
        f"- Casos com decisão diferente: **{n_discordam:,}** de {len(X_test):,} (**{n_discordam/len(X_test):.1%}**)"
    )
    linhas.append(
        f"- Taxa real de default nesses casos: **{taxa_default_discordancia:.1%}** "
        f"(contra {target.mean():.1%} na carteira toda)"
    )
    linhas.append(
        "\nÉ nesta fatia que a escolha de estratégia importa — e é exatamente ela que alimentaria a "
        "Camada 2 (agente): casos que o motor manda deferir e o baseline aprovaria direto."
    )

    _, lo_n, hi_n = deltas["NEGAR"]
    if lo_n > 0:
        veredito = "No cenário conservador (zona cinzenta negada), o motor supera o baseline com significância."
    elif hi_n < 0:
        veredito = (
            "No cenário conservador (zona cinzenta negada), o motor fica **abaixo** do baseline com "
            "significância. Faz sentido: deferir tem custo — cada caso deferido e negado abre mão da margem "
            "de um cliente que, na base, provavelmente pagaria. O ganho do deferral só aparece se o humano "
            "(ou o agente) decidir melhor que a regra automática — que é justamente o que a Camada 2 precisa provar."
        )
    else:
        veredito = "O intervalo cruza zero — a diferença não é estatisticamente significativa."
    linhas.append(f"\n**Veredito:** {veredito}")

    frac_acima_040 = (p_hat > RISCO_BAIXO_MAX).mean()
    linhas.append("\n## Por que as duas estratégias se parecem tanto agora\n")
    linhas.append(
        f"Com a margem **medida** ({MARGEM_MEDIANA_CASH:.1%} para Cash loans), o ponto de indiferença fica em "
        f"`p*` ≈ {calcular_p_estrela(MARGEM_MEDIANA_CASH, 0.70):.0%} — muito acima da taxa real de default "
        f"({target.mean():.1%}). Ou seja: **com a precificação real da Home Credit, vale emprestar para quase "
        f"todo mundo**, e o trabalho do modelo é achar a cauda pequena onde não vale. O threshold legado de "
        f"0,40 estava, por acaso, **próximo do ponto economicamente correto** — só {frac_acima_040:.1%} dos "
        f"casos o ultrapassam."
    )
    linhas.append(
        "\n**Isto revisa a conclusão da 1ª versão deste relatório.** Lá o motor aparecia ~21 mil u.m./caso à "
        "frente do baseline, mas aquele número vinha de um proxy de margem defeituoso — correlação de Spearman "
        "**negativa (−0,40)** com a margem real (ADR-0002 §2.8) — que tornava o motor artificialmente "
        "conservador. Corrigida a margem, a vantagem desaparece. **O que permanece válido** do achado anterior "
        "é que um threshold numérico fixo é frágil a mudanças de calibração do modelo: `p* = m/(m+ℓ)` se "
        "recalcula a partir de premissas de negócio, um número decorado não."
    )
    linhas.append("\n## Tentativa de corrigir o proxy de margem — testada e revertida (2026-08-04)\n")
    linhas.append(
        "Ao revisar o débito #12 (o proxy `AMT_ANNUITY/AMT_CREDIT` confunde prazo com margem), tentamos "
        "reconstruir a fórmula do Gate 0 usando `previous_cnt_payment_mean` — o **prazo médio real dos "
        "contratos anteriores do próprio cliente**, já agregado na Camada 1, com 94,5% de cobertura. "
        "Parecia a correção certa pelo princípio do ADR-0006 (substituir premissa por medição onde há dado)."
    )
    linhas.append(
        "\n**Falhou, e o motivo é instrutivo:** a fórmula passou a produzir **margem negativa em 77% dos casos** "
        "— economicamente absurdo (implicaria emprestar esperando receber menos que o principal). Diagnóstico: "
        "o crédito **atual** precisa de ~20 meses (mediana) só para amortizar o principal, mas o histórico do "
        "cliente tem prazo mediano de **12 meses**. São **populações de contrato diferentes** — os anteriores "
        "são empréstimos pequenos de varejo/consumo; o atual é substancialmente maior. Um não estima o outro."
    )
    linhas.append(
        "\n**Lição registrada:** \"existe dado disponível\" não é o mesmo que \"existe dado aplicável\". "
        "O prazo histórico é uma medição real, mas de um objeto diferente do que se quer medir — usá-lo teria "
        "trocado um viés conhecido e documentado por um erro maior e silencioso (a razão anuidade/crédito ao "
        "menos é sempre positiva e monotônica na intensidade de pagamento). O proxy original foi mantido, com "
        "seu viés declarado. A função `margem_via_prazo_historico_cliente()` segue em `app/motor_decisao.py` "
        "com testes, documentada como **não usada em produção** — serve de registro do experimento negativo."
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
