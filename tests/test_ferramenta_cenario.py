"""Testes da ferramenta de cenario (ADR-0007 familia "cenario", ADR-0008).

Nenhum teste toca a rede: o buscador e injetado. Teste que depende de API
externa e teste que falha por motivo errado.

O teste mais importante deste arquivo e o de NAO-DECORACAO: o ADR-0008
condiciona a existencia desta ferramenta a ela MOVER um corte. Se o cenario
nao muda nenhuma decisao, ele e enfeite e deve sair do projeto.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ferramenta_cenario import (  # noqa: E402
    LGD_FALLBACK,
    LGD_PISO,
    LGD_TETO,
    SELIC_BENIGNA,
    SELIC_ESTRESSADA,
    CenarioMacro,
    FerramentaCenario,
    posicionar_lgd,
)
from app.motor_decisao import calcular_p_estrela  # noqa: E402
from app.memo_credito import TERMOS_PROIBIDOS_SCORE  # noqa: E402


def buscador_fixo(valor):
    return lambda serie: valor


def buscador_que_falha(serie):
    return None


# --- Posicionamento da LGD dentro da faixa declarada ---

def test_cenario_benigno_leva_a_lgd_ao_piso():
    assert posicionar_lgd(SELIC_BENIGNA) == LGD_PISO
    assert posicionar_lgd(5.0) == LGD_PISO, "abaixo da ancora nao pode passar do piso"


def test_cenario_estressado_leva_a_lgd_ao_teto():
    assert posicionar_lgd(SELIC_ESTRESSADA) == LGD_TETO
    assert posicionar_lgd(30.0) == LGD_TETO, "acima da ancora nao pode passar do teto"


def test_lgd_nunca_sai_da_faixa_declarada_no_adr_0002():
    """O macro POSICIONA dentro da faixa; nao a amplia."""
    for selic in [0.0, 5.0, 10.0, 12.5, 15.0, 40.0, 100.0]:
        assert LGD_PISO <= posicionar_lgd(selic) <= LGD_TETO


def test_juro_maior_produz_lgd_maior():
    """Direcao com fundamento economico: juro alto piora a recuperacao."""
    assert posicionar_lgd(11.0) < posicionar_lgd(13.0) < posicionar_lgd(14.0)


def test_sem_selic_usa_ponto_medio_e_nao_o_piso():
    """Assumir o piso na ausencia de dado seria otimismo silencioso."""
    assert posicionar_lgd(None) == LGD_FALLBACK
    assert posicionar_lgd(None) > LGD_PISO


# --- Fallback declarado (ADR-0007: nunca inventar valor) ---

def test_api_indisponivel_usa_fallback_declarado_e_avisa():
    c = FerramentaCenario(buscador=buscador_que_falha).consultar_cenario()
    assert c.usou_fallback is True
    assert c.selic_aa is None
    assert c.lgd == LGD_FALLBACK
    assert "FALLBACK" in c.fonte, "o fallback tem que aparecer na fonte citavel"


def test_api_disponivel_registra_serie_e_data_na_fonte():
    c = FerramentaCenario(buscador=buscador_fixo(12.5)).consultar_cenario()
    assert c.usou_fallback is False
    assert "SGS" in c.fonte and "432" in c.fonte


# --- Invariante: 1 chamada por LOTE (ADR-0007 SS2.2) ---

def test_chamadas_repetidas_nao_batem_na_api_de_novo():
    f = FerramentaCenario(buscador=buscador_fixo(12.0))
    for _ in range(50):
        f.consultar_cenario()
    assert f.n_buscas_externas == 1, (
        "cenario e premissa do LOTE - buscar por cliente sugere que o macro "
        "e atributo da pessoa (violacao do ADR-0008)"
    )


def test_consultas_repetidas_devolvem_exatamente_o_mesmo_cenario():
    """Dois clientes do mesmo lote nao podem receber cenarios diferentes."""
    f = FerramentaCenario(buscador=buscador_fixo(12.0))
    assert f.consultar_cenario() == f.consultar_cenario()


# --- NAO-DECORACAO (condicao de existencia, ADR-0008) ---

def test_cenario_precisa_mover_o_ponto_de_corte():
    """Se o cenario nao muda nenhuma decisao, e enfeite e deve sair.

    Este teste e a condicao de existencia da ferramenta inteira.
    """
    margem = 0.414   # premissa medida do motor (Cash loans)
    p_benigno = calcular_p_estrela(margem, posicionar_lgd(SELIC_BENIGNA))
    p_estresse = calcular_p_estrela(margem, posicionar_lgd(SELIC_ESTRESSADA))

    assert p_estresse < p_benigno, "cenario pior tem que apertar o corte"
    assert (p_benigno - p_estresse) > 0.03, (
        f"o cenario move o corte em apenas {p_benigno - p_estresse:.1%} - "
        "se for menor que a banda de indiferenca, nao muda decisao de ninguem "
        "e a ferramenta e decoracao (ADR-0008)"
    )


# --- Cegueira ao score ---

def test_cenario_nao_carrega_o_score():
    for campo in CenarioMacro.model_fields:
        for proibido in TERMOS_PROIBIDOS_SCORE:
            assert proibido not in campo.lower()


# --- Contrato com o memo ---

def test_cenario_encaixa_no_campo_do_memo():
    """A LGD e a fonte precisam preencher CenarioAssumido do parecer."""
    from app.memo_credito import CenarioAssumido

    c = FerramentaCenario(buscador=buscador_fixo(12.5)).consultar_cenario()
    assumido = CenarioAssumido(lgd=c.lgd, fonte=c.fonte)
    assert assumido.lgd == pytest.approx(c.lgd)
