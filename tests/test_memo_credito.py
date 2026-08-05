"""Testes do contrato do memo de credito (ADR-0003).

O teste mais importante deste arquivo e o de CEGUEIRA AO SCORE: ele guarda
o invariante mais fragil do projeto. Se alguem adicionar um campo com o
score da Camada 1 no memo, o experimento inteiro perde sentido e nenhum
outro teste acusaria.
"""
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.memo_credito import (  # noqa: E402
    MAX_FATORES,
    MIN_FATORES,
    TERMOS_PROIBIDOS_SCORE,
    CenarioAssumido,
    FatorCliente,
    MemoCredito,
    Peso,
    Recomendacao,
    renderizar_narrativa,
)


def _memo_valido(**overrides):
    base = dict(
        cliente_id="SK_100034",
        recomendacao=Recomendacao.NEGAR,
        fatores_cliente=[
            FatorCliente(
                fato="3 atrasos acima de 30 dias nos ultimos 12 meses",
                fonte_tool="bureau_balance",
                peso=Peso.DESFAVORAVEL,
            ),
            FatorCliente(
                fato="Cliente da casa ha 4 anos, sem atraso aqui",
                fonte_tool="previous_application",
                peso=Peso.FAVORAVEL,
            ),
            FatorCliente(
                fato="Comprometimento de renda em 61%",
                fonte_tool="dados_cadastrais",
                peso=Peso.DESFAVORAVEL,
            ),
        ],
        cenario_assumido=CenarioAssumido(lgd=0.78, fonte="BCB SGS serie 11, 2026-08-04"),
    )
    base.update(overrides)
    return MemoCredito(**base)


# --- Invariante 1: groundedness (rubrica eliminatoria do ADR-0004) ---

def test_fato_sem_fonte_tool_e_rejeitado():
    with pytest.raises(ValidationError):
        FatorCliente(fato="cliente parece arriscado", fonte_tool="", peso=Peso.DESFAVORAVEL)


def test_fonte_tool_so_com_espaco_e_rejeitada():
    with pytest.raises(ValidationError):
        FatorCliente(fato="tem atraso", fonte_tool="   ", peso=Peso.DESFAVORAVEL)


def test_memo_sem_nenhum_fato_e_rejeitado():
    with pytest.raises(ValidationError):
        _memo_valido(fatores_cliente=[])


# --- Teto e piso de fatos (medidos, ver MAX_FATORES em app/memo_credito.py) ---

def _n_fatores(n):
    return [
        FatorCliente(fato=f"fato numero {i}", fonte_tool="bureau", peso=Peso.NEUTRO)
        for i in range(n)
    ]


def test_memo_com_menos_que_o_piso_de_fatos_e_rejeitado():
    with pytest.raises(ValidationError):
        _memo_valido(fatores_cliente=_n_fatores(MIN_FATORES - 1))


def test_memo_acima_do_teto_de_fatos_e_rejeitado():
    """Forca o agente a PRIORIZAR em vez de despejar tudo que achou."""
    with pytest.raises(ValidationError):
        _memo_valido(fatores_cliente=_n_fatores(MAX_FATORES + 1))


def test_memo_exatamente_no_piso_e_no_teto_e_aceito():
    for n in (MIN_FATORES, MAX_FATORES):
        assert len(_memo_valido(fatores_cliente=_n_fatores(n)).fatores_cliente) == n


# --- Invariante 2: separacao cliente x cenario (ADR-0008) ---

def test_cenario_fica_em_campo_proprio_e_nao_vira_fato_do_cliente():
    memo = _memo_valido()
    assert memo.cenario_assumido.lgd == 0.78
    # nenhum fator de cliente carrega a premissa macro
    assert all("lgd" not in f.fato.lower() for f in memo.fatores_cliente)


def test_lgd_fora_do_intervalo_valido_e_rejeitada():
    with pytest.raises(ValidationError):
        CenarioAssumido(lgd=1.4, fonte="fonte qualquer")


# --- Invariante 3: cegueira ao score (ADR-0003 SS2.1) ---

def test_memo_nao_tem_nenhum_campo_que_carregue_o_score():
    """Guarda mecanica: nenhum campo do contrato pode carregar p_default.

    Se este teste quebrar, NAO relaxe o teste - o vazamento do score para
    a Camada 2 invalida o experimento inteiro.
    """
    campos = set(MemoCredito.model_fields)
    campos |= set(FatorCliente.model_fields)
    campos |= set(CenarioAssumido.model_fields)

    for campo in campos:
        for proibido in TERMOS_PROIBIDOS_SCORE:
            assert proibido not in campo.lower(), (
                f"campo '{campo}' sugere vazamento do score da Camada 1"
            )


def test_memo_rejeita_campo_extra_com_score():
    """extra='forbid' impede injetar o score por fora do contrato."""
    with pytest.raises(ValidationError):
        _memo_valido(p_default=0.42)


# --- Regra do deferral (Learning to Defer) ---

def test_deferir_sem_dizer_o_que_falta_e_rejeitado():
    with pytest.raises(ValidationError, match="informacao_faltante"):
        _memo_valido(recomendacao=Recomendacao.DEFERIR, informacao_faltante=[])


def test_deferir_com_informacao_faltante_e_aceito():
    memo = _memo_valido(
        recomendacao=Recomendacao.DEFERIR,
        informacao_faltante=["renda atual nao verificada"],
    )
    assert memo.recomendacao is Recomendacao.DEFERIR


def test_aprovar_e_negar_nao_exigem_informacao_faltante():
    for r in (Recomendacao.APROVAR, Recomendacao.NEGAR):
        assert _memo_valido(recomendacao=r).informacao_faltante == []


# --- Narrativa renderizada dos campos, nunca escrita pelo agente ---

def test_narrativa_nao_e_campo_de_entrada_do_agente():
    """Se fosse campo, a prosa poderia contradizer os dados."""
    assert "narrativa" not in MemoCredito.model_fields


def test_narrativa_cita_a_fonte_de_todo_fato():
    texto = renderizar_narrativa(_memo_valido())
    for f in _memo_valido().fatores_cliente:
        assert f.fato in texto
        assert f"[fonte: {f.fonte_tool}]" in texto


def test_narrativa_mostra_o_que_faltou_quando_defere():
    memo = _memo_valido(
        recomendacao=Recomendacao.DEFERIR,
        informacao_faltante=["renda atual nao verificada"],
    )
    texto = renderizar_narrativa(memo)
    assert "O que faltou saber" in texto
    assert "renda atual nao verificada" in texto


def test_narrativa_omite_secao_de_faltantes_quando_nao_ha():
    assert "O que faltou saber" not in renderizar_narrativa(_memo_valido())
