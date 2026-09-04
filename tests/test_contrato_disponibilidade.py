import pandas as pd
import pytest

from app.contrato_disponibilidade import (
    BloqueioDisponibilidade,
    ModoExecucao,
    RegraDisponibilidade,
    StatusDisponibilidade,
    validar_disponibilidade_temporal,
)


def _contrato_permitido(*, coluna_data: str | None = None):
    return {
        "renda_declarada": RegraDisponibilidade(
            feature="renda_declarada",
            status=StatusDisponibilidade.PERMITIDA,
            evidencia="Informada pelo solicitante no momento da proposta.",
            coluna_data=coluna_data,
        )
    }


def test_feature_permitida_e_disponivel_antes_da_decisao_passam():
    dados = pd.DataFrame(
        {
            "renda_declarada": [1500.0, 2500.0],
            "data_origem": ["2020-01-01", "2020-01-02"],
            "date_decision": ["2020-01-02", "2020-01-02"],
        }
    )

    relatorio = validar_disponibilidade_temporal(
        dados,
        features=["renda_declarada"],
        contrato=_contrato_permitido(coluna_data="data_origem"),
    )

    assert relatorio.registros_validados == 2


def test_feature_nova_sem_contrato_e_bloqueada_em_vez_de_passar_em_silencio():
    dados = pd.DataFrame({"feature_nova": [1.0]})

    with pytest.raises(BloqueioDisponibilidade, match="feature_nova"):
        validar_disponibilidade_temporal(
            dados,
            features=["feature_nova"],
            contrato={},
        )


@pytest.mark.parametrize(
    "status",
    [StatusDisponibilidade.BLOQUEADA, StatusDisponibilidade.DESCONHECIDA],
)
def test_feature_nao_permitida_bloqueia_a_execucao(status):
    dados = pd.DataFrame({"renda_declarada": [1500.0]})
    contrato = _contrato_permitido()
    contrato["renda_declarada"] = RegraDisponibilidade(
        feature="renda_declarada",
        status=status,
        evidencia="A origem temporal não foi comprovada.",
    )

    with pytest.raises(BloqueioDisponibilidade, match="renda_declarada"):
        validar_disponibilidade_temporal(
            dados,
            features=["renda_declarada"],
            contrato=contrato,
        )


def test_proxy_semantica_e_bloqueada_no_modo_estrito_padrao():
    dados = pd.DataFrame({"renda_declarada": [1500.0]})
    contrato = _contrato_permitido()
    contrato["renda_declarada"] = RegraDisponibilidade(
        feature="renda_declarada",
        status=StatusDisponibilidade.PROXY_SEMANTICA,
        evidencia="Descrição sugere origem na proposta; tempo não comprovado.",
    )

    with pytest.raises(BloqueioDisponibilidade, match="PROXY_SEMANTICA"):
        validar_disponibilidade_temporal(
            dados,
            features=["renda_declarada"],
            contrato=contrato,
        )


def test_proxy_semantica_so_passa_no_modo_exploratorio_e_registra_o_modo():
    dados = pd.DataFrame({"renda_declarada": [1500.0]})
    contrato = _contrato_permitido()
    contrato["renda_declarada"] = RegraDisponibilidade(
        feature="renda_declarada",
        status=StatusDisponibilidade.PROXY_SEMANTICA,
        evidencia="Descrição sugere origem na proposta; tempo não comprovado.",
    )

    relatorio = validar_disponibilidade_temporal(
        dados,
        features=["renda_declarada"],
        contrato=contrato,
        modo=ModoExecucao.EXPLORATORIO,
    )

    assert relatorio.modo is ModoExecucao.EXPLORATORIO


