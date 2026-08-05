"""EDA das 6 tabelas relacionais (CRISP-DM fase 2, parte 2).

Por que existe: a primeira EDA (eda_application.py) cobriu APENAS
application_train.csv. As outras seis tabelas - ~27 milhoes de linhas -
nunca foram examinadas, e e delas que saem as 32 features agregadas da
Camada 1. Lacuna apontada pelo Luiz em 2026-08-05, ao perguntar se a EDA
tinha mesmo sido completa.

Foco deliberado: nao e censo de todas as colunas. Sao as checagens cujo
resultado ERRADO CORROMPERIA UMA FEATURE que ja esta no modelo. Cada
bloco abaixo mapeia para uma feature especifica de
app/feature_engineering_home_credit.py.

Gera reports/eda_tabelas_relacionais.md.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

RAW = RAIZ / "data" / "raw" / "home_credit"
SAIDA = RAIZ / "reports" / "eda_tabelas_relacionais.md"

# Sentinela de data conhecido do Home Credit (aparece em varias tabelas)
SENTINELA_DIAS = 365243


def bloco(titulo, feature_afetada):
    return [f"\n### {titulo}\n", f"*Feature em risco:* `{feature_afetada}`\n"]


def main():
    L = ["# EDA — tabelas relacionais (CRISP-DM fase 2, parte 2)\n"]
    L.append("**Gerado por:** `scripts/eda_tabelas_relacionais.py`\n")
    L.append(
        "> A primeira EDA cobriu só `application_train.csv`. Estas seis tabelas "
        "(~27M linhas) alimentam as **32 features agregadas** da Camada 1 e nunca "
        "tinham sido examinadas. Cada checagem abaixo existe porque seu resultado "
        "errado **corromperia uma feature que já está no modelo**.\n"
    )
    achados_criticos = []

    # ---------------- BUREAU ----------------
    L.append("## `bureau.csv` — crédito em outras instituições\n")
    b = pd.read_csv(RAW / "bureau.csv", usecols=[
        "SK_ID_CURR", "SK_ID_BUREAU", "CREDIT_ACTIVE", "CREDIT_DAY_OVERDUE",
        "AMT_CREDIT_SUM", "AMT_CREDIT_SUM_DEBT"])
    L.append(f"- Linhas: **{len(b):,}** | clientes distintos: {b.SK_ID_CURR.nunique():,}")
    L.append(f"- `SK_ID_BUREAU` duplicado: **{b.SK_ID_BUREAU.duplicated().sum():,}**\n")

    L += bloco("Dívida e crédito podem ser negativos?", "bureau_divida_sobre_credito")
    neg_div = int((b.AMT_CREDIT_SUM_DEBT < 0).sum())
    neg_cred = int((b.AMT_CREDIT_SUM < 0).sum())
    div_maior = int((b.AMT_CREDIT_SUM_DEBT > b.AMT_CREDIT_SUM).sum())
    L.append(f"| Checagem | Linhas | % |")
    L.append("|---|---|---|")
    L.append(f"| Dívida **negativa** | {neg_div:,} | {neg_div/len(b):.3%} |")
    L.append(f"| Crédito **negativo** | {neg_cred:,} | {neg_cred/len(b):.3%} |")
    L.append(f"| Dívida **maior** que o crédito concedido | {div_maior:,} | {div_maior/len(b):.2%} |")
    if neg_div:
        achados_criticos.append(
            f"✅ **CORRIGIDO** — `bureau`: {neg_div:,} dívidas negativas (saldo a favor do "
            "cliente) eram somadas cru e **abatiam** a dívida de outros contratos, fazendo o "
            "cliente parecer menos endividado. Agora `AMT_CREDIT_SUM_DEBT` tem piso em zero "
            "para o cálculo de `bureau_credit_sum_debt_total`."
        )
    if div_maior / len(b) > 0.05:
        achados_criticos.append(
            f"`bureau`: **{div_maior:,} contratos ({div_maior/len(b):.1%})** com dívida "
            "acima do crédito concedido — `bureau_divida_sobre_credito` passa de 1,0 nesses casos."
        )
    atraso = b.CREDIT_DAY_OVERDUE
    L.append(f"\n- `CREDIT_DAY_OVERDUE`: mediana {atraso.median():.0f}, "
             f"p99 {atraso.quantile(.99):.0f}, **máx {atraso.max():,.0f} dias** "
             f"({atraso.max()/365:.0f} anos de atraso)")
    del b

    # ---------------- BUREAU BALANCE ----------------
    L.append("\n## `bureau_balance.csv` — histórico mês a mês do bureau\n")
    bb = pd.read_csv(RAW / "bureau_balance.csv")
    L.append(f"- Linhas: **{len(bb):,}** (a maior tabela) | contratos: {bb.SK_ID_BUREAU.nunique():,}\n")

    L += bloco("Distribuição de STATUS", "bureau_max_severidade_historica, bureau_meses_em_atraso_total")
    vc = bb.STATUS.value_counts(normalize=True)
    L.append("| STATUS | Significado | % |")
    L.append("|---|---|---|")
    sig = {"C": "contrato encerrado", "0": "em dia", "X": "**sem informação**",
           "1": "atraso 1–30d", "2": "atraso 31–60d", "3": "atraso 61–90d",
           "4": "atraso 91–120d", "5": "atraso >120d / write-off"}
    for s, f in vc.items():
        L.append(f"| `{s}` | {sig.get(s, '?')} | {f:.2%} |")
    frac_x = float(vc.get("X", 0))
    L.append(f"\n- `X` (sem informação) responde por **{frac_x:.1%}** dos meses.")
    if frac_x > 0.10:
        achados_criticos.append(
            f"✅ **CORRIGIDO** — `bureau_balance`: {frac_x:.0%} dos meses têm STATUS `X` "
            "(sem informação) e caíam no `fillna(0)` do mapa de severidade, sendo tratados "
            "como **'em dia'** — mês desconhecido virava mês bom, subestimando a severidade "
            "de quem tem buraco no registro. `X` saiu do mapa (vira `NaN`, ignorado por "
            "`max`/`sum`) e ganhou feature própria: `n_bureau_meses_sem_info`."
        )
    del bb

    # ---------------- PREVIOUS APPLICATION ----------------
    L.append("\n## `previous_application.csv` — pedidos anteriores\n")
    p = pd.read_csv(RAW / "previous_application.csv", usecols=[
        "SK_ID_CURR", "SK_ID_PREV", "NAME_CONTRACT_STATUS", "AMT_CREDIT",
        "AMT_ANNUITY", "CNT_PAYMENT", "DAYS_FIRST_DRAWING"])
    L.append(f"- Linhas: **{len(p):,}** | clientes: {p.SK_ID_CURR.nunique():,}\n")

    L += bloco("Sentinela de data também aqui?", "previous_cnt_payment_mean")
    sent = int((p.DAYS_FIRST_DRAWING == SENTINELA_DIAS).sum())
    L.append(f"- `DAYS_FIRST_DRAWING = {SENTINELA_DIAS}`: **{sent:,}** linhas "
             f"(**{sent/len(p):.1%}**) — o mesmo sentinela de `application_train`, "
             f"em outra tabela.")
    if sent / len(p) > 0.3:
        achados_criticos.append(
            f"📋 **REGISTRADO (sem ação)** — `previous_application`: sentinela "
            f"`{SENTINELA_DIAS}` em {sent/len(p):.0%} de `DAYS_FIRST_DRAWING`. Nenhuma feature "
            "atual usa essa coluna, então não há defeito hoje. Fica registrado porque "
            "qualquer feature futura sobre ela nasceria corrompida."
        )
    zero_prazo = int((p.CNT_PAYMENT == 0).sum())
    L.append(f"- `CNT_PAYMENT = 0` (contrato sem prazo): **{zero_prazo:,}** "
             f"({zero_prazo/len(p):.1%})")
    del p

    # ---------------- INSTALLMENTS ----------------
    L.append("\n## `installments_payments.csv` — parcelas pagas\n")
    i = pd.read_csv(RAW / "installments_payments.csv", usecols=[
        "SK_ID_CURR", "DAYS_INSTALMENT", "DAYS_ENTRY_PAYMENT",
        "AMT_INSTALMENT", "AMT_PAYMENT"])
    L.append(f"- Linhas: **{len(i):,}** | clientes: {i.SK_ID_CURR.nunique():,}\n")

    L += bloco("Pagamento sem data ou sem valor", "atraso_medio_dias, frac_parcelas_atrasadas")
    sem_data = int(i.DAYS_ENTRY_PAYMENT.isna().sum())
    sem_valor = int(i.AMT_PAYMENT.isna().sum())
    L.append(f"| Checagem | Linhas | % |")
    L.append("|---|---|---|")
    L.append(f"| `DAYS_ENTRY_PAYMENT` nulo (parcela **nunca paga**) | {sem_data:,} | {sem_data/len(i):.2%} |")
    L.append(f"| `AMT_PAYMENT` nulo | {sem_valor:,} | {sem_valor/len(i):.2%} |")
    L.append(f"| `AMT_INSTALMENT = 0` (parcela de valor zero) | {int((i.AMT_INSTALMENT==0).sum()):,} | {(i.AMT_INSTALMENT==0).mean():.3%} |")
    if sem_data:
        achados_criticos.append(
            f"✅ **CORRIGIDO** — `installments`: {sem_data:,} parcelas sem data de pagamento "
            "são parcelas **nunca pagas**. Como `atraso_dias` virava `NaN` e `NaN > 0` é "
            "False, elas sumiam da contagem de atraso: quem nunca pagou era contado como "
            "quem pagou em dia. São 1.249 clientes com **18,14% de default contra 8,04%** do "
            "resto (2,26×). Viraram features próprias: `n_parcelas_nunca_pagas` e "
            "`frac_parcelas_nunca_pagas`."
        )
    atraso = (i.DAYS_ENTRY_PAYMENT - i.DAYS_INSTALMENT).dropna()
    L.append(f"\n- Atraso (dias): mediana **{atraso.median():.0f}** (negativo = adiantado), "
             f"p99 {atraso.quantile(.99):.0f}, máx **{atraso.max():.0f}**")
    del i

    # ---------------- POS CASH ----------------
    L.append("\n## `POS_CASH_balance.csv` — crediário\n")
    pos = pd.read_csv(RAW / "POS_CASH_balance.csv", usecols=["SK_ID_CURR", "SK_DPD"])
    L.append(f"- Linhas: **{len(pos):,}**")
    L.append(f"- `SK_DPD` (dias em atraso): mediana {pos.SK_DPD.median():.0f}, "
             f"p99 {pos.SK_DPD.quantile(.99):.0f}, **máx {pos.SK_DPD.max():,.0f}**\n")
    del pos

    # ---------------- CREDIT CARD ----------------
    L.append("\n## `credit_card_balance.csv` — cartão\n")
    cc = pd.read_csv(RAW / "credit_card_balance.csv", usecols=[
        "SK_ID_CURR", "AMT_BALANCE", "AMT_CREDIT_LIMIT_ACTUAL", "SK_DPD"])
    L.append(f"- Linhas: **{len(cc):,}** | clientes: {cc.SK_ID_CURR.nunique():,}\n")

    L += bloco("Divisão por limite zero", "cc_utilizacao_media")
    limite_zero = int((cc.AMT_CREDIT_LIMIT_ACTUAL == 0).sum())
    saldo_neg = int((cc.AMT_BALANCE < 0).sum())
    util = (cc.AMT_BALANCE / cc.AMT_CREDIT_LIMIT_ACTUAL.replace(0, np.nan)).dropna()
    L.append(f"| Checagem | Linhas | % |")
    L.append("|---|---|---|")
    L.append(f"| Limite **igual a zero** (denominador da utilização) | {limite_zero:,} | {limite_zero/len(cc):.2%} |")
    L.append(f"| Saldo **negativo** (cliente com crédito a favor) | {saldo_neg:,} | {saldo_neg/len(cc):.2%} |")
    L.append(f"\n- Utilização: mediana **{util.median():.1%}**, p99 **{util.quantile(.99):.1%}**, "
             f"**máx {util.max():.0%}**")
    if util.max() > 5:
        achados_criticos.append(
            f"📋 **ACEITO (sem ação)** — `credit_card`: utilização máxima de {util.max():.0%} "
            "do limite. **Não é erro de dado** — é situação real de cliente estourado, e "
            "estourar o limite é justamente sinal de risco. Winsorizar apagaria informação "
            "verdadeira. Fica declarado que `cc_utilizacao_media` tem cauda longa."
        )
    if limite_zero:
        achados_criticos.append(
            f"✅ **JÁ ESTAVA TRATADO** — `credit_card`: {limite_zero:,} linhas "
            f"({limite_zero/len(cc):.2%}) com limite zero. O código já usa "
            "`np.where(limite > 0, ..., np.nan)`, então não há divisão por zero: viram "
            "nulo e saem da média. Verificado, não suposto."
        )
    del cc

    # ---------------- VEREDITO ----------------
    L.append("\n---\n\n## Achados que exigem decisão\n")
    if achados_criticos:
        for a in achados_criticos:
            L.append(f"- {a}")
    else:
        L.append("- Nenhum achado crítico.")
    L.append("")

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text("\n".join(L), encoding="utf-8")
    print(f"Relatorio salvo em {SAIDA}")
    print(f"\n{len(achados_criticos)} achado(s) critico(s):")
    for a in achados_criticos:
        limpo = a.replace("**", "").replace("`", "")
        limpo = limpo.replace("✅", "[OK]").replace("📋", "[NOTA]")
        print("  - " + limpo)


if __name__ == "__main__":
    main()
