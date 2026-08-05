"""Testes das ferramentas de caso (ADR-0007).

Rodam sobre CSV sintetico em tmp_path - nao dependem do dataset de 3,3GB,
entao a suite continua rapida e reproduzivel em maquina limpa.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ferramentas_caso import FerramentasCaso, ResultadoBureau  # noqa: E402
from app.memo_credito import TERMOS_PROIBIDOS_SCORE  # noqa: E402


@pytest.fixture
def ferramentas(tmp_path):
    """Cliente 1: 3 contratos (2 ativos, 1 em atraso), com historico mensal.
    Cliente 2: 1 contrato encerrado, sem historico mensal.
    Cliente 3: nao existe no bureau.
    """
    pd.DataFrame({
        "SK_ID_CURR":         [1, 1, 1, 2],
        "SK_ID_BUREAU":       [10, 11, 12, 20],
        "CREDIT_ACTIVE":      ["Active", "Active", "Closed", "Closed"],
        "CREDIT_DAY_OVERDUE": [0, 45, 0, 0],
        "AMT_CREDIT_SUM":     [1000.0, 2000.0, 1000.0, 500.0],
        "AMT_CREDIT_SUM_DEBT": [300.0, 500.0, 0.0, 0.0],
    }).to_csv(tmp_path / "bureau.csv", index=False)

    pd.DataFrame({
        "SK_ID_BUREAU": [10, 10, 11],
        "MONTHS_BALANCE": [-1, -2, -1],
        "STATUS": ["0", "1", "0"],
    }).to_csv(tmp_path / "bureau_balance.csv", index=False)

    return FerramentasCaso(raw_dir=tmp_path)


def test_conta_contratos_ativos_e_em_atraso(ferramentas):
    r = ferramentas.consultar_bureau(1)
    assert r.tem_registro is True
    assert r.n_contratos == 3
    assert r.n_ativos == 2
    assert r.n_em_atraso_hoje == 1


def test_calcula_utilizacao_como_divida_sobre_credito(ferramentas):
    r = ferramentas.consultar_bureau(1)
    assert r.credito_total == 4000.0
    assert r.divida_total == 800.0
    assert r.utilizacao == pytest.approx(0.2)


def test_cliente_sem_bureau_devolve_ausencia_nao_erro(ferramentas):
    """'Sem divida externa' e um fato apurado, nao uma falha de consulta."""
    r = ferramentas.consultar_bureau(3)
    assert r.tem_registro is False
    assert r.n_contratos == 0
    assert r.utilizacao is None


def test_sinaliza_quando_vale_aprofundar_no_historico_mensal(ferramentas):
    """E o gancho do multi-hop: o agente so desce se houver o que ler."""
    assert ferramentas.consultar_bureau(1).tem_historico_mensal is True
    assert ferramentas.consultar_bureau(2).tem_historico_mensal is False


# --- Auditabilidade (ADR-0007 SS2.3) ---

def test_toda_chamada_entra_na_trace(ferramentas):
    ferramentas.consultar_bureau(1)
    ferramentas.consultar_bureau(2)
    assert len(ferramentas.trace) == 2
    assert [c.ferramenta for c in ferramentas.trace] == ["consultar_bureau"] * 2


def test_trace_guarda_argumento_e_retorno(ferramentas):
    ferramentas.consultar_bureau(1)
    chamada = ferramentas.trace[0]
    assert chamada.argumentos == {"sk_id_curr": 1}
    assert chamada.retorno["n_contratos"] == 3


def test_fonte_tool_do_memo_resolve_contra_a_trace(ferramentas):
    """Groundedness so e verificavel se o nome citado bate com a trace."""
    ferramentas.consultar_bureau(1)
    nomes_na_trace = {c.ferramenta for c in ferramentas.trace}
    assert "consultar_bureau" in nomes_na_trace


# --- Cegueira ao score (ADR-0003 SS2.1) ---

def test_nenhum_campo_de_saida_carrega_o_score():
    for campo in ResultadoBureau.model_fields:
        for proibido in TERMOS_PROIBIDOS_SCORE:
            assert proibido not in campo.lower(), (
                f"campo '{campo}' sugere vazamento do score da Camada 1"
            )
