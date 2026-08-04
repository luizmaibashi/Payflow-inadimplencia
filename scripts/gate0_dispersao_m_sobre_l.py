"""Gate 0 (ADR-0002 §2.3/§5): mede a dispersao de m/l na carteira Home Credit.

Pergunta que este script responde: o corte por observacao (p* por cliente)
se justifica, ou a razao margem/LGD e homogenea o bastante para o corte
por observacao reproduzir um corte global?

m_i  = margem total do contrato como fracao do principal
       (AMT_ANNUITY * CNT_PAYMENT - AMT_CREDIT) / AMT_CREDIT
l_i  = proxy de LGD por tipo de contrato (0.70 garantido / 0.85 nao garantido),
       ancorado na faixa declarada do ADR-0002 (70-85%), nao medido do zero.
p*_i = m_i / (m_i + l_i)

Fonte: data/raw/home_credit/previous_application.csv (contratos historicos
reais da Home Credit, com prazo e parcela reais - nao a solicitacao atual
em application_train.csv, que nao tem CNT_PAYMENT).
"""
import pandas as pd
import numpy as np
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "raw" / "home_credit"
OUT = Path(__file__).resolve().parents[1] / "reports"
OUT.mkdir(exist_ok=True)

LGD_GARANTIDO = 0.70   # piso da faixa declarada (ADR-0002): compra vinculada a bem (colateral)
LGD_NAO_GARANTIDO = 0.85  # teto da faixa declarada: cash loan sem colateral

def carregar():
    cols = [
        "SK_ID_PREV", "SK_ID_CURR", "NAME_CONTRACT_TYPE", "AMT_ANNUITY",
        "AMT_CREDIT", "AMT_GOODS_PRICE", "CNT_PAYMENT",
        "NAME_CONTRACT_STATUS", "NAME_YIELD_GROUP", "NAME_PORTFOLIO",
    ]
    df = pd.read_csv(DATA / "previous_application.csv", usecols=cols)
    return df


def filtrar_contratos_validos(df: pd.DataFrame) -> pd.DataFrame:
    """Contratos efetivamente originados, com prazo/parcela reais.

    Exclui: nao aprovados (sem contrato de fato), revolving (sem CNT_PAYMENT
    fixo - cartao de credito, nao se compara a emprestimo parcelado), e
    registros com dado degenerado (CNT_PAYMENT/AMT_CREDIT/AMT_ANNUITY <= 0).
    """
    f = df[
        (df["NAME_CONTRACT_STATUS"] == "Approved")
        & (df["NAME_CONTRACT_TYPE"] != "Revolving loans")
        & (df["CNT_PAYMENT"].fillna(0) > 0)
        & (df["AMT_CREDIT"].fillna(0) > 0)
        & (df["AMT_ANNUITY"].fillna(0) > 0)
    ].copy()
    return f


def calcular_p_estrela(df: pd.DataFrame) -> pd.DataFrame:
    df["m_i"] = (df["AMT_ANNUITY"] * df["CNT_PAYMENT"] - df["AMT_CREDIT"]) / df["AMT_CREDIT"]
    # Proxy de garantia: NAME_CONTRACT_TYPE, nao AMT_GOODS_PRICE.
    # Achado na 1a rodada: apos filtrar Approved + CNT_PAYMENT valido, o Home
    # Credit preenche AMT_GOODS_PRICE mesmo para Cash loans (0% nulo nos dois
    # tipos) - a coluna nao distingue mais secured/unsecured nessa amostra.
    # NAME_CONTRACT_TYPE e o proxy correto: Consumer loans = ponto de venda,
    # vinculado a um bem; Cash loans = uso livre, sem colateral.
    df["garantido"] = df["NAME_CONTRACT_TYPE"] == "Consumer loans"
    df["l_i"] = np.where(df["garantido"], LGD_GARANTIDO, LGD_NAO_GARANTIDO)
    df["p_estrela_i"] = df["m_i"] / (df["m_i"] + df["l_i"])
    return df


