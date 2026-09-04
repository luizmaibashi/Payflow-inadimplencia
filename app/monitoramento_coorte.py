"""Fluxo seguro de disponibilidade, score e monitoramento por coorte."""

from dataclasses import dataclass
from typing import Callable, Iterable, Mapping, Sequence

import pandas as pd

from app.contrato_disponibilidade import (
    BloqueioDisponibilidade,
    ModoExecucao,
    RegraDisponibilidade,
    RelatorioDisponibilidade,
    validar_disponibilidade_temporal,
)
from app.estabilidade_coorte import (
    PoliticaMaturacao,
    RelatorioEstabilidade,
    avaliar_estabilidade_coorte,
)
from app.politica_uso_modelo import DecisaoCoorte, DecisaoUsoModelo


@dataclass(frozen=True)
class ResultadoMonitoramentoCoorte:
    """Evidência de que o score só ocorreu após a validação da entrada."""

    disponibilidade: RelatorioDisponibilidade | None
    coortes: RelatorioEstabilidade | None
    decisao: DecisaoCoorte | None = None


def executar_monitoramento_coorte(
    dados: pd.DataFrame,
    *,
    features: Iterable[str],
    contrato: Mapping[str, RegraDisponibilidade],
    scorer: Callable[[pd.DataFrame], Sequence[float]],
    coluna_coorte: str = "coorte",
    coluna_target: str = "target",
    modo: ModoExecucao = ModoExecucao.ESTRITO,
    maturacao: PoliticaMaturacao | None = None,
    amostras_bootstrap: int = 200,
) -> ResultadoMonitoramentoCoorte:
    """Executa a ordem que protege o negócio: gate, score e boletim.

    `scorer` é injetado para que o orquestrador não escolha nem treine o modelo.
    Assim, ele pode ser testado sem dado real e não contorna o contrato de
    disponibilidade para obter uma previsão conveniente.
    """

    if not isinstance(dados, pd.DataFrame):
        raise TypeError("dados deve ser um pandas.DataFrame")
    if not callable(scorer):
        raise TypeError("scorer deve ser uma função chamável")
    if not isinstance(maturacao, PoliticaMaturacao):
        raise TypeError("maturacao deve ser uma PoliticaMaturacao")

    features_solicitadas = tuple(features)
    try:
        disponibilidade = validar_disponibilidade_temporal(
            dados,
            features=features_solicitadas,
            contrato=contrato,
            modo=modo,
        )
    except BloqueioDisponibilidade as bloqueio:
        return ResultadoMonitoramentoCoorte(
            disponibilidade=None,
            coortes=None,
            decisao=DecisaoCoorte(
                status=DecisaoUsoModelo.BLOQUEAR,
                motivo=str(bloqueio),
            ),
        )

    predicoes = pd.Series(scorer(dados.loc[:, list(features_solicitadas)]))
    if len(predicoes) != len(dados):
        raise ValueError("predicao retornada pelo scorer tem tamanho diferente da coorte")

    colunas_boletim = [
        coluna_coorte,
        coluna_target,
        maturacao.coluna_data_decisao,
    ]
    boletim = dados.loc[:, list(dict.fromkeys(colunas_boletim))].copy()
    boletim["predicao"] = predicoes.to_numpy()
    coortes = avaliar_estabilidade_coorte(
        boletim,
        coluna_coorte=coluna_coorte,
        coluna_predicao="predicao",
        coluna_target=coluna_target,
        maturacao=maturacao,
        amostras_bootstrap=amostras_bootstrap,
    )
    return ResultadoMonitoramentoCoorte(
        disponibilidade=disponibilidade,
        coortes=coortes,
    )
