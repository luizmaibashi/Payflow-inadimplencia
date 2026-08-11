"""Backtest da Camada 2 contra default real — a medicao que o ADR-0004 SS2.1
chama de "a contribuicao do projeto":

    "Nao no agente, nao no juiz - no backtest de custo contra default real,
    que so e possivel por causa do ADR-0001."

Essa medicao ainda NAO EXISTE no codigo. O que existe (motor_decisao_backtest.py)
mede o MOTOR da Camada 1 contra o threshold legado - pergunta diferente.

PERGUNTA DESTE SCRIPT: as recomendacoes do AGENTE (APROVAR/NEGAR/DEFERIR)
separam risco real (TARGET) na zona cinzenta? E se sim, o quanto?

MEDICAO PRELIMINAR (2026-08-08, n=86, ad-hoc, NAO reproduzida por script):
  APROVAR: 15/49 = 30.6% default real
  NEGAR:   14/37 = 37.8% default real
  separacao = +7.2pp, IC95% aprox [-13.0%; +27.5%] - CRUZA ZERO, n pequeno demais

PRE-REQUISITO: rodar o piloto com n maior antes de este script fazer sentido.
Poder estatistico pra detectar separacao de 10pp exige ~722 casos (calculado
por teste de duas proporcoes, alpha=0.05, poder=0.80):

    python scripts/piloto_camada2.py --n 722 --seed 42 --modelo gemini-2.5-flash

Custo estimado: ~US$8 (medido: US$0.0109/caso no piloto de 86).
Isso SOBRESCREVE piloto_camada2_memos.jsonl - copiar o lote de 86 antes se
quiser preservar aquela rotulagem em paralelo.

Uso:
    python scripts/backtest_camada2.py
"""
import json
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from calibrar_juiz import intervalo_wilson  # noqa: E402

MEMOS_PATH = RAIZ / "data" / "processed" / "piloto_camada2_memos.jsonl"
ZONA_CINZENTA_PATH = RAIZ / "data" / "processed" / "zona_cinzenta.parquet"
REPORT_PATH = RAIZ / "reports" / "backtest_camada2.md"

N_BOOTSTRAP = 2000  # reamostragens - ADR-0004 SS2.5 pede IC bootstrap aqui,
                     # nao Wilson (Wilson e pra UMA proporcao; aqui a pergunta
                     # e sobre a DIFERENCA entre duas proporcoes correlacionadas
                     # pela mesma amostra)


def carregar_memos_com_desfecho() -> pd.DataFrame:
    """Le piloto_camada2_memos.jsonl e devolve so os casos com memo valido:
    sk_id_curr, recomendacao (APROVAR/NEGAR/DEFERIR).

    TODO: implementar. Ver _carregar_memos() em calibrar_juiz.py para o
    padrao de leitura do jsonl (mesmo arquivo, mesmo formato).
    """
    linhas = []
    with MEMOS_PATH.open(encoding="utf-8") as fh:
        for linha in fh:
            reg = json.loads(linha)
            if reg.get("memo"):
                linhas.append({
                    "sk_id_curr": reg["sk_id_curr"],
                    "recomendacao": reg["memo"]["recomendacao"],
                })
    return pd.DataFrame(linhas)


def juntar_com_target(memos: pd.DataFrame) -> pd.DataFrame:
    """Merge de `memos` com zona_cinzenta.parquet pelo SK_ID_CURR.

    zona_cinzenta.parquet tem as colunas: SK_ID_CURR, TARGET, p_hat,
    decisao_motor, plato_p_hat (confirmado em sessao anterior via
    pd.read_parquet(...).columns).

    TODO: implementar o merge (inner - so interessam casos com os dois lados).
    Avisar se algum sk_id_curr do memo nao aparecer na zona cinzenta (nao
    deveria acontecer, mas silencio aqui esconderia bug de universo).
    """
    zona = pd.read_parquet(ZONA_CINZENTA_PATH)
    df = memos.merge(
        zona, left_on="sk_id_curr", right_on="SK_ID_CURR", how="inner",
    )
    faltantes = set(memos["sk_id_curr"]) - set(df["sk_id_curr"])
    if faltantes:
        print(
            f"AVISO: {len(faltantes)} sk_id_curr do memo nao apareceram na "
            f"zona cinzenta (bug de universo?): {sorted(faltantes)[:10]}"
        )
    return df


