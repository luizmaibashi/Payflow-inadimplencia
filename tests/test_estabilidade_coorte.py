import pandas as pd
import pytest

from app.estabilidade_coorte import (
    PoliticaMaturacao,
    StatusCoorte,
    avaliar_estabilidade_coorte,
)


def test_coorte_completa_retorna_metricas_e_incerteza_da_inadimplencia():
    dados = pd.DataFrame(
        {
            "coorte": ["2020-01"] * 4,
            "predicao": [0.10, 0.20, 0.80, 0.90],
            "target": [0, 0, 1, 1],
        }
    )

    resultado = avaliar_estabilidade_coorte(dados).coortes[0]

    assert resultado.status is StatusCoorte.AVALIADA
    assert resultado.n_total == 4
    assert resultado.n_target_amadurecido == 4
    assert resultado.n_avaliavel == 4
    assert resultado.taxa_inadimplencia == pytest.approx(0.5)
    assert resultado.ic95_inadimplencia_inferior < resultado.taxa_inadimplencia
    assert resultado.ic95_inadimplencia_superior > resultado.taxa_inadimplencia
    assert resultado.auc == pytest.approx(1.0)
    assert resultado.brier == pytest.approx(0.025)


def test_coorte_sem_target_aguarda_maturacao_sem_inventar_auc_ou_brier():
    dados = pd.DataFrame(
        {
            "coorte": ["2020-02"] * 2,
            "predicao": [0.20, 0.70],
            "target": [pd.NA, pd.NA],
        }
    )

    resultado = avaliar_estabilidade_coorte(dados).coortes[0]

    assert resultado.status is StatusCoorte.AGUARDAR_MATURACAO
    assert resultado.n_target_amadurecido == 0
    assert resultado.auc is None
    assert resultado.brier is None


def test_coorte_com_uma_classe_nao_calcula_auc_falsa():
    dados = pd.DataFrame(
        {
            "coorte": ["2020-03"] * 3,
            "predicao": [0.10, 0.20, 0.30],
            "target": [0, 0, 0],
        }
    )

    resultado = avaliar_estabilidade_coorte(dados).coortes[0]

    assert resultado.status is StatusCoorte.TARGET_SEM_VARIACAO
    assert resultado.taxa_inadimplencia == 0.0
    assert resultado.auc is None


def test_dataframe_vazio_vira_coorte_vazia_em_vez_de_erro():
    dados = pd.DataFrame(columns=["coorte", "predicao", "target"])

    resultado = avaliar_estabilidade_coorte(dados).coortes[0]

    assert resultado.status is StatusCoorte.COORTE_VAZIA
    assert resultado.n_total == 0
    assert resultado.auc is None


def test_predicao_ausente_e_reportada_sem_calcular_metricas_parciais():
    dados = pd.DataFrame(
        {
            "coorte": ["2020-04"] * 2,
            "predicao": [0.10, pd.NA],
            "target": [0, 1],
        }
    )

    resultado = avaliar_estabilidade_coorte(dados).coortes[0]

    assert resultado.status is StatusCoorte.PREDICAO_INCOMPLETA
    assert resultado.n_previsao_valida == 1
    assert resultado.auc is None


@pytest.mark.parametrize("predicao", [-0.01, 1.01, "nao-numerica"])
def test_predicao_fora_do_intervalo_ou_nao_numerica_e_rejeitada(predicao):
    dados = pd.DataFrame(
        {
            "coorte": ["2020-05"],
            "predicao": [predicao],
            "target": [0],
        }
    )

    with pytest.raises(ValueError, match="predicao"):
        avaliar_estabilidade_coorte(dados)


def test_target_fora_do_binario_e_rejeitado():
    dados = pd.DataFrame(
        {
            "coorte": ["2020-05"],
            "predicao": [0.20],
            "target": [2],
        }
    )

    with pytest.raises(ValueError, match="target"):
        avaliar_estabilidade_coorte(dados)


def test_target_preenchido_antes_da_janela_ainda_aguarda_maturacao():
    dados = pd.DataFrame(
        {
            "coorte": ["2020-01"] * 2,
            "date_decision": ["2020-01-10", "2020-01-11"],
            "predicao": [0.10, 0.90],
            "target": [0, 1],
        }
    )

    resultado = avaliar_estabilidade_coorte(
        dados,
        maturacao=PoliticaMaturacao(
            coluna_data_decisao="date_decision",
            data_referencia="2020-02-01",
            janela_dias=30,
        ),
    ).coortes[0]

    assert resultado.status is StatusCoorte.AGUARDAR_MATURACAO
    assert resultado.n_elegivel_maturacao == 0
    assert resultado.auc is None
