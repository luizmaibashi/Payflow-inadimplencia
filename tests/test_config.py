"""Testes do ponto unico de configuracao (app/config.py).

Nenhum teste le o .env real do desenvolvedor: `monkeypatch.setenv/delenv`
isola o ambiente por caso. Teste que depende de segredo da maquina nao roda
em CI e falha diferente em cada estacao.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import ChaveAusente, exigir_chave  # noqa: E402


def test_exigir_chave_devolve_valor_do_ambiente(monkeypatch):
    monkeypatch.setenv("CHAVE_DE_TESTE", "valor-123")
    assert exigir_chave("CHAVE_DE_TESTE") == "valor-123"


def test_chave_ausente_falha_com_instrucao_acionavel(monkeypatch):
    """A mensagem tem que dizer O QUE FAZER, nao so que faltou algo."""
    monkeypatch.delenv("CHAVE_DE_TESTE", raising=False)
    with pytest.raises(ChaveAusente) as exc:
        exigir_chave("CHAVE_DE_TESTE")
    mensagem = str(exc.value)
    assert "CHAVE_DE_TESTE" in mensagem
    assert ".env" in mensagem


def test_chave_vazia_conta_como_ausente(monkeypatch):
    """`GEMINI_API_KEY=` no .env e o erro mais provavel: a variavel existe,
    o valor nao. String vazia tem que falhar como ausencia, nao passar adiante
    e virar erro de autenticacao no meio de um lote de 120 casos."""
    monkeypatch.setenv("CHAVE_DE_TESTE", "")
    with pytest.raises(ChaveAusente):
        exigir_chave("CHAVE_DE_TESTE")


def test_ambiente_vence_o_arquivo_env():
    """`load_dotenv(override=False)`: variavel ja injetada (CI, container,
    deploy) nao pode ser sobrescrita pelo .env local do desenvolvedor."""
    import inspect

    import app.config as config

    fonte = inspect.getsource(config)
    assert "override=False" in fonte
