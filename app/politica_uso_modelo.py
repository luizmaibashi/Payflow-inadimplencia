"""Política de uso do score após o boletim de estabilidade por coorte."""

from dataclasses import dataclass
from enum import Enum

from app.contrato_disponibilidade import ModoExecucao
from app.estabilidade_coorte import ResultadoCoorte, StatusCoorte


class DecisaoUsoModelo(str, Enum):
    """Ação sobre o uso do modelo, não sobre um cliente individual."""

    BLOQUEAR = "BLOQUEAR"
    AGUARDAR = "AGUARDAR"
    PESQUISA = "PESQUISA"
    MANTER = "MANTER"
    REVISAR = "REVISAR"


@dataclass(frozen=True)
class DecisaoCoorte:
    """Decisão rastreável e seu motivo para uma coorte já pontuada."""

    status: DecisaoUsoModelo
    motivo: str


@dataclass(frozen=True)
class PoliticaEvidencia:
    """Limites que a instituição aceita para manter um modelo em uso."""

    auc_referencia: float
    brier_referencia: float
    minimo_observacoes: int
    minimo_inadimplentes: int
    tolerancia_auc: float
    tolerancia_brier: float
    auc_ic_inferior_minimo: float

    def __post_init__(self) -> None:
        for nome, valor in (
            ("auc_referencia", self.auc_referencia),
            ("brier_referencia", self.brier_referencia),
            ("tolerancia_auc", self.tolerancia_auc),
            ("tolerancia_brier", self.tolerancia_brier),
            ("auc_ic_inferior_minimo", self.auc_ic_inferior_minimo),
        ):
            if not isinstance(valor, (float, int)) or not 0 <= valor <= 1:
                raise ValueError(f"{nome} deve estar no intervalo [0, 1]")
        for nome, valor in (
            ("minimo_observacoes", self.minimo_observacoes),
            ("minimo_inadimplentes", self.minimo_inadimplentes),
        ):
            if not isinstance(valor, int) or valor <= 0:
                raise ValueError(f"{nome} deve ser um inteiro positivo")


def decidir_uso_coorte(
    coorte: ResultadoCoorte,
    *,
    modo: ModoExecucao,
    politica: PoliticaEvidencia,
) -> DecisaoCoorte:
    """Decide o uso do modelo sem confundir ausência de evidência com sucesso."""

    if not isinstance(coorte, ResultadoCoorte):
        raise TypeError("coorte deve ser um ResultadoCoorte")
    if not isinstance(modo, ModoExecucao):
        raise TypeError("modo deve ser um ModoExecucao")
    if not isinstance(politica, PoliticaEvidencia):
        raise TypeError("politica deve ser uma PoliticaEvidencia")

    if coorte.status is not StatusCoorte.AVALIADA or coorte.auc is None:
        return DecisaoCoorte(
            status=DecisaoUsoModelo.AGUARDAR,
            motivo=f"Coorte não avaliável: {coorte.status.value}",
        )
    if coorte.n_avaliavel < politica.minimo_observacoes:
        return DecisaoCoorte(
            status=DecisaoUsoModelo.AGUARDAR,
            motivo="Coorte abaixo do mínimo de observações definido pela política.",
        )
    if (
        coorte.inadimplentes_observados is None
        or coorte.inadimplentes_observados < politica.minimo_inadimplentes
    ):
        return DecisaoCoorte(
            status=DecisaoUsoModelo.AGUARDAR,
            motivo="Coorte abaixo do mínimo de inadimplentes definido pela política.",
        )
    if (
        coorte.auc_ic95_inferior is None
        or coorte.auc_ic95_inferior < politica.auc_ic_inferior_minimo
    ):
        return DecisaoCoorte(
            status=DecisaoUsoModelo.AGUARDAR,
            motivo="IC da AUC ainda não sustenta a discriminação mínima definida.",
        )
    if coorte.auc < politica.auc_referencia - politica.tolerancia_auc:
        return DecisaoCoorte(
            status=DecisaoUsoModelo.REVISAR,
            motivo=(
                f"AUC {coorte.auc:.4f} caiu mais que {politica.tolerancia_auc:.4f} "
                f"frente à referência {politica.auc_referencia:.4f}."
            ),
        )
    if coorte.brier is None or coorte.brier > politica.brier_referencia + politica.tolerancia_brier:
        return DecisaoCoorte(
            status=DecisaoUsoModelo.REVISAR,
            motivo="Brier indica calibração pior que a tolerância definida.",
        )
    if modo is ModoExecucao.EXPLORATORIO:
        return DecisaoCoorte(
            status=DecisaoUsoModelo.PESQUISA,
            motivo="Modo exploratório não libera uso operacional do modelo.",
        )
    return DecisaoCoorte(
        status=DecisaoUsoModelo.MANTER,
        motivo="AUC está dentro da tolerância definida para a referência.",
    )
