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
    raise NotImplementedError


def juntar_com_target(memos: pd.DataFrame) -> pd.DataFrame:
    """Merge de `memos` com zona_cinzenta.parquet pelo SK_ID_CURR.

    zona_cinzenta.parquet tem as colunas: SK_ID_CURR, TARGET, p_hat,
    decisao_motor, plato_p_hat (confirmado em sessao anterior via
    pd.read_parquet(...).columns).

    TODO: implementar o merge (inner - so interessam casos com os dois lados).
    Avisar se algum sk_id_curr do memo nao aparecer na zona cinzenta (nao
    deveria acontecer, mas silencio aqui esconderia bug de universo).
    """
    raise NotImplementedError


def taxa_default_por_recomendacao(df: pd.DataFrame) -> pd.DataFrame:
    """Para cada recomendacao (APROVAR/NEGAR/DEFERIR): k (defaults reais),
    n (casos), taxa, IC95% de Wilson.

    TODO: implementar. Reusar intervalo_wilson de calibrar_juiz.py
    (`from calibrar_juiz import intervalo_wilson` - mesmo diretorio scripts/).
    """
    raise NotImplementedError


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
    raise NotImplementedError


def comparar_com_motor(df: pd.DataFrame) -> pd.DataFrame:
    """Nos MESMOS casos, decisao_motor (Camada 1) concorda ou discorda da
    recomendacao do agente? Quando discordam, quem acerta mais o TARGET?

    Pergunta espelhada no debito #13 (o motor sozinho NAO supera o threshold
    legado, ADR-0002 SS2.8) - mesma pergunta, agora para o agente: ele
    concorda com o motor, ou agrega informacao que o motor nao tem?

    TODO: implementar. df ja tem decisao_motor (da zona_cinzenta.parquet) e
    recomendacao (do memo) lado a lado apos juntar_com_target(). Cruzar as
    duas, ver onde discordam, comparar taxa de default real nos dois
    subconjuntos (concordam vs discordam).
    """
    raise NotImplementedError


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
            f"⚠️  n={len(df)} e pequeno demais para separacao de 10pp "
            f"(precisa de ~722). Rode com mais casos antes de confiar no resultado."
        )

    taxas = taxa_default_por_recomendacao(df)
    print("\ntaxa de default real por recomendacao:")
    print(taxas)

    sep = bootstrap_separacao(df)
    print(f"\nseparacao NEGAR - APROVAR: {sep['delta_observado']:+.1%} "
          f"IC95% [{sep['ic_lo']:+.1%}; {sep['ic_hi']:+.1%}]")

    comp = comparar_com_motor(df)
    print("\nagente vs motor da Camada 1:")
    print(comp)

    # TODO: escrever reports/backtest_camada2.md seguindo o padrao dos outros
    # reports (limitacoes declaradas no topo, IC sempre ao lado da proporcao,
    # aviso de "leia o intervalo nao a proporcao" se n for pequeno).


if __name__ == "__main__":
    main()
