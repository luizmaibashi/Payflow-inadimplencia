"""Experimento reproduzível do proxy semântico no Home Credit Stability."""

from dataclasses import dataclass
from typing import Iterable

import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

from app.calibracao_faixas import (
    PoliticaCalibracao,
    RelatorioCalibracaoFaixas,
    avaliar_calibracao_faixas,
    criar_limites_quanticos,
    formatar_calibracao_markdown,
)
from app.contrato_disponibilidade import ModoExecucao
from app.contrato_home_credit_proxy import contrato_proxy_proposta
from app.drift_features import (
    PoliticaDrift,
    RelatorioDriftFeatures,
    avaliar_drift_features,
    formatar_resumo_drift_markdown,
)
from app.estabilidade_coorte import PoliticaMaturacao, ResultadoCoorte, StatusCoorte
from app.monitoramento_coorte import executar_monitoramento_coorte
from app.politica_uso_modelo import (
    DecisaoCoorte,
    PoliticaEvidencia,
    decidir_uso_coorte,
)


FEATURES_PROXY = tuple(contrato_proxy_proposta())


@dataclass(frozen=True)
class ConfiguracaoExperimentoProxy:
    """Parâmetros declarados que tornam a reconstrução auditável."""

    data_referencia: str | pd.Timestamp
    janela_dias: int
    corte_treino: str = "2019-09-30"
    random_state: int = 42
    max_iter: int = 200
    learning_rate: float = 0.05
    l2_regularization: float = 1.0
    amostras_bootstrap: int = 200

    def __post_init__(self) -> None:
        if not isinstance(self.janela_dias, int) or self.janela_dias <= 0:
            raise ValueError("janela_dias deve ser um inteiro positivo")
        if not isinstance(self.random_state, int):
            raise TypeError("random_state deve ser inteiro")
        if not isinstance(self.max_iter, int) or self.max_iter <= 0:
            raise ValueError("max_iter deve ser um inteiro positivo")
        if not isinstance(self.learning_rate, (float, int)) or self.learning_rate <= 0:
            raise ValueError("learning_rate deve ser positivo")
        if not isinstance(self.l2_regularization, (float, int)) or self.l2_regularization < 0:
            raise ValueError("l2_regularization não pode ser negativo")
        if not isinstance(self.amostras_bootstrap, int) or self.amostras_bootstrap < 100:
            raise ValueError("amostras_bootstrap deve ser maior ou igual a 100")
        for nome, valor in (
            ("data_referencia", self.data_referencia),
            ("corte_treino", self.corte_treino),
        ):
            data = pd.to_datetime(valor, errors="coerce", utc=True)
            if pd.isna(data):
                raise ValueError(f"{nome} deve ser uma data válida")


@dataclass(frozen=True)
class ResultadoExperimentoProxy:
    """Saída rastreável do treino e das três coortes futuras."""

    n_total: int
    n_treino: int
    coortes: tuple[ResultadoCoorte, ...]
    decisoes: tuple[DecisaoCoorte, ...]
    drift_coortes: tuple[RelatorioDriftFeatures, ...]
    calibracao_coortes: tuple[RelatorioCalibracaoFaixas, ...]
    configuracao: ConfiguracaoExperimentoProxy


def rotular_particao_temporal(datas: pd.Series) -> pd.Series:
    """Separa treino e coortes futuras sem sobreposição temporal."""

    datas_normalizadas = pd.to_datetime(datas, errors="coerce", format="mixed", utc=True)
    if bool(datas_normalizadas.isna().any()):
        raise ValueError("data de decisão nula ou malformada")

    rotulos = pd.Series(pd.NA, index=datas.index, dtype="string")
    rotulos.loc[datas_normalizadas <= pd.Timestamp("2019-09-30", tz="UTC")] = "TREINO"
    rotulos.loc[datas_normalizadas.between("2019-10-01", "2019-12-31")] = "2019-Q4"
    rotulos.loc[datas_normalizadas.between("2020-01-01", "2020-06-30")] = "2020-H1"
    rotulos.loc[datas_normalizadas.between("2020-07-01", "2020-12-31")] = "2020-H2"
    if bool(rotulos.isna().any()):
        raise ValueError("há data fora da janela temporal declarada no experimento")
    return rotulos


