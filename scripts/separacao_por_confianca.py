"""Hipotese (b) do debito #34: a separacao de risco aparece nos casos em que
o agente estava CONFIANTE, e some nos que ele foi forcado a decidir?

CONTEXTO. O backtest principal (backtest_camada2.py) mede a separacao
NEGAR-APROVAR sobre os 564 casos de uma vez: +1,3pp, IC95% [-6,7%; +9,2%].
O AGENTS.md registrou, como hipotese NAO TESTADA, que essa media pode estar
diluida: desde o debito #28 o prompt PROIBE o agente de deferir por
informacao inobtenivel, entao ele decide ate onde a evidencia e ambigua.
Se a separacao existir so onde a evidencia e clara, a media global a
esconderia.

PROXY DE CONFIANCA. O memo nao tem campo de confianca - inventar um exigiria
gerar memo novo (API desvinculada, e mudaria o objeto ja rotulado). O proxy
usa o que ja esta la: cada item de `fatores_cliente` tem `peso`
("favoravel" | "desfavoravel"). Um memo onde todos os fatos apontam pro
mesmo lado e evidencia unanime; um memo meio a meio e decisao apertada.

    assimetria = |n_favoravel - n_desfavoravel| / n_fatos    em [0, 1]

LIMITE DO PROXY, declarado antes de olhar o resultado: isso mede a
UNANIMIDADE DA EVIDENCIA QUE O AGENTE ESCOLHEU CITAR, nao a confianca dele
nem a dificuldade real do caso. Um agente que so cita o que sustenta a
decisao ja tomada teria assimetria alta por vies de selecao, nao por caso
facil. O proxy nao distingue os dois. Se a separacao NAO aparecer nem no
grupo unanime, o resultado e informativo (nem no melhor cenario o sinal
aparece); se aparecer, e sugestivo mas confundido com esse vies.

COMPARACOES MULTIPLAS. Sao 3 grupos testados para responder UMA pergunta -
3 chances de um parecer bom por ruido. Nivel dos IC corrigido por Bonferroni
(.claude/rules/dados.md, gate de comparacoes multiplas).

Uso:
    python scripts/separacao_por_confianca.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

MEMOS_PATH = RAIZ / "data" / "processed" / "piloto_camada2_memos.jsonl"
ZONA_PATH = RAIZ / "data" / "processed" / "zona_cinzenta.parquet"
REPORT_PATH = RAIZ / "reports" / "separacao_por_confianca.md"

RANDOM_STATE = 42
N_BOOTSTRAP = 2000
N_GRUPOS = 3
ALPHA_FAMILIA = 0.05

# Contrato de app/memo_credito.py::Peso - TRES valores, nao dois.
# `neutro` existe e e usado (447 dos 2.885 fatos do lote, 15,5%).
PESOS_VALIDOS = {"favoravel", "desfavoravel", "neutro"}


def assimetria_evidencia(fatores):
    """|favoraveis - desfavoraveis| / n_fatos, em [0, 1].

    1,0 = todos os fatos apontam pro mesmo lado (evidencia unanime).
    0,0 = os lados se anulam (decisao apertada, ou tudo neutro).

    DECISAO SOBRE `neutro`: entra no DENOMINADOR, nao no numerador. Um fato
    neutro nao sustenta lado nenhum, entao um memo cheio deles nao e um memo
    confiante - e um memo que reuniu evidencia que nao decide. Excluir o
    neutro do denominador (|fav-desf|/(fav+desf)) daria assimetria 1,0 a um
    memo com 1 fato favoravel e 5 neutros, que e o oposto de unanimidade.

    Custo dessa escolha, declarado: a metrica passa a nao distinguir
    "evidencia conflitante" (3 fav, 3 desf) de "evidencia inconclusiva"
    (6 neutros) - as duas dao 0,0. Sao situacoes diferentes; para a pergunta
    aqui ("o agente tinha base clara?") as duas respondem nao, entao a fusao
    e aceitavel. Ver limitacao no relatorio.

    Levanta se um `peso` fora do contrato aparecer, em vez de ignora-lo:
    peso desconhecido contado como zero deslocaria a assimetria e o vies
    passaria batido. (Foi essa guarda que revelou o `neutro` - a primeira
    versao deste script assumia dois valores.)
    """
    if not fatores:
        raise ValueError("memo sem fatores_cliente - assimetria indefinida")

    pesos = [f["peso"] for f in fatores]
    desconhecidos = set(pesos) - PESOS_VALIDOS
    if desconhecidos:
        raise ValueError(
            f"peso fora do contrato do memo: {sorted(desconhecidos)}. "
            f"Esperado: {sorted(PESOS_VALIDOS)}"
        )

    n_fav = sum(1 for p in pesos if p == "favoravel")
    n_desf = sum(1 for p in pesos if p == "desfavoravel")
    return abs(n_fav - n_desf) / len(pesos), n_fav, n_desf


def carregar_memos_com_assimetria():
    """Le o jsonl e devolve os casos com memo valido, com a assimetria e a
    recomendacao de cada um."""
    linhas = []
    ignorados = 0
    with MEMOS_PATH.open(encoding="utf-8") as fh:
        for linha in fh:
            reg = json.loads(linha)
            memo = reg.get("memo")
            if not memo:
                ignorados += 1
                continue
            fatores = memo["fatores_cliente"]
            assim, n_fav, n_desf = assimetria_evidencia(fatores)
            linhas.append({
                "sk_id_curr": reg["sk_id_curr"],
                "recomendacao": memo["recomendacao"],
                "assimetria": assim,
                "n_favoravel": n_fav,
                "n_desfavoravel": n_desf,
                "n_neutro": len(fatores) - n_fav - n_desf,
                "n_fatos": len(fatores),
            })
    print(f"  memos validos: {len(linhas)} (ignorados sem memo: {ignorados})")
    return pd.DataFrame(linhas)


def separacao_com_ic(df, n_bootstrap=N_BOOTSTRAP, seed=RANDOM_STATE, alpha=0.05):
    """taxa_default(NEGAR) - taxa_default(APROVAR), com IC bootstrap.

    Mesma metodologia de bootstrap_separacao() em backtest_camada2.py -
    reamostra cada grupo com reposicao, mantendo os tamanhos. Devolve None
    nos campos de IC se algum grupo estiver vazio (grupo pequeno demais nao
    e erro, e informacao a reportar).
    """
    alvo_neg = df.loc[df["recomendacao"] == "NEGAR", "TARGET"].to_numpy()
    alvo_apr = df.loc[df["recomendacao"] == "APROVAR", "TARGET"].to_numpy()

    base = {
        "n_negar": len(alvo_neg),
        "n_aprovar": len(alvo_apr),
        "taxa_negar": alvo_neg.mean() if len(alvo_neg) else None,
        "taxa_aprovar": alvo_apr.mean() if len(alvo_apr) else None,
        "alpha": alpha,
    }
    if not len(alvo_neg) or not len(alvo_apr):
        return {**base, "delta": None, "ic_lo": None, "ic_hi": None}

    rng = np.random.default_rng(seed)
    deltas = np.empty(n_bootstrap)
    for i in range(n_bootstrap):
        a = rng.choice(alvo_neg, size=len(alvo_neg), replace=True)
        b = rng.choice(alvo_apr, size=len(alvo_apr), replace=True)
        deltas[i] = a.mean() - b.mean()

    lo, hi = np.percentile(deltas, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {
        **base,
        "delta": alvo_neg.mean() - alvo_apr.mean(),
        "ic_lo": lo,
        "ic_hi": hi,
    }


def main():
    for caminho in (MEMOS_PATH, ZONA_PATH):
        if not caminho.exists():
            raise SystemExit(f"{caminho} nao existe.")

    print("Carregando memos...")
    memos = carregar_memos_com_assimetria()

    zona = pd.read_parquet(ZONA_PATH)
    df = memos.merge(zona[["SK_ID_CURR", "TARGET"]], left_on="sk_id_curr",
                     right_on="SK_ID_CURR", how="inner")
    perdidos = len(memos) - len(df)
    if perdidos:
        print(f"AVISO: {perdidos} memos sem TARGET na zona cinzenta")
    print(f"  casos com memo + TARGET: {len(df)}")

    print(f"\nassimetria da evidencia: min={df['assimetria'].min():.2f} "
          f"mediana={df['assimetria'].median():.2f} max={df['assimetria'].max():.2f}")
    print(f"fatos por memo: mediana={df['n_fatos'].median():.0f}")

    print("\n[1/2] Separacao global (replica do backtest_camada2, controle)...")
    global_ = separacao_com_ic(df)
    print(f"  NEGAR-APROVAR: {global_['delta']:+.1%} "
          f"IC95% [{global_['ic_lo']:+.1%}; {global_['ic_hi']:+.1%}]")

    print(f"\n[2/2] Separacao por grupo de assimetria "
          f"(Bonferroni: {N_GRUPOS} comparacoes)...")
    alpha_corrigido = ALPHA_FAMILIA / N_GRUPOS

    # qcut com duplicates="drop": a assimetria tem poucos valores distintos
    # (razao de inteiros pequenos), entao os tercis podem colidir. Falhar aqui
    # seria pior que reportar menos grupos do que o pedido.
    df["grupo"], bins = pd.qcut(
        df["assimetria"], N_GRUPOS, labels=None, retbins=True, duplicates="drop"
    )
    grupos_reais = df["grupo"].cat.categories
    if len(grupos_reais) < N_GRUPOS:
        print(f"AVISO: assimetria tem poucos valores distintos - "
              f"{len(grupos_reais)} grupos em vez de {N_GRUPOS}")

    resultados = []
    for cat in grupos_reais:
        sub = df[df["grupo"] == cat]
        res = separacao_com_ic(sub, alpha=alpha_corrigido)
        res["faixa"] = f"{cat.left:.2f}–{cat.right:.2f}"
        res["n"] = len(sub)
        res["assimetria_media"] = sub["assimetria"].mean()
        resultados.append(res)
        ic = ("n/d" if res["delta"] is None
              else f"[{res['ic_lo']:+.1%}; {res['ic_hi']:+.1%}]")
        delta = "n/d" if res["delta"] is None else f"{res['delta']:+.1%}"
        print(f"  assimetria {res['faixa']}: n={res['n']:>3} "
              f"delta={delta:>7} IC{100*(1-alpha_corrigido):.2f}% {ic}")

    # --- relatorio ---
    nivel = 100 * (1 - alpha_corrigido)
    com_ic = [r for r in resultados if r["delta"] is not None]
    algum_separa = [r for r in com_ic if r["ic_lo"] > 0]
    mais_unanime = max(com_ic, key=lambda r: r["assimetria_media"])

    # A tendencia dos PONTOS e uma leitura separada da significancia dos IC.
    # Reportar so "nenhum IC exclui zero" esconderia um gradiente monotonico na
    # direcao da hipotese, que e informacao real mesmo sem poder estatistico -
    # e reportar so o gradiente sem o IC seria o erro oposto. Os dois entram.
    por_assimetria = sorted(com_ic, key=lambda r: r["assimetria_media"])
    deltas_ordenados = [r["delta"] for r in por_assimetria]
    monotonico_crescente = all(
        a < b for a, b in zip(deltas_ordenados, deltas_ordenados[1:])
    )
    largura_media = np.mean([r["ic_hi"] - r["ic_lo"] for r in com_ic])

    linhas = [
        "# Separação de risco por confiança aparente do agente (hipótese (b) do débito #34)",
        "",
        "**Gerado por:** `scripts/separacao_por_confianca.py`  ",
        "**Pergunta:** a separação NEGAR−APROVAR aparece nos casos em que a "
        "evidência citada pelo agente era unânime, e some nos casos apertados?",
        "",
        "> Hipótese registrada como **não testada** no débito #34 desde "
        "2026-08-12. Custo zero de API — usa os memos já gerados.",
        "",
        "## Por que a hipótese era plausível",
        "",
        "Desde o débito #28 o prompt proíbe `DEFERIR` por informação inobtenível — "
        "o agente decide mesmo quando a evidência é ambígua (`DEFERIR` saiu em "
        "1 de 564 casos). Se a separação de risco existisse só onde a evidência é "
        "clara, a média global a diluiria com os casos forçados.",
        "",
        "## Proxy usado, e o que ele não mede",
        "",
        "O memo não tem campo de confiança. O proxy usa `peso` "
        "(`favoravel`/`desfavoravel`) de cada item de `fatores_cliente`:",
        "",
        "```",
        "assimetria = |n_favoravel − n_desfavoravel| / n_fatos      ∈ [0, 1]",
        "```",
        "",
        "1,0 = todos os fatos apontam pro mesmo lado. 0,0 = empate perfeito.",
        "",
        "> **Limite declarado antes de olhar o resultado:** isso mede a unanimidade "
        "da evidência que o agente **escolheu citar** — não a confiança dele nem a "
        "dificuldade real do caso. Um agente que só cita o que sustenta a decisão "
        "já tomada teria assimetria alta por viés de seleção. O proxy não separa os "
        "dois casos.",
        "",
        f"## Resultado (n={len(df)})",
        "",
        "**Controle — separação global (replica o `backtest_camada2.md`):**",
        "",
        f"NEGAR−APROVAR = **{global_['delta']:+.1%}**, IC95% "
        f"[{global_['ic_lo']:+.1%}; {global_['ic_hi']:+.1%}] "
        f"(`NEGAR` n={global_['n_negar']}, `APROVAR` n={global_['n_aprovar']})",
        "",
        "**Por grupo de assimetria:**",
        "",
        f"| Assimetria | n | `NEGAR` (n / taxa) | `APROVAR` (n / taxa) | "
        f"Separação | IC{nivel:.2f}% (Bonferroni) |",
        "|---|---|---|---|---|---|",
    ]
    for r in resultados:
        if r["delta"] is None:
            linhas.append(
                f"| {r['faixa']} | {r['n']} | {r['n_negar']} | {r['n_aprovar']} | "
                f"n/d (grupo vazio de um lado) | n/d |"
            )
            continue
        linhas.append(
            f"| {r['faixa']} | {r['n']} | {r['n_negar']} / {r['taxa_negar']:.1%} | "
            f"{r['n_aprovar']} / {r['taxa_aprovar']:.1%} | "
            f"**{r['delta']:+.1%}** | [{r['ic_lo']:+.1%}; {r['ic_hi']:+.1%}] |"
        )

    linhas += [
        "",
        f"> **Correção de comparações múltiplas aplicada.** {len(com_ic)} grupos "
        f"testados para responder uma pergunta são {len(com_ic)} chances de um "
        f"parecer bom por ruído. Os intervalos estão a {nivel:.2f}%, não 95% "
        f"(Bonferroni, α = {ALPHA_FAMILIA}/{N_GRUPOS}).",
        "",
        "## Veredito",
        "",
        (
            f"**Hipótese (b) NÃO SUSTENTADA — mas não refutada com força.** "
            f"Nenhum grupo tem separação estatisticamente detectável: todos os "
            f"intervalos corrigidos contêm zero, inclusive o de evidência mais "
            f"unânime (assimetria média "
            f"{mais_unanime['assimetria_media']:.2f}, n={mais_unanime['n']}), "
            f"onde o proxy dá ao agente o cenário mais favorável possível — "
            f"separação {mais_unanime['delta']:+.1%}, IC "
            f"[{mais_unanime['ic_lo']:+.1%}; {mais_unanime['ic_hi']:+.1%}]."
            if not algum_separa else
            f"⚠️ **Hipótese (b) NÃO refutada.** {len(algum_separa)} grupo(s) com "
            f"separação acima de zero mesmo após correção: "
            f"{', '.join(r['faixa'] for r in algum_separa)}. Revisar antes de "
            f"manter a conclusão global do débito #34 — mas ler junto com o viés "
            f"de seleção declarado acima, que não foi controlado."
        ),
        "",
    ]

    if monotonico_crescente:
        linhas += [
            "**O que os pontos mostram, e por que não basta.** Os três pontos "
            "crescem de forma monotônica na direção que a hipótese previa "
            "(" + " → ".join(f"{d:+.1%}" for d in deltas_ordenados) + ", da "
            "evidência mais apertada para a mais unânime). Isso é consistente com "
            "a hipótese e não deve ser omitido. Mas os intervalos têm largura "
            f"média de {largura_media:.0%} e todos cruzam zero — três pontos "
            "ordenados por acaso acontecem em 1 de 6 vezes, e nenhum deles é "
            "individualmente distinguível de zero.",
            "",
            "**Conclusão precisa:** este teste descarta que exista um sinal "
            "**grande** escondido nos casos de evidência unânime — se houvesse "
            "separação de 20pp lá, apareceria. Ele **não** descarta um sinal "
            "pequeno: com n≈190 por grupo (contra os 722 que o próprio projeto "
            "calculou serem necessários para detectar 10pp), o estudo está cerca "
            "de 4× subdimensionado. A leitura honesta é \"não achamos\", não "
            "\"não existe\".",
            "",
            "> Isso **não reabre** o débito #34. A conclusão central dele não vem "
            "deste teste, e sim do AUC de 0,56 do próprio modelo campeão dentro "
            "da zona (`reports/auc_zona_cinzenta.md`) — que mede o teto do "
            "previsível ali, independente de qual agente decide. Um sinal pequeno "
            "sobrevivente nos casos unânimes seria compatível com esse teto, não "
            "uma contradição dele.",
            "",
        ]

    linhas += [
        "## Limitações",
        "",
        f"- **IC bootstrap percentil, {N_BOOTSTRAP} reamostragens, seed "
        f"{RANDOM_STATE}**, mesma metodologia do `backtest_camada2.py`.",
        "- **Grupos menores que a amostra global** — cada um tem cerca de um "
        "terço do `n`, então os intervalos são mais largos por construção. Um "
        "efeito pequeno mas real poderia não ser detectável aqui mesmo existindo. "
        "O que o resultado sustenta é \"não há sinal grande escondido nos casos "
        "unânimes\", não \"não há sinal nenhum\".",
        "- **O proxy não foi validado contra julgamento humano.** Ninguém "
        "verificou se assimetria alta de fato corresponde a caso subjetivamente "
        "fácil — seria trabalho de rotulagem, não de script.",
        "- **A ambiguidade real do caso não é observável aqui.** O agente pode "
        "citar evidência unânime sobre um caso que, pelos dados, é indecidível — "
        "e é exatamente o que o AUC de 0,56 dentro da zona sugere "
        "(`reports/auc_zona_cinzenta.md`).",
        "",
    ]

    REPORT_PATH.write_text("\n".join(linhas), encoding="utf-8")
    print(f"\nrelatorio: {REPORT_PATH}")


if __name__ == "__main__":
    main()
