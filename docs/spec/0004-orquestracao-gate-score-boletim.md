# Spec 0004 — Orquestração gate → score → boletim

**Data:** 2026-09-04
**Status:** Implementada — revisão humana pendente
**Dono da aprovação de merge:** Luiz Maibashi

## Objetivo

Executar o fluxo de monitoramento na ordem correta: validar disponibilidade,
pontuar somente se a entrada passar e, então, medir estabilidade por coorte.

## Escopo

Inclui um orquestrador puro que recebe dados anonimizados, contrato e uma função
de score injetada. Não inclui treino, persistência, API, dashboard ou decisão
autônoma de crédito.

## Critérios de aceitação

1. O score não é chamado quando o gate bloqueia uma feature.
2. Quando o gate passa, as previsões alimentam o boletim de coorte.
3. Modo exploratório aparece no relatório final.
4. Predição com tamanho diferente da coorte falha de modo explícito.
5. Teste inicia vermelho e a suíte completa termina verde.

## Riscos e política de entrada

Somente DataFrames públicos/anonimizados e uma função local são aceitos. O
orquestrador não recebe PII, credenciais nem chama provedores externos.

**Evidência executada:** o teste começou vermelho pela ausência do módulo;
depois 5 testes de integração passaram (91% de cobertura do orquestrador) e a
suíte completa passou com 220 testes.