def montar_base_proxy(
    base: pd.DataFrame,
    particoes_estaticas: Iterable[pd.DataFrame],
) -> pd.DataFrame:
    """Monta uma linha por proposta e falha se a junção perder observações."""

    if not isinstance(base, pd.DataFrame):
        raise TypeError("base deve ser um pandas.DataFrame")
    obrigatorias_base = {"case_id", "date_decision", "target"}
    ausentes_base = obrigatorias_base - set(base.columns)
    if ausentes_base:
        raise ValueError(f"colunas ausentes na base: {sorted(ausentes_base)}")
    if bool(base["case_id"].duplicated().any()):
        raise ValueError("case_id duplicado na base")

    partes = tuple(particoes_estaticas)
    if not partes:
        raise ValueError("particoes_estaticas deve conter ao menos uma tabela")
    estaticas = pd.concat(partes, ignore_index=True)
    obrigatorias_static = {"case_id", *FEATURES_PROXY}
    ausentes_static = obrigatorias_static - set(estaticas.columns)
    if ausentes_static:
        raise ValueError(f"colunas ausentes nas features estáticas: {sorted(ausentes_static)}")
    if bool(estaticas["case_id"].duplicated().any()):
        raise ValueError("case_id duplicado nas features estáticas")

    colunas_static = ["case_id", *FEATURES_PROXY]
    dados = base.loc[:, ["case_id", "date_decision", "target"]].merge(
        estaticas.loc[:, colunas_static],
        on="case_id",
        how="left",
        validate="one_to_one",
        indicator=True,
    )
    sem_features = int((dados["_merge"] != "both").sum())
    if sem_features:
        raise ValueError(f"{sem_features} caso(s) sem features estáticas")
    dados = dados.drop(columns="_merge")
    dados["coorte"] = rotular_particao_temporal(dados["date_decision"])
    return dados


def executar_experimento_proxy(
    dados: pd.DataFrame,
    *,
    configuracao: ConfiguracaoExperimentoProxy,
    politica: PoliticaEvidencia,
    politica_drift: PoliticaDrift,
    politica_calibracao: PoliticaCalibracao,
    n_faixas_calibracao: int = 10,
) -> ResultadoExperimentoProxy:
    """Treina no passado e mede apenas as coortes posteriores ao corte."""

    if not isinstance(configuracao, ConfiguracaoExperimentoProxy):
        raise TypeError("configuracao deve ser uma ConfiguracaoExperimentoProxy")
    if not isinstance(politica, PoliticaEvidencia):
        raise TypeError("politica deve ser uma PoliticaEvidencia")
    if not isinstance(politica_drift, PoliticaDrift):
        raise TypeError("politica_drift deve ser uma PoliticaDrift")
    if not isinstance(politica_calibracao, PoliticaCalibracao):
        raise TypeError("politica_calibracao deve ser uma PoliticaCalibracao")

    corte = pd.to_datetime(configuracao.corte_treino, utc=True)
    datas = pd.to_datetime(dados["date_decision"], errors="coerce", utc=True)
    treino = dados.loc[datas <= corte].copy()
    avaliacao = dados.loc[datas > corte].copy()
    if treino.empty or avaliacao.empty:
        raise ValueError("experimento exige observações antes e depois do corte de treino")
    if treino["target"].nunique() < 2:
        raise ValueError("target de treino precisa conter as duas classes")

    modelo = HistGradientBoostingClassifier(
        max_iter=configuracao.max_iter,
        learning_rate=float(configuracao.learning_rate),
        l2_regularization=float(configuracao.l2_regularization),
        random_state=configuracao.random_state,
    )
    modelo.fit(treino.loc[:, FEATURES_PROXY], treino["target"])
    limites_calibracao = criar_limites_quanticos(
        pd.Series(modelo.predict_proba(treino.loc[:, FEATURES_PROXY])[:, 1]),
        n_faixas=n_faixas_calibracao,
    )

    monitoramento = executar_monitoramento_coorte(
        avaliacao,
        features=FEATURES_PROXY,
        contrato=contrato_proxy_proposta(),
        scorer=lambda features: modelo.predict_proba(features)[:, 1],
        coluna_coorte="coorte",
        coluna_target="target",
        modo=ModoExecucao.EXPLORATORIO,
        maturacao=PoliticaMaturacao(
            coluna_data_decisao="date_decision",
            data_referencia=configuracao.data_referencia,
            janela_dias=configuracao.janela_dias,
        ),
        amostras_bootstrap=configuracao.amostras_bootstrap,
    )
    if monitoramento.coortes is None:
        raise RuntimeError("contrato proxy foi bloqueado durante o experimento exploratório")
    decisoes = tuple(
        decidir_uso_coorte(
            coorte,
            modo=ModoExecucao.EXPLORATORIO,
            politica=politica,
        )
        for coorte in monitoramento.coortes.coortes
    )
    drift_coortes = tuple(
        avaliar_drift_features(
            treino,
            grupo,
            features=FEATURES_PROXY,
            coorte=str(coorte),
            politica=politica_drift,
        )
        for coorte, grupo in avaliacao.groupby("coorte", sort=True)
    )
    status_por_coorte = {
        coorte.coorte: coorte.status for coorte in monitoramento.coortes.coortes
    }
    calibracao_coortes = tuple(
        avaliar_calibracao_faixas(
            pd.DataFrame(
                {
                    "predicao": modelo.predict_proba(grupo.loc[:, FEATURES_PROXY])[:, 1],
                    "target": grupo["target"].to_numpy(),
                }
            ),
            limites=limites_calibracao,
            coorte=str(coorte),
            politica=politica_calibracao,
        )
        for coorte, grupo in avaliacao.groupby("coorte", sort=True)
        if status_por_coorte[str(coorte)] is StatusCoorte.AVALIADA
    )
    return ResultadoExperimentoProxy(
        n_total=len(dados),
        n_treino=len(treino),
        coortes=monitoramento.coortes.coortes,
        decisoes=decisoes,
        drift_coortes=drift_coortes,
        calibracao_coortes=calibracao_coortes,
        configuracao=configuracao,
    )