def taxa_default_por_recomendacao(df: pd.DataFrame) -> pd.DataFrame:
    """Para cada recomendacao (APROVAR/NEGAR/DEFERIR): k (defaults reais),
    n (casos), taxa, IC95% de Wilson.

    TODO: implementar. Reusar intervalo_wilson de calibrar_juiz.py
    (`from calibrar_juiz import intervalo_wilson` - mesmo diretorio scripts/).
    """
    linhas = []
    for rec in ("APROVAR", "NEGAR", "DEFERIR"):
        sub = df[df["recomendacao"] == rec]
        n = len(sub)
        k = int(sub["TARGET"].sum())
        taxa = k / n if n else None
        ic_lo, ic_hi = intervalo_wilson(k, n) if n else (None, None)
        linhas.append({
            "recomendacao": rec, "k": k, "n": n,
            "taxa": taxa, "ic_lo": ic_lo, "ic_hi": ic_hi,
        })
    return pd.DataFrame(linhas)


def bootstrap_separacao(df: pd.DataFrame, grupo_a="NEGAR", grupo_b="APROVAR",
                         n_reamostragens: int = N_BOOTSTRAP, seed: int = 42) -> dict:
    """IC bootstrap para taxa_default(grupo_a) - taxa_default(grupo_b).

    TODO: implementar. Esqueleto do algoritmo:
      1. rng = numpy.random.default_rng(seed)
      2. Para cada uma das n_reamostragens:
         a. reamostra os casos do grupo_a COM REPOSICAO (mesmo tamanho n_a)
         b. reamostra os casos do grupo_b COM REPOSICAO (mesmo tamanho n_b)
         c. calcula taxa_a - taxa_b nessa reamostragem
         d. guarda o delta
      3. IC95% = percentis 2.5 e 97.5 da lista de deltas
      4. devolver {"delta_observado": ..., "ic_lo": ..., "ic_hi": ...}

    Por que bootstrap e nao formula fechada: a diferenca entre duas
    proporcoes tem formula fechada simples (a que foi usada na medicao
    preliminar do docstring do modulo), mas o ADR-0004 SS2.5 pede bootstrap
    para consistencia com o resto do projeto (motor_decisao_backtest.py ja
    usa bootstrap para o delta de EV) - mesma metodologia, resultados
    comparaveis entre motor e agente.
    """
    import numpy as np

    alvo_a = df.loc[df["recomendacao"] == grupo_a, "TARGET"].to_numpy()
    alvo_b = df.loc[df["recomendacao"] == grupo_b, "TARGET"].to_numpy()
    n_a, n_b = len(alvo_a), len(alvo_b)

    rng = np.random.default_rng(seed)
    deltas = np.empty(n_reamostragens)
    for i in range(n_reamostragens):
        reamostra_a = rng.choice(alvo_a, size=n_a, replace=True)
        reamostra_b = rng.choice(alvo_b, size=n_b, replace=True)
        deltas[i] = reamostra_a.mean() - reamostra_b.mean()

    delta_observado = alvo_a.mean() - alvo_b.mean()
    ic_lo, ic_hi = np.percentile(deltas, [2.5, 97.5])
    return {
        "delta_observado": delta_observado,
        "ic_lo": ic_lo,
        "ic_hi": ic_hi,
    }


def comparar_com_motor(df: pd.DataFrame) -> pd.DataFrame | None:
    """NAO FAZ SENTIDO com os dados atuais - documentado, nao implementado.

    A premissa do TODO original era comparar decisao_motor (APROVAR/NEGAR do
    motor) com a recomendacao do agente. Mas `zona_cinzenta.parquet` e, por
    definicao, o recorte onde o motor se ABSTEVE - toda linha tem
    decisao_motor == "ZONA_CINZENTA" (confirmado 2026-08-11, nenhuma
    variacao). Nao existe uma decisao real do motor pra comparar dentro
    deste universo - e exatamente por isso que a Camada 2 existe (decidir
    onde o motor nao decide).

    Uma comparacao alternativa (ex.: usar p_hat vs o ponto medio de
    p_estrela_inf/p_estrela_sup como proxy de "o que o motor faria sem
    abster-se") e uma decisao de design nova, nao a implementacao do que
    ja estava especificado - fica para decisao futura, nao bloqueia o
    backtest principal (taxa_default_por_recomendacao + bootstrap_separacao
    ja respondem a pergunta central do ADR-0004 SS2.1).
    """
    return None


