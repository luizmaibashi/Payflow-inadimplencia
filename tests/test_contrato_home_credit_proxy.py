from app.contrato_disponibilidade import StatusDisponibilidade
from app.contrato_home_credit_proxy import contrato_proxy_proposta


def test_contrato_proxy_lista_as_seis_features_e_nao_as_promove_para_estrito():
    contrato = contrato_proxy_proposta()

    assert set(contrato) == {
        "annuity_780A",
        "credamount_770A",
        "downpmt_116A",
        "price_1097A",
        "maininc_215A",
        "inittransactionamount_650A",
    }
    assert all(regra.status is StatusDisponibilidade.PROXY_SEMANTICA for regra in contrato.values())


def test_contrato_proxy_retorna_nova_colecao_para_evitar_mutacao_silenciosa():
    primeiro = contrato_proxy_proposta()
    segundo = contrato_proxy_proposta()

    primeiro.pop("annuity_780A")

    assert "annuity_780A" in segundo
