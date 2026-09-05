import math

import pandas as pd
import pytest

from app.calibracao_faixas import (
    PoliticaCalibracao,
    StatusCalibracao,
    avaliar_calibracao_faixas,
    criar_limites_quanticos,
    formatar_calibracao_markdown,
)


def _politica(**sobrescritas):
    valores = {
        "minimo_observacoes": 2,
        "minimo_inadimplentes": 1,
        "tolerancia_absoluta": 0.02,
    }
    valores.update(sobrescritas)
    return PoliticaCalibracao(**valores)


def _avaliar(predicoes, targets, *, limites=(0.0, 0.5, 1.0), politica=None):
    return avaliar_calibracao_faixas(
        pd.DataFrame({"predicao": predicoes, "target": targets}),
        limites=limites,
        coorte="2020-H2",
        politica=politica or _politica(),
    )


def test_limites_sao_derivados_dos_quantis_do_treino():
    limites = criar_limites_quanticos(
        pd.Series([0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08]),
        n_faixas=4,
    )

    assert limites == pytest.approx((0.0, 0.0275, 0.045, 0.0625, 1.0))


def test_limites_repetidos_falham_em_vez_de_reduzir_faixas_em_silencio():
    with pytest.raises(ValueError, match="limites distintos"):
        criar_limites_quanticos(pd.Series([0.10] * 20), n_faixas=10)


@pytest.mark.parametrize("valor", [pd.NA, "erro", math.inf, -0.01, 1.01])
def test_score_invalido_falha_explicito(valor):
    with pytest.raises(ValueError, match="predicao"):
        criar_limites_quanticos(pd.Series([0.10, valor, 0.20]), n_faixas=2)


def test_gap_pequeno_fica_aproximado():
    resultado = _avaliar(
        [0.24, 0.26, 0.74, 0.76],
        [0, 1, 1, 1],
        politica=_politica(tolerancia_absoluta=0.26),
    )

    assert resultado.resultados[1].status is StatusCalibracao.APROXIMADA


def test_observado_maior_que_previsto_indica_subestimacao_de_risco():
    resultado = _avaliar([0.10, 0.20], [1, 1])

    assert resultado.resultados[0].status is StatusCalibracao.SUBESTIMA_RISCO


def test_observado_menor_que_previsto_indica_superestimacao_de_risco():
    resultado = _avaliar([0.80, 0.90], [0, 1])

    assert resultado.resultados[1].status is StatusCalibracao.SUPERESTIMA_RISCO


def test_poucas_observacoes_nao_parecem_calibradas():
    resultado = _avaliar(
        [0.10, 0.20],
        [0, 1],
        politica=_politica(minimo_observacoes=3),
    )

    assert resultado.resultados[0].status is StatusCalibracao.INSUFICIENTE


def test_poucos_eventos_nao_parecem_calibrados():
    resultado = _avaliar(
        [0.10, 0.20, 0.30],
        [0, 0, 0],
        politica=_politica(minimo_inadimplentes=1),
    )

    assert resultado.resultados[0].status is StatusCalibracao.INSUFICIENTE


def test_observacao_no_limite_entra_em_uma_unica_faixa():
    resultado = _avaliar([0.49, 0.50, 0.51], [0, 1, 1])

    assert sum(item.n_observacoes for item in resultado.resultados) == 3


def test_taxa_observada_traz_intervalo_e_gap_com_sinal():
    resultado = _avaliar([0.10, 0.20], [0, 1]).resultados[0]

    assert resultado.ic95_inferior < resultado.taxa_observada
    assert resultado.ic95_superior > resultado.taxa_observada
    assert resultado.gap_observado_previsto == pytest.approx(0.35)


def test_markdown_traduz_direcao_do_erro_para_negocio():
    markdown = formatar_calibracao_markdown(
        [_avaliar([0.10, 0.20], [1, 1])]
    )

    assert "modelo estima menos inadimplência" in markdown


def test_markdown_mostra_zero_incluido_na_primeira_faixa():
    markdown = formatar_calibracao_markdown(
        [_avaliar([0.0, 0.20], [0, 1])]
    )

    assert "[0.00%; 50.00%]" in markdown
