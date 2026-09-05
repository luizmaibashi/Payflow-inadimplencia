"""Diagnóstico de calibração com faixas de score congeladas no treino."""

from dataclasses import dataclass
from enum import Enum
from math import sqrt
from typing import Iterable, Sequence

import numpy as np
import pandas as pd


class StatusCalibracao(str, Enum):
    """Direção prática do erro de probabilidade em uma faixa."""

    APROXIMADA = "APROXIMADA"
    SUBESTIMA_RISCO = "SUBESTIMA_RISCO"
    SUPERESTIMA_RISCO = "SUPERESTIMA_RISCO"
    INSUFICIENTE = "INSUFICIENTE"


@dataclass(frozen=True)
class PoliticaCalibracao:
    """Evidência e diferença material exigidas para interpretar uma faixa."""

    minimo_observacoes: int
    minimo_inadimplentes: int
    tolerancia_absoluta: float

    def __post_init__(self) -> None:
        for nome, valor in (
            ("minimo_observacoes", self.minimo_observacoes),
            ("minimo_inadimplentes", self.minimo_inadimplentes),
        ):
            if not isinstance(valor, int) or valor <= 0:
                raise ValueError(f"{nome} deve ser um inteiro positivo")
        if (
            not isinstance(self.tolerancia_absoluta, (float, int))
            or not 0 <= self.tolerancia_absoluta <= 1
        ):
            raise ValueError("tolerancia_absoluta deve estar no intervalo [0, 1]")


@dataclass(frozen=True)
class ResultadoFaixaCalibracao:
    """Confronto entre probabilidade prometida e frequência observada."""

    indice_faixa: int
    limite_inferior: float
    limite_superior: float
    n_observacoes: int
    n_inadimplentes: int
    score_medio: float | None
    taxa_observada: float | None
    ic95_inferior: float | None
    ic95_superior: float | None
    gap_observado_previsto: float | None
    status: StatusCalibracao


@dataclass(frozen=True)
class RelatorioCalibracaoFaixas:
    """Faixas comparáveis de uma coorte e a régua usada para formá-las."""

    coorte: str
    limites: tuple[float, ...]
    resultados: tuple[ResultadoFaixaCalibracao, ...]


def _normalizar_scores(valores: pd.Series) -> pd.Series:
    scores = pd.to_numeric(valores, errors="coerce")
    invalidos = (
        valores.isna()
        | scores.isna()
        | ~np.isfinite(scores)
        | ~scores.between(0, 1)
    )
    if bool(invalidos.any()):
        raise ValueError(
            "predicao deve ser numérica, finita, não ausente e estar no intervalo [0, 1]"
        )
    return scores.astype("float64")


def _normalizar_target(valores: pd.Series) -> pd.Series:
    target = pd.to_numeric(valores, errors="coerce")
    invalidos = valores.isna() | target.isna() | ~target.isin([0, 1])
    if bool(invalidos.any()):
        raise ValueError("target deve ser binário (0 ou 1) e não ausente")
    return target.astype("int64")


def criar_limites_quanticos(
    predicoes_treino: pd.Series,
    *,
    n_faixas: int = 10,
) -> tuple[float, ...]:
    """Cria uma régua no treino que não muda ao observar coortes futuras."""

    if not isinstance(predicoes_treino, pd.Series):
        raise TypeError("predicoes_treino deve ser uma pandas.Series")
    if not isinstance(n_faixas, int) or n_faixas < 2:
        raise ValueError("n_faixas deve ser um inteiro maior ou igual a 2")
    if predicoes_treino.empty:
        raise ValueError("predicoes_treino não pode ser vazia")
    scores = _normalizar_scores(predicoes_treino)
    quantis = np.linspace(0, 1, n_faixas + 1)[1:-1]
    interiores = scores.quantile(quantis).to_numpy(dtype="float64")
    limites = (0.0, *(float(valor) for valor in interiores), 1.0)
    if any(atual <= anterior for anterior, atual in zip(limites, limites[1:])):
        raise ValueError(
            "scores do treino não produzem limites distintos para todas as faixas"
        )
    return limites


def _validar_limites(limites: Sequence[float]) -> tuple[float, ...]:
    try:
        normalizados = tuple(float(valor) for valor in limites)
    except (TypeError, ValueError) as erro:
        raise ValueError("limites devem ser numéricos") from erro
    if len(normalizados) < 3:
        raise ValueError("limites devem formar ao menos duas faixas")
    if normalizados[0] != 0.0 or normalizados[-1] != 1.0:
        raise ValueError("limites devem começar em 0 e terminar em 1")
    if any(not np.isfinite(valor) for valor in normalizados):
        raise ValueError("limites devem ser finitos")
    if any(atual <= anterior for anterior, atual in zip(normalizados, normalizados[1:])):
        raise ValueError("limites devem ser estritamente crescentes")
    return normalizados


def _intervalo_wilson_95(eventos: int, total: int) -> tuple[float, float]:
    z = 1.959963984540054
    proporcao = eventos / total
    denominador = 1 + z**2 / total
    centro = (proporcao + z**2 / (2 * total)) / denominador
    margem = z * sqrt(
        proporcao * (1 - proporcao) / total + z**2 / (4 * total**2)
    ) / denominador
    return centro - margem, centro + margem


