"""Piloto da Camada 2 contra o gerador REAL (Gemini) - mede o debito #20.

OBJETIVO: a Camada 2 foi construida e testada com dubles deterministicos e
rodada UMA vez, a mao, contra um caso. Este script e a primeira execucao em
lote contra provider real. Ele nao avalia qualidade de parecer (isso e o passo
seguinte, com rotulagem humana) - ele mede se o encanamento aguenta:

  ok             memo valido produzido
  groundedness   memo citou ferramenta nao chamada (gate do ADR-0004 barrou)
  teto           MAX_CHAMADAS_POR_CASO sem concluir (loop de exploracao)
  memo_invalido  provider devolveu JSON fora do contrato (RespostaLLMInvalida)
  erro_provider  rede, rate limit, auth - qualquer falha do lado de fora

As duas ultimas SAO o debito #20 do AGENTS.md ("adaptador sem retry/timeout/
controle de custo - decisao consciente de medir antes"). Por isso este script
NAO TEM RETRY, de proposito: retry aqui esconderia justamente a taxa que
justifica (ou nao) construir a politica de retry.

CENARIO 1x POR LOTE (ADR-0008): consultar_cenario() e chamado uma vez, antes
do loop, e o mesmo CenarioMacro vai para todos os casos. Chamar por cliente
seria violacao de trajectory efficiency, nao mera ineficiencia.

AMOSTRA: sorteio SIMPLES dentro da zona cinzenta, nao estratificado. As taxas
acima sao globais - estratificar nao muda a estimativa delas e gastaria
desenho de amostragem num piloto que existe para descobrir se o gerador se
sustenta. A amostra estratificada e do passo seguinte (rotulagem).
Reusa preparar_lote(), que embaralha: ordem por risco vazaria o score pela
posicao na fila (ADR-0003 SS2.1).

CUSTO: cada caso gasta ate MAX_CHAMADAS_POR_CASO chamadas de API. Com n=25 e
teto 6, o pior caso sao 150 chamadas. Rode com --n pequeno na primeira vez.

Uso:
    python scripts/piloto_camada2.py --n 25
    python scripts/piloto_camada2.py --n 5 --modelo gemini-2.5-flash
"""
import argparse
import json
import math
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app.agente_underwriting import AgenteUnderwriting, preparar_lote  # noqa: E402
from app.clientes_llm import (  # noqa: E402
    ClienteGemini,
    FalhaProvider,
    RespostaLLMInvalida,
)
from app.ferramenta_cenario import FerramentaCenario  # noqa: E402
from app.ferramentas_caso import FerramentasCaso  # noqa: E402

# PREMISSA DECLARADA, nao medicao: precos em USD por 1 MILHAO de tokens,
# consultados em ai.google.dev/gemini-api/docs/pricing em 2026-08-06.
# Preco de modelo muda; se esta constante envelhecer, o custo reportado mente
# com cara de medicao. A CONTAGEM de tokens ao lado dela e medida (vem do
# provider) - so a conversao para dinheiro e premissa.
#
# O Pro tem faixa mais cara acima de 200k tokens de prompt. O pico deste
# desenho e ~750 tokens (o contexto acumula por ate 6 saltos), entao vale a
# faixa barata. Se MAX_CHAMADAS_POR_CASO crescer muito, revisar.
PRECOS_USD_POR_MILHAO = {
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
}

# Escopo do projeto inteiro para a projecao (ADR-0004 SS2.5: eval set de
# 150-200 casos) mais uma 2a rodada apos correcao de prompt, mais folga.
CASOS_PROJETO_INTEIRO = 450

UNIVERSO = RAIZ / "data" / "processed" / "zona_cinzenta.parquet"
SAIDA_JSONL = RAIZ / "data" / "processed" / "piloto_camada2_memos.jsonl"
SAIDA_REPORT = RAIZ / "reports" / "piloto_camada2.md"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """IC de Wilson para uma proporcao.

    Wilson e nao o normal porque com n pequeno e proporcao perto de 0 ou 1 o
    intervalo normal vaza para fora de [0,1] - regra do ADR-0004 SS2.5 e do
    AGENTS.md ("nunca reportar proporcao sem n e sem intervalo").
    """
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z**2 / n
    centro = (p + z**2 / (2 * n)) / d
    meia = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / d
    return (max(0.0, centro - meia), min(1.0, centro + meia))