def formatar_relatorio_markdown(resultado: ResultadoExperimentoProxy) -> str:
    """Traduz métricas técnicas para um artefato legível de auditoria."""

    linhas = [
        "# Experimento reproduzível — proxy temporal",
        "",
        "**Uso:** pesquisa. As seis variáveis não têm prova point-in-time.",
        f"**Dados:** n={resultado.n_total:,}; treino={resultado.n_treino:,}.",
        (
            "**Maturação declarada:** "
            f"{resultado.configuracao.janela_dias} dias; "
            f"data de referência={resultado.configuracao.data_referencia}."
        ),
        "",
        "| Coorte | n | Inadimplentes | Taxa (IC95%) | AUC (IC95%) | Brier | Decisão |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for coorte, decisao in zip(resultado.coortes, resultado.decisoes, strict=True):
        taxa = (
            "—"
            if coorte.taxa_inadimplencia is None
            else (
                f"{coorte.taxa_inadimplencia:.2%} "
                f"[{coorte.ic95_inadimplencia_inferior:.2%}; "
                f"{coorte.ic95_inadimplencia_superior:.2%}]"
            )
        )
        auc = (
            "—"
            if coorte.auc is None
            else (
                f"{coorte.auc:.4f} "
                f"[{coorte.auc_ic95_inferior:.4f}; {coorte.auc_ic95_superior:.4f}]"
            )
        )
        brier = "—" if coorte.brier is None else f"{coorte.brier:.4f}"
        inadimplentes = (
            "—" if coorte.inadimplentes_observados is None else str(coorte.inadimplentes_observados)
        )
        linhas.append(
            f"| {coorte.coorte} | {coorte.n_avaliavel:,} | {inadimplentes} | "
            f"{taxa} | {auc} | {brier} | {decisao.status.value} |"
        )
    linhas.extend(
        [
            "",
            "> A janela de maturação é uma hipótese explícita de demonstração. "
            "A competição não publica horizonte suficiente para tratá-la como política real.",
        ]
    )
    linhas.extend(["", formatar_resumo_drift_markdown(resultado.drift_coortes)])
    linhas.extend(["", formatar_calibracao_markdown(resultado.calibracao_coortes)])
    return "\n".join(linhas)
