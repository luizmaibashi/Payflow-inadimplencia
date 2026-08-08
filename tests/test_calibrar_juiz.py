"""Testes das funcoes puras de scripts/calibrar_juiz.py (debito #10).

So a matematica (Wilson, matriz de confusao) - o fluxo de IO/API do
`main()` nao e testado aqui de proposito, mesma razao do resto do
projeto: exige API real e chave, e nao e logica deterministica testavel
sem rede.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from calibrar_juiz import calcular_tpr_tnr, intervalo_wilson  # noqa: E402


def test_wilson_caso_perfeito_fica_dentro_de_0_1():
    baixo, alto = intervalo_wilson(10, 10)
    assert 0.0 <= baixo <= alto <= 1.0


def test_wilson_n_zero_nao_quebra():
    assert intervalo_wilson(0, 0) == (0.0, 0.0)


def test_wilson_intervalo_encolhe_com_mais_n():
    baixo_pequeno, alto_pequeno = intervalo_wilson(8, 10)
    baixo_grande, alto_grande = intervalo_wilson(80, 100)
    largura_pequena = alto_pequeno - baixo_pequeno
    largura_grande = alto_grande - baixo_grande
    assert largura_grande < largura_pequena


def test_tpr_tnr_juiz_perfeito():
    pares = [("FALHA", "FALHA"), ("OK", "OK"), ("FALHA", "FALHA"), ("OK", "OK")]
    m = calcular_tpr_tnr(pares)
    assert m["tpr"] == 1.0
    assert m["tnr"] == 1.0
    assert m["tp"] == 2 and m["tn"] == 2 and m["fp"] == 0 and m["fn"] == 0


def test_tpr_tnr_juiz_perde_todas_as_falhas():
    pares = [("OK", "FALHA"), ("OK", "FALHA"), ("OK", "OK")]
    m = calcular_tpr_tnr(pares)
    assert m["tpr"] == 0.0  # juiz nunca detectou a falha real
    assert m["tnr"] == 1.0
    assert m["fn"] == 2


def test_tpr_none_quando_nenhum_falha_no_humano():
    pares = [("OK", "OK"), ("FALHA", "OK")]
    m = calcular_tpr_tnr(pares)
    assert m["tpr"] is None  # sem caso FALHA no humano, TPR nao e definido
    assert m["n_falha_humano"] == 0
    assert m["ic_tpr"] is None