def custo_usd(tokens: dict, modelo: str) -> float | None:
    """Converte tokens medidos em dolares. None se o modelo nao esta na tabela
    - preferivel a devolver 0,00 e passar por 'de graca'."""
    preco = PRECOS_USD_POR_MILHAO.get(modelo)
    if preco is None:
        return None
    # thinking e cobrado como OUTPUT (tabela do Google, 2026-08-06). Somar aqui
    # e o que impede o custo de sair subestimado nos modelos 2.5.
    saida = tokens["output"] + tokens["thinking"]
    return (tokens["input"] * preco["input"] + saida * preco["output"]) / 1_000_000


def classificar_resultado(resultado) -> str:
    """Traduz o ResultadoAnalise nos desfechos que este piloto conta."""
    if resultado.memo is not None:
        return "ok"
    if resultado.atingiu_teto:
        return "teto"
    if resultado.erro and "ferramenta nao chamada" in resultado.erro:
        return "groundedness"
    return "erro_orquestracao"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=25, help="casos a rodar (default 25)")
    ap.add_argument("--seed", type=int, default=42, help="seed do embaralhamento")
    ap.add_argument("--modelo", default="gemini-2.5-pro", help="modelo do gerador")
    ap.add_argument(
        "--sem-retry", action="store_true",
        help="1 tentativa por chamada - mede a taxa de falha BRUTA do provider, "
             "sem o backoff mascarando",
    )
    args = ap.parse_args()

    if not UNIVERSO.exists():
        raise SystemExit(
            f"{UNIVERSO} nao existe. Rode antes:\n"
            f"  python scripts/zona_cinzenta_universo.py"
        )

    universo = pd.read_parquet(UNIVERSO)
    fila = preparar_lote(universo["SK_ID_CURR"].tolist(), seed=args.seed)[: args.n]
    print(f"Zona cinzenta: {len(universo):,} casos | piloto: {len(fila)}")

    # Cenario UMA vez para o lote inteiro (ADR-0008).
    cenario = FerramentaCenario().consultar_cenario()
    print(f"Cenario: LGD={cenario.lgd:.0%} | fallback={cenario.usou_fallback} | {cenario.fonte}")

    ferramentas = FerramentasCaso()
    print(f"Instanciando gerador ({args.modelo})...")
    cliente = ClienteGemini(
        modelo=args.modelo, **({"max_tentativas": 1} if args.sem_retry else {})
    )
    agente = AgenteUnderwriting(
        ferramentas=ferramentas, cenario=cenario, cliente_llm=cliente
    )

    registros, desfechos = [], Counter()
    politica = "sem retry - taxa de falha BRUTA" if args.sem_retry else "com retry (backoff)"
    print(f"\nRodando ({politica}):")

    for i, sk_id in enumerate(fila, 1):
        t0 = time.perf_counter()
        tokens_antes = dict(cliente.tokens)
        reg = {"sk_id_curr": int(sk_id)}
        try:
            r = agente.analisar(int(sk_id))
            desfecho = classificar_resultado(r)
            reg.update(
                n_chamadas=len(r.trace),
                ferramentas=[c.ferramenta for c in r.trace],
                erro=r.erro,
                violacoes_trajetoria=r.violacoes_trajetoria,
                memo=r.memo.model_dump(mode="json") if r.memo else None,
            )
            # Memo valido COM violacao de trajetoria conta separado: passou no
            # gate eliminatorio (groundedness) e mesmo assim tem defeito. E a
            # distincao que o piloto de 2026-08-06 nao sabia fazer.
            if desfecho == "ok" and r.violacoes_trajetoria:
                desfecho = "ok_com_violacao"
        except RespostaLLMInvalida as e:
            desfecho = "memo_invalido"
            reg.update(erro=str(e)[:1000])
        except FalhaProvider as e:
            # Sobreviveu ao retry: e falha real do provider, nao oscilacao.
            desfecho = "erro_provider"
            reg.update(erro=str(e)[:1000], tentativas_na_falha=e.tentativas)
        except Exception as e:  # noqa: BLE001 - rede/rate limit/auth entram aqui
            # Amplo DE PROPOSITO: o objetivo e medir a taxa de falha externa,
            # e nao ha lista fechada de excecoes que os SDKs levantam. O tipo
            # fica registrado para a analise depois.
            desfecho = "erro_provider"
            reg.update(erro=f"{type(e).__name__}: {e}"[:1000],
                       traceback=traceback.format_exc()[-2000:])

        reg["desfecho"] = desfecho
        reg["segundos"] = round(time.perf_counter() - t0, 2)
        # Tokens DESTE caso: diferenca dos acumuladores. Vale tambem para caso
        # que falhou - tentativa que chegou ao modelo e cobrada mesmo que a
        # resposta nao sirva.
        reg["tokens"] = {k: cliente.tokens[k] - tokens_antes[k] for k in cliente.tokens}
        reg["custo_usd"] = custo_usd(reg["tokens"], args.modelo)
        desfechos[desfecho] += 1
        registros.append(reg)
        print(f"  [{i:>3}/{len(fila)}] {sk_id}  {desfecho:<18} {reg['segundos']:>6.1f}s")

    SAIDA_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with SAIDA_JSONL.open("w", encoding="utf-8") as fh:
        for reg in registros:
            fh.write(json.dumps(reg, ensure_ascii=False) + "\n")

    n = len(registros)
    linhas = [
        "# Piloto da Camada 2 contra gerador real\n",
        f"**Gerado por:** `scripts/piloto_camada2.py`  ",
        f"**Modelo:** `{args.modelo}` | temperatura 0 | **sem retry** (proposital)  ",
        f"**Amostra:** sorteio simples de n={n} na zona cinzenta "
        f"({len(universo):,} casos), seed={args.seed}  ",
        f"**Cenario do lote:** LGD={cenario.lgd:.0%} (fallback={cenario.usou_fallback})\n",
        "## Desfechos\n",
        "| Desfecho | k | proporcao | IC95% (Wilson) |",
        "|---|---|---|---|",
    ]
    for desfecho, k in desfechos.most_common():
        lo, hi = wilson(k, n)
        linhas.append(f"| `{desfecho}` | {k} | {k/n:.1%} | [{lo:.1%}; {hi:.1%}] |")

    tempos = [r["segundos"] for r in registros]
    chamadas = [r.get("n_chamadas") for r in registros if r.get("n_chamadas") is not None]
    retries = cliente.tentativas_gastas - cliente.n_chamadas
    linhas += [
        f"\n**Latencia por caso:** mediana {pd.Series(tempos).median():.1f}s, "
        f"total {sum(tempos)/60:.1f} min",
        f"**Custo de transporte:** {cliente.n_chamadas} pedidos ao gerador custaram "
        f"{cliente.tentativas_gastas} idas ao provider (**{retries} retries**"
        f"{', retry desligado' if args.sem_retry else ''}). A diferenca e a taxa "
        f"de falha bruta que o backoff absorve - sem ela, o `erro_provider` "
        f"abaixo subestima a instabilidade real.",
    ]
    if chamadas:
        linhas.append(
            f"**Chamadas de ferramenta por caso:** mediana {pd.Series(chamadas).median():.0f}, "
            f"max {max(chamadas)}"
        )
    tk = cliente.tokens
    total_usd = custo_usd(tk, args.modelo)
    linhas.append("\n## Custo medido\n")
    if tk["medido"] == 0:
        linhas.append(
            "⚠️ **O provider nao reportou uso em nenhuma resposta.** Zero aqui "
            "significa NAO MEDIDO, nao 'de graca' - nao use estes numeros."
        )
    else:
        linhas += [
            f"Uso reportado pelo provider em {tk['medido']} resposta(s) "
            f"(a contagem e medida; so a conversao em dolar e premissa da tabela "
            f"de {list(PRECOS_USD_POR_MILHAO)[0].split('-')[0]} consultada em 2026-08-06).\n",
            "| | tokens |",
            "|---|---|",
            f"| input | {tk['input']:,} |",
            f"| output (visivel) | {tk['output']:,} |",
            f"| thinking (cobrado como output) | {tk['thinking']:,} |",
            f"| **total** | **{tk['total']:,}** |",
        ]
        if total_usd is not None:
            por_caso = total_usd / n
            linhas += [
                f"\n**Custo deste lote:** US$ {total_usd:.4f} "
                f"(**US$ {por_caso:.4f} por caso**, n={n})",
                f"\n**Projecao para o projeto inteiro** ({CASOS_PROJETO_INTEIRO} execucoes "
                f"de caso: piloto + eval set de 150-200 do ADR-0004 §2.5 + 2a rodada + "
                f"folga): **US$ {por_caso * CASOS_PROJETO_INTEIRO:.2f}** no `{args.modelo}`.",
            ]
            visivel = tk["output"] or 1
            linhas.append(
                f"\nRazao thinking/saida visivel: **{tk['thinking']/visivel:.1f}x** - "
                f"e o multiplicador que estimativa por contagem de caracteres nao "
                f"consegue enxergar, e que domina a conta nos modelos 2.5."
            )
        else:
            linhas.append(
                f"\n⚠️ `{args.modelo}` nao esta em `PRECOS_USD_POR_MILHAO` - "
                f"tokens medidos acima, custo nao convertido."
            )

    todas_violacoes = [
        (r["sk_id_curr"], v) for r in registros for v in r.get("violacoes_trajetoria") or []
    ]
    if todas_violacoes:
        linhas.append(
            f"\n## Violacoes de trajetoria (rubrica #4, mecanica)\n\n"
            f"{len(todas_violacoes)} em {n} casos. Nao sao eliminatorias - o memo "
            f"passou no gate de groundedness e mesmo assim tem defeito.\n"
        )
        for sk_id, v in todas_violacoes:
            linhas.append(f"- `{sk_id}`: {v}")

    linhas += [
        "\n> ⚠️ **Leia os intervalos, nao as proporcoes.** Com n desta ordem, o IC "
        "de Wilson e largo o bastante para que a estimativa pontual nao sustente "
        "decisao de politica sozinha (ADR-0004 §2.5). O piloto serve para detectar "
        "falha GROSSA de encanamento, nao para calibrar taxa fina.",
        f"\n**Memos e traces brutos:** `{SAIDA_JSONL.relative_to(RAIZ)}` (fora do git).",
    ]

    SAIDA_REPORT.parent.mkdir(parents=True, exist_ok=True)
    SAIDA_REPORT.write_text("\n".join(linhas), encoding="utf-8")

    print(f"\n{'desfecho':<20} {'k':>4} {'prop':>8}  IC95% Wilson")
    for desfecho, k in desfechos.most_common():
        lo, hi = wilson(k, n)
        print(f"{desfecho:<20} {k:>4} {k/n:>7.1%}  [{lo:.1%}; {hi:.1%}]")
    if tk["medido"]:
        print(f"\ntokens: {tk['input']:,} in | {tk['output']:,} out | "
              f"{tk['thinking']:,} thinking")
        if total_usd is not None:
            print(f"custo:  US$ {total_usd:.4f} neste lote | "
                  f"US$ {total_usd/n:.4f}/caso | "
                  f"projecao {CASOS_PROJETO_INTEIRO} casos: "
                  f"US$ {total_usd/n*CASOS_PROJETO_INTEIRO:.2f}")
    else:
        print("\n⚠️ provider nao reportou uso - custo NAO MEDIDO (nao e zero)")

    print(f"\nRelatorio: {SAIDA_REPORT}\nBrutos:    {SAIDA_JSONL}")


if __name__ == "__main__":
    main()