def avaliar_calibracao_faixas(
    dados: pd.DataFrame,
    *,
    limites: Sequence[float],
    coorte: str,
    politica: PoliticaCalibracao,
    coluna_predicao: str = "predicao",
    coluna_target: str = "target",
) -> RelatorioCalibracaoFaixas:
    """Aplica uma régua fixa e mede a direção material do erro em cada faixa."""

    if not isinstance(dados, pd.DataFrame):
        raise TypeError("dados deve ser um pandas.DataFrame")
    if not isinstance(coorte, str) or not coorte.strip():
        raise ValueError("coorte deve ser uma string não vazia")
    if not isinstance(politica, PoliticaCalibracao):
        raise TypeError("politica deve ser uma PoliticaCalibracao")
    for coluna in (coluna_predicao, coluna_target):
        if coluna not in dados.columns:
            raise ValueError(f"coluna obrigatória ausente: {coluna}")
    limites_fixos = _validar_limites(limites)
    scores = _normalizar_scores(dados[coluna_predicao])
    target = _normalizar_target(dados[coluna_target])
    indices = pd.cut(
        scores,
        bins=limites_fixos,
        labels=False,
        include_lowest=True,
        right=True,
    )

    resultados: list[ResultadoFaixaCalibracao] = []
    for indice in range(len(limites_fixos) - 1):
        mascara = indices == indice
        n = int(mascara.sum())
        eventos = int(target.loc[mascara].sum()) if n else 0
        if not n:
            resultados.append(
                ResultadoFaixaCalibracao(
                    indice_faixa=indice + 1,
                    limite_inferior=limites_fixos[indice],
                    limite_superior=limites_fixos[indice + 1],
                    n_observacoes=0,
                    n_inadimplentes=0,
                    score_medio=None,
                    taxa_observada=None,
                    ic95_inferior=None,
                    ic95_superior=None,
                    gap_observado_previsto=None,
                    status=StatusCalibracao.INSUFICIENTE,
                )
            )
            continue

        score_medio = float(scores.loc[mascara].mean())
        taxa = eventos / n
        ic_inferior, ic_superior = _intervalo_wilson_95(eventos, n)
        gap = taxa - score_medio
        if n < politica.minimo_observacoes or eventos < politica.minimo_inadimplentes:
            status = StatusCalibracao.INSUFICIENTE
        elif abs(gap) <= politica.tolerancia_absoluta:
            status = StatusCalibracao.APROXIMADA
        elif gap > 0:
            status = StatusCalibracao.SUBESTIMA_RISCO
        else:
            status = StatusCalibracao.SUPERESTIMA_RISCO
        resultados.append(
            ResultadoFaixaCalibracao(
                indice_faixa=indice + 1,
                limite_inferior=limites_fixos[indice],
                limite_superior=limites_fixos[indice + 1],
                n_observacoes=n,
                n_inadimplentes=eventos,
                score_medio=score_medio,
                taxa_observada=taxa,
                ic95_inferior=ic_inferior,
                ic95_superior=ic_superior,
                gap_observado_previsto=gap,
                status=status,
            )
        )
    return RelatorioCalibracaoFaixas(
        coorte=coorte,
        limites=limites_fixos,
        resultados=tuple(resultados),
    )


def formatar_calibracao_markdown(
    relatorios: Iterable[RelatorioCalibracaoFaixas],
) -> str:
    """Mostra a conta técnica e explicita a consequência de negócio."""

    linhas = [
        "## Calibração por faixa de score",
        "",
        "| Coorte | Faixa | Intervalo | n | Inadimplentes | Previsto | Observado (IC95%) | Gap | Estado |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for relatorio in relatorios:
        if not isinstance(relatorio, RelatorioCalibracaoFaixas):
            raise TypeError("relatorios deve conter RelatorioCalibracaoFaixas")
        for resultado in relatorio.resultados:
            previsto = "-" if resultado.score_medio is None else f"{resultado.score_medio:.2%}"
            observado = (
                "-"
                if resultado.taxa_observada is None
                else (
                    f"{resultado.taxa_observada:.2%} "
                    f"[{resultado.ic95_inferior:.2%}; {resultado.ic95_superior:.2%}]"
                )
            )
            gap = (
                "-"
                if resultado.gap_observado_previsto is None
                else f"{resultado.gap_observado_previsto:+.2%}"
            )
            abertura = "[" if resultado.indice_faixa == 1 else "("
            linhas.append(
                f"| {relatorio.coorte} | {resultado.indice_faixa} | "
                f"{abertura}{resultado.limite_inferior:.2%}; {resultado.limite_superior:.2%}] | "
                f"{resultado.n_observacoes:,} | {resultado.n_inadimplentes:,} | "
                f"{previsto} | {observado} | {gap} | {resultado.status.value} |"
            )
    linhas.extend(
        [
            "",
            "> `SUBESTIMA_RISCO`: o modelo estima menos inadimplência do que ocorreu; "
            "aprovação, provisão ou preço podem ficar otimistas.",
            "> `SUPERESTIMA_RISCO`: o modelo estima mais inadimplência do que ocorreu; "
            "o negócio pode recusar bons clientes ou reservar capital demais.",
            "> O diagnóstico localiza o problema; não autoriza recalibração automática.",
        ]
    )
    return "\n".join(linhas)
