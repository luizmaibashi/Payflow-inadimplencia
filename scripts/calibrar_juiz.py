"""Calibra o juiz de Task Completion contra os 87 labels humanos (debito #10).

TPR/TNR com IC de Wilson (ADR-0004 SS2.5) - nunca agreement bruto (trap
metric sob classes desbalanceadas, o mesmo ADR explica por que).

Requer:
  - data/labels/task_completion_labels.json (existe, versionado, 87 labels)
  - data/processed/piloto_camada2_memos.jsonl (NAO existe nesta maquina -
    regeneravel via `python scripts/piloto_camada2.py --n 100 --seed 42
    --modelo gemini-2.5-flash`, mas isso GASTA CHAMADA DE API REAL. Rodar
    de proposito, nao por engano.)
  - GROQ_API_KEY no .env (o juiz roda de verdade, gasta chamada de API)

Uso:
  python scripts/calibrar_juiz.py
"""
import json
import math
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
LABELS_PATH = RAIZ / "data" / "labels" / "task_completion_labels.json"
MEMOS_PATH = RAIZ / "data" / "processed" / "piloto_camada2_memos.jsonl"
# Vereditos do juiz sao saida de LLM: NAO regeneraveis (debito #30, medido
# nos memos do gerador). Versionados pelo mesmo motivo - sem isso, reescrever
# o relatorio exigiria rejulgar tudo, e o resultado voltaria diferente.
VEREDITOS_PATH = RAIZ / "data" / "labels" / "juiz_task_completion.json"
REPORT_PATH = RAIZ / "reports" / "calibracao_juiz.md"

sys.path.insert(0, str(RAIZ))


def intervalo_wilson(acertos: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """IC de Wilson para uma proporcao. NAO usar normal: com proporcao perto
    de 0 ou 1 e `n` pequeno, o IC normal vaza para fora de [0, 1] (ADR-0004
    SS2.5 - e por isso que este projeto usa Wilson em vez do padrao mais
    comum)."""
    if n == 0:
        return (0.0, 0.0)
    p = acertos / n
    denom = 1 + z**2 / n
    centro = p + z**2 / (2 * n)
    margem = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))
    return (max(0.0, (centro - margem) / denom), min(1.0, (centro + margem) / denom))


def calcular_tpr_tnr(pares: list[tuple[str, str]]) -> dict:
    """`pares` = [(veredito_juiz, veredito_humano), ...], cada veredito
    "OK" ou "FALHA". FALHA e o positivo (o juiz "detectou" o problema).

    TPR (sensibilidade): dos casos que o humano marcou FALHA, quantos o
    juiz tambem marcou FALHA.
    TNR (especificidade): dos casos que o humano marcou OK, quantos o
    juiz tambem marcou OK.
    """
    tp = sum(1 for j, h in pares if j == "FALHA" and h == "FALHA")
    fn = sum(1 for j, h in pares if j == "OK" and h == "FALHA")
    tn = sum(1 for j, h in pares if j == "OK" and h == "OK")
    fp = sum(1 for j, h in pares if j == "FALHA" and h == "OK")

    n_falha_humano = tp + fn
    n_ok_humano = tn + fp

    tpr = tp / n_falha_humano if n_falha_humano else None
    tnr = tn / n_ok_humano if n_ok_humano else None

    return {
        "tp": tp, "fn": fn, "tn": tn, "fp": fp,
        "n_falha_humano": n_falha_humano, "n_ok_humano": n_ok_humano,
        "tpr": tpr, "tnr": tnr,
        "ic_tpr": intervalo_wilson(tp, n_falha_humano) if n_falha_humano else None,
        "ic_tnr": intervalo_wilson(tn, n_ok_humano) if n_ok_humano else None,
    }


def _carregar_labels() -> dict[int, str]:
    dados = json.loads(LABELS_PATH.read_text(encoding="utf-8"))
    labels = {}
    for c in dados["labels"]:
        veredito = c["task_completion"]["veredito"]
        if veredito is None:
            continue  # pendencia sem julgamento humano - exclui, nao inventa
        labels[c["sk_id_curr"]] = veredito
    return labels


