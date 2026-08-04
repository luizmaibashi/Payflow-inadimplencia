# SPEC FINAL — Refatoração completa: crédito com camada agêntica de underwriting

**Data:** 2026-08-04
**Origem:** 9 tickets Wayfinder resolvidos (0001-0009) nesta pasta
**Status:** Pronta para `/grill-with-docs` (validação final) → ADRs → implementação

---

## 1. Contexto e motivação

Projeto originalmente construído durante a Pós-Tech (FIAP) como classificador de inadimplência sobre **dado sintético** de uma empresa fictícia ("PayFlow"). A refatoração foi motivada por três achados desta sessão:

1. **Análise de valor do portfólio** — nenhum dos 7 projetos tem camada agêntica ou evals; a disciplina de engenharia mais alta está no `stable-treasury` (12 ADRs, 9 suítes de teste, val-loop).
2. **Pesquisa de mercado 2026** — crédito é o domínio com o salto de técnica mais nítido (scoring clássico → agentes de underwriting multi-etapa com humano no loop); LLM-as-judge virou infraestrutura esperada, não diferencial.
3. **Lacuna de literatura** (ticket 0004) — não existe trabalho publicado avaliando memo de crédito gerado por agente LLM contra outcome real de default. É onde este projeto contribui.

**Escopo real:** não é "adicionar um agente". A Camada 1 é reconstruída sobre dado real — na prática, projeto novo reaproveitando o esqueleto arquitetural do anterior.

---

## 2. Decisões consolidadas

| # | Decisão | Ticket |
|---|---|---|
| D1 | Dataset **Home Credit Default Risk** (Kaggle, ~307k clientes, tabelas relacionais). Retreino completo da Camada 1. | [0001](0001-estrategia-de-dados.md), [0007](0007-dataset-lgd-fontes-externas.md) |
| D2 | Decisão por **valor esperado por observação**, não corte global. LGD 70-85% (recuperação 15-30%) como premissa declarada. | [0002](0002-origem-dos-thresholds.md) |
| D3 | Memo em **JSON Pydantic** como fonte de verdade; narrativa renderizada dos campos. Agente **não vê** o score da Camada 1. | [0003](0003-contrato-memo-de-credito.md) |
| D4 | Avaliação com **DeepEval**, 4 rubricas **binárias**, juiz de família diferente do gerador. | [0004](0004-metodologia-avaliacao-llm-judge.md) |
| D5 | `docs/adr/` do zero; docs de refatoração antigos excluídos. | [0005](0005-housekeeping-docs-legado.md) |
| D6 | Padrão de rigor herdado do `stable-treasury` (ver §6). | [0006](0006-nivel-de-disciplina-stable-treasury.md) |
| D7 | Agente com **duas famílias de ferramentas**: caso (multi-hop no Home Credit) + cenário (BCB/IBGE, por lote). | [0008](0008-escopo-camada-2-contexto-externo.md) |
| D8 | Cenário macro brasileiro entra **pela LGD**, como stress declarado — nunca como atributo do cliente. | [0009](0009-conflito-dataset-vs-fontes-externas.md) |

---

## 3. Arquitetura alvo

```
                    ┌─────────────────────────────────────┐
   Home Credit ────►│ CAMADA 1 — classificador (PD)       │
   (application)    │ paridade treino-serving testada     │
                    └──────────────┬──────────────────────┘
                                   │ p_default
                    ┌──────────────▼──────────────────────┐
                    │ MOTOR DE DECISÃO                    │
                    │ valor esperado por observação:      │
                    │  custo_aprovar = p × EAD × LGD      │
                    │  custo_negar   = (1−p) × margem     │
                    │  → APROVAR | ZONA CINZENTA | NEGAR  │
                    └──────────────┬──────────────────────┘
                                   │ só a zona cinzenta
                    ┌──────────────▼──────────────────────┐
                    │ CAMADA 2 — agente (não vê p_default)│
                    │  tools de CASO (multi-hop):         │
                    │   bureau · bureau_balance ·         │
                    │   previous_application ·            │
                    │   installments_payments             │
                    │  tool de CENÁRIO (1×/lote):         │
                    │   BCB SGS · SCR.data · IBGE → LGD   │
                    │  → memo JSON (APROVAR|NEGAR|DEFERIR)│
                    └──────────────┬──────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
      ┌──────────────┐   ┌──────────────────┐  ┌────────────────┐
      │ EVALS        │   │ TELA DE REVISÃO  │  │ BACKTEST       │
      │ DeepEval,    │   │ Streamlit:       │  │ custo esperado │
      │ 4 rubricas   │   │ analista decide  │  │ realizado vs.  │
      │ binárias     │   │ → 100 labels     │  │ threshold puro │
      └──────────────┘   └──────────────────┘  └────────────────┘
```

**Ponto crítico do desenho:** o agente forma parecer **independente** do score. O confronto parecer × score acontece depois, e é o que permite medir se o agente agrega informação (não apenas parafraseia o modelo).

---

## 4. Linguagem Ubíqua (semente do `AGENTS.md`)

