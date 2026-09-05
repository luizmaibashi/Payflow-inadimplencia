# ADR-0021 — Remover o runtime V1 e preservar sua narrativa

**Status:** Accepted
**Data:** 2026-09-04

## Contexto

A V1 usava dado sintético, Random Forest, cortes arbitrários e uma API/Streamlit próprios. A V2 substituiu modelo e pergunta; a V3 acrescentou monitoramento por coorte. Mesmo despublicada, a V1 continuava executável na árvore principal e mantinha dois entrypoints, duas dependências de servidor, dois modelos e um notebook sem consumidor atual.

Isso cria dois riscos: o leitor pode executar a versão errada e a manutenção pode tratar código morto como produto suportado.

## Decisão

Remover do estado atual:

- `app/main.py`, `app/api.py`, `app/service.py`, `app/schemas.py`, `app/utils.py`;
- `models/modelo_payflow_v1.pkl`, `models/colunas_modelo.pkl`;
- `data/raw/payflow_credit_risk.csv`;
- `notebooks/01_credit_risk_modeling_payflow.ipynb`.

Preservar:

- `docs/LEGADO_V1.md`, reescrito como registro não executável;
- figuras históricas pequenas;
- commits anteriores, que permitem recuperar qualquer artefato removido.

## Alternativas consideradas

1. **Manter tudo rotulado como legado.** Rejeitada: a rotulagem não elimina entrypoints mortos nem a possibilidade de executar a versão errada.
2. **Mover a V1 para uma pasta `legacy/`.** Rejeitada: reduz a confusão visual, mas mantém dependências, artefatos binários e manutenção sem benefício atual.
3. **Apagar também documentação e figuras.** Rejeitada: perderia a evolução técnica e a lição de negócio que ajudam a explicar o projeto.

## Consequências

- a árvore principal passa a representar somente V2 e V3;
- `fastapi` e `uvicorn` deixam de ser dependências;
- a V1 não roda a partir do `HEAD`, mas continua recuperável no histórico Git;
- o README e o documento de legado precisam declarar claramente essa fronteira.

## Reversibilidade

Alta. A remoção não reescreve o histórico; arquivos podem ser restaurados de um commit anterior se surgir uma necessidade real.
