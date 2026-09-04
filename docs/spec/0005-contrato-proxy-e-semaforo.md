# Spec 0005 — Contrato proxy e semáforo de uso

**Data:** 2026-09-04
**Status:** Implementada — revisão humana pendente
**Dono da aprovação de merge:** Luiz Maibashi

## Objetivo

Transformar o recorte exploratório de seis features em contrato reutilizável e
converter o boletim de coorte em uma decisão de uso compreensível.

## Escopo

Inclui o contrato `PROXY_SEMANTICA` das seis variáveis e a política
`BLOQUEAR`/`AGUARDAR`/`PESQUISA`/`MANTER`/`REVISAR`. Não inclui re-treino,
dashboard, API ou decisão de crédito individual.

## Critérios de aceitação

1. As seis features são classificadas como proxy, nunca permitidas estritas.
2. Modo exploratório recebe `PESQUISA` mesmo com AUC estável.
3. Execução estrita com AUC dentro de 0,03 da referência recebe `MANTER`.
4. Queda maior que 0,03 recebe `REVISAR`.
5. Target imaturo ou AUC indisponível recebe `AGUARDAR`.
6. Testes começam vermelhos e a suíte completa termina verde.

## Riscos e política de entrada

Não há PII, credenciais ou fontes externas. A referência de AUC é um parâmetro
explícito; não pode ser inferida silenciosamente da própria coorte avaliada.

**Evidência executada:** os testes começaram vermelhos pela ausência dos
módulos; depois 11 testes novos passaram e a suíte completa passou com 231
testes.
