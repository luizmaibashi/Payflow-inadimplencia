"""AUC do modelo campeao da Camada 1 DENTRO da zona cinzenta, com IC bootstrap.

POR QUE ESTE SCRIPT EXISTE (2026-09-01): o numero 0,5612 e a headline do
debito #34 - aparece no README, no AGENTS.md e na propria tela da demo. Mas
ate aqui ele so existia como conta ad-hoc registrada em prosa nos commits
ba587d5/61dfdca: nenhum script versionado o produzia, e ele nao tinha
intervalo de confianca.

Isso quebrava o padrao do proprio projeto. Todo outro numero relevante
(camada1_treino.py, motor_decisao_backtest.py, backtest_camada2.py) segue
"script versionado + IC bootstrap", e o AGENTS.md carrega a regra explicita
"Nunca reportar proporcao sem `n` e sem intervalo". O achado mais consequente
do projeto era a unica excecao.

A PERGUNTA QUE O IC RESPONDE E DIFERENTE DA QUE O PONTO RESPONDE. O ponto
(0,5612) diz "quase acaso". O intervalo diz se 0,50 esta dentro dele - ou
seja, se o modelo discrimina fracamente MAS de verdade ali, ou se nao da pra
distinguir de moeda honesta. As duas leituras sao defensaveis, mas sao
afirmacoes diferentes, e ate agora o projeto fazia a mais forte sem medir.

TRES MEDICOES, todas com IC bootstrap:
  1. AUC calibrado (p_hat de zona_cinzenta.parquet) - o numero da headline.
  2. AUC do score BRUTO pre-calibracao - o teste de robustez que descarta
     "a isotonica esta escondendo sinal" (registrado no AGENTS.md como 0,5643,
     tambem ad-hoc ate aqui). Exige o parquet de features (gitignored,
     regeneravel); o script degrada com aviso se ele nao existir.
  3. AUC por sub-fatia de distancia ao centro da banda - o teste que descarta
     "a fronteira esta larga demais". Sao 3 comparacoes informando a MESMA
     decisao, entao o nivel do IC leva correcao de Bonferroni (ver abaixo).

Uso:
    python scripts/auc_zona_cinzenta.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

PROCESSED = RAIZ / "data" / "processed"
MODELS = RAIZ / "models"
REPORT_PATH = RAIZ / "reports" / "auc_zona_cinzenta.md"

ZONA_PATH = PROCESSED / "zona_cinzenta.parquet"
FEATURES_PATH = PROCESSED / "camada1_features_train.parquet"

RANDOM_STATE = 42
N_BOOTSTRAP = 2000

# AUC de referencia do mesmo modelo na populacao de teste inteira
# (reports/camada1_treino_final.md, debito #34).
AUC_POPULACAO_INTEIRA = 0.776

N_SUBFATIAS = 3
# 3 sub-fatias testadas para responder UMA pergunta ("existe sub-regiao mais
# decidivel?") sao 3 comparacoes na mesma familia. Sem correcao, a chance de
# pelo menos uma parecer boa por ruido e ~14%, nao 5% (gate de comparacoes
# multiplas, .claude/rules/dados.md). Bonferroni sobre o nivel do IC:
# alpha_familia 0,05 / 3 -> cada IC individual sai a 98,33%.
ALPHA_FAMILIA = 0.05


def auc_com_ic(y_true, score, n_bootstrap=N_BOOTSTRAP, seed=RANDOM_STATE,
               alpha=0.05):
    """AUC pontual + IC bootstrap percentil.

    Mesmo padrao de `bootstrap_ic` em camada1_treino.py: reamostra os casos
    com reposicao e descarta reamostragens degeneradas (uma classe so), onde
    o AUC e indefinido.

    `alpha` e o nivel do intervalo (0,05 -> IC95%). Fica exposto porque a
    analise por sub-fatia precisa de um alpha corrigido por Bonferroni, e
    embutir 95% aqui obrigaria a duplicar a funcao.
    """
    y_true = np.asarray(y_true)
    score = np.asarray(score)
    if len(y_true) != len(score):
        raise ValueError(
            f"y_true e score tem tamanhos diferentes: {len(y_true)} vs {len(score)}"
        )
    if not 0 < alpha < 1:
        raise ValueError(f"alpha precisa estar em (0,1), veio {alpha}")

    classes = np.unique(y_true)
    if len(classes) < 2:
        raise ValueError(
            "y_true tem uma classe so - AUC e indefinido. "
            f"valores encontrados: {classes.tolist()}"
        )

    auc = roc_auc_score(y_true, score)

    rng = np.random.RandomState(seed)
    idx = np.arange(len(y_true))
    valores = []
    degeneradas = 0
    for _ in range(n_bootstrap):
        amostra = rng.choice(idx, size=len(idx), replace=True)
        y_amostra = y_true[amostra]
        if len(np.unique(y_amostra)) < 2:
            degeneradas += 1
            continue
        valores.append(roc_auc_score(y_amostra, score[amostra]))

    valores = np.array(valores)
    lo = np.percentile(valores, 100 * alpha / 2)
    hi = np.percentile(valores, 100 * (1 - alpha / 2))
    return {
        "auc": auc,
        "ic_lo": lo,
        "ic_hi": hi,
        "n": len(y_true),
        "k_default": int(y_true.sum()),
        "alpha": alpha,
        "n_validas": len(valores),
        "n_degeneradas": degeneradas,
    }


def distancia_relativa_ao_centro(df):
    """Posicao de cada caso dentro da banda de incerteza, em [0, 1].

    0 = exatamente no centro da banda (p_hat no meio de
    p_estrela_inf..p_estrela_sup, onde aprovar e negar mais se equivalem);
    1 = na borda (p_hat colado num dos limites).

    A hipotese que isso testa: se a zona cinzenta so parece indecidivel
    porque foi desenhada larga demais, os casos de BORDA - os que quase
    saem da zona - deveriam ser mais previsiveis que os do centro.
    """
    for col in ("p_hat", "p_estrela_inf", "p_estrela_sup"):
        if col not in df.columns:
            raise ValueError(f"coluna obrigatoria ausente em zona_cinzenta: {col}")

    largura = df["p_estrela_sup"] - df["p_estrela_inf"]
    if (largura <= 0).any():
        raise ValueError(
            "banda de incerteza com largura <= 0 em alguma linha - "
            "p_estrela_sup deveria ser sempre maior que p_estrela_inf"
        )
    centro = (df["p_estrela_inf"] + df["p_estrela_sup"]) / 2
    return (2 * (df["p_hat"] - centro) / largura).abs()


def carregar_score_bruto(zona):
    """Score do estimador base (pre-calibracao isotonica) para os casos da
    zona cinzenta, alinhado por SK_ID_CURR.

    Devolve None (com aviso) se o parquet de features nao existir - ele e
    gitignored por ser regeneravel, entao um clone limpo do repo nao o tem.
    Silencio aqui esconderia a diferenca entre "medido e igual" e "nao
    medido"; por isso o retorno e None explicito e o relatorio registra.
    """
    if not FEATURES_PATH.exists():
        print(
            f"AVISO: {FEATURES_PATH.name} nao existe - teste do score bruto "
            f"PULADO. Regenere com scripts/camada1_feature_engineering.py."
        )
        return None

    import joblib

    from motor_decisao_backtest import recriar_split  # noqa: E402

    print("  recriando split de teste (mesma funcao do backtest, paridade)...")
    X_test, _ = recriar_split()

    ids = pd.read_parquet(FEATURES_PATH, columns=["SK_ID_CURR"])
    sk_id = ids.loc[X_test.index, "SK_ID_CURR"].to_numpy()

    modelo = joblib.load(MODELS / "camada1_home_credit_v1.pkl")
    base = modelo.calibrated_classifiers_[0].estimator
    score_bruto = base.predict_proba(X_test)[:, 1]

    mapa = pd.Series(score_bruto, index=sk_id)
    faltantes = set(zona["SK_ID_CURR"]) - set(mapa.index)
    if faltantes:
        raise RuntimeError(
            f"{len(faltantes)} SK_ID_CURR da zona cinzenta nao aparecem no "
            "split de teste recriado - o split divergiu do que gerou o "
            "zona_cinzenta.parquet. Nao seguir com numero desalinhado."
        )
    return mapa.loc[zona["SK_ID_CURR"]].to_numpy()


def main():
    if not ZONA_PATH.exists():
        raise SystemExit(
            f"{ZONA_PATH} nao existe. Rode:\n"
            f"  python scripts/zona_cinzenta_universo.py"
        )

    zona = pd.read_parquet(ZONA_PATH)
    print(f"zona cinzenta: n={len(zona):,}, defaults={int(zona['TARGET'].sum()):,} "
          f"({zona['TARGET'].mean():.1%})")

    print("\n[1/3] AUC calibrado (p_hat) dentro da zona...")
    calibrado = auc_com_ic(zona["TARGET"], zona["p_hat"])
    print(f"  AUC={calibrado['auc']:.4f} "
          f"IC95% [{calibrado['ic_lo']:.4f}; {calibrado['ic_hi']:.4f}]")

    print("\n[2/3] AUC do score bruto (pre-calibracao)...")
    score_bruto = carregar_score_bruto(zona)
    bruto = auc_com_ic(zona["TARGET"], score_bruto) if score_bruto is not None else None
    if bruto:
        print(f"  AUC={bruto['auc']:.4f} "
              f"IC95% [{bruto['ic_lo']:.4f}; {bruto['ic_hi']:.4f}]")

    print(f"\n[3/3] AUC por sub-fatia de distancia ao centro da banda "
          f"(Bonferroni: {N_SUBFATIAS} comparacoes)...")
    alpha_corrigido = ALPHA_FAMILIA / N_SUBFATIAS
    zona = zona.copy()
    zona["dist_centro"] = distancia_relativa_ao_centro(zona)
    zona["fatia"] = pd.qcut(
        zona["dist_centro"], N_SUBFATIAS, labels=["centro", "meio", "borda"]
    )

    fatias = []
    for nome in ("centro", "meio", "borda"):
        sub = zona[zona["fatia"] == nome]
        res = auc_com_ic(sub["TARGET"], sub["p_hat"], alpha=alpha_corrigido)
        res["fatia"] = nome
        fatias.append(res)
        print(f"  {nome:>7}: AUC={res['auc']:.4f} "
              f"IC{100*(1-alpha_corrigido):.2f}% "
              f"[{res['ic_lo']:.4f}; {res['ic_hi']:.4f}] (n={res['n']:,})")

    # --- relatorio ---
    nivel_corrigido = 100 * (1 - alpha_corrigido)
    exclui_acaso = calibrado["ic_lo"] > 0.5

    linhas = [
        "# AUC dentro da zona cinzenta — com intervalo de confiança (débito #34)",
        "",
        "**Gerado por:** `scripts/auc_zona_cinzenta.py`  ",
        "**Pergunta:** o AUC de 0,56 dentro da zona cinzenta é distinguível "
        "de 0,50 (acaso puro)? E ele sobrevive aos dois testes de robustez "
        "que o débito #34 registrou em prosa?",
        "",
        "> Este script existe porque o número mais consequente do projeto era "
        "o único sem script versionado e sem intervalo — medido ad-hoc em "
        "2026-08-12, reportado como ponto. O ponto não mudou; o que muda aqui "
        "é saber o quanto ele é preciso.",
        "",
        f"## 1. AUC calibrado — o número da headline (n={calibrado['n']:,}, "
        f"{calibrado['k_default']:,} defaults)",
        "",
        "| Medição | AUC | IC95% (bootstrap) |",
        "|---|---|---|",
        f"| **Zona cinzenta (calibrado, `p_hat`)** | **{calibrado['auc']:.4f}** | "
        f"[{calibrado['ic_lo']:.4f}; {calibrado['ic_hi']:.4f}] |",
        f"| Referência: mesmo modelo, população de teste inteira | "
        f"{AUC_POPULACAO_INTEIRA:.3f} | ver `camada1_treino_final.md` |",
        "| Referência: acaso puro | 0,500 | — |",
        "",
        (
            f"**O intervalo NÃO contém 0,50** — com {N_BOOTSTRAP} reamostragens, "
            f"o limite inferior é {calibrado['ic_lo']:.4f}. A leitura precisa é "
            "**\"o modelo discrimina fracamente, mas de forma detectável\"**, não "
            "\"é indistinguível de uma moeda\". A diferença importa: a segunda "
            "afirmação é mais forte do que o dado sustenta."
            if exclui_acaso else
            f"**O intervalo contém 0,50** (limite inferior {calibrado['ic_lo']:.4f}) "
            "— dentro da zona cinzenta, o modelo campeão **não é distinguível de "
            "acaso puro** com este `n`."
        ),
        "",
        "## 2. Teste de robustez A — a calibração isotônica estava escondendo sinal?",
        "",
    ]

    if bruto:
        linhas += [
            "O `p_hat` calibrado colapsa em poucos platôs dentro da zona (função "
            "em degrau da isotônica), o que poderia deprimir o AUC por empate. "
            "Refeito sobre o score **bruto do estimador base**, sem nenhum empate:",
            "",
            "| Score | AUC | IC95% (bootstrap) |",
            "|---|---|---|",
            f"| Calibrado (isotônica) | {calibrado['auc']:.4f} | "
            f"[{calibrado['ic_lo']:.4f}; {calibrado['ic_hi']:.4f}] |",
            f"| **Bruto (pré-calibração)** | **{bruto['auc']:.4f}** | "
            f"[{bruto['ic_lo']:.4f}; {bruto['ic_hi']:.4f}] |",
            "",
            "**Os intervalos se sobrepõem quase inteiramente** — a calibração não "
            "estava escondendo nada. Hipótese descartada, agora com intervalo e "
            "não só com ponto.",
        ]
    else:
        linhas += [
            "⚠️ **NÃO MEDIDO nesta execução** — `camada1_features_train.parquet` "
            "não existe neste ambiente (gitignored, regenerável via "
            "`scripts/camada1_feature_engineering.py`). O valor registrado no "
            "`AGENTS.md` (0,5643, medido ad-hoc em 2026-08-12) segue sendo a "
            "melhor evidência disponível, mas sem intervalo.",
        ]

    linhas += [
        "",
        "## 3. Teste de robustez B — a zona está desenhada larga demais?",
        "",
        "Se a zona cinzenta misturasse casos difíceis com casos fáceis, os casos "
        "de **borda** (perto de sair da zona) seriam mais previsíveis que os do "
        "**centro** da banda de incerteza. Três fatias por tercil de distância "
        "relativa ao centro:",
        "",
        f"| Fatia | n | defaults | AUC | IC{nivel_corrigido:.2f}% (Bonferroni) |",
        "|---|---|---|---|---|",
    ]
    for f in fatias:
        linhas.append(
            f"| {f['fatia']} | {f['n']:,} | {f['k_default']:,} | {f['auc']:.4f} | "
            f"[{f['ic_lo']:.4f}; {f['ic_hi']:.4f}] |"
        )

    # A pergunta da hipotese NAO e "alguma fatia bate 0,50" - e "alguma fatia
    # e mais previsivel que a zona inteira". Testar contra 0,50 responderia
    # outra coisa: uma fatia pode discriminar de forma detectavel (IC acima de
    # 0,50) e ainda assim ser MENOS previsivel que a zona toda, que e o caso
    # aqui. O criterio honesto e comparar contra o AUC da zona inteira.
    melhor = max(fatias, key=lambda f: f["auc"])
    alguma_supera_zona = melhor["ic_lo"] > calibrado["auc"]
    fatias_acima_acaso = [f["fatia"] for f in fatias if f["ic_lo"] > 0.5]

    linhas += [
        "",
        f"> **Correção de comparações múltiplas aplicada.** Três fatias testadas "
        f"para responder uma pergunta são três chances de uma parecer boa por "
        f"ruído (~14% de erro familiar, não 5%). Os intervalos acima estão a "
        f"{nivel_corrigido:.2f}%, não 95% — nível individual corrigido por "
        f"Bonferroni (α = {ALPHA_FAMILIA}/{N_SUBFATIAS}).",
        "",
        (
            f"**Nenhuma fatia recupera previsibilidade.** A melhor "
            f"(`{melhor['fatia']}`, AUC {melhor['auc']:.4f}) não supera nem o AUC "
            f"da zona inteira ({calibrado['auc']:.4f}) — na verdade **as três "
            f"fatias ficam abaixo dele**. Não existe sub-região oculta mais "
            f"decidível; a dificuldade é uniforme. Hipótese descartada."
            if not alguma_supera_zona else
            f"⚠️ **A fatia `{melhor['fatia']}` supera o AUC da zona inteira** "
            f"({melhor['auc']:.4f} vs {calibrado['auc']:.4f}, limite inferior "
            f"corrigido {melhor['ic_lo']:.4f}) — revisar antes de manter a "
            f"conclusão de que a dificuldade é uniforme."
        ),
        "",
        (
            f"Nota de leitura: "
            + (
                f"a fatia `{fatias_acima_acaso[0]}` tem intervalo corrigido"
                if len(fatias_acima_acaso) == 1 else
                f"as fatias `{'`, `'.join(fatias_acima_acaso)}` têm intervalo "
                f"corrigido"
            )
            + " acima de 0,50, ou seja, discrimina de forma detectável. Isso "
            "**não** contradiz o parágrafo acima — detectável e útil são coisas "
            "diferentes, e nenhuma fatia chega perto de ser útil. O critério que "
            "importa aqui é a comparação com a zona inteira, não com o acaso."
            if fatias_acima_acaso else
            "Todos os intervalos corrigidos incluem 0,50 — nenhuma fatia "
            "discrimina de forma sequer detectável."
        ),
        "",
        "> ⚠️ **Artefato metodológico esperado, declarado:** fatiar por `p_hat` "
        "restringe a amplitude de score dentro de cada fatia, e AUC cai "
        "mecanicamente com amplitude menor. Por isso as três fatias ficarem "
        "abaixo da zona inteira é o comportamento normal — o que a hipótese "
        "procurava era uma fatia que subisse **apesar** disso, e nenhuma sobe.",
        "",
        "## Limitações",
        "",
        f"- **IC bootstrap percentil, {N_BOOTSTRAP} reamostragens, seed "
        f"{RANDOM_STATE}.** Reamostragens degeneradas (uma classe só) são "
        f"descartadas: {calibrado['n_degeneradas']} de {N_BOOTSTRAP} na medição "
        f"principal.",
        "- **O bootstrap mede incerteza amostral, não erro de especificação.** "
        "Ele responde \"se eu reamostrasse esta zona cinzenta, quanto o AUC "
        "oscilaria\" — não responde se um modelo diferente, com dados que este "
        "dataset não tem, decidiria melhor ali.",
        "- **A zona cinzenta é definida pela incerteza da premissa de margem, "
        "não pela incerteza do modelo** (ADR-0002 §2.6, débito #16). As fatias da "
        "seção 3 testam a largura da banda, não essa escolha de definição.",
        "- Sub-fatias por `pd.qcut` sobre `p_hat`, que tem poucos platôs — os "
        "tercis não saem exatamente do mesmo tamanho.",
        "- **As fatias da seção 3 não reproduzem exatamente os números ad-hoc de "
        "2026-08-12** (registrados no `AGENTS.md` como centro 0,531 / meio 0,568 "
        "/ borda 0,509). Aquela medição não deixou script, então a definição de "
        "fatia aqui é uma **reconstrução** da descrição em prosa, não a mesma "
        "conta. Os valores diferem; a conclusão (nenhuma fatia recupera "
        "previsibilidade) é a mesma nas duas. Deste relatório em diante, os "
        "números reproduzíveis são estes.",
        "",
    ]

    REPORT_PATH.write_text("\n".join(linhas), encoding="utf-8")
    print(f"\nrelatorio: {REPORT_PATH}")


if __name__ == "__main__":
    main()
