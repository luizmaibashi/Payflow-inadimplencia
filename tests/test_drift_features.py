import math

import pandas as pd
import pytest

from app.drift_features import (
    PoliticaDrift,
    StatusDrift,
    avaliar_drift_features,
    formatar_resumo_drift_markdown,
)


def _politica(**sobrescritas):
    valores = {
        "minimo_nao_nulos": 2,
        "ks_alerta": 0.10,
        "ks_critico": 0.20,
        "ausencia_alerta": 0.10,
        "ausencia_critica": 0.20,
    }
    valores.update(sobrescritas)
    return PoliticaDrift(**valores)


def _avaliar(referencia, atual, *, politica=None):
    return avaliar_drift_features(
        pd.DataFrame({"renda": referencia}),
        pd.DataFrame({"renda": atual}),
        features=["renda"],
        coorte="2020-H1",
        politica=politica or _politica(),
    ).resultados[0]


def test_distribuicao_igual_fica_estavel():
    resultado = _avaliar([1, 2, 3, 4], [1, 2, 3, 4])

    assert resultado.status is StatusDrift.ESTAVEL


def test_mudanca_grande_na_distribuicao_fica_critica():
    resultado = _avaliar([0, 0, 0, 0], [1, 1, 1, 1])

    assert resultado.status is StatusDrift.CRITICO
    assert resultado.ks == pytest.approx(1.0)


def test_aumento_de_ausencia_pode_ser_critico_mesmo_com_valores_iguais():
    resultado = _avaliar([1, 2, 1, 2], [1, 2, None, None])

    assert resultado.status is StatusDrift.CRITICO
    assert resultado.delta_ausencia == pytest.approx(0.50)


def test_amostra_nao_nula_pequena_nunca_parece_estavel():
    resultado = _avaliar(
        [1, 2, 3],
        [1, None, None],
        politica=_politica(minimo_nao_nulos=2, ausencia_critica=0.90),
    )

    assert resultado.status is StatusDrift.INSUFICIENTE
    assert resultado.ks is None


def test_coorte_vazia_fica_insuficiente_em_vez_de_estavel():
    resultado = _avaliar([1, 2, 3], [])

    assert resultado.status is StatusDrift.INSUFICIENTE


def test_feature_constante_igual_nos_dois_lados_fica_estavel():
    resultado = _avaliar([7, 7, 7], [7, 7, 7])

    assert resultado.status is StatusDrift.ESTAVEL


@pytest.mark.parametrize("valor", ["erro", math.inf, -math.inf])
def test_valor_nao_numerico_ou_infinito_falha_explicito(valor):
    with pytest.raises(ValueError, match="renda"):
        _avaliar([1, 2, 3], [1, 2, valor])


def test_feature_ausente_mostra_o_nome_da_coluna():
    with pytest.raises(ValueError, match="renda"):
        avaliar_drift_features(
            pd.DataFrame({"outra": [1, 2]}),
            pd.DataFrame({"renda": [1, 2]}),
            features=["renda"],
            coorte="2020-H1",
            politica=_politica(),
        )


def test_limite_critico_precisa_ser_maior_que_alerta():
    with pytest.raises(ValueError, match="ks_critico"):
        _politica(ks_alerta=0.20, ks_critico=0.10)


def test_resumo_mostra_contagem_e_feature_de_maior_gravidade():
    relatorio = avaliar_drift_features(
        pd.DataFrame({"estavel": [1, 2, 3, 4], "mudou": [0, 0, 0, 0]}),
        pd.DataFrame({"estavel": [1, 2, 3, 4], "mudou": [1, 1, 1, 1]}),
        features=["estavel", "mudou"],
        coorte="2020-H1",
        politica=_politica(),
    )

    resumo = formatar_resumo_drift_markdown([relatorio])

    assert "| 2020-H1 | 1 | 0 | 1 | 0 | mudou | 1.0000 |" in resumo


def test_resumo_usa_texto_compativel_com_terminal_windows():
    relatorio = avaliar_drift_features(
        pd.DataFrame({"renda": [1, 2, 3]}),
        pd.DataFrame({"renda": [1, 2, 3]}),
        features=["renda"],
        coorte="2020-H1",
        politica=_politica(),
    )

    resumo = formatar_resumo_drift_markdown([relatorio])

    assert "Delta ausência" in resumo
