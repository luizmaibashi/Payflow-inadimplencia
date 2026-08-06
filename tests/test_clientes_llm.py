"""Testes dos adaptadores reais de LLM (app/clientes_llm.py).

Nenhum teste aqui faz chamada de rede: o que se testa e a TRADUCAO
JSON -> dataclasses e o comportamento diante de resposta malformada.
Qualidade de julgamento do modelo e objeto de eval (ADR-0004).
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agente_underwriting import AcaoChamarFerramenta, AcaoConcluir  # noqa: E402
from app.clientes_llm import (  # noqa: E402
    ClienteGemini,
    ClienteGroq,
    DependenciaAusente,
    RespostaLLMInvalida,
    _parse_resposta,
    _prompt_sistema,
)
from app.memo_credito import Peso, Recomendacao  # noqa: E402

FERRAMENTAS = {"consultar_bureau": "credito em outras instituicoes"}


def _memo_json(recomendacao="NEGAR", **extra):
    memo = {
        "cliente_id": "1",
        "recomendacao": recomendacao,
        "fatores_cliente": [
            {"fato": f"fato {i}", "fonte_tool": "consultar_bureau", "peso": "desfavoravel"}
            for i in range(3)
        ],
        "cenario_assumido": {"lgd": 0.78, "fonte": "BCB SGS 432"},
    }
    memo.update(extra)
    return memo


def test_parse_chamar_ferramenta():
    acao = _parse_resposta(json.dumps({
        "acao": "chamar_ferramenta",
        "ferramenta": "consultar_bureau",
        "argumentos": {"sk_id_curr": 1},
    }))
    assert isinstance(acao, AcaoChamarFerramenta)
    assert acao.ferramenta == "consultar_bureau"
    assert acao.argumentos == {"sk_id_curr": 1}


def test_parse_chamar_ferramenta_sem_argumentos_usa_dict_vazio():
    acao = _parse_resposta(json.dumps({
        "acao": "chamar_ferramenta", "ferramenta": "consultar_bureau",
    }))
    assert acao.argumentos == {}


def test_parse_concluir_devolve_memo_validado():
    acao = _parse_resposta(json.dumps({"acao": "concluir", "memo": _memo_json()}))
    assert isinstance(acao, AcaoConcluir)
    assert acao.memo.recomendacao is Recomendacao.NEGAR
    assert len(acao.memo.fatores_cliente) == 3
    assert acao.memo.fatores_cliente[0].peso is Peso.DESFAVORAVEL


def test_json_malformado_levanta_erro_claro():
    with pytest.raises(RespostaLLMInvalida, match="nao e JSON valido"):
        _parse_resposta("{acao: concluir")


def test_acao_desconhecida_levanta_erro():
    with pytest.raises(RespostaLLMInvalida, match="acao' desconhecido"):
        _parse_resposta(json.dumps({"acao": "pensar_mais"}))


def test_chamar_ferramenta_sem_nome_levanta_erro():
    with pytest.raises(RespostaLLMInvalida, match="campo obrigatorio"):
        _parse_resposta(json.dumps({"acao": "chamar_ferramenta", "argumentos": {}}))


def test_memo_que_viola_contrato_levanta_erro_em_vez_de_passar():
    """Menos de MIN_FATORES fatos tem que barrar no adaptador, nao virar memo
    invalido circulando pelo agente."""
    memo_curto = _memo_json()
    memo_curto["fatores_cliente"] = memo_curto["fatores_cliente"][:1]
    with pytest.raises(RespostaLLMInvalida, match="nao bateu com o contrato"):
        _parse_resposta(json.dumps({"acao": "concluir", "memo": memo_curto}))


def test_deferir_sem_informacao_faltante_barra_no_adaptador():
    with pytest.raises(RespostaLLMInvalida, match="nao bateu com o contrato"):
        _parse_resposta(json.dumps({
            "acao": "concluir", "memo": _memo_json(recomendacao="DEFERIR")}))


def test_prompt_sistema_lista_as_ferramentas_recebidas():
    prompt = _prompt_sistema(FERRAMENTAS)
    assert "consultar_bureau" in prompt
    assert "credito em outras instituicoes" in prompt


@pytest.mark.parametrize("cliente,sdk", [
    (ClienteGemini, "google.generativeai"),
    (ClienteGroq, "groq"),
])
def test_sdk_ausente_da_mensagem_com_o_comando_de_instalacao(cliente, sdk, monkeypatch):
    """O preco do import lazy e falhar so em runtime. A mensagem tem que
    pagar esse preco: dizer o comando exato, nao 'No module named groq'."""
    monkeypatch.setitem(sys.modules, sdk, None)  # simula pacote ausente
    with pytest.raises(DependenciaAusente, match="requirements-llm.txt"):
        cliente()


def test_prompt_sistema_nao_menciona_score():
    """Cegueira ao score (ADR-0003 SS2.1): o adaptador nao pode reintroduzir
    o vocabulario do modelo no prompt."""
    prompt = _prompt_sistema(FERRAMENTAS).lower()
    for termo in ("p_default", "probabilidade de default", "camada1", "p_estrela"):
        assert termo not in prompt