def relatorio(df: pd.DataFrame) -> str:
    n_bruto = len(df)
    # remove m_i implausivel: negativo (parcela nao cobre nem o principal -
    # erro de dado ou oferta cancelada a meio caminho) ou > 300% (outlier extremo)
    valido = df[(df["m_i"] > 0) & (df["m_i"] < 3.0)].copy()
    n_valido = len(valido)
    descartados = n_bruto - n_valido

    p = valido["p_estrela_i"]
    m = valido["m_i"]

    linhas = []
    linhas.append(f"# Gate 0 — Dispersão de m/ℓ na carteira Home Credit\n")
    linhas.append(f"**Gerado por:** `scripts/gate0_dispersao_m_sobre_l.py`  ")
    linhas.append(f"**Fonte:** `previous_application.csv`, contratos `Approved`, não-revolving\n")
    linhas.append(f"## Amostra\n")
    linhas.append(f"- Contratos aprovados não-revolving com prazo/parcela válidos: **{n_bruto:,}**")
    linhas.append(f"- Descartados por `m_i` implausível (≤0 ou >300%): **{descartados:,}** ({descartados/n_bruto:.1%})")
    linhas.append(f"- Amostra final: **{n_valido:,}**\n")

    linhas.append(f"## Distribuição de `m_i` (margem total do contrato / principal)\n")
    linhas.append("| Estatística | Valor |")
    linhas.append("|---|---|")
    for label, val in [
        ("Mínimo", m.min()), ("P5", m.quantile(0.05)), ("P25", m.quantile(0.25)),
        ("Mediana", m.median()), ("Média", m.mean()), ("P75", m.quantile(0.75)),
        ("P95", m.quantile(0.95)), ("Máximo", m.max()), ("Desvio padrão", m.std()),
    ]:
        linhas.append(f"| {label} | {val:.1%} |")

    linhas.append(f"\n## Distribuição de `p*_i` (limiar de indiferença por contrato)\n")
    linhas.append("| Estatística | Valor |")
    linhas.append("|---|---|")
    for label, val in [
        ("Mínimo", p.min()), ("P5", p.quantile(0.05)), ("P25", p.quantile(0.25)),
        ("Mediana", p.median()), ("Média", p.mean()), ("P75", p.quantile(0.75)),
        ("P95", p.quantile(0.95)), ("Máximo", p.max()), ("Desvio padrão", p.std()),
    ]:
        linhas.append(f"| {label} | {val:.1%} |")

    iqr = p.quantile(0.75) - p.quantile(0.25)
    p90_10 = p.quantile(0.95) - p.quantile(0.05)
    linhas.append(f"\n**Amplitude interquartil (P25-P75) de `p*`: {iqr:.1%}**")
    linhas.append(f"**Amplitude P5-P95 de `p*`: {p90_10:.1%}**\n")

    # Histograma em texto (10 bins)
    linhas.append("## Histograma de `p*_i` (texto, 10 faixas)\n")
    linhas.append("```")
    counts, edges = np.histogram(p.clip(0, 1), bins=10, range=(0, 1))
    maxc = counts.max()
    for i in range(len(counts)):
        bar = "#" * int(60 * counts[i] / maxc) if maxc else ""
        linhas.append(f"{edges[i]:.0%}-{edges[i+1]:.0%}: {counts[i]:>7,} {bar}")
    linhas.append("```\n")

    # Sanity check: m_i deveria crescer com NAME_YIELD_GROUP declarado pela Home Credit
    linhas.append("## Checagem cruzada: `m_i` medido × `NAME_YIELD_GROUP` declarado\n")
    yield_check = valido.groupby("NAME_YIELD_GROUP")["m_i"].agg(["count", "median", "mean"])
    yield_check = yield_check.sort_values("median")
    linhas.append("| NAME_YIELD_GROUP | n | m_i mediana | m_i média |")
    linhas.append("|---|---|---|---|")
    for idx, row in yield_check.iterrows():
        linhas.append(f"| {idx} | {int(row['count']):,} | {row['median']:.1%} | {row['mean']:.1%} |")

    # Segmentação por garantia (proxy de LGD)
    linhas.append("\n## Segmentação por garantia (proxy de ℓ: Consumer loans = garantido)\n")
    garantia_check = valido.groupby("garantido")["p_estrela_i"].agg(["count", "median", "mean"])
    linhas.append("| Garantido (NAME_CONTRACT_TYPE == Consumer loans) | n | p* mediana | p* média |")
    linhas.append("|---|---|---|---|")
    for idx, row in garantia_check.iterrows():
        linhas.append(f"| {idx} | {int(row['count']):,} | {row['median']:.1%} | {row['mean']:.1%} |")

    # Veredito do Gate
    limiar_estreito = 0.03  # 3 p.p., mesma ordem de grandeza da faixa isolada de LGD (ADR-0002 §2.4)
    veredito = "REPROVADO — dispersão estreita, corte por observação NÃO se justifica" if iqr < limiar_estreito else \
               "APROVADO — dispersão relevante, corte por observação pode agregar valor sobre corte global"
    linhas.append(f"\n## Veredito do Gate 0\n")
    linhas.append(f"**Critério:** IQR de `p*` menor que {limiar_estreito:.0%} (mesma ordem de grandeza do efeito isolado da LGD, ADR-0002 §2.4) indica que a dispersão não compensa a complexidade do motor por observação.\n")
    linhas.append(f"**Resultado: {veredito}**\n")
    linhas.append(f"IQR observado: **{iqr:.1%}**. Amplitude P5-P95: **{p90_10:.1%}**.\n")
    linhas.append("> ⚠️ Nota de honestidade: este Gate mede dispersão de `m/ℓ`, não a fração de clientes cujo `p̂` cai dentro da faixa de variação de `p*` — essa é a métrica final e mais afiada (ver `wiki/concepts/04_business/Valor_Esperado_Decisao_Credito.md`, Teste de Domínio P3), e só é calculável depois que a Camada 1 estiver treinada e calibrada.")

    return "\n".join(linhas)


def main():
    print("Carregando previous_application.csv...")
    df = carregar()
    print(f"  {len(df):,} linhas brutas")
    df = filtrar_contratos_validos(df)
    print(f"  {len(df):,} apos filtro de contratos validos")
    df = calcular_p_estrela(df)
    texto = relatorio(df)
    out_path = OUT / "gate0_dispersao_m_sobre_l.md"
    out_path.write_text(texto, encoding="utf-8")
    print(f"\nRelatorio salvo em {out_path}")


if __name__ == "__main__":
    main()
