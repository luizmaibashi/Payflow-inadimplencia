"""Ferramenta de CENARIO da Camada 2 (ADR-0007 familia "cenario", ADR-0008).

Familia separada das ferramentas de caso, com granularidade deliberadamente
diferente: **1 chamada por LOTE, nunca por cliente**.

Por que a regra e dura (ADR-0008): consultar a SELIC dentro do loop de um
cliente sugere que o macro e atributo daquela pessoa. Nao e. O dataset e de
mercados emergentes anonimizados; o cenario BR e premissa declarada da
CARTEIRA. Chamar por cliente e violacao registrada - falha na rubrica de
trajectory efficiency, nao mera ineficiencia.

Como o macro entra na decisao (a unica porta autorizada): ele posiciona a
LGD dentro da faixa JA declarada no ADR-0002 (70-85%). Nao inventa faixa
nova. Cenario benigno -> piso; cenario estressado -> teto. Isso move o
ponto de corte de forma rastreavel - e se nao movesse nenhum corte, seria
decoracao e deveria sair (condicao do ADR-0008).

Robustez obrigatoria: cache, timeout e FALLBACK DECLARADO. Se a serie nao
vier, o cenario e o default declarado - nunca um valor inventado.
"""
from datetime import date
from typing import Callable

from pydantic import BaseModel, Field

# Series do BCB SGS
SERIE_SELIC_META = 432      # Taxa Selic meta, % a.a.
SERIE_IPCA_12M = 13522      # IPCA acumulado 12 meses, %

URL_SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados/ultimos/1?formato=json"
TIMEOUT_S = 8

# Faixa de LGD declarada no ADR-0002. O macro POSICIONA dentro dela, nao a
# amplia - qualquer valor fora disto seria premissa nova, nao ajuste.
LGD_PISO = 0.70
LGD_TETO = 0.85

# Ancoras de estresse. SAO PREMISSA DECLARADA, nao medicao: nao existe no
# dataset (mercado emergente anonimizado) nem serie publica que ligue SELIC
# a taxa de recuperacao de credito pessoal no Brasil. Escolhidas como faixa
# plausivel da SELIC no ciclo recente.
SELIC_BENIGNA = 10.0
SELIC_ESTRESSADA = 15.0

# Usado quando a API nao responde. Ponto medio da faixa: assumir o piso
# (cenario benigno) seria otimismo silencioso justamente quando falta
# informacao.
LGD_FALLBACK = (LGD_PISO + LGD_TETO) / 2


class CenarioMacro(BaseModel):
    """Premissa macro do LOTE. Nunca um atributo de cliente."""

    selic_aa: float | None = Field(None, description="Selic meta, % a.a.")
    ipca_12m: float | None = Field(None, description="IPCA acumulado 12m, %")
    lgd: float = Field(
        ..., ge=LGD_PISO, le=LGD_TETO,
        description="Perda dado o default posicionada na faixa do ADR-0002",
    )
    fonte: str = Field(..., description="Origem rastreavel, com serie e data")
    usou_fallback: bool = Field(
        ..., description="True se a API nao respondeu e valeu o default declarado"
    )


def posicionar_lgd(selic_aa: float | None) -> float:
    """Mapeia a SELIC para uma posicao na faixa de LGD declarada.

    Logica economica: juro alto aperta o devedor e derruba o valor de
    garantia, entao a recuperacao piora e a LGD sobe. A DIRECAO tem
    fundamento; a MAGNITUDE e premissa declarada (ver ancoras acima).
    """
    if selic_aa is None:
        return LGD_FALLBACK
    if selic_aa <= SELIC_BENIGNA:
        return LGD_PISO
    if selic_aa >= SELIC_ESTRESSADA:
        return LGD_TETO
    fracao = (selic_aa - SELIC_BENIGNA) / (SELIC_ESTRESSADA - SELIC_BENIGNA)
    return LGD_PISO + fracao * (LGD_TETO - LGD_PISO)


def _buscar_sgs(serie: int) -> float | None:
    """Le a ultima observacao de uma serie do BCB SGS. None se falhar."""
    try:
        import requests

        r = requests.get(URL_SGS.format(serie=serie), timeout=TIMEOUT_S)
        r.raise_for_status()
        dados = r.json()
        return float(dados[-1]["valor"].replace(",", ".")) if dados else None
    except Exception:
        # Falha de rede/parse NAO pode virar excecao que derruba o lote nem,
        # pior, um numero inventado. Vira None e o fallback declarado assume.
        return None


class FerramentaCenario:
    """Cenario macro do lote, com cache e contador de chamadas.

    O contador existe para o teste do invariante do ADR-0007: se o agente
    chamar isto mais de uma vez por lote, o desenho esta errado.
    """

    def __init__(self, buscador: Callable[[int], float | None] = _buscar_sgs):
        self._buscador = buscador
        self._cache: CenarioMacro | None = None
        self.n_buscas_externas = 0

    def consultar_cenario(self) -> CenarioMacro:
        """Cenario macro vigente. Idempotente: busca externa so na 1a vez."""
        if self._cache is not None:
            return self._cache

        self.n_buscas_externas += 1
        selic = self._buscador(SERIE_SELIC_META)
        ipca = self._buscador(SERIE_IPCA_12M)

        if selic is None:
            fonte = (
                f"FALLBACK DECLARADO (BCB SGS indisponivel em {date.today().isoformat()}) "
                f"- LGD = ponto medio da faixa {LGD_PISO:.0%}-{LGD_TETO:.0%} do ADR-0002"
            )
        else:
            fonte = (
                f"BCB SGS serie {SERIE_SELIC_META} (Selic meta), "
                f"consultada em {date.today().isoformat()}"
            )

        self._cache = CenarioMacro(
            selic_aa=selic,
            ipca_12m=ipca,
            lgd=posicionar_lgd(selic),
            fonte=fonte,
            usou_fallback=selic is None,
        )
        return self._cache
