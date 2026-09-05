# Ticket 0003 — Legado e política de retenção

## Decisão a resolver

Quais artefatos da V1 ainda agregam valor e quais só aumentam ambiguidade e superfície de manutenção?

## Critério

- **manter:** evidência histórica pequena, documentação, figuras e decisões ainda úteis;
- **remover do estado atual:** código, modelo, dataset e notebook sem consumidor atual;
- **não apagar a história:** tudo permanece recuperável no Git e a narrativa fica em `docs/LEGADO_V1.md`.

## Evidência necessária

Busca de referências prova que nenhum entrypoint, teste ou script atual importa os módulos V1 ou lê seus artefatos.
