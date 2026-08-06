"""Ponto unico de leitura de configuracao/segredo do projeto.

POR QUE ESTE ARQUIVO EXISTE: o projeto tem QUATRO entrypoints (scripts/,
notebooks/, Streamlit em app/main.py, FastAPI). Chamar `load_dotenv()` em cada
um significa lembrar em quatro lugares — e o esquecido sempre e o notebook.
Chamar dentro do adaptador esconderia efeito colateral em codigo de biblioteca
(importar um modulo passaria a mexer no ambiente do processo, vazando entre
testes). Centralizar aqui resolve os dois: explicito, achavel, um lugar so.

NENHUMA CHAVE MORA NESTE ARQUIVO. Elas vivem em `.env` na raiz (ignorado pelo
git) — este modulo so le. Ver `.env.example` para os nomes esperados.
"""
import os
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parents[1]

# Carrega .env uma unica vez, na importacao. `override=False`: variavel ja
# presente no ambiente (CI, container, deploy) VENCE o arquivo local — o .env
# e conveniencia de desenvolvimento, nao fonte de verdade em producao.
try:
    from dotenv import load_dotenv

    load_dotenv(RAIZ_PROJETO / ".env", override=False)
except ImportError:  # pragma: no cover - ambiente sem python-dotenv
    # Sem o pacote, so o ambiente do processo vale. Nao e erro: em container as
    # variaveis ja chegam injetadas e o .env nem existe.
    pass


class ChaveAusente(RuntimeError):
    """Segredo obrigatorio nao configurado. Mensagem diz onde resolver."""


def exigir_chave(nome: str) -> str:
    """Le um segredo obrigatorio ou falha com instrucao acionavel.

    Falhar cedo e de proposito: chave ausente que vira `None` so estoura la na
    frente, no meio de um lote de 120 casos, com erro de autenticacao do
    provider — mensagem que nao diz o que fazer.
    """
    valor = os.environ.get(nome)
    if not valor:
        raise ChaveAusente(
            f"{nome} nao configurada.\n"
            f"  1. copie {RAIZ_PROJETO / '.env.example'} para .env\n"
            f"  2. preencha {nome} com a chave do provider\n"
            f"  (.env esta no .gitignore — a chave nunca vai para o repositorio)"
        )
    return valor
