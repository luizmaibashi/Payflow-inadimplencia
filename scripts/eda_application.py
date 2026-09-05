"""EDA sistematica de application_train.csv (CRISP-DM fase 2).

Por que este script existe tarde demais (2026-08-05): o projeto foi ate a
Camada 1 treinada, motor de decisao e primeira ferramenta da Camada 2 sem
nunca ter feito exame sistematico do dado. Os dois problemas conhecidos
ate aqui (sentinela de DAYS_EMPLOYED, colapso do AMT_GOODS_PRICE) foram
achados POR TROPECO, no meio de outra tarefa. Achar dois por acaso sugere
que existem outros que nao foram tropecados - foi o que motivou rodar
isto, a pedido do Luiz.

Nao substitui o dicionario (docs/DICIONARIO_DADOS.md): aquele documenta o
que cada coluna SIGNIFICA, este mede o que cada coluna ESTA.

Gera reports/eda_application.md.
"""
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

RAW = RAIZ / "data" / "raw" / "home_credit" / "application_train.csv"
SAIDA = RAIZ / "reports" / "eda_application.md"

LIMITE_CONSTANTE = 0.995   # acima disso a coluna nao distingue ninguem
LIMITE_REDUNDANCIA = 0.95  # correlacao acima disso = informacao repetida
CODIGOS_AUSENCIA = {"XNA", "XAP", "UNKNOWN", "NA", "N/A", "NONE", "", "NOT SPECIFIED"}


def colunas_constantes(df):
    achados = []
    for c in df.columns:
        if c in ("SK_ID_CURR", "TARGET"):
            continue
        vc = df[c].value_counts(dropna=False, normalize=True)
        if len(vc) and vc.iloc[0] > LIMITE_CONSTANTE:
            achados.append((c, vc.index[0], vc.iloc[0]))
    return achados


def codigos_ausencia_mascarados(df):
    """Categorias que sao 'sem informacao' disfarcada de valor valido."""
    achados = []
    for c in df.select_dtypes(include=["object"]).columns:
        vc = df[c].value_counts(dropna=False)
        for v in vc.index:
            if isinstance(v, str) and v.strip().upper() in CODIGOS_AUSENCIA:
                achados.append((c, v, vc[v], vc[v] / len(df)))
    return sorted(achados, key=lambda x: -x[3])


def outliers_monetarios(df, colunas):
    achados = []
    for c in colunas:
        s = df[c].dropna()
        if s.empty:
            continue
        p99 = s.quantile(0.99)
        achados.append((c, s.median(), p99, s.max(), s.max() / p99 if p99 else np.nan))
    return achados


def trios_redundantes(df):
    """As medidas de predio vem em _AVG/_MODE/_MEDI. Mede se sao a mesma coisa."""
    bases = sorted({
        c.rsplit("_", 1)[0] for c in df.columns if c.endswith(("_AVG", "_MODE", "_MEDI"))
    })
    achados = []
    for b in bases:
        trio = [f"{b}_AVG", f"{b}_MODE", f"{b}_MEDI"]
        if not all(t in df.columns for t in trio):
            continue
        sub = df[trio].dropna()
        if len(sub) < 1000:
            continue
        m = sub.corr().values
        achados.append((b, float(min(m[0, 1], m[0, 2], m[1, 2])), len(sub)))
    return sorted(achados, key=lambda x: -x[1])


