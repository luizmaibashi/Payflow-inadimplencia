import pandas as pd
import pytest

from app.calibracao_faixas import PoliticaCalibracao
from app.drift_features import PoliticaDrift
from app.experimento_proxy_estabilidade import (
    FEATURES_PROXY,
    ConfiguracaoExperimentoProxy,
    executar_experimento_proxy,
    formatar_relatorio_markdown,
    montar_base_proxy,
    rotular_particao_temporal,
)
from app.politica_uso_modelo import PoliticaEvidencia
from app.snapshot_monitoramento import construir_snapshot


def _base():
    return pd.DataFrame(
        {
            "case_id": [1, 2, 3],
            "date_decision": ["2019-09-30", "2019-10-01", "2020-07-01"],
            "target": [0, 1, 0],
        }
    )


def _static():
    dados = {"case_id": [1, 2, 3]}
    dados.update({feature: [1.0, 2.0, 3.0] for feature in FEATURES_PROXY})
    return pd.DataFrame(dados)


def test_datas_sao_rotuladas_sem_vazar_coorte_futura_no_treino():
    rotulos = rotular_particao_temporal(
        pd.Series(
            ["2019-09-30", "2019-10-01", "2020-01-01", "2020-07-01"]
        )
    )

    assert rotulos.tolist() == ["TREINO", "2019-Q4", "2020-H1", "2020-H2"]


def test_data_fora_das_janelas_conhecidas_falha_explicita():
    with pytest.raises(ValueError, match="janela temporal"):
        rotular_particao_temporal(pd.Series(["2021-01-01"]))


def test_case_id_duplicado_na_tabela_estatica_falha_fechado():
    static = pd.concat([_static(), _static().iloc[[0]]], ignore_index=True)

    with pytest.raises(ValueError, match="duplicado"):
        montar_base_proxy(_base(), [static])


def test_case_sem_registro_estatico_falha_em_vez_de_sumir_na_juncao():
    with pytest.raises(ValueError, match="sem features estáticas"):
        montar_base_proxy(_base(), [_static().iloc[:2]])


def test_configuracao_exige_maturacao_declarada():
    with pytest.raises(ValueError, match="janela_dias"):
        ConfiguracaoExperimentoProxy(
            data_referencia="2021-01-01",
            janela_dias=0,
        )


@pytest.fixture
def resultado_experimento_com_drift():
    datas = (
        ["2019-09-20"] * 8
        + ["2019-10-15"] * 4
        + ["2020-03-15"] * 4
        + ["2020-08-15"] * 4
    )
    dados = pd.DataFrame(
        {
            "case_id": range(20),
            "date_decision": datas,
            "target": [0, 1] * 10,
        }
    )
    for indice, feature in enumerate(FEATURES_PROXY):
        dados[feature] = [float((linha + indice) % 2) for linha in range(20)]
    dados.loc[12:15, FEATURES_PROXY[0]] = 10.0
    dados["coorte"] = rotular_particao_temporal(dados["date_decision"])

    return executar_experimento_proxy(
        dados,
        configuracao=ConfiguracaoExperimentoProxy(
            data_referencia="2021-01-04",
            janela_dias=90,
            amostras_bootstrap=100,
        ),
        politica=PoliticaEvidencia(
            auc_referencia=0.50,
            brier_referencia=0.25,
            minimo_observacoes=4,
            minimo_inadimplentes=2,
            tolerancia_auc=0.20,
            tolerancia_brier=0.20,
            auc_ic_inferior_minimo=0.0,
        ),
        politica_drift=PoliticaDrift(
            minimo_nao_nulos=2,
            ks_alerta=0.10,
            ks_critico=0.20,
            ausencia_alerta=0.10,
            ausencia_critica=0.20,
        ),
        politica_calibracao=PoliticaCalibracao(
            minimo_observacoes=2,
            minimo_inadimplentes=1,
            tolerancia_absoluta=0.20,
        ),
        n_faixas_calibracao=2,
    )


def test_experimento_calcula_seis_features_em_cada_coorte(
    resultado_experimento_com_drift,
):
    tamanhos = [
        len(relatorio.resultados)
        for relatorio in resultado_experimento_com_drift.drift_coortes
    ]

    assert tamanhos == [6, 6, 6]


def test_relatorio_integrado_exibe_resumo_de_drift(resultado_experimento_com_drift):
    relatorio = formatar_relatorio_markdown(resultado_experimento_com_drift)

    assert "## Drift das features contra o treino" in relatorio


def test_experimento_usa_as_mesmas_faixas_de_calibracao_em_todas_as_coortes(
    resultado_experimento_com_drift,
):
    limites = {
        relatorio.limites
        for relatorio in resultado_experimento_com_drift.calibracao_coortes
    }

    assert len(limites) == 1


def test_relatorio_integrado_exibe_calibracao_por_faixa(
    resultado_experimento_com_drift,
):
    relatorio = formatar_relatorio_markdown(resultado_experimento_com_drift)

    assert "## Calibração por faixa de score" in relatorio


def test_snapshot_do_experimento_carrega_metricas_agregadas(
    resultado_experimento_com_drift,
):
    snapshot = construir_snapshot(
        resultado_experimento_com_drift,
        gerado_em="2026-09-04T12:00:00Z",
    )

    assert len(snapshot.coortes) == 3
