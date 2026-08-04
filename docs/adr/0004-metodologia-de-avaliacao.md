# ADR-0004: Metodologia de avaliação — DeepEval, rubricas binárias e calibração do juiz

**Data**: 2026-08-04
**Status**: Accepted
**Contexto**: PayFlow — decisão D4 da `SPEC_FINAL.md`, pesquisa do ticket Wayfinder [0004](../wayfinder/refatoracao-camada-agentica/0004-metodologia-avaliacao-llm-judge.md)

---

## 1. CONTEXTO (O QUÊ?)

Um agente que escreve memos precisa de avaliação, e "parece bom" não é avaliação. A pesquisa de mercado apontou LLM-as-judge como **infraestrutura esperada em 2026, não diferencial** — ou seja: não ter é penalidade, ter não é mérito. O mérito tem que vir de outro lugar.

## 2. DECISÃO (POR QUÊ?)

### 2.1 O achado que reposiciona o projeto

Duas descobertas da pesquisa:

1. **A zona cinzenta tem nome formal: *Learning to Defer* (L2D).** FiFAR (arXiv 2312.13218, Feedzai 2023; benchmark em *Scientific Data*/Nature 2025); Leitão et al. (ICML HMCaT 2022); *appropriate reliance* (Schemmer et al., IUI 2023). "Pedir mais informação" é literalmente a ação de deferral. O desenho passa a estar ancorado em literatura, não em intuição.
2. **Não existe literatura avaliando memo de crédito gerado por agente LLM contra outcome real de default.** O trabalho mais próximo (MASCA, arXiv 2507.22758, 2025) **não** faz backtest de custo. O resto é material de vendor.

> **É aqui que está a contribuição.** Não no agente, não no juiz — no **backtest de custo contra default real**, que só é possível por causa do ADR-0001.

### 2.2 Rubricas: todas **binárias**, nunca Likert

| # | Rubrica | Tipo | O que checa |
|---|---|---|---|
| 1 | **Tool Correctness** | Determinística | Tools chamadas × gabarito por caso |
| 2 | **Groundedness** | Juiz binário — **eliminatória** | Toda afirmação numérica rastreia a um retorno de tool |
| 3 | **Task Completion / formato** | Juiz binário | Memo cumpre o contrato do ADR-0003 |
| 4 | **Trajectory efficiency** | Determinística | Sem chamadas redundantes; tool de cenário **não** usada por cliente |

**Por que binário** (Husain, evals-faq 2026): a diferença entre 3 e 4 numa escala 1–5 é subjetiva e inconsistente entre anotadores; anotadores puxam para o meio; e detectar diferença estatística numa escala exige amostra maior que num pass/fail. Pairwise só para comparar variantes de prompt — nunca para medir qualidade absoluta.

**Por que groundedness é eliminatória:** um memo com um número inventado é pior que memo nenhum — dá confiança falsa a um humano que vai decidir crédito com base nele. Falhou groundedness, o caso falhou, independentemente do resto.

Avaliação em três níveis (DeepEval, 2026): end-to-end, *trajectory-level*, component-level. Modelo mental de referência: **BFCL v4** (unitário, determinístico) × **τ-bench** (integração multi-turn, `pass@1`).

### 2.3 Viés do juiz e a mitigação que realmente importa

Vieses documentados (Zheng et al., NeurIPS 2023, arXiv 2306.05685): *position*, *verbosity*, *self-enhancement*. Mitigações estruturais adotadas: **juiz de família diferente do gerador** + swap de posição em qualquer pairwise.

**Mas a mitigação prioritária é outra:** calibrar o juiz contra **labels humanos** e reportar **TPR e TNR** num holdout rotulado. *Agreement* bruto é *trap metric* — com classes desbalanceadas, o juiz acerta muito e erra exatamente as falhas raras que importam.

Os labels vêm da tela de revisão do ADR-0003. Sem ela, não há calibração.

### 2.4 Ferramenta: DeepEval

