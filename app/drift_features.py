"""Diagnóstico univariado de mudança populacional entre coortes."""

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp


class StatusDrift(str, Enum):
    """Gravidade do sinal, sem autorizar retreino automático."""

    ESTAVEL = "ESTAVEL"
    ALERTA = "ALERTA"
    CRITICO = "CRITICO"
    INSUFICIENTE = "INSUFICIENTE"


@dataclass(frozen=True)
class PoliticaDrift:
    """Limites explícitos e substituíveis pela política da instituição."""

    minimo_nao_nulos: int
    ks_alerta: float
    ks_critico: float
    ausencia_alerta: float
    ausencia_critica: float

    def __post_init__(self) -> None:
        if (
            not isinstance(self.minimo_nao_nulos, int)
            or isinstance(self.minimo_nao_nulos, bool)
            or self.minimo_nao_nulos <= 0
        ):
            raise ValueError("minimo_nao_nulos deve ser um inteiro positivo")
        for nome, valor in (
            ("ks_alerta", self.ks_alerta),
            ("ks_critico", self.ks_critico),
            ("ausencia_alerta", self.ausencia_alerta),
            ("ausencia_critica", self.ausencia_critica),
        ):
            if (
                not isinstance(valor, (int, float))
                or isinstance(valor, bool)
                or not 0 <= valor <= 1
            ):
                raise ValueError(f"{nome} deve estar no intervalo [0, 1]")
        if self.ks_critico <= self.ks_alerta:
            raise ValueError("ks_critico deve ser maior que ks_alerta")
        if self.ausencia_critica <= self.ausencia_alerta:
            raise ValueError(
                "ausencia_critica deve ser maior que ausencia_alerta"
            )


@dataclass(frozen=True)
class ResultadoDriftFeature:
    """Evidência de drift de uma feature em uma coorte."""

    feature: str
    coorte: str
    n_referencia: int
    n_coorte: int
    n_validos_referencia: int
    n_validos_coorte: int
    taxa_ausencia_referencia: float | None
    taxa_ausencia_coorte: float | None
    delta_ausencia: float | None
    ks: float | None
    status: StatusDrift
    motivos: tuple[str, ...]


@dataclass(frozen=True)
class RelatorioDriftFeatures:
    """Resultados ordenados na mesma ordem das features solicitadas."""

    resultados: tuple[ResultadoDriftFeature, ...]


def _normalizar_feature(serie: pd.Series, *, feature: str) -> pd.Series:
    valores = pd.to_numeric(serie, errors="coerce")
    invalidos = serie.notna() & valores.isna()
    infinitos = valores.notna() & ~np.isfinite(valores)
    if bool((invalidos | infinitos).any()):
        raise ValueError(f"feature {feature} contém valor não numérico ou infinito")
    return valores.astype("float64")


def _validar_features(
    referencia: pd.DataFrame,
    atual: pd.DataFrame,
    features: Iterable[str],
) -> tuple[str, ...]:
    if not isinstance(referencia, pd.DataFrame) or not isinstance(atual, pd.DataFrame):
        raise TypeError("referencia e atual devem ser pandas.DataFrame")
    nomes = tuple(features)
    if not nomes:
        raise ValueError("features deve conter ao menos uma coluna")
    if any(not isinstance(nome, str) or not nome.strip() for nome in nomes):
        raise ValueError("features deve conter nomes de colunas não vazios")
    if len(set(nomes)) != len(nomes):
        raise ValueError("features não pode conter nomes duplicados")
    for nome in nomes:
        if nome not in referencia.columns:
            raise ValueError(f"feature ausente na referência: {nome}")
        if nome not in atual.columns:
            raise ValueError(f"feature ausente na coorte: {nome}")
    return nomes


