# ADR-0007: Duas famílias de ferramentas do agente — caso e cenário

**Data**: 2026-08-04
**Status**: Accepted
**Contexto**: PayFlow — decisão D7 da `SPEC_FINAL.md`, ticket Wayfinder [0008](../wayfinder/refatoracao-camada-agentica/0008-escopo-camada-2-contexto-externo.md), fechado após o [0009](../wayfinder/refatoracao-camada-agentica/0009-conflito-dataset-vs-fontes-externas.md)

---

## 1. CONTEXTO (O QUÊ?)

A Camada 2 podia ser (B) um assistente que redige sobre os dados já presentes no prompt, ou (C) um agente que **busca** contexto antes de recomendar. A opção C foi escolhida — mas "agente com tools" só tem valor se as tools fizerem trabalho que o prompt não faria.

O risco concreto: um agente que "consulta" dados que já estavam no contexto é tool-use de fachada. Passa em demo, não passa em entrevista.

## 2. DECISÃO (POR QUÊ?)

**Duas famílias de ferramentas, com granularidades e papéis deliberadamente diferentes.**

| Família | Ferramentas | Granularidade | Papel |
|---|---|---|---|
| **Caso** (multi-hop real) | `bureau`, `bureau_balance`, `previous_application`, `installments_payments`, `credit_card_balance` | **Por cliente** | O agente decide *o que puxar* para o caso em análise |
| **Cenário** (stress declarado) | BCB SGS (SELIC/IPCA), BCB SCR.data, IBGE SIDRA | **Por lote**, nunca por cliente | Calibra a premissa macro (via LGD → ponto de corte) |

### 2.1 Por que as tools de caso são multi-hop genuíno

O agente **não** recebe as tabelas pré-agregadas no prompt. Ele recebe o `SK_ID_CURR` e decide a sequência: consultar o bureau primeiro? Se houver atraso, aprofundar em `bureau_balance`? Vale olhar aplicações anteriores?

Isso é literalmente o que um analista de crédito faz — e é o que o ADR-0001 comprou ao escolher um dataset relacional. Pré-agregar tudo no prompt destruiria essa propriedade e reduziria o agente a um redator.

**Consequência para o eval:** a *sequência* passa a ser objeto de medição (trajectory quality, ADR-0004), não só a resposta final.

### 2.2 Por que a tool de cenário é por lote — e por que isso é regra dura

Consultar SELIC por cliente sugeriria que o macro é atributo daquele cliente. Não é: o dataset é de mercados emergentes anonimizados (ADR-0001), e o cenário BR é premissa da carteira, não característica da pessoa (ADR-0008).

> **Chamar a tool de cenário dentro do loop de um cliente é violação declarada** — vira falha na rubrica de trajectory efficiency (ADR-0004, rubrica 4), não apenas ineficiência.

Dois efeitos colaterais bem-vindos: custo e latência caem (1 chamada por lote em vez de `n`), e o cache é trivial.

### 2.3 Auditabilidade obrigatória

Toda chamada registra tool, argumentos, série/data quando aplicável, e valor retornado. É esse registro que torna a rubrica de **groundedness** verificável — o `fonte_tool` do memo (ADR-0003) precisa resolver contra a trace real.

---

## 3. CONSEQUÊNCIAS

**Positivas:**
- Tool-use genuíno, alinhado ao padrão de mercado 2026 (underwriting multi-etapa).
- Separação de granularidade impede, por construção, que o macro contamine o caso.
- A trace vira insumo de três coisas ao mesmo tempo: groundedness, trajectory eval e auditoria.

**Negativas / limitações:**
- Multi-hop custa tokens e latência por caso — sobe o custo por decisão, que precisa entrar no backtest.
- O agente pode entrar em loop de exploração; exige teto de chamadas por caso.
- **Gabarito de tools por caso é trabalho manual** (a rubrica Tool Correctness precisa dele) — não há atalho.
- APIs externas (BCB/IBGE) são ponto de falha: exigem cache, timeout e fallback declarado (se a série não vier, o cenário é o default declarado, não um valor inventado).

---

## 4. ALTERNATIVAS DESCARTADAS

| Opção | Por quê rejeitada |
|-------|----------------------|
| Assistente sem tools (opção B) | Sem tool-use real; o projeto não fecha a lacuna do portfólio |
| Tudo pré-agregado no prompt | Tool-use de fachada; mata o multi-hop que justificou o dataset |
| Tool de cenário por cliente | Sugere que o macro é atributo do cliente — o furo que o ADR-0008 existe para fechar |
| Fontes macro internacionais (FRED/World Bank) para casar com o dataset | Coerente, mas perde o exercício com API brasileira; o ADR-0008 resolve a coerência por outro caminho (stress declarado) |
| Bureau individual real (Serasa/SPC) | Não existe API pública no Brasil (LC 105 + LGPD) — fingir consulta seria desonestidade de produto |

---

## 5. IMPACTO & VALIDAÇÃO

**Métrica de sucesso:** Tool Correctness contra gabarito por caso; trajectory efficiency sem chamadas redundantes; **zero** chamadas de tool de cenário dentro do escopo de um cliente; 100% dos `fonte_tool` do memo resolvíveis na trace.

**Risco de regressão:** teste automatizado que falha se a tool de cenário for chamada mais de uma vez por lote — o invariante precisa estar no código, não só no ADR.

---

## 6. LINKS RELACIONADOS

- Tickets `0008-escopo-camada-2-contexto-externo.md`, `0009-conflito-dataset-vs-fontes-externas.md`
- ADR-0001 (dataset relacional que habilita o multi-hop), ADR-0003 (memo que consome as tools), ADR-0004 (rubricas), ADR-0008 (por que o cenário é por lote)