def main() -> None:
    if not MEMOS_PATH.exists():
        raise SystemExit(
            f"{MEMOS_PATH} nao existe. Rode primeiro:\n"
            f"  python scripts/piloto_camada2.py --n 722 --seed 42 "
            f"--modelo gemini-2.5-flash\n"
            f"(~US$8, poder estatistico para separacao de 10pp)"
        )
    if not ZONA_CINZENTA_PATH.exists():
        raise SystemExit(
            f"{ZONA_CINZENTA_PATH} nao existe. Rode:\n"
            f"  python scripts/zona_cinzenta_universo.py"
        )

    memos = carregar_memos_com_desfecho()
    df = juntar_com_target(memos)

    print(f"casos com memo + TARGET: {len(df)}")
    if len(df) < 400:
        print(
            f"AVISO: n={len(df)} e pequeno demais para separacao de 10pp "
            f"(precisa de ~722). Rode com mais casos antes de confiar no resultado."
        )

    taxas = taxa_default_por_recomendacao(df)
    print("\ntaxa de default real por recomendacao:")
    print(taxas)

    sep = bootstrap_separacao(df)
    print(f"\nseparacao NEGAR - APROVAR: {sep['delta_observado']:+.1%} "
          f"IC95% [{sep['ic_lo']:+.1%}; {sep['ic_hi']:+.1%}]")

    comp = comparar_com_motor(df)
    if comp is None:
        print(
            "\ncomparacao com o motor: NAO DISPONIVEL - zona_cinzenta.parquet "
            "so tem decisao_motor='ZONA_CINZENTA' (motor se absteve em todos "
            "os casos deste universo, por definicao)."
        )

    def fmt_pct(v):
        return "n/d" if pd.isna(v) else f"{v:.1%}"

    linhas_taxas = [
        "| Recomendação | k (default) | n | Taxa | IC95% (Wilson) |",
        "|---|---|---|---|---|",
    ]
    for _, r in taxas.iterrows():
        ic = "n/d" if pd.isna(r["ic_lo"]) else f"[{r['ic_lo']:.1%}; {r['ic_hi']:.1%}]"
        linhas_taxas.append(
            f"| {r['recomendacao']} | {r['k']} | {r['n']} | "
            f"{fmt_pct(r['taxa'])} | {ic} |"
        )

    aviso_n = ""
    if len(df) < 400:
        aviso_n = (
            f"\n> ⚠️ **n={len(df)} é pequeno demais pra separação de 10pp** "
            f"(poder estatístico exige ~722). Leia o intervalo, não o ponto "
            f"— não sustenta decisão de política sozinho (ADR-0004 §2.5).\n"
        )

    linhas = [
        "# Backtest da Camada 2 — agente vs. default real (ADR-0004 §2.1)",
        "",
        "**Gerado por:** `scripts/backtest_camada2.py`  ",
        "**Pergunta:** as recomendações do agente (APROVAR/NEGAR/DEFERIR) "
        "separam risco real (`TARGET`) na zona cinzenta?",
        "",
        f"## O que foi medido (n={len(df)})",
        aviso_n,
        "### Taxa de default real por recomendação",
        "",
        *linhas_taxas,
        "",
        "### Separação NEGAR − APROVAR (IC bootstrap, ADR-0004 §2.5)",
        "",
        f"**{sep['delta_observado']:+.1%}**, IC95% "
        f"[{sep['ic_lo']:+.1%}; {sep['ic_hi']:+.1%}]",
        "",
        "## Limitações declaradas",
        "",
        "- **Comparação com o motor da Camada 1 não disponível.** "
        "`zona_cinzenta.parquet` é, por definição, o recorte onde o motor "
        "se absteve (`decisao_motor` constante). Não existe decisão real "
        "do motor pra comparar dentro deste universo.",
        "- **DEFERIR não separa risco por construção** — é encaminhamento "
        "a humano, não uma aposta de risco. A taxa de default sob `DEFERIR` "
        "não é comparável às outras duas colunas do mesmo jeito.",
        "- Revisor único e não especialista aplicou o critério de Task "
        "Completion (ADR-0011) aos memos — este backtest mede separação de "
        "`TARGET`, não a qualidade do julgamento humano.",
        "",
    ]
    REPORT_PATH.write_text("\n".join(linhas), encoding="utf-8")
    print(f"\nrelatorio: {REPORT_PATH}")


if __name__ == "__main__":
    main()