| Ferramenta | Veredito |
|---|---|
| **DeepEval** | ✅ Métricas agênticas de primeira classe (Tool Correctness, Task Completion, trace-level), G-Eval para critérios custom, roda como teste pytest → vira gate em CI. Contra: empurra para o SaaS Confident AI (ignorável) |
| Inspect AI (UK AISI) | 🔶 Mais cerimônia; alternativa se quiser sinalizar rigor extra |
| Ragas | 🔶 Escopo RAG, não agente |
| promptfoo | ❌ Forte em red-teaming, menos natural para trace de agente |
| LangSmith / Braintrust | ❌ SaaS, custo e infra externa |

O projeto já usa pytest — DeepEval encaixa sem infraestrutura nova.

### 2.5 Amostras e estatística

- **Error analysis:** ≥100 traces; parar quando ~20 traces seguidos não gerarem categoria nova.
- **Calibração do juiz:** 100+ exemplos rotulados à mão → **TPR/TNR com IC de Wilson** (não normal — com proporções extremas o intervalo normal vaza para fora de [0,1]).
- **Eval set da Camada 2:** 150–200 casos da zona cinzenta, estratificado por `TARGET`.
- **Backtest de custo:** faixa completa, com **IC bootstrap** sobre o delta agente × threshold.

> ⚠️ **Regra dura:** com `n=100` e 80% de acerto, o IC95% vai de ~72% a ~88%. Um delta de 4 p.p. entre dois prompts é **menos da metade do ruído**. Nunca reportar proporção sem `n` e sem intervalo — vale para eval, README e deck.

---

## 3. CONSEQUÊNCIAS

**Positivas:**
- Evals viram gate de CI, não relatório manual.
- Groundedness eliminatória cria uma linha de segurança clara.
- A contribuição do projeto fica explícita e mensurável (backtest de custo).

**Negativas / limitações:**
- Rubricas binárias perdem granularidade: um memo "quase certo" e um péssimo falham igual. Aceito — a granularidade volta pela análise de erro qualitativa.
- Custo de API do juiz por rodada de eval.
- **Até existirem os 100 labels, as rubricas com juiz são indicativas, não medidas** (débito #10).
- Um único revisor não-especialista como ground truth é limitação declarada, não resolvida.

---

## 4. ALTERNATIVAS DESCARTADAS

| Opção | Por quê rejeitada |
|-------|----------------------|
| Escala Likert 1–5 | Subjetiva, inconsistente entre anotadores, exige amostra maior para o mesmo poder |
| Agreement bruto juiz × humano | *Trap metric* sob desbalanceamento — mascara erro nas falhas raras |
| Mesmo modelo como gerador e juiz | *Self-enhancement bias* documentado |
| Só métricas determinísticas (sem juiz) | Não capturam groundedness da narrativa nem cumprimento semântico da tarefa |
| Eval só end-to-end | Não localiza a falha; trajectory e component-level dizem **onde** quebrou |

---

## 5. IMPACTO & VALIDAÇÃO

**Métrica de sucesso:** suíte DeepEval rodando em pytest; relatório com `n` e intervalo para cada rubrica; TPR/TNR do juiz com IC de Wilson; delta de custo do backtest com IC bootstrap.

**Risco de regressão:** eval set versionado. Trocar casos do eval set entre rodadas invalida a comparação — mesmo problema de comparar modelos com perguntas diferentes (pareamento).

---

## 6. LINKS RELACIONADOS

- Ticket `0004-metodologia-avaliacao-llm-judge.md`
- ADR-0003 (contrato avaliado + tela que produz os labels), ADR-0007 (trajetória avaliada)
- `wiki/concepts/01_data_and_mlops/Estatistica_de_Avaliacao.md` (base de conhecimento)
- Zheng et al., NeurIPS 2023 (arXiv 2306.05685); FiFAR (arXiv 2312.13218); τ-bench (arXiv 2406.12045)