def labels_obsoletos(labels: dict[int, str], memos: dict[int, dict]) -> dict[int, str]:
    """Labels que o debito #30 tornou factualmente errados.

    Um label `FALHA` do tipo "recomendacao_ignora_fato" sempre significou, na
    rotulagem de 2026-08-07, "o agente NEGOU um cliente que os fatos mostram
    bom pagador". Se o memo regerado passou a recomendar APROVAR, o agente
    fez exatamente o que o humano cobrou - e a etiqueta FALHA descreve um
    memo que nao existe mais.

    O inverso nao vale como teste: FALHA que continua NEGAR segue coerente
    com a queixa original, entao nao ha razao para descartar.

    Devolve {sk_id: motivo}. Nao remove nada sozinho - main() reporta as duas
    contas (com e sem), porque descartar dado tem que ser decisao visivel.
    """
    obsoletos = {}
    for sk_id, veredito in labels.items():
        if veredito != "FALHA":
            continue
        reg = memos.get(sk_id)
        if reg is None:
            continue
        if reg["memo"]["recomendacao"] == "APROVAR":
            obsoletos[sk_id] = (
                "rotulado FALHA (agente negou bom pagador), mas o memo "
                "regerado recomenda APROVAR - a queixa original nao se aplica"
            )
    return obsoletos


def _carregar_memos() -> dict[int, dict]:
    if not MEMOS_PATH.exists():
        raise FileNotFoundError(
            f"{MEMOS_PATH} nao existe. E gitignored/regeneravel - rode "
            "scripts/piloto_camada2.py de novo (gasta API real) ou copie o "
            "arquivo de outra maquina antes de calibrar."
        )
    memos = {}
    with MEMOS_PATH.open(encoding="utf-8") as fh:
        for linha in fh:
            reg = json.loads(linha)
            if reg.get("memo"):
                memos[reg["sk_id_curr"]] = reg
    return memos


def criterio_inconsistente(labels: dict[int, str], memos: dict[int, dict]) -> list[dict]:
    """Casos com a MESMA assinatura nos dados brutos e vereditos humanos
    diferentes.

    A assinatura e a que o proprio revisor usou ao escrever as evidencias de
    FALHA em 2026-08-07 ("claramente um bom pagador... nunca deixou de pagar
    ... paga adiantado em media"), traduzida para os campos crus de
    `consultar_pagamentos`: recomendacao NEGAR + `n_nunca_pagas == 0` +
    `atraso_medio_dias < 0`.

    Se o mesmo padrao aparece rotulado ora FALHA ora OK, o ground truth tem
    ruido de criterio - e nenhum TPR calculado contra ele mede o juiz, mede a
    divergencia entre um criterio implicito e um explicito.
    """
    achados = []
    for sk_id, reg in sorted(memos.items()):
        if labels.get(sk_id) is None:
            continue
        if reg["memo"]["recomendacao"] != "NEGAR":
            continue
        pag = next(
            (c["retorno"] for c in reg["trace"] if c["ferramenta"] == "consultar_pagamentos"),
            None,
        )
        if not pag or not pag.get("tem_registro"):
            continue
        if pag.get("n_nunca_pagas") == 0 and (pag.get("atraso_medio_dias") or 0) < 0:
            achados.append({
                "sk_id_curr": sk_id,
                "humano": labels[sk_id],
                "atraso_medio_dias": round(pag["atraso_medio_dias"], 1),
                "dias_desde_ultimo_atraso": pag.get("dias_desde_ultimo_atraso"),
            })
    return achados


