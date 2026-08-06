"""Renderiza os memos do piloto (JSONL) em markdown legivel para leitura humana.

Reaproveita `renderizar_narrativa` (app/memo_credito.py) - a mesma funcao que
gera o parecer em producao. Nao inventa formatacao nova: o humano le exatamente
o texto que o sistema produziria.

Uso:
    python scripts/ler_memos_piloto.py
"""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from app.memo_credito import MemoCredito, renderizar_narrativa
ENTRADA = RAIZ / "data" / "processed" / "piloto_camada2_memos.jsonl"
SAIDA = RAIZ / "reports" / "piloto_camada2_leitura.md"


def main() -> None:
    regs = [json.loads(l) for l in ENTRADA.read_text(encoding="utf-8").splitlines()]

    partes = ["# Leitura dos memos do piloto (n=25)\n"]
    for i, r in enumerate(regs, 1):
        partes.append(f"---\n## Caso {i}/{len(regs)} — `{r['sk_id_curr']}`\n")
        partes.append(
            f"**Desfecho:** `{r['desfecho']}`  \n"
            f"**Chamadas:** {r.get('n_chamadas', '—')}  \n"
            f"**Ferramentas usadas:** {', '.join(r.get('ferramentas', []) or [])}  \n"
            f"**Violacoes de trajetoria:** {r.get('violacoes_trajetoria') or 'nenhuma'}  \n"
        )
        if r.get("erro"):
            partes.append(f"\n**Erro:**\n```\n{r['erro'][:600]}\n```\n")
        if r.get("memo"):
            memo = MemoCredito(**r["memo"])
            partes.append("\n```\n" + renderizar_narrativa(memo) + "\n```\n")

    SAIDA.write_text("\n".join(partes), encoding="utf-8")
    print(f"Escrito: {SAIDA}")


if __name__ == "__main__":
    main()
