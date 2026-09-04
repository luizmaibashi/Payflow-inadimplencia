"""Medição honesta de desempenho de crédito por coorte temporal."""

from dataclasses import dataclass
from enum import Enum
from math import sqrt

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score


class StatusCoorte(str, Enum):
    """Estado de evidência disponível para avaliar uma coorte."""

    AVALIADA = "AVALIADA"
    AGUARDAR_MATURACAO = "AGUARDAR_MATURACAO"
    PREDICAO_INCOMPLETA = "PREDICAO_INCOMPLETA"
    TARGET_SEM_VARIACAO = "TARGET_SEM_VARIACAO"
    COORTE_VAZIA = "COORTE_VAZIA"


@dataclass(frozen=True)
class PoliticaMaturacao:
    """Define quando um outcome pode virar evidência de crédito."""

    coluna_data_decisao: str
    data_referencia: str | pd.Timestamp
    janela_dias: int

    def __post_init__(self) -> None:
        if not isinstance(self.coluna_data_decisao, str) or not self.coluna_data_decisao.strip():
            raise ValueError("coluna_data_decisao deve ser uma string não vazia")
        if not isinstance(self.janela_dias, int) or self.janela_dias <= 0:
            raise ValueError("janela_dias deve ser um inteiro positivo")
        try:
            data = pd.to_datetime(self.data_referencia, utc=True)
        except (TypeError, ValueError) as erro:
            raise ValueError("data_referencia deve ser uma data válida") from erro
        if pd.isna(data):
            raise ValueError("data_referencia deve ser uma data válida")


@dataclass(frozen=True)
class ResultadoCoorte:
    """Métricas e limites de evidência de uma turma temporal."""

    coorte: str
    status: StatusCoorte
    n_total: int
    n_previsao_valida: int
    n_target_amadurecido: int
    n_avaliavel: int
    inadimplentes_observados: int | None
    taxa_inadimplencia: float | None
    ic95_inadimplencia_inferior: float | None
    ic95_inadimplencia_superior: float | None
    auc: float | None
    brier: float | None
    n_elegivel_maturacao: int | None = None
    auc_ic95_inferior: float | None = None
    auc_ic95_superior: float | None = None


@dataclass(frozen=True)
class RelatorioEstabilidade:
    """Coleção ordenada de resultados, um por coorte."""

    coortes: tuple[ResultadoCoorte, ...]


def _intervalo_wilson_95(*, eventos: int, total: int) -> tuple[float, float]:
    """Calcula IC de Wilson para não dar falsa precisão a uma proporção."""

    z = 1.959963984540054
    proporcao = eventos / total
    denominador = 1 + (z**2 / total)
    centro = (proporcao + z**2 / (2 * total)) / denominador
    margem = z * sqrt(
        (proporcao * (1 - proporcao) / total) + (z**2 / (4 * total**2))
    ) / denominador
    return centro - margem, centro + margem


def _intervalo_bootstrap_auc(
    target: pd.Series,
    predicao: pd.Series,
    *,
    amostras: int,
    seed: int,
) -> tuple[float, float]:
    """Estima incerteza da AUC por reamostragem determinística."""

    if not isinstance(amostras, int) or amostras < 100:
        raise ValueError("amostras_bootstrap deve ser um inteiro maior ou igual a 100")
    rng = np.random.default_rng(seed)
    target_array = target.to_numpy()
    predicao_array = predicao.to_numpy()
    aucs: list[float] = []
    for _ in range(amostras):
        indices = rng.integers(0, len(target_array), len(target_array))
        target_amostrado = target_array[indices]
        if np.unique(target_amostrado).size < 2:
            continue
        aucs.append(float(roc_auc_score(target_amostrado, predicao_array[indices])))
    if not aucs:
        raise ValueError("não foi possível estimar IC da AUC por bootstrap")
    return float(np.quantile(aucs, 0.025)), float(np.quantile(aucs, 0.975))


def _normalizar_predicao(serie: pd.Series) -> pd.Series:
    previsao = pd.to_numeric(serie, errors="coerce")
    nao_numerica = serie.notna() & previsao.isna()
    fora_do_intervalo = previsao.notna() & ~previsao.between(0, 1)
    if bool((nao_numerica | fora_do_intervalo).any()):
        raise ValueError("predicao deve ser numérica, ausente ou estar no intervalo [0, 1]")
    return previsao.astype("float64")


def _normalizar_target(serie: pd.Series) -> pd.Series:
    target = pd.to_numeric(serie, errors="coerce")
    nao_numerico = serie.notna() & target.isna()
    fora_do_binario = target.notna() & ~target.isin([0, 1])
    if bool((nao_numerico | fora_do_binario).any()):
        raise ValueError("target deve ser binário (0 ou 1) ou ausente durante a maturação")
    return target.astype("float64")


def _resultado_vazio() -> ResultadoCoorte:
    return ResultadoCoorte(
        coorte="SEM_DADOS",
        status=StatusCoorte.COORTE_VAZIA,
        n_total=0,
        n_previsao_valida=0,
        n_target_amadurecido=0,
        n_avaliavel=0,
        inadimplentes_observados=None,
        taxa_inadimplencia=None,
        ic95_inadimplencia_inferior=None,
        ic95_inadimplencia_superior=None,
        auc=None,
        brier=None,
        n_elegivel_maturacao=0,
    )


