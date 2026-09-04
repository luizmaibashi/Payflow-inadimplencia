import pytest

from app.contrato_disponibilidade import ModoExecucao
from app.estabilidade_coorte import ResultadoCoorte, StatusCoorte
from app.politica_uso_modelo import (
    DecisaoUsoModelo,
    PoliticaEvidencia,
    decidir_uso_coorte,
)


def _coorte(*, status=StatusCoorte.AVALIADA, auc=0.61):
    return ResultadoCoorte(
        coorte="2020-01",
        status=status,
        n_total=100,
        n_previsao_valida=100,
        n_target_amadurecido=100,
        n_avaliavel=100,
        inadimplentes_observados=10,
        taxa_inadimplencia=0.10,
        ic95_inadimplencia_inferior=0.05,
        ic95_inadimplencia_superior=0.18,
        auc=auc,
        brier=0.08,
        auc_ic95_inferior=0.55,
        auc_ic95_superior=0.67,
    )


def _politica(**sobrescritas):
    valores = {
        "auc_referencia": 0.61,
        "brier_referencia": 0.08,
        "minimo_observacoes": 100,
        "minimo_inadimplentes": 10,
        "tolerancia_auc": 0.03,
        "tolerancia_brier": 0.01,
        "auc_ic_inferior_minimo": 0.50,
    }
    valores.update(sobrescritas)
    return PoliticaEvidencia(**valores)


def test_modo_exploratorio_recebe_pesquisa_mesmo_com_auc_estavel():
    decisao = decidir_uso_coorte(
        _coorte(auc=0.61),
        modo=ModoExecucao.EXPLORATORIO,
        politica=_politica(),
    )

    assert decisao.status is DecisaoUsoModelo.PESQUISA


def test_modo_exploratorio_nao_esconde_queda_de_desempenho():
    decisao = decidir_uso_coorte(
        _coorte(auc=0.57),
        modo=ModoExecucao.EXPLORATORIO,
        politica=_politica(),
    )

    assert decisao.status is DecisaoUsoModelo.REVISAR


def test_modo_estrito_mantem_quando_auc_esta_dentro_da_tolerancia():
    decisao = decidir_uso_coorte(
        _coorte(auc=0.59),
        modo=ModoExecucao.ESTRITO,
        politica=_politica(),
    )

    assert decisao.status is DecisaoUsoModelo.MANTER


def test_modo_estrito_manda_revisar_quando_auc_cai_mais_de_tres_pontos():
    decisao = decidir_uso_coorte(
        _coorte(auc=0.57),
        modo=ModoExecucao.ESTRITO,
        politica=_politica(),
    )

    assert decisao.status is DecisaoUsoModelo.REVISAR


def test_queda_exata_na_tolerancia_ainda_mantem_o_modelo():
    decisao = decidir_uso_coorte(
        _coorte(auc=0.58),
        modo=ModoExecucao.ESTRITO,
        politica=_politica(),
    )

    assert decisao.status is DecisaoUsoModelo.MANTER


@pytest.mark.parametrize(
    "status",
    [
        StatusCoorte.AGUARDAR_MATURACAO,
        StatusCoorte.PREDICAO_INCOMPLETA,
        StatusCoorte.TARGET_SEM_VARIACAO,
        StatusCoorte.COORTE_VAZIA,
    ],
)
def test_coorte_sem_evidencia_suficiente_aguarda(status):
    decisao = decidir_uso_coorte(
        _coorte(status=status, auc=None),
        modo=ModoExecucao.ESTRITO,
        politica=_politica(),
    )

    assert decisao.status is DecisaoUsoModelo.AGUARDAR


def test_politica_com_referencia_fora_do_intervalo_e_rejeitada():
    with pytest.raises(ValueError, match="auc_referencia"):
        _politica(auc_referencia=1.01)


def test_amostra_abaixo_do_minimo_aguarda_em_vez_de_manter_modelo():
    coorte = _coorte()
    coorte = ResultadoCoorte(
        **{
            **coorte.__dict__,
            "n_total": 2,
            "n_previsao_valida": 2,
            "n_target_amadurecido": 2,
            "n_avaliavel": 2,
            "inadimplentes_observados": 1,
        }
    )

    decisao = decidir_uso_coorte(
        coorte,
        modo=ModoExecucao.ESTRITO,
        politica=_politica(),
    )

    assert decisao.status is DecisaoUsoModelo.AGUARDAR


def test_ic_da_auc_abaixo_do_minimo_aguarda_em_vez_de_liberar_modelo():
    coorte = _coorte()
    coorte = ResultadoCoorte(
        **{**coorte.__dict__, "auc_ic95_inferior": 0.49}
    )

    decisao = decidir_uso_coorte(
        coorte,
        modo=ModoExecucao.ESTRITO,
        politica=_politica(),
    )

    assert decisao.status is DecisaoUsoModelo.AGUARDAR


def test_brier_pior_que_a_tolerancia_manda_revisar_modelo():
    coorte = _coorte()
    coorte = ResultadoCoorte(**{**coorte.__dict__, "brier": 0.10})

    decisao = decidir_uso_coorte(
        coorte,
        modo=ModoExecucao.ESTRITO,
        politica=_politica(),
    )

    assert decisao.status is DecisaoUsoModelo.REVISAR
