"""Catraca fail-closed para dados usados em decisões de crédito.

Uma métrica de modelo só é confiável quando as entradas existiam no instante em
que a decisão seria tomada. Este módulo impede que ausência de prova seja tratada
como permissão.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping

import pandas as pd


class StatusDisponibilidade(str, Enum):
    """Estado de uma feature no instante da decisão."""

    PERMITIDA = "PERMITIDA"
    PROXY_SEMANTICA = "PROXY_SEMANTICA"
    BLOQUEADA = "BLOQUEADA"
    DESCONHECIDA = "DESCONHECIDA"


class ModoExecucao(str, Enum):
    """Delimita pesquisa exploratória e uso com evidência point-in-time."""

    ESTRITO = "ESTRITO"
    EXPLORATORIO = "EXPLORATORIO"


@dataclass(frozen=True)
class RegraDisponibilidade:
    """Evidência mínima para uma feature ser usada no modelo."""

    feature: str
    status: StatusDisponibilidade
    evidencia: str
    coluna_data: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.feature, str) or not self.feature.strip():
            raise ValueError("feature deve ser uma string não vazia")
        if not isinstance(self.status, StatusDisponibilidade):
            raise TypeError("status deve ser um StatusDisponibilidade")
        if not isinstance(self.evidencia, str) or not self.evidencia.strip():
            raise ValueError("evidência deve explicar por que a feature pode ser usada")
        if self.coluna_data is not None and (
            not isinstance(self.coluna_data, str) or not self.coluna_data.strip()
        ):
            raise ValueError("coluna_data deve ser uma string não vazia ou None")


@dataclass(frozen=True)
class DetalheBloqueio:
    """Motivo rastreável de uma execução não poder continuar."""

    feature: str
    motivo: str
    registros_afetados: int | None = None


class BloqueioDisponibilidade(ValueError):
    """Interrompe uma rodada quando não há evidência temporal suficiente."""

    def __init__(self, detalhe: DetalheBloqueio) -> None:
        self.detalhe = detalhe
        mensagem = f"Bloqueio de disponibilidade em '{detalhe.feature}': {detalhe.motivo}"
        super().__init__(mensagem)


@dataclass(frozen=True)
class RelatorioDisponibilidade:
    """Confirma que todas as features solicitadas passaram pela catraca."""

    features_validadas: tuple[str, ...]
    registros_validados: int
    modo: ModoExecucao


def _bloquear(
    feature: str,
    motivo: str,
    *,
    registros_afetados: int | None = None,
) -> None:
    raise BloqueioDisponibilidade(
        DetalheBloqueio(
            feature=feature,
            motivo=motivo,
            registros_afetados=registros_afetados,
        )
    )


def _converter_datas_ou_bloquear(
    serie: pd.Series,
    *,
    feature: str,
) -> pd.Series:
    datas = pd.to_datetime(serie, errors="coerce", format="mixed", utc=True)
    invalidas = int(datas.isna().sum())
    if invalidas:
        _bloquear(
            feature,
            f"{invalidas} registro(s) com data nula ou malformada",
            registros_afetados=invalidas,
        )
    return datas


def validar_disponibilidade_temporal(
    dados: pd.DataFrame,
    *,
    features: Iterable[str],
    contrato: Mapping[str, RegraDisponibilidade],
    coluna_decisao: str = "date_decision",
    modo: ModoExecucao = ModoExecucao.ESTRITO,
) -> RelatorioDisponibilidade:
    """Valida se as features existiam até a data da decisão.

    A função falha fechada: uma feature sem contrato ou sem prova temporal não
    recebe o benefício da dúvida. Assim, uma nova coluna não melhora a AUC por
    acidente apenas porque alguém esqueceu de atualizar uma lista manual.
    """

    if not isinstance(dados, pd.DataFrame):
        raise TypeError("dados deve ser um pandas.DataFrame")
    if not isinstance(coluna_decisao, str) or not coluna_decisao.strip():
        raise ValueError("coluna_decisao deve ser uma string não vazia")
    if not isinstance(modo, ModoExecucao):
        raise TypeError("modo deve ser um ModoExecucao")

    features_solicitadas = tuple(features)
    if not features_solicitadas:
        raise ValueError("features deve conter ao menos uma feature")
    if any(not isinstance(feature, str) or not feature.strip() for feature in features_solicitadas):
        raise TypeError("cada feature deve ser uma string não vazia")

    regras_temporais: list[RegraDisponibilidade] = []
    for feature in features_solicitadas:
        regra = contrato.get(feature)
        if regra is None:
            _bloquear(feature, "feature sem contrato de disponibilidade")
        if regra.feature != feature:
            _bloquear(feature, "contrato inconsistente com o nome da feature")
        permitida_no_modo = regra.status is StatusDisponibilidade.PERMITIDA or (
            modo is ModoExecucao.EXPLORATORIO
            and regra.status is StatusDisponibilidade.PROXY_SEMANTICA
        )
        if not permitida_no_modo:
            _bloquear(feature, f"status do contrato é {regra.status.value}")
        if feature not in dados.columns:
            _bloquear(feature, "feature contratada, mas ausente nos dados")
        if regra.coluna_data is not None:
            regras_temporais.append(regra)

    if not regras_temporais:
        return RelatorioDisponibilidade(
            features_validadas=features_solicitadas,
            registros_validados=len(dados),
            modo=modo,
        )

    if coluna_decisao not in dados.columns:
        _bloquear(coluna_decisao, "coluna da data de decisão ausente nos dados")
    datas_decisao = _converter_datas_ou_bloquear(
        dados[coluna_decisao],
        feature=coluna_decisao,
    )

    for regra in regras_temporais:
        assert regra.coluna_data is not None
        if regra.coluna_data not in dados.columns:
            _bloquear(regra.coluna_data, "coluna de origem temporal ausente nos dados")
        datas_origem = _converter_datas_ou_bloquear(
            dados[regra.coluna_data],
            feature=regra.coluna_data,
        )
        posteriores = datas_origem > datas_decisao
        quantidade_posterior = int(posteriores.sum())
        if quantidade_posterior:
            _bloquear(
                regra.feature,
                f"{quantidade_posterior} registro(s) posterior(es) à data de decisão",
                registros_afetados=quantidade_posterior,
            )

    return RelatorioDisponibilidade(
        features_validadas=features_solicitadas,
        registros_validados=len(dados),
        modo=modo,
    )