def _avaliar_feature(
    referencia: pd.Series,
    atual: pd.Series,
    *,
    feature: str,
    coorte: str,
    politica: PoliticaDrift,
) -> ResultadoDriftFeature:
    ref = _normalizar_feature(referencia, feature=feature)
    coorte_atual = _normalizar_feature(atual, feature=feature)
    n_ref = len(ref)
    n_atual = len(coorte_atual)
    validos_ref = ref.dropna()
    validos_atual = coorte_atual.dropna()
    taxa_ausencia_ref = None if n_ref == 0 else float(ref.isna().mean())
    taxa_ausencia_atual = None if n_atual == 0 else float(coorte_atual.isna().mean())
    delta_ausencia = (
        None
        if taxa_ausencia_ref is None or taxa_ausencia_atual is None
        else abs(taxa_ausencia_atual - taxa_ausencia_ref)
    )

    if (
        len(validos_ref) < politica.minimo_nao_nulos
        or len(validos_atual) < politica.minimo_nao_nulos
    ):
        return ResultadoDriftFeature(
            feature=feature,
            coorte=coorte,
            n_referencia=n_ref,
            n_coorte=n_atual,
            n_validos_referencia=len(validos_ref),
            n_validos_coorte=len(validos_atual),
            taxa_ausencia_referencia=taxa_ausencia_ref,
            taxa_ausencia_coorte=taxa_ausencia_atual,
            delta_ausencia=delta_ausencia,
            ks=None,
            status=StatusDrift.INSUFICIENTE,
            motivos=("amostra não nula abaixo do mínimo",),
        )

    ks = float(ks_2samp(validos_ref, validos_atual).statistic)
    motivos: list[str] = []
    if ks >= politica.ks_critico:
        motivos.append("KS acima do limite crítico")
    elif ks >= politica.ks_alerta:
        motivos.append("KS acima do limite de alerta")
    if delta_ausencia is not None and delta_ausencia >= politica.ausencia_critica:
        motivos.append("ausência acima do limite crítico")
    elif delta_ausencia is not None and delta_ausencia >= politica.ausencia_alerta:
        motivos.append("ausência acima do limite de alerta")

    if ks >= politica.ks_critico or (
        delta_ausencia is not None and delta_ausencia >= politica.ausencia_critica
    ):
        status = StatusDrift.CRITICO
    elif ks >= politica.ks_alerta or (
        delta_ausencia is not None and delta_ausencia >= politica.ausencia_alerta
    ):
        status = StatusDrift.ALERTA
    else:
        status = StatusDrift.ESTAVEL
        motivos.append("KS e ausência dentro dos limites")

    return ResultadoDriftFeature(
        feature=feature,
        coorte=coorte,
        n_referencia=n_ref,
        n_coorte=n_atual,
        n_validos_referencia=len(validos_ref),
        n_validos_coorte=len(validos_atual),
        taxa_ausencia_referencia=taxa_ausencia_ref,
        taxa_ausencia_coorte=taxa_ausencia_atual,
        delta_ausencia=delta_ausencia,
        ks=ks,
        status=status,
        motivos=tuple(motivos),
    )


def avaliar_drift_features(
    referencia: pd.DataFrame,
    atual: pd.DataFrame,
    *,
    features: Iterable[str],
    coorte: str,
    politica: PoliticaDrift,
) -> RelatorioDriftFeatures:
    """Compara uma coorte com o treino sem inferir causa ou retreinar."""

    if not isinstance(coorte, str) or not coorte.strip():
        raise ValueError("coorte deve ser uma string não vazia")
    if not isinstance(politica, PoliticaDrift):
        raise TypeError("politica deve ser uma PoliticaDrift")
    nomes = _validar_features(referencia, atual, features)
    resultados = tuple(
        _avaliar_feature(
            referencia[nome],
            atual[nome],
            feature=nome,
            coorte=coorte,
            politica=politica,
        )
        for nome in nomes
    )
    return RelatorioDriftFeatures(resultados=resultados)


def formatar_resumo_drift_markdown(
    relatorios: Iterable[RelatorioDriftFeatures],
) -> str:
    """Resume gravidade por coorte sem esconder a feature de maior mudança."""

    linhas = [
        "## Drift das features contra o treino",
        "",
        "| Coorte | Estáveis | Alertas | Críticas | Insuficientes | Destaque | KS | Delta ausência |",
        "|---|---:|---:|---:|---:|---|---:|---:|",
    ]
    gravidade = {
        StatusDrift.INSUFICIENTE: 3,
        StatusDrift.CRITICO: 2,
        StatusDrift.ALERTA: 1,
        StatusDrift.ESTAVEL: 0,
    }
    for relatorio in relatorios:
        if not isinstance(relatorio, RelatorioDriftFeatures):
            raise TypeError("relatorios deve conter RelatorioDriftFeatures")
        if not relatorio.resultados:
            continue
        contagens = {
            status: sum(
                resultado.status is status for resultado in relatorio.resultados
            )
            for status in StatusDrift
        }
        destaque = max(
            relatorio.resultados,
            key=lambda resultado: (
                gravidade[resultado.status],
                max(resultado.ks or 0.0, resultado.delta_ausencia or 0.0),
            ),
        )
        ks = "-" if destaque.ks is None else f"{destaque.ks:.4f}"
        delta = (
            "-"
            if destaque.delta_ausencia is None
            else f"{destaque.delta_ausencia:.2%}"
        )
        linhas.append(
            f"| {destaque.coorte} | {contagens[StatusDrift.ESTAVEL]} | "
            f"{contagens[StatusDrift.ALERTA]} | {contagens[StatusDrift.CRITICO]} | "
            f"{contagens[StatusDrift.INSUFICIENTE]} | {destaque.feature} | {ks} | {delta} |"
        )
    linhas.extend(
        [
            "",
            "> KS e ausência sinalizam mudança, mas não provam a causa nem autorizam retreino automático.",
        ]
    )
    return "\n".join(linhas)
