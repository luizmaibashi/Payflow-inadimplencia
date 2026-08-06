"""Gera UM documento markdown para leitura + julgamento manual dos memos do piloto.

Junta: narrativa do memo (renderizar_narrativa), dados brutos das ferramentas
(trace) lado a lado para cross-check de groundedness, e campos em branco para
o humano preencher o veredito das 4 rubricas do ADR-0004 SS2.2.

Uso:
    python scripts/gerar_analise_piloto.py
"""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from app.memo_credito import MemoCredito, renderizar_narrativa

ENTRADA = RAIZ / "data" / "processed" / "piloto_camada2_memos.jsonl"
SAIDA = RAIZ / "reports" / "piloto_camada2_analise.md"

INTRO = """\
# Analise manual do piloto Camada 2 (n=25)

Este arquivo tem duas partes: um exemplo resolvido (pra voce ver como se faz)
e os 25 casos reais, cada um com espaco em branco pra voce preencher.

## As 4 rubricas (ADR-0004 SS2.2)

| # | Rubrica | O que pergunta |
|---|---|---|
| 1 | **Groundedness** (ELIMINATORIA) | O numero citado no fato existe mesmo no retorno da ferramenta apontada? |
| 2 | **Task completion** | A recomendacao (APROVAR/NEGAR/DEFERIR) e defensavel dados os fatos? Se DEFERIR, disse o que faltou de forma concreta? |
| 3 | **Trajectory** | O agente usou as ferramentas com eficiencia (sem repetir, sem pular a que faltava)? |
| 4 | **Cegueira ao score** | Nenhum fato menciona score/probabilidade/nota de risco? |

Groundedness e ELIMINATORIA: se falhar, o caso falhou - nao precisa julgar as
outras 3, so anote a evidencia.

## Exemplo resolvido - caso `151515`

**O que a ferramenta `consultar_bureau` devolveu de verdade:**
```
n_contratos: 18   n_ativos: 5   n_em_atraso_hoje: 0   utilizacao: 0.3205
```

**O que o memo disse, citando essa ferramenta:**
> "O cliente possui um historico de credito extenso em outras instituicoes,
> com **18 contratos** registrados, sendo **5 ativos** e **nenhum em atraso**
> atualmente." ... "A utilizacao do limite de credito ... e de aproximadamente
> **32%**"

**Cross-check:** 18 = 18 ✓ | 5 = 5 ✓ | 0 atraso = 0 ✓ | 32% ≈ 0.3205 ✓
Todos os numeros do fato aparecem, sem distorcao, no retorno bruto da
ferramenta que o memo apontou como fonte. **Groundedness: OK.**

**Recomendacao foi APROVAR, e os 4 fatos sao todos favoraveis** (nenhum
desfavoravel ou neutro) - recomendacao bate com os fatos. **Task
completion: OK.**

Isso e o nivel de checagem que se pede para cada caso abaixo: pegar o numero
do texto e achar ele (ou a conta que leva nele) no bloco "Dados brutos".

---

"""

VEREDITO_TEMPLATE = """\
**Seu veredito:**
- [ ] 1. Groundedness: `OK` / `FALHA` — evidencia: ___________________________
- [ ] 2. Task completion: `OK` / `FALHA` — evidencia: _________________________
- [ ] 3. Trajectory: `OK` / `FALHA` — evidencia: ______________________________
- [ ] 4. Cegueira ao score: `OK` / `FALHA` — evidencia: _______________________
- Nota geral: ___________________________________________________________
"""

RODAPE = """\

---

## Resumo (preencher por ultimo)

- Groundedness: __ / 25 OK
- Task completion: __ / 25 OK
- Trajectory: __ / 25 OK
- Cegueira ao score: __ / 25 OK

## Padroes observados

(O que se repete entre casos - nao liste cada caso, liste o PADRAO.)

-

## Casos-exemplo para virar teste

(1 exemplo concreto por rubrica que falhou: cliente_id + o que quebrou.)

-
"""


def formatar_retorno(d: dict) -> str:
    linhas = []
    for k, v in d.items():
        if v is None:
            continue
        if isinstance(v, float):
            v = round(v, 4)
        linhas.append(f"  {k}: {v}")
    return "\n".join(linhas) if linhas else "  (sem dados)"


def main() -> None:
    regs = [json.loads(l) for l in ENTRADA.read_text(encoding="utf-8").splitlines()]

    partes = [INTRO]
    for i, r in enumerate(regs, 1):
        partes.append(f"---\n## Caso {i}/25 — cliente `{r['sk_id_curr']}`\n")
        partes.append(
            f"**Desfecho automatico:** `{r['desfecho']}` "
            f"(isto mede so formato/mecanica - NAO substitui seu julgamento)  \n"
            f"**Chamadas:** {r.get('n_chamadas', '—')}  \n"
            f"**Violacoes de trajetoria (detectadas automaticamente):** "
            f"{r.get('violacoes_trajetoria') or 'nenhuma'}  \n"
        )

        if r.get("erro"):
            partes.append(f"\n**Erro:**\n```\n{r['erro'][:600]}\n```\n")

        if r.get("trace"):
            partes.append("\n**Dados brutos das ferramentas** (para checar groundedness):\n")
            for c in r["trace"]:
                partes.append(f"`{c['ferramenta']}`:\n```\n{formatar_retorno(c['retorno'])}\n```")

        if r.get("memo"):
            memo = MemoCredito(**r["memo"])
            partes.append("\n**Memo (narrativa que o sistema geraria):**\n```\n" + renderizar_narrativa(memo) + "\n```\n")
        else:
            partes.append("\n*(sem memo — caso nao concluiu)*\n")

        partes.append("\n" + VEREDITO_TEMPLATE + "\n")

    partes.append(RODAPE)

    SAIDA.write_text("\n".join(partes), encoding="utf-8")
    print(f"Escrito: {SAIDA}")


if __name__ == "__main__":
    main()