def main():
    df = pd.read_csv(RAW)
    try:
        cols_modelo = set(joblib.load(
            RAIZ / "models" / "camada1_home_credit_v1_colunas.pkl")["colunas"])
    except FileNotFoundError:
        cols_modelo = set()

    L = ["# EDA — `application_train.csv` (CRISP-DM fase 2)\n"]
    L.append("**Gerado por:** `scripts/eda_application.py`  ")
    L.append(f"**Base:** {len(df):,} linhas × {df.shape[1]} colunas  ")
    L.append(f"**Taxa de default:** {df['TARGET'].mean():.2%}\n")
    L.append(
        "> **Por que este relatório é tardio:** o projeto chegou à Camada 1 treinada, "
        "motor de decisão e primeira ferramenta da Camada 2 **sem exame sistemático do "
        "dado**. Os dois problemas conhecidos até aqui foram achados por tropeço. "
        "Achar dois por acaso sugere que havia outros — e havia.\n"
    )

    # --- integridade basica ---
    L.append("## 1. Integridade\n")
    dup_id = df["SK_ID_CURR"].duplicated().sum()
    dup_lin = df.drop(columns=["SK_ID_CURR"]).duplicated().sum()
    L.append(f"- `SK_ID_CURR` duplicado: **{dup_id}**")
    L.append(f"- Linhas inteiramente duplicadas: **{dup_lin}**")
    L.append(f"- Colunas sem nenhum nulo: **{(df.isna().mean() == 0).sum()}** de {df.shape[1]}\n")

    # --- constantes ---
    const = colunas_constantes(df)
    no_modelo = [c for c, _, _ in const if c in cols_modelo]
    L.append("## 2. 🔴 Colunas que não distinguem ninguém\n")
    L.append(
        f"**{len(const)} colunas** têm um único valor em mais de {LIMITE_CONSTANTE:.1%} "
        f"das linhas — não separam cliente bom de ruim. "
        f"**{len(no_modelo)} delas estão dentro do modelo treinado.**\n"
    )
    L.append("| Coluna | Valor dominante | Frequência | No modelo? |")
    L.append("|---|---|---|---|")
    for c, v, f in sorted(const, key=lambda x: -x[2]):
        L.append(f"| `{c}` | `{v}` | {f:.2%} | {'sim' if c in cols_modelo else 'não'} |")
    L.append("")

    # --- codigos de ausencia ---
    L.append("## 3. Ausência disfarçada de categoria\n")
    L.append("Valores que parecem categoria válida mas significam *sem informação*.\n")
    L.append("| Coluna | Código | Linhas | % |")
    L.append("|---|---|---|---|")
    for c, v, n, frac in codigos_ausencia_mascarados(df):
        L.append(f"| `{c}` | `{v}` | {n:,} | {frac:.2%} |")
    L.append("")

    # --- o segmento dos 18% ---
    sent = df["DAYS_EMPLOYED"] == 365243
    xna = df["ORGANIZATION_TYPE"] == "XNA"
    L.append("## 4. O segmento de 18% — mesmo grupo, três codificações\n")
    L.append(
        f"- `DAYS_EMPLOYED = 365243` (≈1.000 anos): **{sent.sum():,}** linhas ({sent.mean():.2%})\n"
        f"- `ORGANIZATION_TYPE = XNA`: **{xna.sum():,}** linhas ({xna.mean():.2%})\n"
        f"- Divergência entre os dois conjuntos: **{(sent ^ xna).sum()}** linhas\n"
    )
    top_renda = df.loc[sent, "NAME_INCOME_TYPE"].value_counts().head(2)
    L.append(
        f"São **exatamente a mesma população**, e ela tem nome: "
        f"{top_renda.index[0].lower()}s ({top_renda.iloc[0]:,} de {sent.sum():,}).\n"
    )
    L.append(
        f"**E são melhores pagadores:** default de **{df.loc[sent, 'TARGET'].mean():.2%}** "
        f"contra **{df.loc[~sent, 'TARGET'].mean():.2%}** no resto da base.\n"
    )
    L.append(
        "> Ou seja: o valor 'ausente' não era ausência — era o marcador de um segmento "
        "de **menor** risco. A informação sobrevive via `NAME_INCOME_TYPE` e "
        "`ORGANIZATION_TYPE`, então convertê-lo para nulo no treino não perdeu sinal. "
        "Mas foi sorte, não desenho.\n"
    )

    # --- outliers ---
    money = ["AMT_INCOME_TOTAL", "AMT_CREDIT", "AMT_ANNUITY", "AMT_GOODS_PRICE"]
    L.append("## 5. 🔴 Outliers monetários\n")
    L.append("| Coluna | Mediana | p99 | Máximo | Máx/p99 |")
    L.append("|---|---|---|---|---|")
    for c, med, p99, mx, r in outliers_monetarios(df, money):
        alerta = " ⚠️" if r > 10 else ""
        L.append(f"| `{c}` | {med:,.0f} | {p99:,.0f} | {mx:,.0f} | **{r:.0f}×**{alerta} |")
    top = df.nlargest(3, "AMT_INCOME_TOTAL")[
        ["SK_ID_CURR", "AMT_INCOME_TOTAL", "AMT_CREDIT", "NAME_INCOME_TYPE", "TARGET"]]
    L.append("\n**As três maiores rendas declaradas:**\n")
    L.append("| SK_ID_CURR | Renda | Crédito | Tipo de renda | Deu calote? |")
    L.append("|---|---|---|---|---|")
    for _, r in top.iterrows():
        L.append(
            f"| {int(r.SK_ID_CURR)} | {r.AMT_INCOME_TOTAL:,.0f} | {r.AMT_CREDIT:,.0f} | "
            f"{r.NAME_INCOME_TYPE} | {'SIM' if r.TARGET == 1 else 'não'} |"
        )
    L.append(
        "\n> A maior renda declarada é **248× o percentil 99** e pertence a alguém "
        "classificado como *Working* que pediu um empréstimo de 562 mil — e deu calote. "
        "Renda de 117 milhões com empréstimo de 562 mil não é plausível: é erro de "
        "digitação, quase certamente zeros a mais. **Qualquer razão que use renda no "
        "denominador fica contaminada por esta linha.**\n"
    )

    # --- nulos ---
    nul = df.isna().mean().sort_values(ascending=False)
    L.append("## 6. Nulos\n")
    L.append(f"- Colunas com **mais de 50% nulo**: **{(nul > 0.5).sum()}**")
    L.append(f"- Colunas com algum nulo: {(nul > 0).sum()}")
    L.append(f"- Pior caso: `{nul.index[0]}` com {nul.iloc[0]:.1%}\n")

    # --- redundancia ---
    trios = trios_redundantes(df)
    redundantes = [t for t in trios if t[1] > LIMITE_REDUNDANCIA]
    L.append("## 7. Redundância `_AVG` / `_MODE` / `_MEDI`\n")
    L.append(
        f"Cada medida de prédio aparece em três versões. Medindo a correlação **mínima** "
        f"dentro de cada trio: **{len(redundantes)} de {len(trios)}** trios têm as três "
        f"versões correlacionadas acima de {LIMITE_REDUNDANCIA:.0%} — são a mesma "
        f"informação escrita três vezes (**~{len(redundantes) * 2} colunas redundantes**).\n"
    )
    L.append("| Grupo | Correlação mínima do trio |")
    L.append("|---|---|")
    for b, v, _ in trios[:8]:
        L.append(f"| `{b}_*` | {v:.3f} |")
    L.append("")

    # --- item 8 do checklist: relacao com o alvo ---
    L.append("## 8. Relação com o alvo — onde está o sinal\n")
    L.append(
        "Item que faltava na 1ª versão deste relatório. Sem ele a EDA descreve a base "
        "mas não diz **o que serve para prever**.\n"
    )
    blocos = {
        "Scores externos (bureau)": ["EXT_SOURCE_1", "EXT_SOURCE_2", "EXT_SOURCE_3"],
        "Pedido (valores do contrato)": ["AMT_CREDIT", "AMT_ANNUITY", "AMT_GOODS_PRICE",
                                         "AMT_INCOME_TOTAL"],
        "Perfil pessoal": ["DAYS_BIRTH", "CNT_CHILDREN", "CNT_FAM_MEMBERS"],
        "Trabalho e renda": ["DAYS_EMPLOYED", "DAYS_REGISTRATION", "DAYS_ID_PUBLISH"],
        "Consultas ao bureau": [c for c in df.columns if c.startswith("AMT_REQ_")],
        "Círculo social": [c for c in df.columns if "SOCIAL_CIRCLE" in c],
        "Características do prédio": [c for c in df.columns
                                      if c.endswith(("_AVG", "_MODE", "_MEDI"))],
        "Documentos entregues": [c for c in df.columns if c.startswith("FLAG_DOCUMENT_")],
    }
    L.append("| Bloco | Colunas | Maior correlação com `TARGET` | Coluna |")
    L.append("|---|---|---|---|")
    linhas_bloco = []
    for nome, cols in blocos.items():
        cols = [c for c in cols if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        if not cols:
            continue
        corrs = df[cols].corrwith(df["TARGET"]).abs().dropna()
        if corrs.empty:
            continue
        linhas_bloco.append((nome, len(cols), corrs.max(), corrs.idxmax()))
    for nome, n, v, qual in sorted(linhas_bloco, key=lambda x: -x[2]):
        L.append(f"| {nome} | {n} | **{v:.3f}** | `{qual}` |")

    if linhas_bloco:
        topo = max(linhas_bloco, key=lambda x: x[2])
        fundo = min(linhas_bloco, key=lambda x: x[2])
        L.append(
            f"\n> **O sinal é muito concentrado.** O bloco mais forte (*{topo[0]}*) tem "
            f"correlação de {topo[2]:.3f}; o mais fraco (*{fundo[0]}*, com {fundo[1]} colunas) "
            f"tem {fundo[2]:.3f}. Ou seja: **a maior parte das 122 colunas quase não "
            f"carrega sinal**, e o que carrega são scores calculados por terceiros — "
            f"limitação honesta do domínio, registrada também em `DICIONARIO_DADOS.md`.\n"
        )

    # --- comparacao treino x teste ---
    caminho_teste = RAW.parent / "application_test.csv"
    if caminho_teste.exists():
        L.append("## 9. `application_train` × `application_test` — mesma população?\n")
        dt = pd.read_csv(caminho_teste)
        L.append(f"- Treino: **{len(df):,}** linhas · Teste: **{len(dt):,}** linhas\n")
        comuns = [c for c in dt.columns if c in df.columns
                  and pd.api.types.is_numeric_dtype(df[c]) and c != "SK_ID_CURR"]
        difs = []
        for c in comuns:
            a, b_ = df[c].dropna(), dt[c].dropna()
            if len(a) < 100 or len(b_) < 100 or a.std() == 0:
                continue
            difs.append((c, abs(a.mean() - b_.mean()) / a.std(),
                         abs(df[c].isna().mean() - dt[c].isna().mean())))
        difs.sort(key=lambda x: -x[1])
        L.append("Diferença padronizada de média (|média_treino − média_teste| ÷ desvio do treino). "
                 "Acima de 0,10 costuma indicar deslocamento relevante.\n")
        L.append("| Coluna | Dif. padronizada | Dif. de % nulo |")
        L.append("|---|---|---|")
        for c, d, dn in difs[:8]:
            L.append(f"| `{c}` | {d:.3f} | {dn:.2%} |")
        acima = sum(1 for _, d, _ in difs if d > 0.10)
        L.append(
            f"\n> **{acima} de {len(difs)}** colunas passam de 0,10 de diferença padronizada — "
            f"as duas amostras **não** são intercambiáveis.\n"
        )
        L.append(
            "> **Por que isso não invalida nada do projeto:** `application_test.csv` é o "
            "conjunto de submissão do Kaggle e **não tem `TARGET`**. Todo número reportado "
            "aqui (AUC, Brier, backtest do motor) vem de um split interno de "
            "`application_train`, nunca deste arquivo. O `camada1_features_test.parquet` é "
            "gerado mas **não é usado** por nenhum script de avaliação.\n"
        )
        L.append(
            "> **Quando isso passaria a importar:** se alguém decidir usar esse arquivo para "
            "inferência ou para submeter ao Kaggle. Aí o deslocamento acima precisa ser "
            "tratado — em especial `FLAG_EMAIL` (0,458) e as consultas ao bureau.\n"
        )
        del dt

    # --- datasets presentes mas fora de uso ---
    L.append("## 10. Datasets auxiliares e históricos\n")
    L.append(
        "Registrado para não virar lacuna silenciosa no gate de CRISP-DM — arquivo "
        "que existe mas ninguém examina é exatamente o tipo de coisa que some do radar.\n"
    )
    L.append("| Arquivo | Situação |")
    L.append("|---|---|")
    L.append(
        "| `payflow_credit_risk.csv` | **Legado removido do estado atual.** Base "
        "sintética substituída pelo Home Credit no ADR-0001; narrativa preservada em "
        "`docs/LEGADO_V1.md` e artefato recuperável no histórico Git. |"
    )
    L.append(
        "| `sample_submission.csv` | Template de submissão do Kaggle, não é dado de análise. |"
    )
    L.append(
        "| `HomeCredit_columns_description.csv` | Dicionário oficial de colunas — "
        "traduzido em `docs/DICIONARIO_DADOS.md`. |\n"
    )

    # --- veredito ---
    L.append("## 11. O que fazer com isto\n")
    L.append("| Achado | Gravidade | Ação |")
    L.append("|---|---|---|")
    L.append(f"| {len(no_modelo)} colunas constantes dentro do modelo | Baixa (desperdício) | Remover do treino |")
    L.append("| Renda de 117 milhões | **Alta (corrompe razões)** | Decidir: teto, remoção ou manter declarado |")
    L.append(f"| ~{len(redundantes) * 2} colunas redundantes | Baixa | Manter uma versão por grupo |")
    L.append(f"| {(nul > 0.5).sum()} colunas com >50% nulo | Média | Avaliar remoção em bloco |")
    L.append("| Segmento de aposentados (18%) | Informativo | Documentar — é segmento real, menor risco |")
    L.append(
        "\n> **Nenhum destes explica a performance atual do modelo** (árvores ignoram "
        "constante e lidam com nulo). O ganho é de higiene, custo de treino e — "
        "principalmente — de **saber o que está na base antes de afirmar coisas sobre ela**.\n"
    )

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text("\n".join(L), encoding="utf-8")
    print(f"Relatorio salvo em {SAIDA}")
    print(f"  constantes no modelo: {len(no_modelo)} | trios redundantes: {len(redundantes)}")
    print(f"  colunas >50% nulo: {(nul > 0.5).sum()}")


if __name__ == "__main__":
    main()
