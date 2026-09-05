"""Contrato versionado entre o experimento pesado e o dashboard estático."""

from datetime import date, datetime
from math import isclose
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.experimento_proxy_estabilidade import ResultadoExperimentoProxy


class ModeloFechado(BaseModel):
    """Impede campo desconhecido de atravessar silenciosamente para a tela."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class DriftSnapshot(ModeloFechado):
    feature: str = Field(min_length=1)
    status: Literal["ESTAVEL", "ALERTA", "CRITICO", "INSUFICIENTE"]
    ks: float | None = Field(ge=0, le=1)
    delta_ausencia: float | None = Field(ge=-1, le=1)


class CalibracaoSnapshot(ModeloFechado):
    faixa: int = Field(ge=1)
    limite_inferior: float = Field(ge=0, le=1)
    limite_superior: float = Field(ge=0, le=1)
    n: int = Field(ge=0)
    inadimplentes: int = Field(ge=0)
    previsto: float | None = Field(ge=0, le=1)
    observado: float | None = Field(ge=0, le=1)
    observado_ic95_inferior: float | None = Field(ge=0, le=1)
    observado_ic95_superior: float | None = Field(ge=0, le=1)
    gap: float | None = Field(ge=-1, le=1)
    status: Literal[
        "APROXIMADA",
        "SUBESTIMA_RISCO",
        "SUPERESTIMA_RISCO",
        "INSUFICIENTE",
    ]

    @model_validator(mode="after")
    def validar_coerencia(self):
        if self.limite_inferior >= self.limite_superior:
            raise ValueError("limite inferior deve ser menor que o superior")
        if self.inadimplentes > self.n:
            raise ValueError("inadimplentes da faixa não pode exceder n")

        metricas = (
            self.previsto,
            self.observado,
            self.observado_ic95_inferior,
            self.observado_ic95_superior,
            self.gap,
        )
        if any(valor is None for valor in metricas):
            if not all(valor is None for valor in metricas):
                raise ValueError("métricas da faixa devem estar todas presentes ou ausentes")
            return self

        assert self.previsto is not None
        assert self.observado is not None
        assert self.observado_ic95_inferior is not None
        assert self.observado_ic95_superior is not None
        assert self.gap is not None
        if not (
            self.observado_ic95_inferior
            <= self.observado
            <= self.observado_ic95_superior
        ):
            raise ValueError("observado deve pertencer ao seu intervalo de confiança")
        if not isclose(self.gap, self.observado - self.previsto, abs_tol=1e-9):
            raise ValueError("gap deve ser observado menos previsto")
        return self


class CoorteSnapshot(ModeloFechado):
    coorte: str = Field(min_length=1)
    decisao: Literal["BLOQUEAR", "AGUARDAR", "PESQUISA", "MANTER", "REVISAR"]
    motivo: str = Field(min_length=1)
    n: int = Field(ge=0)
    inadimplentes: int | None = Field(ge=0)
    taxa_inadimplencia: float | None = Field(ge=0, le=1)
    taxa_ic95_inferior: float | None = Field(ge=0, le=1)
    taxa_ic95_superior: float | None = Field(ge=0, le=1)
    auc: float | None = Field(ge=0, le=1)
    auc_ic95_inferior: float | None = Field(ge=0, le=1)
    auc_ic95_superior: float | None = Field(ge=0, le=1)
    brier: float | None = Field(ge=0, le=1)
    drift: list[DriftSnapshot] = Field(min_length=1)
    calibracao: list[CalibracaoSnapshot] = Field(min_length=1)

    @model_validator(mode="after")
    def validar_coerencia(self):
        if self.inadimplentes is not None and self.inadimplentes > self.n:
            raise ValueError("inadimplentes não pode exceder n")
        intervalo = (self.taxa_ic95_inferior, self.taxa_ic95_superior)
        if all(valor is not None for valor in intervalo):
            assert self.taxa_ic95_inferior is not None
            assert self.taxa_ic95_superior is not None
            if self.taxa_ic95_inferior > self.taxa_ic95_superior:
                raise ValueError("intervalo de inadimplência está invertido")
            if self.taxa_inadimplencia is not None and not (
                self.taxa_ic95_inferior
                <= self.taxa_inadimplencia
                <= self.taxa_ic95_superior
            ):
                raise ValueError("taxa de inadimplência deve pertencer ao seu intervalo")
        intervalo_auc = (self.auc_ic95_inferior, self.auc_ic95_superior)
        if all(valor is not None for valor in intervalo_auc):
            assert self.auc_ic95_inferior is not None
            assert self.auc_ic95_superior is not None
            if self.auc_ic95_inferior > self.auc_ic95_superior:
                raise ValueError("intervalo de AUC está invertido")
            if self.auc is not None and not (
                self.auc_ic95_inferior <= self.auc <= self.auc_ic95_superior
            ):
                raise ValueError("AUC deve pertencer ao seu intervalo")
        faixas = [item.faixa for item in self.calibracao]
        if len(faixas) != len(set(faixas)):
            raise ValueError("faixas de calibração duplicadas")
        return self


class SnapshotMonitoramento(ModeloFechado):
    versao_schema: Literal[1]
    gerado_em: datetime
    uso: Literal["PESQUISA"]
    n_total: int = Field(gt=0)
    n_treino: int = Field(gt=0)
    janela_maturacao_dias: int = Field(gt=0)
    data_referencia: date
    coortes: list[CoorteSnapshot] = Field(min_length=1)

    @model_validator(mode="after")
    def coortes_devem_ser_unicas(self):
        if self.gerado_em.tzinfo is None or self.gerado_em.utcoffset() is None:
            raise ValueError("gerado_em deve informar fuso horário")
        rotulos = [coorte.coorte for coorte in self.coortes]
        if len(rotulos) != len(set(rotulos)):
            raise ValueError("coortes duplicadas no snapshot")
        if self.n_treino > self.n_total:
            raise ValueError("n_treino não pode exceder n_total")
        return self


def construir_snapshot(
    resultado: ResultadoExperimentoProxy,
    *,
    gerado_em: str | datetime,
) -> SnapshotMonitoramento:
    """Reduz o resultado a agregados suficientes para decisão e auditoria."""

    if not isinstance(resultado, ResultadoExperimentoProxy):
        raise TypeError("resultado deve ser um ResultadoExperimentoProxy")
    drift_por_coorte = {
        relatorio.resultados[0].coorte: relatorio
        for relatorio in resultado.drift_coortes
        if relatorio.resultados
    }
    calibracao_por_coorte = {
        relatorio.coorte: relatorio for relatorio in resultado.calibracao_coortes
    }
    coortes: list[dict] = []
    for medicao, decisao in zip(resultado.coortes, resultado.decisoes, strict=True):
        if medicao.coorte not in drift_por_coorte:
            raise ValueError(f"coorte sem detalhe de drift: {medicao.coorte}")
        if medicao.coorte not in calibracao_por_coorte:
            raise ValueError(f"coorte sem detalhe de calibração: {medicao.coorte}")
        drift = drift_por_coorte[medicao.coorte]
        calibracao = calibracao_por_coorte[medicao.coorte]
        coortes.append(
            {
                "coorte": medicao.coorte,
                "decisao": decisao.status.value,
                "motivo": decisao.motivo,
                "n": medicao.n_avaliavel,
                "inadimplentes": medicao.inadimplentes_observados,
                "taxa_inadimplencia": medicao.taxa_inadimplencia,
                "taxa_ic95_inferior": medicao.ic95_inadimplencia_inferior,
                "taxa_ic95_superior": medicao.ic95_inadimplencia_superior,
                "auc": medicao.auc,
                "auc_ic95_inferior": medicao.auc_ic95_inferior,
                "auc_ic95_superior": medicao.auc_ic95_superior,
                "brier": medicao.brier,
                "drift": [
                    {
                        "feature": item.feature,
                        "status": item.status.value,
                        "ks": item.ks,
                        "delta_ausencia": item.delta_ausencia,
                    }
                    for item in drift.resultados
                ],
                "calibracao": [
                    {
                        "faixa": item.indice_faixa,
                        "limite_inferior": item.limite_inferior,
                        "limite_superior": item.limite_superior,
                        "n": item.n_observacoes,
                        "inadimplentes": item.n_inadimplentes,
                        "previsto": item.score_medio,
                        "observado": item.taxa_observada,
                        "observado_ic95_inferior": item.ic95_inferior,
                        "observado_ic95_superior": item.ic95_superior,
                        "gap": item.gap_observado_previsto,
                        "status": item.status.value,
                    }
                    for item in calibracao.resultados
                ],
            }
        )
    return SnapshotMonitoramento.model_validate(
        {
            "versao_schema": 1,
            "gerado_em": gerado_em,
            "uso": "PESQUISA",
            "n_total": resultado.n_total,
            "n_treino": resultado.n_treino,
            "janela_maturacao_dias": resultado.configuracao.janela_dias,
            "data_referencia": str(resultado.configuracao.data_referencia),
            "coortes": coortes,
        }
    )


def carregar_snapshot(caminho: str | Path) -> SnapshotMonitoramento:
    """Carrega o artefato sem converter erro de contrato em tela vazia."""

    arquivo = Path(caminho)
    if not arquivo.is_file():
        raise FileNotFoundError(
            "Snapshot ausente. Regenere com proxy_estabilidade_reproduzivel.py "
            "e a opção --saida-json."
        )
    try:
        return SnapshotMonitoramento.model_validate_json(
            arquivo.read_text(encoding="utf-8")
        )
    except (OSError, ValidationError) as erro:
        raise ValueError(f"Snapshot inválido: {erro}") from erro


def obter_coorte(snapshot: SnapshotMonitoramento, rotulo: str) -> CoorteSnapshot:
    """Seleciona uma coorte sem cair silenciosamente na primeira disponível."""

    if not isinstance(snapshot, SnapshotMonitoramento):
        raise TypeError("snapshot deve ser um SnapshotMonitoramento")
    for coorte in snapshot.coortes:
        if coorte.coorte == rotulo:
            return coorte
    raise ValueError(f"Coorte não encontrada no snapshot: {rotulo}")