def _avaliar_uma_coorte(
    coorte: object,
    dados: pd.DataFrame,
    *,
    coluna_predicao: str,
    coluna_target: str,
    elegivel_maturacao: pd.Series,
    amostras_bootstrap: int,
    seed_bootstrap: int,
) -> ResultadoCoorte:
    predicoes = dados[coluna_predicao]
    targets = dados[coluna_target]
    n_total = len(dados)
    n_previsao_valida = int(predicoes.notna().sum())
    target_amadurecido = elegivel_maturacao & targets.notna()
    n_target_amadurecido = int(target_amadurecido.sum())
    n_elegivel_maturacao = int(elegivel_maturacao.sum())
    avaliaveis = predicoes.notna() & target_amadurecido
    n_avaliavel = int(avaliaveis.sum())

    inadimplentes = None
    taxa = None
    ic_inferior = None
    ic_superior = None
    if n_target_amadurecido:
        inadimplentes = int(targets.loc[target_amadurecido].sum())
        taxa = inadimplentes / n_target_amadurecido
        ic_inferior, ic_superior = _intervalo_wilson_95(
            eventos=inadimplentes,
            total=n_target_amadurecido,
        )

    coorte_formatada = "SEM_COORTE" if pd.isna(coorte) else str(coorte)
    campos = dict(
        coorte=coorte_formatada,
        n_total=n_total,
        n_previsao_valida=n_previsao_valida,
        n_target_amadurecido=n_target_amadurecido,
        n_avaliavel=n_avaliavel,
        inadimplentes_observados=inadimplentes,
        taxa_inadimplencia=taxa,
        ic95_inadimplencia_inferior=ic_inferior,
        ic95_inadimplencia_superior=ic_superior,
        n_elegivel_maturacao=n_elegivel_maturacao,
    )

    if n_elegivel_maturacao != n_total or n_target_amadurecido != n_total:
        return ResultadoCoorte(
            status=StatusCoorte.AGUARDAR_MATURACAO,
            auc=None,
            brier=None,
            **campos,
        )
    if n_previsao_valida != n_total:
        return ResultadoCoorte(
            status=StatusCoorte.PREDICAO_INCOMPLETA,
            auc=None,
            brier=None,
            **campos,
        )

    target_avaliavel = targets.loc[avaliaveis]
    predicao_avaliavel = predicoes.loc[avaliaveis]
    if target_avaliavel.nunique() < 2:
        return ResultadoCoorte(
            status=StatusCoorte.TARGET_SEM_VARIACAO,
            auc=None,
            brier=None,
            **campos,
        )

    auc_ic_inferior, auc_ic_superior = _intervalo_bootstrap_auc(
        target_avaliavel,
        predicao_avaliavel,
        amostras=amostras_bootstrap,
        seed=seed_bootstrap,
    )
    return ResultadoCoorte(
        status=StatusCoorte.AVALIADA,
        auc=float(roc_auc_score(target_avaliavel, predicao_avaliavel)),
        brier=float(brier_score_loss(target_avaliavel, predicao_avaliavel)),
        auc_ic95_inferior=auc_ic_inferior,
        auc_ic95_superior=auc_ic_superior,
        **campos,
    )


def avaliar_estabilidade_coorte(
    dados: pd.DataFrame,
    *,
    coluna_coorte: str = "coorte",
    coluna_predicao: str = "predicao",
    coluna_target: str = "target",
    maturacao: PoliticaMaturacao | None = None,
    amostras_bootstrap: int = 200,
    seed_bootstrap: int = 42,
) -> RelatorioEstabilidade:
    """Produz um boletim por coorte sem transformar ausência de target em acerto.

    AUC e Brier só surgem quando todos os casos da coorte têm previsão e target
    amadurecido. Essa escolha evita avaliar apenas a parte conveniente dos dados.
    """

    if not isinstance(dados, pd.DataFrame):
        raise TypeError("dados deve ser um pandas.DataFrame")
    for coluna in (coluna_coorte, coluna_predicao, coluna_target):
        if not isinstance(coluna, str) or not coluna.strip():
            raise ValueError("nomes de colunas devem ser strings não vazias")
        if coluna not in dados.columns:
            raise ValueError(f"coluna obrigatória ausente: {coluna}")
    if maturacao is not None:
        if not isinstance(maturacao, PoliticaMaturacao):
            raise TypeError("maturacao deve ser uma PoliticaMaturacao ou None")
        if maturacao.coluna_data_decisao not in dados.columns:
            raise ValueError(
                f"coluna obrigatória ausente: {maturacao.coluna_data_decisao}"
            )
    if dados.empty:
        return RelatorioEstabilidade(coortes=(_resultado_vazio(),))

    dados_normalizados = dados.copy()
    dados_normalizados[coluna_predicao] = _normalizar_predicao(
        dados_normalizados[coluna_predicao]
    )
    dados_normalizados[coluna_target] = _normalizar_target(
        dados_normalizados[coluna_target]
    )
    if maturacao is None:
        dados_normalizados["__elegivel_maturacao"] = True
    else:
        datas_decisao = pd.to_datetime(
            dados_normalizados[maturacao.coluna_data_decisao],
            errors="coerce",
            format="mixed",
            utc=True,
        )
        if bool(datas_decisao.isna().any()):
            raise ValueError("data de decisão nula ou malformada para maturação")
        data_referencia = pd.to_datetime(maturacao.data_referencia, utc=True)
        limite = data_referencia - pd.Timedelta(days=maturacao.janela_dias)
        dados_normalizados["__elegivel_maturacao"] = datas_decisao <= limite

    resultados = tuple(
        _avaliar_uma_coorte(
            coorte,
            grupo,
            coluna_predicao=coluna_predicao,
            coluna_target=coluna_target,
            elegivel_maturacao=grupo["__elegivel_maturacao"],
            amostras_bootstrap=amostras_bootstrap,
            seed_bootstrap=seed_bootstrap,
        )
        for coorte, grupo in dados_normalizados.groupby(coluna_coorte, dropna=False, sort=True)
    )
    return RelatorioEstabilidade(coortes=resultados)
