"""Re-roda os 6 casos DEFERIR do piloto de 2026-08-06 contra o prompt corrigido.

Achado que motivou a correcao: revisor humano aceitou 1/6 DEFERIR, rejeitou os
outros 5 - todos citavam renda/emprego/patrimonio em informacao_faltante, dado
que nenhuma ferramenta deste sistema fornece. Prompt em app/clientes_llm.py
(_prompt_sistema) foi ajustado para proibir isso. Este script confirma se a
mudanca teve efeito nos MESMOS casos, nao numa amostra nova - controle antes/
depois.

Uso:
    python scripts/reteste_deferir.py
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from app.agente_underwriting import AgenteUnderwriting  # noqa: E402
from app.clientes_llm import ClienteGemini, RespostaLLMInvalida  # noqa: E402
from app.ferramenta_cenario import FerramentaCenario  # noqa: E402
from app.ferramentas_caso import FerramentasCaso  # noqa: E402

# Os 6 DEFERIR do piloto: 1 aceito pelo humano, 5 rejeitados.
CASOS_ANTES = {
    238067: "DEFERIR (aceito pelo humano)",
    268561: "DEFERIR (rejeitado)",
    285827: "DEFERIR (rejeitado)",
    336278: "DEFERIR (rejeitado)",
    381595: "DEFERIR (rejeitado)",
    398836: "DEFERIR (rejeitado)",
}


def main():
    cenario = FerramentaCenario().consultar_cenario()
    print(f"Cenario: LGD={cenario.lgd:.0%} | {cenario.fonte}\n")

    ferramentas = FerramentasCaso()
    cliente = ClienteGemini(modelo="gemini-2.5-flash")
    agente = AgenteUnderwriting(ferramentas=ferramentas, cenario=cenario, cliente_llm=cliente)

    print(f"{'sk_id':>8}  {'antes':<28} {'agora':<10}  faltante citado agora")
    for sk_id, antes in CASOS_ANTES.items():
        try:
            r = agente.analisar(sk_id)
        except RespostaLLMInvalida as e:
            print(f"{sk_id:>8}  {antes:<28} {'FALHA FORMATO':<10}  {str(e)[:80]}")
            continue
        if r.memo:
            recom = r.memo.recomendacao.value
            faltante = "; ".join(r.memo.informacao_faltante) or "(vazio)"
        else:
            recom = f"SEM MEMO ({r.erro[:60] if r.erro else '?'})"
            faltante = "-"
        print(f"{sk_id:>8}  {antes:<28} {recom:<10}  {faltante}")


if __name__ == "__main__":
    main()