def test_feature_desconhecida_continua_bloqueada_no_modo_exploratorio():
    dados = pd.DataFrame({"renda_declarada": [1500.0]})
    contrato = _contrato_permitido()
    contrato["renda_declarada"] = RegraDisponibilidade(
        feature="renda_declarada",
        status=StatusDisponibilidade.DESCONHECIDA,
        evidencia="Não há prova de disponibilidade.",
    )

    with pytest.raises(BloqueioDisponibilidade, match="DESCONHECIDA"):
        validar_disponibilidade_temporal(
            dados,
            features=["renda_declarada"],
            contrato=contrato,
            modo=ModoExecucao.EXPLORATORIO,
        )


def test_feature_contratada_mas_ausente_no_dado_bloqueia_a_execucao():
    dados = pd.DataFrame({"outra_coluna": [1.0]})

    with pytest.raises(BloqueioDisponibilidade, match="renda_declarada"):
        validar_disponibilidade_temporal(
            dados,
            features=["renda_declarada"],
            contrato=_contrato_permitido(),
        )


@pytest.mark.parametrize("data_origem", [None, "nao-e-data"])
def test_data_de_origem_nula_ou_malformada_bloqueia(data_origem):
    dados = pd.DataFrame(
        {
            "renda_declarada": [1500.0],
            "data_origem": [data_origem],
            "date_decision": ["2020-01-02"],
        }
    )

    with pytest.raises(BloqueioDisponibilidade, match="data_origem"):
        validar_disponibilidade_temporal(
            dados,
            features=["renda_declarada"],
            contrato=_contrato_permitido(coluna_data="data_origem"),
        )


def test_data_posterior_a_decisao_bloqueia_e_informa_quantidade_afetada():
    dados = pd.DataFrame(
        {
            "renda_declarada": [1500.0, 2500.0],
            "data_origem": ["2020-01-03", "2020-01-02"],
            "date_decision": ["2020-01-02", "2020-01-02"],
        }
    )

    with pytest.raises(BloqueioDisponibilidade, match="1 registro"):
        validar_disponibilidade_temporal(
            dados,
            features=["renda_declarada"],
            contrato=_contrato_permitido(coluna_data="data_origem"),
        )


def test_coluna_da_decisao_ausente_bloqueia_quando_ha_regra_temporal():
    dados = pd.DataFrame(
        {
            "renda_declarada": [1500.0],
            "data_origem": ["2020-01-02"],
        }
    )

    with pytest.raises(BloqueioDisponibilidade, match="date_decision"):
        validar_disponibilidade_temporal(
            dados,
            features=["renda_declarada"],
            contrato=_contrato_permitido(coluna_data="data_origem"),
        )


@pytest.mark.parametrize("date_decision", [None, "nao-e-data"])
def test_data_de_decisao_nula_ou_malformada_bloqueia(date_decision):
    dados = pd.DataFrame(
        {
            "renda_declarada": [1500.0],
            "data_origem": ["2020-01-02"],
            "date_decision": [date_decision],
        }
    )

    with pytest.raises(BloqueioDisponibilidade, match="date_decision"):
        validar_disponibilidade_temporal(
            dados,
            features=["renda_declarada"],
            contrato=_contrato_permitido(coluna_data="data_origem"),
        )


def test_regra_permitida_sem_evidencia_e_rejeitada_ao_criar_contrato():
    with pytest.raises(ValueError, match="evidência"):
        RegraDisponibilidade(
            feature="renda_declarada",
            status=StatusDisponibilidade.PERMITIDA,
            evidencia="",
        )


def test_datas_com_timezone_misto_sao_comparadas_em_utc_sem_typeerror_bruto():
    dados = pd.DataFrame(
        {
            "renda_declarada": [1500.0],
            "data_origem": ["2020-01-01T00:00:00Z"],
            "date_decision": ["2020-01-02"],
        }
    )

    relatorio = validar_disponibilidade_temporal(
        dados,
        features=["renda_declarada"],
        contrato=_contrato_permitido(coluna_data="data_origem"),
    )

    assert relatorio.registros_validados == 1
