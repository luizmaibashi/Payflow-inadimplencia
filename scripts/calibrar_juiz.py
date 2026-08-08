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


def main() -> None:
    from app.clientes_llm import FalhaProvider, RespostaLLMInvalida
    from app.ferramentas_caso import ChamadaFerramenta
    from app.juiz_camada2 import ClienteGroqJuiz, julgar_task_completion
    from app.memo_credito import MemoCredito

    labels = _carregar_labels()
    memos = _carregar_memos()

    faltando_memo = sorted(set(labels) - set(memos))
    if faltando_memo:
        print(f"aviso: {len(faltando_memo)} sk_id_curr rotulados sem memo correspondente: {faltando_memo}")

    cliente_juiz = ClienteGroqJuiz()
    pares: list[tuple[str, str]] = []
    erros: list[tuple[int, str]] = []

    for sk_id, veredito_humano in sorted(labels.items()):
        reg = memos.get(sk_id)
        if reg is None:
            continue
        memo = MemoCredito(**reg["memo"])
        trace = [ChamadaFerramenta(**c) for c in reg["trace"]]
        try:
            resultado = julgar_task_completion(memo, trace, cliente_juiz)
        except (RespostaLLMInvalida, FalhaProvider) as e:
            erros.append((sk_id, str(e)))
            continue
        pares.append((resultado.veredito.value, veredito_humano))

    metricas = calcular_tpr_tnr(pares)

    linhas = [
        "# Calibração do juiz — Task Completion (débito #10)",
        "",
        f"`n` avaliado: {len(pares)} de {len(labels)} labels humanos "
        f"({len(erros)} erro(s) de provider/parsing, {len(faltando_memo)} sem memo).",
        "",
        "**Regra dura do ADR-0004 §2.5**: com `n` pequeno o IC de Wilson é largo — "
        "não tratar TPR/TNR pontual como medição fina.",
        "",
        f"- TPR (sensibilidade a FALHA real): {metricas['tpr']} "
        f"(IC95% {metricas['ic_tpr']}, n={metricas['n_falha_humano']})",
        f"- TNR (especificidade em OK real): {metricas['tnr']} "
        f"(IC95% {metricas['ic_tnr']}, n={metricas['n_ok_humano']})",
        f"- Matriz: TP={metricas['tp']} FN={metricas['fn']} TN={metricas['tn']} FP={metricas['fp']}",
        "",
    ]
    if erros:
        linhas.append("## Erros de provider/parsing (excluídos da matriz)")
        linhas += [f"- `{sk}`: {msg}" for sk, msg in erros]

    REPORT_PATH.write_text("\n".join(linhas), encoding="utf-8")
    print(f"relatorio escrito em {REPORT_PATH}")


if __name__ == "__main__":
    main()
