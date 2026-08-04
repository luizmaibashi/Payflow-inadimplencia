---
tipo: pesquisa
status: resolvido
criado: 2026-08-04
---

# Ticket 0004: Metodologia de avaliação (LLM-as-judge) sem ground truth real

## Bloqueio
A pesquisa de mercado desta sessão apontou LLM-as-judge como infraestrutura esperada em 2026 (não diferencial), mas não há ground truth real de underwriting humano neste projeto (dado sintético, sem analistas de crédito reais avaliando os casos).

Precisa investigar/decidir:
1. **Que rubrica usar para o juiz?** (ex: coerência entre fatores citados e a decisão da Camada 1; ausência de alucinação de dados que não estavam no input; consistência entre casos similares — não "acertou o crédito", já que não há verdade absoluta no dado sintético)
2. **Que dataset de teste usar?** Amostra da faixa REVISAR do próprio `data/raw/payflow_credit_risk.csv`, ou casos sintéticos adicionais desenhados para cobrir edge cases (ex: renda alta mas muitos cartões, autônomo com score alto)?
3. **Referência técnica**: revisar o padrão descrito no paper citado na pesquisa desta sessão ("Building Customer Support AI Agents at 100M-User Scale", KDD'26, arxiv 2606.08867) — métricas usadas lá (task success rate, trajectory quality, safety/hallucination rate, custo por tarefa) são adaptáveis a underwriting?
4. **Ferramenta**: implementar do zero (prompt de juiz + parsing) ou usar framework existente (ex: promptfoo, ragas adaptado, ou algo mais simples dado o escopo de portfólio)?

## Resultado

Pesquisa concluída em 2026-08-04.

### 1. A faixa "REVISAR" tem nome formal na literatura: **Learning to Defer (L2D)**

Achado mais importante. O que o projeto chama de "zona cinzenta que vai para revisão humana" é um problema com literatura formal, dataset público e benchmark:

- **FiFAR** (arXiv 2312.13218, 2023, Feedzai) — dataset de detecção de fraude com 50 analistas sintéticos, desenhado exatamente para estudar quando deferir a humano. Benchmark publicado em *Scientific Data* (Nature, 2025).
- *Human-AI Collaboration in Decision-Making: Beyond Learning to Defer* (Leitão et al., ICML HMCaT 2022, arXiv 2206.13202) — argumenta que capacidade e custo importam, não só acurácia.
- *Appropriate reliance* (Schemmer et al., IUI 2023) — construto bidimensional: aceitar conselho correto **e** rejeitar o incorreto. Arcabouço decisão-teórico em arXiv 2401.15356 (2024).

**Consequência:** "pedir mais informação" (uma das ações do agente, ticket 0003) é literalmente a **ação de deferral** do L2D. Isso ancora o desenho em literatura, não em intuição.

### 2. Lacuna real de literatura = onde está a contribuição do projeto

Não foi encontrada literatura avaliando **memo de crédito gerado por agente LLM contra outcome real de default**. O trabalho mais próximo (MASCA, arXiv 2507.22758, 2025 — multiagente para credit assessment) **não** faz esse backtest de custo. O resto é material de vendor.

Ou seja: o desenho decidido nos tickets 0002 + 0008 (recomendação do agente validada contra default real, com matriz de custo assimétrica) é uma lacuna genuína — é o que dá ao projeto valor além de exercício de portfólio.

### 3. Rubricas — todas **binárias**, não Likert

Hamel Husain (hamel.dev, evals-faq, 2026) é enfático: pass/fail, não escala 1-5. Razão: a diferença entre 3 e 4 é subjetiva e inconsistente, detectar diferença estatística exige amostra maior, e anotadores puxam para o meio. Pairwise só para comparar variantes de prompt, nunca para medir qualidade absoluta.

Avaliação em **três níveis** (Confident AI/DeepEval, 2026): end-to-end (tarefa cumprida?), *trajectory-level* (caminho eficiente?), component-level (qual tool quebrou?).

| # | Rubrica | Tipo | O que checa |
|---|---|---|---|
| 1 | **Tool Correctness** | Determinística (sem juiz) | Tools chamadas × gabarito esperado por caso |
| 2 | **Groundedness do memo** | Juiz binário — **eliminatória** | Toda afirmação numérica rastreia a um retorno de tool? (anti-alucinação, condição #4 do ticket 0009) |
| 3 | **Task Completion / formato** | Juiz binário | Memo cumpre o contrato do ticket 0003 |
| 4 | **Trajectory efficiency** | Determinística | Chamadas redundantes; ferramenta macro usada como atributo do cliente (violação declarada no ticket 0009) |

Benchmarks de referência para o modelo mental: **BFCL v4** (teste unitário de chamada de função, determinístico) × **τ-bench** (Yao et al., arXiv 2406.12045 — teste de integração multi-turn, `pass@1`).

### 4. Vieses do juiz e mitigação

Fonte primária: **Zheng et al., NeurIPS 2023 (arXiv 2306.05685)** — *position bias*, *verbosity bias*, *self-enhancement bias*. Reporta >80% de concordância GPT-4 × humanos em 3K votos de especialistas. Mitigações: swap de posição, few-shot, reference-guided. Ver também *Self-Preference Bias in LLM-as-a-Judge* (arXiv 2410.21819, 2024).

**Mitigação prioritária (Husain, mais pragmática):** em vez de caçar juiz "neutro", **calibrar contra labels humanos e reportar TPR e TNR num holdout rotulado**. Agreement bruto é *trap metric* — com classes desbalanceadas o juiz acerta muito e erra exatamente as falhas raras que importam.

Regra adotada: **juiz de família diferente do gerador** + swap de posição em qualquer pairwise.

### 5. Framework: **DeepEval** (OSS, pytest-native)

| Ferramenta | Veredito |
|---|---|
| **DeepEval** | ✅ **Escolhido.** Métricas agênticas de primeira classe (Tool Correctness, Task Completion, trace-level), G-Eval para critérios custom, roda como teste pytest → gate em CI. Contra: empurra para o SaaS Confident AI (ignorável). |
| Inspect AI (UK AISI, MIT) | 🔶 Alternativa "séria" se quiser sinalizar mais rigor; mais cerimônia (task-decorator). |
| Ragas | 🔶 Só se quiser a métrica de faithfulness isolada — escopo é RAG, não agente. |
| promptfoo | ❌ Forte em red-teaming, menos natural para trace de agente. |
| LangSmith / Braintrust | ❌ SaaS, infra externa e custo. |

O projeto já usa pytest → DeepEval encaixa sem infraestrutura nova.

### 6. Tamanho do eval set e estatística

- **Error analysis:** ≥100 traces; parar quando ~20 traces seguidos não gerarem categoria nova (Husain, 2026).
- **Calibração do juiz:** 100+ exemplos rotulados à mão, reportando **TPR/TNR com IC de Wilson** (não normal).
- **Eval set da Camada 2:** 150-200 casos da zona cinzenta, estratificado por `TARGET`.
- **Backtest de custo:** test set completo da faixa, com **IC bootstrap** sobre o delta agente-vs-threshold.

⚠️ **Alerta estatístico que valida a regra do `AGENTS.md` raiz:** com n=100 e 80% de acerto, o IC95% vai de ~72% a ~88%. Um delta de 4 pontos entre dois prompts é **menos da metade do ruído**. Não existe número canônico de "mínimo defensável" — a orientação real é poder estatístico para o efeito que se quer detectar.