def main() -> None:
    from app.clientes_llm import FalhaProvider, RespostaLLMInvalida
    from app.ferramentas_caso import ChamadaFerramenta
    from app.juiz_camada2 import ClienteGroqJuiz, julgar_task_completion
    from app.memo_credito import MemoCredito

    rejulgar = "--rejulgar" in sys.argv

    labels = _carregar_labels()
    memos = _carregar_memos()

    faltando_memo = sorted(set(labels) - set(memos))
    if faltando_memo:
        print(f"aviso: {len(faltando_memo)} sk_id_curr rotulados sem memo correspondente: {faltando_memo}")

    obsoletos = labels_obsoletos(labels, memos)
    alvos = sorted(sk for sk in labels if sk in memos)
    erros: list[tuple[int, str]] = []

    if VEREDITOS_PATH.exists() and not rejulgar:
        cache = json.loads(VEREDITOS_PATH.read_text(encoding="utf-8"))
        julgados = cache["julgados"]
        erros = [tuple(e) for e in cache.get("erros", [])]
        print(f"reusando {len(julgados)} vereditos de {VEREDITOS_PATH.name} "
              f"(rode com --rejulgar para gastar API de novo)")
    else:
        cliente_juiz = ClienteGroqJuiz()
        julgados = []
        for i, sk_id in enumerate(alvos, 1):
            reg = memos[sk_id]
            memo = MemoCredito(**reg["memo"])
            trace = [ChamadaFerramenta(**c) for c in reg["trace"]]
            try:
                resultado = julgar_task_completion(memo, trace, cliente_juiz)
            except (RespostaLLMInvalida, FalhaProvider) as e:
                erros.append((sk_id, f"{type(e).__name__}: {e}"[:300]))
                print(f"  [{i:>3}/{len(alvos)}] {sk_id}  ERRO")
                continue
            julgados.append({
                "sk_id_curr": sk_id,
                "juiz": resultado.veredito.value,
                "humano": labels[sk_id],
                "recomendacao": reg["memo"]["recomendacao"],
                "evidencia_juiz": resultado.evidencia,
                "suspeito_dado_ausente": resultado.suspeito_dado_ausente,
            })
            marca = "=" if resultado.veredito.value == labels[sk_id] else "x"
            print(f"  [{i:>3}/{len(alvos)}] {sk_id}  juiz={resultado.veredito.value:<5} "
                  f"humano={labels[sk_id]:<5} {marca}")

        VEREDITOS_PATH.write_text(json.dumps({
            "gerado_em": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc).isoformat().replace("+00:00", "Z"),
            "juiz": "groq/llama-3.3-70b-versatile, temperatura 0",
            "fonte_memos": "data/processed/piloto_camada2_memos.jsonl (2026-08-08)",
            "julgados": julgados,
            "erros": erros,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"vereditos salvos em {VEREDITOS_PATH}")

    # `obsoleto` e derivado, nao vem do cache - a regra pode mudar sem
    # precisar rejulgar nada.
    for j in julgados:
        j["obsoleto"] = j["sk_id_curr"] in obsoletos

    pares_todos = [(j["juiz"], j["humano"]) for j in julgados]
    pares_limpos = [(j["juiz"], j["humano"]) for j in julgados if not j["obsoleto"]]
    m_todos = calcular_tpr_tnr(pares_todos)
    m_limpos = calcular_tpr_tnr(pares_limpos)

    def pct(v):
        return "n/d" if v is None else f"{v:.1%}"

    def ic(par):
        return "n/d" if par is None else f"[{par[0]:.1%}; {par[1]:.1%}]"

    def tabela(m, titulo):
        return [
            f"### {titulo}",
            "",
            "| Métrica | Valor | IC95% (Wilson) | n |",
            "|---|---|---|---|",
            f"| TPR (detecta FALHA real) | {pct(m['tpr'])} | {ic(m['ic_tpr'])} | {m['n_falha_humano']} |",
            f"| TNR (não acusa memo bom) | {pct(m['tnr'])} | {ic(m['ic_tnr'])} | {m['n_ok_humano']} |",
            "",
            f"Matriz: TP={m['tp']} · FN={m['fn']} · TN={m['tn']} · FP={m['fp']}",
            "",
        ]

    linhas = [
        "# Calibração do juiz — Task Completion (débito #10)",
        "",
        f"**Gerado por:** `scripts/calibrar_juiz.py`  ",
        f"**Juiz:** Groq / `llama-3.3-70b-versatile`, temperatura 0  ",
        f"**Gerador dos memos:** `gemini-2.5-flash` (família diferente — ADR-0004 §2.3)  ",
        f"**Memos:** `data/processed/piloto_camada2_memos.jsonl` (2026-08-08, versionado)",
        "",
        "## O que foi medido",
        "",
        f"- Labels humanos disponíveis: **{len(labels)}**",
        f"- Com memo correspondente: **{len(alvos)}** "
        f"({len(faltando_memo)} sem memo — ver débito #30)",
        f"- Julgados sem erro de provider: **{len(julgados)}**",
        "",
        "> ⚠️ **Regra dura (ADR-0004 §2.5):** leia o intervalo, não a proporção. "
        "Com `n` desta ordem o IC de Wilson é largo o bastante para que a "
        "estimativa pontual não sustente decisão de política sozinha.",
        "",
        "## Resultado",
        "",
    ]
    linhas += tabela(m_todos, f"Todos os labels pareáveis (n={len(pares_todos)})")

    if obsoletos:
        linhas += [
            "### Recorte de sensibilidade — sem os labels que o débito #30 invalidou",
            "",
            "Estes labels foram marcados `FALHA` porque o agente **negou** um "
            "cliente que os fatos mostravam bom pagador. Nos memos regerados "
            "ele passou a recomendar `APROVAR` — fez o que o revisor cobrou, "
            "então a etiqueta descreve um memo que não existe mais:",
            "",
        ]
        linhas += [f"- `{sk}` — {motivo}" for sk, motivo in sorted(obsoletos.items())]
        linhas += [""]
        linhas += tabela(m_limpos, f"Sem os {len(obsoletos)} obsoletos (n={len(pares_limpos)})")

    discordancias = [j for j in julgados if j["juiz"] != j["humano"]]
    if discordancias:
        n_suspeitos = sum(1 for j in discordancias if j.get("suspeito_dado_ausente"))
        linhas += [
            f"## Onde juiz e humano discordaram ({len(discordancias)}, "
            f"{n_suspeitos} suspeitos de #33 - dado ausente)",
            "",
            "| caso | recomendação | humano | juiz | suspeito #33? | evidência do juiz |",
            "|---|---|---|---|---|---|",
        ]
        for j in sorted(discordancias, key=lambda x: x["sk_id_curr"]):
            ev = (j["evidencia_juiz"] or "").replace("|", "/")[:160]
            suspeito = "⚠️" if j.get("suspeito_dado_ausente") else ""
            linhas.append(
                f"| `{j['sk_id_curr']}` | {j['recomendacao']} | {j['humano']} | "
                f"{j['juiz']} | {suspeito} | {ev} |"
            )
        linhas += [""]

    if erros:
        linhas += [
            f"## Erros de provider/parsing ({len(erros)}, fora da matriz)",
            "",
        ]
        linhas += [f"- `{sk}`: {msg}" for sk, msg in erros]
        linhas += [""]

    incons = criterio_inconsistente(labels, memos)
    n_falha = sum(1 for a in incons if a["humano"] == "FALHA")
    if incons and 0 < n_falha < len(incons):
        linhas += [
            "## 🔴 O ground truth tem ruído de critério — leia isto antes das métricas",
            "",
            f"**{len(incons)} casos** têm a MESMA assinatura nos dados brutos: o memo "
            f"recomenda `NEGAR`, o cliente **nunca deixou de pagar** "
            f"(`n_nunca_pagas = 0`) e **paga adiantado em média** "
            f"(`atraso_medio_dias < 0`). É exatamente o padrão que o revisor "
            f"descreveu ao justificar as FALHAs de 2026-08-07 "
            f"(*\"claramente um bom pagador, nunca deixou de pagar, paga "
            f"adiantado em média\"*).",
            "",
            f"Desses {len(incons)}, o revisor marcou **{n_falha} como FALHA** e "
            f"**{len(incons) - n_falha} como OK**.",
            "",
            "| caso | veredito humano | atraso médio (dias) | dias desde último atraso |",
            "|---|---|---|---|",
        ]
        for a in incons:
            d = a["dias_desde_ultimo_atraso"]
            linhas.append(
                f"| `{a['sk_id_curr']}` | {a['humano']} | {a['atraso_medio_dias']} | "
                f"{'—' if d is None else d} |"
            )
        linhas += [
            "",
            "**Consequência para este relatório:** o TPR acima não mede a qualidade "
            "do juiz. Mede a distância entre um critério humano *implícito e "
            "aplicado de forma variável* e um critério de juiz *explícito e "
            "constante*. Boa parte dos 'falsos positivos' do juiz cai justamente "
            "nesses casos — o juiz aplicou a mesma régua que o revisor usou em 4 "
            "deles, aos 11 restantes.",
            "",
            "**O que fazer antes de rerrotular qualquer coisa:** escrever o critério "
            "de Task Completion como regra verificável (o que exatamente torna uma "
            "recomendação `NEGAR` indefensável na presença de bom histórico de "
            "pagamento?) e só então rotular. Rotular mais casos com o critério "
            "implícito só aumenta o ruído — não estreita o intervalo.",
            "",
        ]

    linhas += [
        "## Limitações declaradas",
        "",
        "- **O prompt do juiz embute a heurística de contagem de pesos** "
        "(`_prompt_sistema_juiz` manda marcar FALHA quando *\"a recomendação "
        "contraria o peso predominante dos fatores\"*). Qualquer proxy mecânico "
        "que também conte pesos vai concordar com o juiz **por construção** — "
        "isso não é confirmação independente.",
        "- **Revisor único e não especialista** — ground truth fraco por "
        "construção (ADR-0003 §3, débito #10).",
        "- **`n` de positivos pequeno**: o TPR é a métrica que importa (detectar "
        "a falha rara) e é justamente a de intervalo mais largo aqui.",
        "- Os labels reaproveitados de 2026-08-07 descrevem memos regerados em "
        "2026-08-08. A premissa é que um label `OK` sobrevive à regeração salvo "
        "regressão do agente; as duas mudanças observadas foram melhorias. "
        "Premissa **declarada**, não verificada caso a caso.",
        "",
    ]

    REPORT_PATH.write_text("\n".join(linhas), encoding="utf-8")
    print(f"\nTodos      (n={len(pares_todos):>2}): TPR={pct(m_todos['tpr'])} {ic(m_todos['ic_tpr'])} | "
          f"TNR={pct(m_todos['tnr'])} {ic(m_todos['ic_tnr'])}")
    print(f"Sem podres (n={len(pares_limpos):>2}): TPR={pct(m_limpos['tpr'])} {ic(m_limpos['ic_tpr'])} | "
          f"TNR={pct(m_limpos['tnr'])} {ic(m_limpos['ic_tnr'])}")
    print(f"\nrelatorio: {REPORT_PATH}")


if __name__ == "__main__":
    main()
