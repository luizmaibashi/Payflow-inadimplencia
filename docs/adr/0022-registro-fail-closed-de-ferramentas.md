# ADR-0022 — Registro fail-closed de ferramentas do agente

**Status:** Accepted
**Data:** 2026-09-04

## Contexto

`validar_trajetoria()` usava `FERRAMENTAS_SEMPRE_APLICAVEIS`, uma lista manual separada do catálogo entregue ao LLM. Uma ferramenta nova poderia existir em `FerramentasCaso` sem entrar nessa lista. Nesse cenário, ausência de verificação pareceria aprovação.

## Decisão

Descrição e aplicabilidade passam a viver juntas em `DEFINICOES_FERRAMENTAS`. As visões usadas pelo LLM e pelo gate são derivadas desse registro. Um teste introspecta todos os métodos públicos `consultar_*` de `FerramentasCaso` e exige correspondência exata com o registro.

## Consequências

- ferramenta nova sem política explícita quebra a suíte;
- a regra condicional do histórico de bureau continua preservada;
- adicionar ferramenta exige alterar um único registro de domínio;
- o débito #22 deixa de depender da memória de quem edita.

## Alternativa rejeitada

Manter duas listas e acrescentar comentário de lembrete. Comentário não produz sinal automático e não muda o comportamento fail-open.