| Termo | Significado |
|---|---|
| **PD** (Probability of Default) | Probabilidade de inadimplência estimada pela Camada 1 |
| **LGD** (Loss Given Default) | Fração não recuperada dado o default. Premissa: 70-85% (recuperação 15-30%) |
| **EAD** (Exposure at Default) | Valor exposto no momento do default |
| **Perda esperada** | `PD × LGD × EAD` |
| **Zona cinzenta** | Faixa de indiferença em torno do ponto de equilíbrio do valor esperado; substitui os buckets fixos 0.40/0.65 |
| **Deferral** | Ação de encaminhar a humano (`DEFERIR`), formalizada pela literatura de *Learning to Defer* |
| **Ferramenta de caso** | Tool que consulta dado do cliente em análise (tabelas relacionais do Home Credit) |
| **Ferramenta de cenário** | Tool que consulta contexto macro (BCB/IBGE), 1× por lote, nunca por cliente |
| **Stress declarado** | Uso do cenário macro como premissa rotulada ("se esta carteira operasse sob condições BR de {data}"), jamais como atributo do cliente |
| **Groundedness** | Toda afirmação numérica do memo rastreia a um retorno de ferramenta (rubrica eliminatória) |
| **Trajectory quality** | Qualidade da *sequência* de chamadas de ferramenta, não só da resposta final |
| **Ancoragem** | Viés de o agente parafrasear o score em vez de julgar — evitado ocultando `p_default` do agente |

---

## 5. Plano de avaliação

| Rubrica | Tipo | Critério |
|---|---|---|
| Tool Correctness | Determinística | Tools chamadas × gabarito por caso |
| **Groundedness** | Juiz binário — **eliminatória** | Toda afirmação numérica rastreia a uma tool |
| Task Completion / formato | Juiz binário | Memo cumpre o contrato Pydantic |
| Trajectory efficiency | Determinística | Sem chamadas redundantes; tool de cenário não usada por cliente |

**Amostras:** eval set de 150-200 casos da zona cinzenta (estratificado por `TARGET`); 100 labels humanos (da tela de revisão) para calibrar o juiz, reportando **TPR/TNR com IC de Wilson**; backtest de custo com **IC bootstrap** sobre o delta agente × threshold.

⚠️ **Regra estatística:** nunca reportar proporção sem `n` e sem intervalo. Com n=100 e 80% de acerto, o IC95% é ~72-88% — um delta de 4pp entre prompts é menos da metade do ruído.

---

## 6. Definition of Done

1. `AGENTS.md` do projeto: Linguagem Ubíqua + débitos técnicos numerados (resolvidos ficam riscados apontando o ADR) + escopo negativo.
2. `docs/adr/0001…N` — mínimo 6 ADRs, um por decisão D1-D8.
3. Testes: ≥1 arquivo por módulo, incluindo paridade treino-serving reescrita para o esquema Home Credit.
4. Eval set versionado + relatório com `n` e intervalo.
5. `docs/audit/` com ao menos uma auditoria pós-implementação.
6. README com seção "o que este projeto assume abertamente".

**Escopo negativo (a definir formalmente no ADR):** sem decisão de crédito autônoma sem humano; sem consulta a bureau individual (não existe API pública no Brasil); sem PII real.

**Princípio guia** (herdado do `stable-treasury`, ADR-0011 §6):
> Onde existe dado gratuito que substitua uma premissa por medição, substituir. Onde o problema é estrutural, expor o disclaimer — não fingir uma correção que não existe para ser feita de graça.

---

## 7. Riscos assumidos

| Risco | Mitigação |
|---|---|
| Cenário macro virar decoração | Ele **precisa** mover o corte via LGD de forma rastreável (condições #1-4 do ticket 0009) |
| Agente divergir muito do modelo | Divergência é sinal medível, não defeito — é o objeto do backtest |
| Juiz LLM com viés | Juiz de família diferente do gerador; calibração contra labels humanos; TPR/TNR, não agreement bruto |
| Escopo grande (projeto novo, não refactor) | Implementação em fases, ADR por decisão; a Camada 1 precisa estar validada antes da Camada 2 |
| Dataset de mercado emergente ≠ Brasil | Framing honesto: transferência de **método**, declarada — nunca afirmar que o cliente é brasileiro |

---

## 8. Próximos passos

1. ~~Gerar ADRs a partir de D1-D8~~ **FEITO (2026-08-04)** — `AGENTS.md` do projeto + `docs/adr/0001-0008`, um por decisão.
2. **Gate 0 (antes de qualquer código do motor):** medir a dispersão de `M/LGD` na carteira do Home Credit. Se for estreita, o corte por observação reproduz o corte global — ver ADR-0002 §2.3 e §5.
3. **Gate 1:** calibração da Camada 1 (reliability diagram + Brier). Sem ela, o motor de EV é aritmética sobre número sem significado (ADR-0002 §2.5).
4. `/pavc-audit` antes de iniciar implementação (decisão arquitetural pesada).
5. Implementação por fases, com `spec-governance` ativa.

### Correções de rota registradas na aula do Bloco 1 (2026-08-04)

- **`p*` é invariante ao EAD** (`p* = m/(m+ℓ)`): o corte por observação só se paga se a razão margem/LGD variar entre contratos. Vira Gate 0.
- **O rigor estava na premissa errada:** 1 p.p. de erro na margem move `p*` ~4× mais que 1 p.p. na LGD. A margem, que não tinha fonte, passa a ser derivada dos juros implícitos do contrato (ADR-0002 §2.4).
- **Calibração vira gate bloqueante** — o pipeline legado usa `imbalanced-learn`, que desloca o prior e infla `p̂` sem o AUC acusar (débito técnico #3).

> **Pendência de aprendizado registrada:** o usuário pediu aula técnica completa sobre tudo que foi decidido aqui (valor esperado/LGD, Learning to Defer, LLM-as-judge, trajectory eval, IC de Wilson/bootstrap). Regra da base: *aula antes da prova* — ensinar primeiro, ele reexplica com as próprias palavras, `--self-pass`, reteste no dia seguinte.
