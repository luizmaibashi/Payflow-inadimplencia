import json

import pytest
from pydantic import ValidationError

from app.snapshot_monitoramento import (
    SnapshotMonitoramento,
    carregar_snapshot,
    obter_coorte,
)


def _snapshot_dict():
    return {
        "versao_schema": 1,
        "gerado_em": "2026-09-04T12:00:00Z",
        "uso": "PESQUISA",
        "n_total": 1_526_659,
        "n_treino": 733_757,
        "janela_maturacao_dias": 90,
        "data_referencia": "2021-01-04",
        "coortes": [
            {
                "coorte": "2020-H2",
                "decisao": "PESQUISA",
                "motivo": "Modo exploratório não libera uso operacional.",
                "n": 150_240,
                "inadimplentes": 3_175,
                "taxa_inadimplencia": 0.0211,
                "taxa_ic95_inferior": 0.0204,
                "taxa_ic95_superior": 0.0219,
                "auc": 0.6194,
                "auc_ic95_inferior": 0.6105,
                "auc_ic95_superior": 0.6299,
                "brier": 0.0206,
                "drift": [
                    {
                        "feature": "annuity_780A",
                        "status": "ALERTA",
                        "ks": 0.1369,
                        "delta_ausencia": 0.0,
                    }
                ],
                "calibracao": [
                    {
                        "faixa": 10,
                        "limite_inferior": 0.0376,
                        "limite_superior": 1.0,
                        "n": 13_241,
                        "inadimplentes": 708,
                        "previsto": 0.0525,
                        "observado": 0.0535,
                        "observado_ic95_inferior": 0.0498,
                        "observado_ic95_superior": 0.0574,
                        "gap": 0.001,
                        "status": "APROXIMADA",
                    }
                ],
            }
        ],
    }


def test_snapshot_valido_preserva_evidencia_da_coorte():
    snapshot = SnapshotMonitoramento.model_validate(_snapshot_dict())

    assert snapshot.coortes[0].inadimplentes == 3_175


def test_snapshot_rejeita_campo_obrigatorio_ausente():
    dados = _snapshot_dict()
    del dados["coortes"][0]["auc"]

    with pytest.raises(ValidationError):
        SnapshotMonitoramento.model_validate(dados)


def test_snapshot_rejeita_campo_extra_em_vez_de_ignorar():
    dados = _snapshot_dict()
    dados["coortes"][0]["auc_inventada"] = 0.99

    with pytest.raises(ValidationError):
        SnapshotMonitoramento.model_validate(dados)


def test_snapshot_rejeita_versao_desconhecida():
    dados = _snapshot_dict()
    dados["versao_schema"] = 2

    with pytest.raises(ValidationError, match="versao_schema"):
        SnapshotMonitoramento.model_validate(dados)


def test_carregar_snapshot_ausente_explica_como_regenerar(tmp_path):
    with pytest.raises(FileNotFoundError, match="--saida-json"):
        carregar_snapshot(tmp_path / "ausente.json")


def test_carregar_snapshot_corrompido_falha_explicito(tmp_path):
    caminho = tmp_path / "corrompido.json"
    caminho.write_text("{não é json", encoding="utf-8")

    with pytest.raises(ValueError, match="inválido"):
        carregar_snapshot(caminho)


def test_carregar_snapshot_valido(tmp_path):
    caminho = tmp_path / "snapshot.json"
    caminho.write_text(json.dumps(_snapshot_dict()), encoding="utf-8")

    assert carregar_snapshot(caminho).uso == "PESQUISA"


def test_obter_coorte_falha_se_rotulo_nao_existir():
    snapshot = SnapshotMonitoramento.model_validate(_snapshot_dict())

    with pytest.raises(ValueError, match="Coorte não encontrada"):
        obter_coorte(snapshot, "2030-H1")


def test_snapshot_contem_apenas_agregados():
    serializado = json.dumps(_snapshot_dict()).lower()

    assert "case_id" not in serializado


def test_snapshot_rejeita_mais_inadimplentes_que_observacoes():
    dados = _snapshot_dict()
    dados["coortes"][0]["inadimplentes"] = dados["coortes"][0]["n"] + 1

    with pytest.raises(ValidationError, match="inadimplentes não pode exceder n"):
        SnapshotMonitoramento.model_validate(dados)


def test_snapshot_rejeita_intervalo_de_taxa_invertido():
    dados = _snapshot_dict()
    dados["coortes"][0]["taxa_ic95_inferior"] = 0.03
    dados["coortes"][0]["taxa_ic95_superior"] = 0.02

    with pytest.raises(ValidationError, match="intervalo de inadimplência"):
        SnapshotMonitoramento.model_validate(dados)


def test_snapshot_rejeita_calibracao_com_contagem_impossivel():
    dados = _snapshot_dict()
    dados["coortes"][0]["calibracao"][0]["inadimplentes"] = 13_242

    with pytest.raises(ValidationError, match="inadimplentes da faixa"):
        SnapshotMonitoramento.model_validate(dados)


def test_snapshot_rejeita_gap_que_nao_fecha_a_conta():
    dados = _snapshot_dict()
    dados["coortes"][0]["calibracao"][0]["gap"] = 0.20

    with pytest.raises(ValidationError, match="gap deve ser observado menos previsto"):
        SnapshotMonitoramento.model_validate(dados)


def test_snapshot_rejeita_faixa_de_calibracao_duplicada():
    dados = _snapshot_dict()
    dados["coortes"][0]["calibracao"].append(
        dict(dados["coortes"][0]["calibracao"][0])
    )

    with pytest.raises(ValidationError, match="faixas de calibração duplicadas"):
        SnapshotMonitoramento.model_validate(dados)


def test_snapshot_rejeita_drift_fora_do_dominio():
    dados = _snapshot_dict()
    dados["coortes"][0]["drift"][0]["ks"] = 1.2

    with pytest.raises(ValidationError, match="less than or equal to 1"):
        SnapshotMonitoramento.model_validate(dados)


def test_snapshot_rejeita_treino_maior_que_total():
    dados = _snapshot_dict()
    dados["n_treino"] = dados["n_total"] + 1

    with pytest.raises(ValidationError, match="n_treino não pode exceder n_total"):
        SnapshotMonitoramento.model_validate(dados)


def test_snapshot_rejeita_geracao_sem_fuso_horario():
    dados = _snapshot_dict()
    dados["gerado_em"] = "2026-09-04T12:00:00"

    with pytest.raises(ValidationError, match="gerado_em deve informar fuso horário"):
        SnapshotMonitoramento.model_validate(dados)


def test_snapshot_rejeita_data_referencia_invalida():
    dados = _snapshot_dict()
    dados["data_referencia"] = "amanhã"

    with pytest.raises(ValidationError):
        SnapshotMonitoramento.model_validate(dados)


def test_snapshot_rejeita_intervalo_auc_invertido():
    dados = _snapshot_dict()
    dados["coortes"][0]["auc_ic95_inferior"] = 0.70
    dados["coortes"][0]["auc_ic95_superior"] = 0.60

    with pytest.raises(ValidationError, match="intervalo de AUC está invertido"):
        SnapshotMonitoramento.model_validate(dados)
