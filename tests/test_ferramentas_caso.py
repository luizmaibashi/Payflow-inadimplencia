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


# --- 2a ferramenta: historico mes a mes (2o salto do multi-hop) ---

def test_historico_separa_meses_em_dia_atraso_e_sem_informacao(ferramentas):
    """'X' nao pode ser contado como mes bom - e ausencia de informacao."""
    r = ferramentas.consultar_historico_bureau(1)
    assert r.tem_registro is True
    assert r.meses_observados == 3          # contrato 10 tem 2 meses, contrato 11 tem 1
    assert r.meses_em_atraso == 1           # o STATUS '1'
    assert r.meses_em_dia == 2
    assert r.meses_sem_informacao == 0


def test_historico_reporta_pior_severidade(ferramentas):
    assert ferramentas.consultar_historico_bureau(1).pior_severidade == 1


def test_historico_diz_ha_quanto_tempo_foi_o_ultimo_atraso(ferramentas):
    """Distingue problema antigo ja recuperado de problema corrente."""
    r = ferramentas.consultar_historico_bureau(1)
    assert r.meses_desde_ultimo_atraso == 2   # MONTHS_BALANCE = -2


def test_historico_sem_atraso_devolve_severidade_nula(ferramentas):
    """Cliente 2 nao tem historico mensal nenhum."""
    r = ferramentas.consultar_historico_bureau(2)
    assert r.tem_registro is False
    assert r.pior_severidade is None
    assert r.meses_desde_ultimo_atraso is None


def test_historico_conta_status_X_como_sem_informacao(tmp_path):
    from app.ferramentas_caso import FerramentasCaso

    pd.DataFrame({
        "SK_ID_CURR": [1], "SK_ID_BUREAU": [10], "CREDIT_ACTIVE": ["Active"],
        "CREDIT_DAY_OVERDUE": [0], "AMT_CREDIT_SUM": [1000.0],
        "AMT_CREDIT_SUM_DEBT": [100.0],
    }).to_csv(tmp_path / "bureau.csv", index=False)
    pd.DataFrame({
        "SK_ID_BUREAU": [10, 10, 10],
        "MONTHS_BALANCE": [-1, -2, -3],
        "STATUS": ["0", "X", "X"],
    }).to_csv(tmp_path / "bureau_balance.csv", index=False)

    r = FerramentasCaso(raw_dir=tmp_path).consultar_historico_bureau(1)
    assert r.meses_sem_informacao == 2
    assert r.meses_em_dia == 1
    assert r.meses_em_atraso == 0
    assert r.pior_severidade is None, "'X' nao pode virar atraso nem virar mes bom"


def test_multi_hop_a_1a_ferramenta_indica_se_vale_chamar_a_2a(ferramentas):
    """O gancho do multi-hop: o agente so desce onde ha o que ler."""
    assert ferramentas.consultar_bureau(1).tem_historico_mensal is True
    assert ferramentas.consultar_historico_bureau(1).tem_registro is True

    assert ferramentas.consultar_bureau(2).tem_historico_mensal is False
    assert ferramentas.consultar_historico_bureau(2).tem_registro is False


def test_segunda_ferramenta_tambem_entra_na_trace(ferramentas):
    ferramentas.consultar_bureau(1)
    ferramentas.consultar_historico_bureau(1)
    assert [c.ferramenta for c in ferramentas.trace] == [
        "consultar_bureau", "consultar_historico_bureau"
    ]


def test_saida_do_historico_nao_carrega_o_score():
    from app.ferramentas_caso import ResultadoHistoricoBureau

    for campo in ResultadoHistoricoBureau.model_fields:
        for proibido in TERMOS_PROIBIDOS_SCORE:
            assert proibido not in campo.lower()
