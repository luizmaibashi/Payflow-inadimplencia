# ADR-0001: Dataset Home Credit Default Risk e retreino completo da Camada 1

**Data**: 2026-08-04
**Status**: Accepted
**Contexto**: PayFlow — decisão D1 da `SPEC_FINAL.md`, originada do ticket Wayfinder [0001](../wayfinder/refatoracao-camada-agentica/0001-estrategia-de-dados.md) e da pesquisa do [0007](../wayfinder/refatoracao-camada-agentica/0007-dataset-lgd-fontes-externas.md)

---

## 1. CONTEXTO (O QUÊ?)

A Camada 1 do projeto foi treinada sobre `data/raw/payflow_credit_risk.csv` — dado **sintético** gerado para uma empresa fictícia durante a Pós-Tech. O modelo está em produção (Streamlit + Render) com paridade treino-serving testada.

O problema não é a qualidade da engenharia: é que **não existe outcome real**. Sem rótulo de default verdadeiro:

- não há backtest possível (não se pode medir custo realizado contra custo esperado);
- a recomendação do futuro agente não tem contra o quê ser validada;
- toda métrica é auto-referente — o modelo acerta o gerador do dado, não o mundo.

Três caminhos estavam abertos: (a) manter e documentar a limitação, (b) manter o modelo e trocar só a narrativa, (c) trocar por dataset público real, com retreino.

## 2. DECISÃO (POR QUÊ?)

**Opção (c): Home Credit Default Risk (Kaggle, 2018) com retreino completo da Camada 1.**

### 2.1 Por que dataset real, e não só re-narrar

A contribuição do projeto (ADR-0004 §2.2) depende de confrontar o parecer do agente com o **default que de fato ocorreu**. Sem rótulo real, o desenho inteiro perde a única evidência que o distingue de um exercício de portfólio. Trocar a narrativa mantendo dado sintético (opção b) seria exatamente o tipo de maquiagem que o projeto se propõe a não fazer.

> **Negócio**: com rótulo real, a frase defensável passa a ser "o agente reduziu o custo esperado em X, com IC de Y" — não "o agente escreveu um memo bonito".

### 2.2 Por que Home Credit especificamente

| Critério | Home Credit |
|---|---|
| Outcome de default | ✅ `TARGET` real, base rate ~8% |
| Estrutura relacional | ✅ `bureau`, `bureau_balance`, `previous_application`, `installments_payments`, `credit_card_balance` — habilita **multi-hop genuíno** do agente (ADR-0007) |
| Volume | ✅ ~307k contratos |
| Economia do contrato | ✅ `AMT_CREDIT`, `AMT_ANNUITY`, `CNT_PAYMENT`, `AMT_GOODS_PRICE` — permite derivar margem e EAD (ADR-0002) |
| Licença/PII | ✅ público, anonimizado |

A estrutura relacional é o critério decisivo e o que separa Home Credit dos concorrentes: um dataset de tabela única daria tool-use de fachada (o agente "consultaria" o que já estava no prompt).

### 2.3 O que sobrevive do projeto atual

**A arquitetura, não o conteúdo:** deep module isolando ML, paridade treino-serving como teste de primeira classe, API e frontend desacoplados, política de decisão externalizada do modelo. O princípio de `tests/test_paridade.py` continua válido e é **reescrito** para o esquema novo.

`app/utils.py::process_credit_features` e `models/*.pkl` são reconstruídos, não adaptados — o esquema sintético (`canal_aquisicao`, `regiao`, `tipo_produto`) não tem correspondente no Home Credit.

### 2.4 Framing honesto

Deixa de ser "a empresa fictícia PayFlow no Brasil". Passa a ser **crédito ao consumidor em mercado emergente, com rótulo real**, e o contexto brasileiro entra como stress declarado (ADR-0008). Nunca afirmar que o cliente do dataset é brasileiro.

---

## 3. CONSEQUÊNCIAS

**Positivas:**
- Backtest real vira possível — é o que sustenta a contribuição do ADR-0004.
- Multi-hop do agente passa a ser genuíno (tabelas relacionais de verdade).
- Margem e EAD deixam de ser arbitrados: saem do contrato (ADR-0002).

**Negativas / limitações (débitos técnicos #1, #8, #9, #11):**
- **Isto deixou de ser um refactor.** EDA nova, feature engineering novo, retreino, testes novos — projeto novo com esqueleto reaproveitado. É o maior risco de escopo da spec.
- Home Credit é de 2018 e de mercados emergentes não-Brasil — validade externa limitada, declarada.
- O deploy público atual continua servindo o modelo legado até a Camada 1 nova passar na paridade. Decidir se despublica ou rotula.
- Dataset grande com muitas tabelas: risco de a Camada 1 consumir o tempo que era do agente. Mitigação: a Camada 1 precisa estar validada **antes** de começar a Camada 2, e "validada" inclui calibração (ADR-0002).

---

## 4. ALTERNATIVAS DESCARTADAS

| Opção | Por quê rejeitada |
|-------|----------------------|
| Manter dado sintético e documentar (a) | Sem outcome real, o backtest — núcleo da contribuição — é impossível |
| Manter modelo, trocar narrativa (b) | Ancorar em "crédito real" texto de README sobre dado fictício é exatamente o número mágico que o projeto combate |
| HMDA (EUA) | Não tem outcome de default — só originação/negação |
| Give Me Some Credit | Tabela única: mataria o multi-hop do agente |
| German Credit | n≈1.000, pequeno demais para eval com intervalo defensável |
| Base brasileira com rótulo individual | **Não existe publicamente** (LC 105 + LGPD). Confirmado em pesquisa |

---

## 5. IMPACTO & VALIDAÇÃO

**Métrica de sucesso:** Camada 1 treinada no Home Credit com (a) `tests/test_paridade.py` reescrito e passando no esquema novo, (b) reliability diagram + Brier reportados, não só AUC (pré-requisito do ADR-0002), (c) base rate e `n` explícitos em qualquer métrica.

**Risco de regressão:** enquanto os dois modelos coexistirem, qualquer comparação de métrica entre o legado e o novo é inválida (datasets diferentes, targets diferentes). Não colocar as duas no mesmo gráfico.

---

## 6. LINKS RELACIONADOS

- Tickets `0001-estrategia-de-dados.md`, `0007-dataset-lgd-fontes-externas.md`
- ADR-0002 (motor de decisão — consome `AMT_CREDIT`/`AMT_ANNUITY`/`CNT_PAYMENT` deste dataset)
- ADR-0007 (tools de caso sobre as tabelas relacionais), ADR-0008 (framing do cenário BR)
