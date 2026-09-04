---
tipo: tarefa-simples
status: resolvido
criado: 2026-09-04
---

# Ticket 0003: Gate fail-closed e testes

## Bloqueio

Uma lista manual desatualizada pode deixar uma feature nova passar sem checagem. Isso é pior do que falhar: parece aprovação.

## Resultado

Entregue em `app/contrato_disponibilidade.py`, com 12 testes em
`tests/test_contrato_disponibilidade.py`. O gate bloqueia feature ausente ou
sem contrato, status desconhecido/bloqueado, coluna ausente, data nula ou
malformada e data posterior à decisão. Isso cobre as bordas de entrada; coorte
vazia/uma classe e target não amadurecido pertencem ao Ticket 0004, porque são
condições do relatório de desempenho, não do contrato de dados.
