"""Contrato exploratório para variáveis aparentes de proposta no Stability."""

from app.contrato_disponibilidade import RegraDisponibilidade, StatusDisponibilidade


def contrato_proxy_proposta() -> dict[str, RegraDisponibilidade]:
    """Retorna proxies semânticos sem promovê-los a evidência point-in-time.

    As descrições vêm de ``feature_definitions.csv`` da competição. Elas sugerem
    disponibilidade no fluxo de proposta, mas não substituem a confirmação de
    origem e timestamp que seria exigida de uma instituição real.
    """

    evidencia_padrao = (
        "Definição oficial da competição sugere campo da proposta; "
        "instante de geração não comprovado."
    )
    return {
        "annuity_780A": RegraDisponibilidade(
            feature="annuity_780A",
            status=StatusDisponibilidade.PROXY_SEMANTICA,
            evidencia=f"Monthly annuity amount. {evidencia_padrao}",
        ),
        "credamount_770A": RegraDisponibilidade(
            feature="credamount_770A",
            status=StatusDisponibilidade.PROXY_SEMANTICA,
            evidencia=f"Loan amount or credit card limit. {evidencia_padrao}",
        ),
        "downpmt_116A": RegraDisponibilidade(
            feature="downpmt_116A",
            status=StatusDisponibilidade.PROXY_SEMANTICA,
            evidencia=f"Amount of downpayment. {evidencia_padrao}",
        ),
        "price_1097A": RegraDisponibilidade(
            feature="price_1097A",
            status=StatusDisponibilidade.PROXY_SEMANTICA,
            evidencia=f"Credit price. {evidencia_padrao}",
        ),
        "maininc_215A": RegraDisponibilidade(
            feature="maininc_215A",
            status=StatusDisponibilidade.PROXY_SEMANTICA,
            evidencia=f"Client's primary income amount. {evidencia_padrao}",
        ),
        "inittransactionamount_650A": RegraDisponibilidade(
            feature="inittransactionamount_650A",
            status=StatusDisponibilidade.PROXY_SEMANTICA,
            evidencia=f"Initial transaction amount of the credit application. {evidencia_padrao}",
        ),
    }
