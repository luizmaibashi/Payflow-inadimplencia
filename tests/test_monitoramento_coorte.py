import pandas as pd
import pytest

from app.contrato_disponibilidade import (
    BloqueioDisponibilidade,
    ModoExecucao,
    RegraDisponibilidade,
    StatusDisponibilidade,
)
from app.estabilidade_coorte import PoliticaMaturacao, StatusCoorte
from app.politica_uso_modelo import DecisaoUsoModelo
from app.monitoramento_coorte import executar_monitoramento_coorte


def _dados():
    return pd.DataFrame(
        {
            "renda_declarada": [1000.0, 2000.0, 3000.0, 4000.0],
            "coorte": ["2020-01"] * 4,
            "date_decision": ["2020-01-01"] * 4,
            "target": [0, 0, 1, 1],
        }
    )


def _contrato(status=StatusDisponibilidade.PERMITIDA):
    return {
        "renda_declarada": RegraDisponibilidade(
            feature="renda_declarada",
            status=status,
            evidencia="Campo recebido na proposta.",
        )
    }


def _maturacao():
    return PoliticaMaturacao(
        coluna_data_decisao="date_decision",
        data_referencia="2020-03-01",
        janela_dias=30,
    )


def test_fluxo_valida_antes_de_pontuar_e_depois_entrega_boletim():
    chamadas = []

    def scorer(features):
        chamadas.append(features.columns.tolist())
        return [0.10, 0.20, 0.80, 0.90]

    resultado = executar_monitoramento_coorte(
        _dados(),
        features=["renda_declarada"],
        contrato=_contrato(),
        scorer=scorer,
        maturacao=_maturacao(),
    )

    assert chamadas == [["renda_declarada"]]
    assert resultado.disponibilidade.modo is ModoExecucao.ESTRITO
    assert resultado.coortes.coortes[0].status is StatusCoorte.AVALIADA
    assert resultado.coortes.coortes[0].auc == pytest.approx(1.0)


def test_gate_retorna_bloqueio_explicito_antes_de_chamar_o_scorer():
    chamou_scorer = False

    def scorer(_):
        nonlocal chamou_scorer
        chamou_scorer = True
        return [0.10]

    resultado = executar_monitoramento_coorte(
        _dados(),
        features=["renda_declarada"],
        contrato=_contrato(StatusDisponibilidade.DESCONHECIDA),
        scorer=scorer,
        maturacao=_maturacao(),
    )

    assert chamou_scorer is False
    assert resultado.decisao.status is DecisaoUsoModelo.BLOQUEAR
    assert resultado.coortes is None


def test_modo_exploratorio_aparece_no_relatorio_final():
    resultado = executar_monitoramento_coorte(
        _dados(),
        features=["renda_declarada"],
        contrato=_contrato(StatusDisponibilidade.PROXY_SEMANTICA),
        scorer=lambda _: [0.10, 0.20, 0.80, 0.90],
        modo=ModoExecucao.EXPLORATORIO,
        maturacao=_maturacao(),
    )

    assert resultado.disponibilidade.modo is ModoExecucao.EXPLORATORIO


def test_predicao_com_tamanho_diferente_da_coorte_falha_explicita():
    with pytest.raises(ValueError, match="tamanho"):
        executar_monitoramento_coorte(
            _dados(),
            features=["renda_declarada"],
            contrato=_contrato(),
            scorer=lambda _: [0.10],
            maturacao=_maturacao(),
        )


def test_coorte_vazia_nao_vira_sucesso_silencioso():
    dados = pd.DataFrame(columns=["renda_declarada", "coorte", "date_decision", "target"])

    resultado = executar_monitoramento_coorte(
        dados,
        features=["renda_declarada"],
        contrato=_contrato(),
        scorer=lambda _: [],
        maturacao=_maturacao(),
    )

    assert resultado.coortes.coortes[0].status is StatusCoorte.COORTE_VAZIA
