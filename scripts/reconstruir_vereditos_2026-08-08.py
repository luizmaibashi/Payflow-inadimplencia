"""Reconstroi os 75 vereditos da PRIMEIRA rodada do juiz (2026-08-08).

Procedencia: a rodada completa (75/75 sem erro) rodou antes de o cache
existir, e a cota diaria do Groq (100k TPD) foi consumida por ela - a segunda
rodada, ja com cache, so conseguiu 31 antes do 429. Os vereditos da primeira
rodada foram capturados da saida de console e sao transcritos aqui.

Conferencia: a matriz reconstruida tem que bater com a que o relatorio da
primeira rodada registrou - TP=4, FN=4, TN=60, FP=7. O assert no fim falha
se a transcricao estiver errada.

O texto de `evidencia_juiz` so existe para as discordancias (era o unico
campo que o relatorio da primeira rodada imprimia). Concordancias ficam com
evidencia vazia - nao inventar.

Uso: python scripts/reconstruir_vereditos_2026-08-08.py
"""
import json
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "data" / "labels" / "juiz_task_completion.json"

# (sk_id_curr, veredito_juiz, veredito_humano)
RODADA_1 = [
    (100525, "OK", "FALHA"), (101080, "OK", "OK"), (108447, "OK", "OK"),
    (109117, "OK", "OK"), (111985, "OK", "OK"), (113011, "OK", "OK"),
    (115682, "OK", "OK"), (117727, "OK", "OK"), (126645, "OK", "OK"),
    (128369, "OK", "OK"), (143212, "OK", "OK"), (148582, "OK", "OK"),
    (151927, "OK", "OK"), (153799, "FALHA", "FALHA"), (161761, "OK", "OK"),
    (166661, "FALHA", "OK"), (169111, "OK", "OK"), (169869, "OK", "OK"),
    (173034, "OK", "OK"), (173954, "OK", "OK"), (181390, "OK", "OK"),
    (183280, "OK", "OK"), (185233, "OK", "OK"), (187682, "OK", "OK"),
    (189743, "OK", "OK"), (192195, "OK", "OK"), (199386, "OK", "OK"),
    (205320, "OK", "OK"), (212372, "OK", "OK"), (219448, "FALHA", "FALHA"),
    (224770, "FALHA", "OK"), (226146, "OK", "OK"), (235261, "OK", "OK"),
    (235776, "OK", "OK"), (238067, "OK", "OK"), (240344, "FALHA", "FALHA"),
    (243962, "OK", "OK"), (244626, "FALHA", "OK"), (246975, "OK", "OK"),
    (252397, "FALHA", "OK"), (259658, "OK", "OK"), (260691, "OK", "OK"),
    (264603, "OK", "FALHA"), (279711, "OK", "OK"), (280852, "OK", "OK"),
    (282047, "OK", "OK"), (285827, "OK", "OK"), (295370, "FALHA", "OK"),
    (299680, "OK", "OK"), (302315, "OK", "OK"), (303376, "FALHA", "OK"),
    (310188, "OK", "FALHA"), (322471, "OK", "OK"), (325723, "OK", "OK"),
    (326137, "OK", "OK"), (331720, "OK", "OK"), (333067, "OK", "OK"),
    (340715, "OK", "OK"), (342044, "OK", "OK"), (348835, "OK", "OK"),
    (350878, "OK", "OK"), (351105, "OK", "OK"), (353468, "OK", "FALHA"),
    (358801, "OK", "OK"), (368123, "OK", "OK"), (371141, "OK", "OK"),
    (374802, "OK", "OK"), (379149, "FALHA", "FALHA"), (386823, "OK", "OK"),
    (396189, "OK", "OK"), (398836, "OK", "OK"), (410339, "OK", "OK"),
    (417173, "FALHA", "OK"), (435752, "OK", "OK"), (449188, "OK", "OK"),
]

# So as discordancias tiveram evidencia impressa pelo relatorio da rodada 1.
EVIDENCIAS = {
    166661: "O cliente não possui contratos em atraso hoje em outras instituições, "
            "utilização do crédito disponível em outras instituições é baixa (28%), "
            "possui um histórico",
    224770: "atraso medio de -11 dias, 0 parcelas nunca pagas, 1 atraso de 10 dias "
            "há 125 dias e limite de crédito total de R$ 357.750,00 sem atrasos, "
            "mas recomendacao foi N",
    244626: "atraso medio de -6.028985507246377 dias, 0 parcelas nunca pagas, "
            "2 atrasos minimos (1 dia), e ultimo atraso ocorreu ha mais de 684 dias, "
            "mas recomendacao foi NE",
    252397: "atraso medio de -7.7 dias e 0 parcelas nunca pagas, mas recomendacao foi NEGAR",
    295370: "atraso médio de -21.67 dias e 5 meses em dia sem atrasos registrados "
            "em outras instituições, mas recomendacao foi NEGAR",
    303376: "atraso médio de -2.28 dias e 0 parcelas nunca pagas, mas recomendacao foi NEGAR",
    417173: "nenhum fator desfavoravel foi citado, mas a recomendacao foi NEGAR",
}


def main() -> None:
    memos = {}
    caminho_memos = RAIZ / "data" / "processed" / "piloto_camada2_memos.jsonl"
    with caminho_memos.open(encoding="utf-8") as fh:
        for linha in fh:
            reg = json.loads(linha)
            if reg.get("memo"):
                memos[reg["sk_id_curr"]] = reg["memo"]["recomendacao"]

    julgados = [{
        "sk_id_curr": sk,
        "juiz": juiz,
        "humano": humano,
        "recomendacao": memos[sk],
        "evidencia_juiz": EVIDENCIAS.get(sk, ""),
    } for sk, juiz, humano in RODADA_1]

    tp = sum(1 for j in julgados if j["juiz"] == "FALHA" and j["humano"] == "FALHA")
    fn = sum(1 for j in julgados if j["juiz"] == "OK" and j["humano"] == "FALHA")
    tn = sum(1 for j in julgados if j["juiz"] == "OK" and j["humano"] == "OK")
    fp = sum(1 for j in julgados if j["juiz"] == "FALHA" and j["humano"] == "OK")
    assert (tp, fn, tn, fp) == (4, 4, 60, 7), f"transcricao errada: {(tp, fn, tn, fp)}"
    assert len(julgados) == 75, len(julgados)

    SAIDA.write_text(json.dumps({
        "gerado_em": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "juiz": "groq/llama-3.3-70b-versatile, temperatura 0",
        "fonte_memos": "data/processed/piloto_camada2_memos.jsonl (2026-08-08)",
        "procedencia": (
            "Rodada 1 de 2026-08-08 (75/75 sem erro), transcrita da saida de "
            "console por scripts/reconstruir_vereditos_2026-08-08.py - o cache de "
            "vereditos so passou a existir depois dela, e a cota diaria do "
            "Groq (100k TPD) foi consumida na mesma rodada. Matriz conferida "
            "por assert contra o relatorio original: TP=4 FN=4 TN=60 FP=7. "
            "evidencia_juiz existe apenas para as 11 discordancias - o "
            "relatorio da rodada 1 nao imprimia a das concordancias."
        ),
        "julgados": julgados,
        "erros": [],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"ok: 75 vereditos escritos em {SAIDA}")
    print(f"    matriz conferida: TP={tp} FN={fn} TN={tn} FP={fp}")


if __name__ == "__main__":
    main()
