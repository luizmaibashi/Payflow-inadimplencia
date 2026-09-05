# Spec 0003 — Modo exploratório isolado

**Data:** 2026-09-04
**Status:** Implementada e aprovada em 2026-09-04
**Dono da aprovação de merge:** Luiz Maibashi

## Objetivo

Permitir pesquisa com features de disponibilidade ainda não comprovada sem
deixar que elas passem por engano como dados aprovados para produção.

## Escopo

Inclui status `PROXY_SEMANTICA`, modo `ESTRITO`/`EXPLORATORIO` e retorno do modo
no relatório. Não inclui treino, interface, API ou liberar uma feature
desconhecida.

## Critérios de aceitação

1. O padrão estrito bloqueia proxy semântico.
2. O modo exploratório libera proxy semântico e retorna o modo usado.
3. `DESCONHECIDA` e `BLOQUEADA` continuam bloqueadas nos dois modos.
4. A suíte nova começa vermelha e a completa termina verde.

## Riscos e política de entrada

Não há PII nem credenciais. O dado é público e anonimizado. O modo exploratório
é uma exceção explícita de pesquisa, não uma autorização para decisão de crédito.

**Evidência executada:** o teste começou vermelho pela ausência de
`ModoExecucao`; depois 15 testes do contrato passaram (89% de cobertura do
módulo) e a suíte completa passou com 215 testes.
