# AGENTS.md — PayFlow (crédito com camada agêntica de underwriting)

> **Projeto**: classificador de risco de crédito (PD) + motor de decisão por valor esperado + agente de underwriting que produz memo de crédito auditável para a zona cinzenta.
> **Stack alvo**: Python · scikit-learn · Pydantic · FastAPI · Streamlit · DeepEval · APIs BCB SGS / IBGE
> **Estado (2026-08-04)**: Camada 1 **treinada e calibrada** sobre Home Credit (AUC 0,776) e motor de decisão implementado/backtestado. Camada 2 (agente), evals e tela de revisão **não iniciados**. O deploy público ainda serve o modelo legado.

> ⚠️ **Este não é um refactor — é projeto novo reaproveitando o esqueleto arquitetural.** A Camada 1 é retreinada do zero sobre dado real (Home Credit). Tratar código, modelo e testes atuais como legado a substituir, não como base a estender.

---

## Mapa do projeto

**Estado atual (legado, dado sintético):**
- `app/main.py` — frontend Streamlit
- `app/api.py` — API FastAPI
- `app/service.py` — carregamento do modelo e inferência
- `app/schemas.py` — contratos Pydantic da API
- `app/utils.py` — `get_decision_thresholds` (buckets fixos 0.40/0.65 — **substituídos** pelo ADR-0002)
- `models/modelo_payflow_v1.pkl`, `models/colunas_modelo.pkl` — artefatos do modelo antigo
- `notebooks/01_credit_risk_modeling_payflow.ipynb` — modelagem original
- `tests/test_paridade.py` — paridade treino-serving (a **reescrever** para o esquema Home Credit)

**Já existe (2026-08-04):**
- `data/raw/home_credit/` — dataset Home Credit Default Risk (Kaggle), ~3,3GB, **não versionado** (`.gitignore`). Reproduzir via `scripts/baixar_home_credit.md`
- `scripts/gate0_dispersao_m_sobre_l.py` — mede a dispersão de `m/ℓ` por contrato (Gate 0 do ADR-0002); resultado em `reports/gate0_dispersao_m_sobre_l.md`
- `scripts/camada1_baseline_e_gate1_calibracao.py` — demonstra o mecanismo de descalibração por undersampling (Gate 1); resultado em `reports/gate1_calibracao.md`
- `app/feature_engineering_home_credit.py` — agregação das 5 tabelas relacionais (bureau, previous_application, installments, POS_CASH, credit_card) em features por cliente, testado em `tests/test_paridade.py`
- `scripts/camada1_feature_engineering.py` — roda a agregação sobre o dado bruto, salva `data/processed/` (não versionado, regenerável)
- `scripts/camada1_treino.py` — treina a **Camada 1 final** com calibração isotônica embutida no pipeline (não só demonstrada); modelo em `models/camada1_home_credit_v1.pkl`, resultado em `reports/camada1_treino_final.md`. **AUC 0,776 (IC95% 0,769–0,782)** — ganho de +0,017 sobre o baseline sem features relacionais (Gate 1)
- `docs/adr/` — 8 ADRs (D1-D8) · `docs/DICIONARIO_DADOS.md` — dicionário completo em PT-BR
- `tests/test_paridade.py` — reescrito para o esquema Home Credit (5 testes, ver débito #8)

- `app/motor_decisao.py` — motor de decisão por valor esperado (ADR-0002), testado em `tests/test_motor_decisao.py` (16 testes)
- `scripts/motor_decisao_backtest.py` — backtest do motor contra o threshold legado sobre a carteira inteira, com IC bootstrap e dois cenários para a zona cinzenta; resultado em `reports/motor_decisao_backtest.md`. **Conclusão: o motor não supera o baseline** — ver ADR-0002 §2.8

**Camada 2 (2026-08-05) — infraestrutura completa, LLM real pendente:**
- `app/memo_credito.py` — contrato do parecer (teto de 8 fatos **medido**, groundedness e cegueira ao score por construção)
- `app/ferramentas_caso.py` — 3 ferramentas de caso com trace de auditoria
- `app/ferramenta_cenario.py` — cenário macro BCB, 1×/lote, cache + fallback declarado
- `app/agente_underwriting.py` — orquestração multi-hop, **cliente LLM injetado** (testável sem rede)

**Adaptadores de LLM (2026-08-05) — ADR-0009:**
- `app/clientes_llm.py` — `ClienteGemini` (gerador padrão) e `ClienteGroq` (gerador **alternativo**, família Llama). Saída JSON garantida pelo provider, temperatura 0, import do SDK lazy. Testado em `tests/test_clientes_llm.py` (12 testes, zero rede)
- `app/config.py` — ponto único de `load_dotenv` + `exigir_chave`, para os 4 entrypoints do projeto. Testado em `tests/test_config.py` (4 testes)
- `requirements-llm.txt` — SDKs separados: a suíte de 109 testes roda **sem** SDK e **sem** chave
- ⚠️ **O juiz do ADR-0004 ainda NÃO existe.** `ClienteGroq` implementa `proxima_acao` (contrato do gerador); o juiz avalia rubricas binárias sobre memo pronto — contrato diferente, módulo próprio, a construir (débito #19)

**Alvo (a construir):**
- Juiz LLM (rubricas binárias do ADR-0004) + eval set
- `docs/audit/` — auditorias pós-implementação
- Eval set versionado + relatório com `n` e intervalo

---

## Arquitetura alvo

```
Home Credit ──► CAMADA 1 (PD, calibrada) ──► MOTOR DE DECISÃO (valor esperado
                                              por observação: p* = M/(M+LGD·EAD))
                                                    │
                                       só a ZONA CINZENTA
                                                    ▼
                              CAMADA 2 — agente (NÃO vê p_default)
                              tools de CASO (multi-hop) + tool de CENÁRIO (1×/lote)
                                       → memo JSON (APROVAR|NEGAR|DEFERIR)
                                                    │
                        ┌───────────────────────────┼───────────────────────┐
                     EVALS                    TELA DE REVISÃO           BACKTEST
                (DeepEval, 4 rubricas)      (Streamlit, 100 labels)   (custo realizado)
```

**Ponto crítico do desenho:** o agente forma parecer **independente** do score. O confronto parecer × score acontece depois — é o que permite medir se o agente agrega informação em vez de parafrasear o modelo.

---

## Linguagem Ubíqua

| Termo | Significado |
|---|---|
| **PD** (*Probability of Default*) | Probabilidade de inadimplência estimada pela Camada 1. Só vale para decisão se **calibrada** (ADR-0002 §2.5) |
| **LGD** (*Loss Given Default*) | Fração não recuperada dado o default. Premissa declarada: 70–85% (recuperação 15–30%) |
| **EAD** (*Exposure at Default*) | Valor exposto no momento do default. Simplificação declarada: `EAD = AMT_CREDIT` (conservadora) |
| **Margem (`M`)** | Lucro esperado do contrato se o cliente pagar. **Premissa global declarada de 41,4%** — mediana medida em `Cash loans` de `previous_application` via `(AMT_ANNUITY × CNT_PAYMENT − AMT_CREDIT)/AMT_CREDIT`. Não é medível por caso: `CNT_PAYMENT` não existe no momento da decisão (ADR-0002 §2.8) |
| **Perda esperada** | `PD × LGD × EAD` |
| **`p*` (limiar de indiferença)** | `M / (M + LGD)`. Ponto em que aprovar e negar têm o mesmo valor esperado; o EAD se cancela quando margem e perda escalam com o principal. ≈ **37,1%** (Cash) / 32,7% (Revolving). **Não depende do modelo** — é premissa de negócio |
| **Zona cinzenta** | Faixa de `p*` implicada pela **incerteza da premissa de margem** (P25–P75 → `p*` de 27,2% a 48,2%): região onde a decisão **inverte** conforme a premissa adotada. Substitui os buckets fixos 0.40/0.65 |
| **Deferral** | Ação de encaminhar a humano (`DEFERIR`), formalizada pela literatura de *Learning to Defer* |
| **Calibração** | Correspondência entre `p̂` e frequência empírica. Medida por reliability diagram + Brier — **não** por AUC |
| **Ferramenta de caso** | Tool que consulta dado do cliente em análise (tabelas relacionais do Home Credit) |
| **Ferramenta de cenário** | Tool que consulta contexto macro (BCB/IBGE), 1× por lote, **nunca** por cliente |
| **Stress declarado** | Cenário macro usado como premissa rotulada ("se esta carteira operasse sob condições BR de {data}"), jamais como atributo do cliente |
| **Groundedness** | Toda afirmação numérica do memo rastreia a um retorno de ferramenta (rubrica **eliminatória**) |
| **Trajectory quality** | Qualidade da *sequência* de chamadas de ferramenta, não só da resposta final |
| **Ancoragem** | Viés de o agente parafrasear o score em vez de julgar — evitado ocultando `p_default` do agente |
| **Memo de crédito** | Objeto Pydantic (fonte de verdade) com decisão, fundamentos e citações de tool; a narrativa é **renderizada** dele, nunca o contrário |

---

## Regras de engenharia

- **Nunca expor `p_default` à Camada 2.** Qualquer atalho que vaze o score invalida o experimento inteiro (ADR-0003). Vale para prompt, contexto, tool e nome de variável.
- **O cenário macro entra só pela LGD.** Nunca como feature do cliente, nunca por cliente (ADR-0008).
- **Sem PII real.** Home Credit é anonimizado; nenhuma consulta a bureau individual (não existe API pública no Brasil).
- **Nunca reportar proporção sem `n` e sem intervalo.** Vale para eval, backtest e README.
- **Calibração antes de decisão.** Nenhum número de EV é válido sobre `p̂` não calibrado.
- **Modelo e política são artefatos separados.** Retreinar o classificador não muda `p*`; mudar a política de risco não exige retreinar.

---

## ADRs registrados

| ADR | Decisão | Status |
|-----|---------|--------|
| 0001 | Dataset Home Credit Default Risk + retreino completo da Camada 1 | Accepted |
| 0002 | Motor de decisão por valor esperado por observação (`p* = M/(M+LGD·EAD)`) | Accepted |
| 0003 | Contrato do memo em JSON Pydantic + agente cego ao score (anti-ancoragem) | Accepted |
| 0004 | Avaliação com DeepEval, 4 rubricas binárias, juiz de família diferente | Accepted |
| 0005 | Reset da documentação de refatoração (`docs/adr/` do zero) | Accepted |
| 0006 | Padrão de rigor herdado do `stable-treasury` | Accepted |
| 0007 | Duas famílias de ferramentas do agente: caso e cenário | Accepted |
| 0008 | Cenário macro brasileiro entra pela LGD, como stress declarado | Accepted |
| 0009 | Adaptadores de LLM: saída JSON estruturada, import lazy, config centralizada | Accepted |
| 0010 | Validação de trajetória registrada, não eliminatória | Accepted |
| 0011 | Critério explícito de Task Completion — quando `NEGAR` é defensável | Accepted |
| 0012 | Validação determinística pós-resposta para falhas de raciocínio do juiz que prompt não corrige | Accepted |

---

## Débitos técnicos conhecidos

1. ~~Camada 1 legada treinada em dado sintético~~ **RESOLVIDO** (2026-08-04) — nova Camada 1 treinada sobre Home Credit real (`models/camada1_home_credit_v1.pkl`, AUC 0,776). `app/service.py`/`app/utils.py` e `models/modelo_payflow_v1.pkl` seguem existindo mas são legado — a integração com a API/frontend ainda não foi feita (ver débito #11).
2. **Thresholds 0.40/0.65 sem derivação** (`app/utils.py::get_decision_thresholds`) — números arbitrários. Substituídos por `p*` calculado (ADR-0002).
3. ~~Calibração nunca medida~~ **PARCIALMENTE RESOLVIDO** (Gate 1, `scripts/camada1_baseline_e_gate1_calibracao.py`, 2026-08-04) — demonstrado empiricamente com baseline diagnóstico: undersampling infla `p̂` em +34,3 p.p. sobre a taxa real (Brier 0,202 vs. 0,068 natural), AUC praticamente idêntico (0,759/0,754/0,753 — confirma que não acusa o problema), isotônica corrige o Brier de volta a 0,068. Relatório em `reports/gate1_calibracao.md`. **Ainda falta:** a Camada 1 final (ADR-0001, com feature engineering completo) precisa incluir a etapa de recalibração no pipeline de produção — isto foi só a prova de mecanismo, não a implementação definitiva.
4. **Premissa de margem (`M`) sem fonte.** A LGD foi ancorada em literatura (ticket 0007), mas `M` — que move `p*` ~4× mais por ponto percentual — não tinha derivação. Endereçado no ADR-0002 §2.4; **validar empiricamente na carteira antes de implementar o motor**.
5. ~~Dispersão de `M/LGD` não medida~~ **RESOLVIDO** (ADR-0002 §2.4.1, 2026-08-04) — `scripts/gate0_dispersao_m_sobre_l.py` sobre 939k contratos reais (`previous_application.csv`): IQR de `p*` = 18,0 p.p. (6× o limiar de reprovação de 3 p.p.). Corte por observação **justificado**. Checagem cruzada com `NAME_YIELD_GROUP` valida a derivação de `m_i`. Relatório em `reports/gate0_dispersao_m_sobre_l.md`.
6. **`EAD = AMT_CREDIT`** ignora amortização — o default raramente ocorre em `t=0`. Premissa conservadora declarada, não medida.
7. **LGD 70–85% é estimativa de mercado internacional**, não número brasileiro — não existe LGD pública do BCB para crédito pessoal. Contrastada com o piso Basel FIRB (45%).
8. ~~`tests/test_paridade.py` é do esquema antigo~~ **RESOLVIDO** (2026-08-04) — reescrito para o esquema Home Credit: 4 testes unitários das funções de agregação (`app/feature_engineering_home_credit.py`) + 1 teste de contrato que trava o esquema de colunas contra o `.pkl` salvo. 5/5 passando.
9. **Dataset de mercado emergente ≠ Brasil.** A transferência é de **método**, declarada. Nunca afirmar que o cliente do dataset é brasileiro (ADR-0008).
10. **Juiz LLM não calibrado até haver labels humanos.** Até as 100 revisões existirem, as rubricas com juiz são indicativas, não medidas (ADR-0004).
11. **Deploy atual (Streamlit + Render) serve o modelo legado.** Enquanto a Camada 1 nova não passar na paridade, o público vê o projeto antigo — decidir se despublica ou rotula.
12. ~~**Margem/LGD do motor são proxies não validados**~~ **PARCIALMENTE RESOLVIDO** (ADR-0002 §2.8) — a margem deixou de ser proxy e virou **premissa global medida** (41,4%, fórmula verdadeira do Gate 0 em `Cash loans` de `previous_application`). `app/motor_decisao.py::margem_proxy_anuidade` segue no código **apenas para regressão/comparação histórica**, fora do caminho de produção. **Débito remanescente:** a LGD (70%/85% por `NAME_CONTRACT_TYPE`) continua premissa não medida — não existe dado de recuperação neste dataset, é limitação estrutural declarada.
13. ~~**Backtest não isola desenho de motor vs. calibração do baseline**~~ **RESOLVIDO / CONCLUSÃO INVERTIDA** (ADR-0002 §2.8, 2026-08-04) — corrigida a margem, **o motor NÃO supera o threshold legado**: cenário conservador (zona cinzenta negada) dá −1.075 u.m./caso, IC95% [−1.548; −616]; cenário otimista dá +323, IC95% [150; 491]. O "ganho de R$21 mil/caso" era artefato do proxy defeituoso. **Segunda falha metodológica corrigida no mesmo passe:** a comparação pareada original filtrava só casos decididos por ambas as estratégias, mas as bandas são **aninhadas** — isso removia exatamente os casos de discordância, e o delta dava zero por construção, não por medição. **O que o motor entrega e é mensurável:** a fatia de discordância (3.090 casos, 5,0% da carteira) tem **35,3% de default real contra 8,1% da carteira** (4,3×) — ele isola corretamente onde a decisão é difícil, mesmo não decidindo melhor sozinho. Isso define a barra da Camada 2.
14. ~~🔴 DEFEITO: proxy de margem negativamente correlacionado com a margem verdadeira~~ **RESOLVIDO** (ADR-0002 §2.8, 2026-08-04) — margem virou **premissa global medida** (41,4%, mediana de `Cash loans` em `previous_application` com a fórmula verdadeira do Gate 0) e a banda de indiferença passou a ser **derivada** da incerteza da premissa (`p*` de 27,2% a 48,2%), implementando o §2.6. Registro do defeito original: o proxy `AMT_ANNUITY/AMT_CREDIT` tinha Spearman ρ = −0,40 com a margem real — Medido na população onde as duas fórmulas são calculáveis (`previous_application`, n=939.001): margem verdadeira mediana 23,4% × proxy 10,9%. Não é só subestimação de nível — é **inversão de ordenação**. Motivo algébrico: `m_true = m_proxy × prazo − 1`, e `m_proxy = anuidade/crédito ≈ 1/prazo`; logo o proxy mede essencialmente "quão curto é o contrato", e contratos curtos têm **menos** juros totais. **Consequência:** o motor atribui `p*` mais baixo justamente aos contratos mais rentáveis — o ajuste por observação está sistematicamente na direção errada, e um `p*` global seria melhor que o atual por observação. **Bloqueante para qualquer alegação de valor do motor.**
15. ~~🔴 O veredito "APROVADO" do Gate 0 não transfere para o motor~~ **RESOLVIDO por obsolescência** (ADR-0002 §2.8) — o motor deixou de decidir margem por observação (virou premissa global medida), então a pergunta do Gate 0 ("a dispersão de `m/ℓ` justifica corte por observação?") não se aplica mais: `p*` agora varia só por LGD. O Gate 0 permanece válido como registro de que a dispersão **existe** na população onde a margem é medível — só não é acessível no momento da decisão.
16. ~~**Banda de indiferença do motor (±3pp) é largura fixa simplificada**~~ **RESOLVIDO** (ADR-0002 §2.8) — banda agora **derivada** da incerteza da premissa de margem (P25–P75 → `p*` de 27,2% a 48,2%), implementando o §2.6: a zona cinzenta é a região onde a decisão inverte conforme a premissa adotada. **Débito remanescente:** ainda não incorpora a incerteza da *estimativa* de PD por caso, só a da premissa de margem.
17. 🟡 **O efeito do cenário macro é 5× menor que a nossa própria incerteza de premissa.** Medido em 2026-08-05: a faixa de SELIC benigna→estressada move `p*` em **4,4pp** (37,2% → 32,8%), enquanto a incerteza da margem sozinha abre a zona cinzenta em **21,0pp** (27,2%–48,2%). A ferramenta de cenário passa na condição de existência do ADR-0008 (move um corte, não é decoração), mas **a afirmação honesta é "o macro desloca o centro dentro de uma faixa muito maior de desconhecimento nosso"** — não "o cenário macro muda materialmente nossas decisões". Não vender além disso em README, deck ou entrevista. Só se inverte se a margem virar medição por caso (hoje bloqueada, ver débito #14).
18. 🟡 **As âncoras de estresse do cenário (SELIC 10% → 15%) são premissa declarada, não medição.** Não existe no dataset (mercado emergente anonimizado) nem em série pública brasileira uma ligação medida entre SELIC e taxa de recuperação de crédito pessoal. A **direção** tem fundamento econômico (juro alto aperta devedor e derruba garantia → recuperação piora); a **magnitude** é escolha nossa. Ver `app/ferramenta_cenario.py`.
19. 🔴 **O juiz do ADR-0004 não existe no código** (2026-08-05). `ClienteGroq` foi criado com a chave destinada ao juiz, mas implementa `proxima_acao` — o contrato do **gerador**. O juiz avalia rubricas **binárias** sobre um memo pronto (`julgar(memo, trace) → veredito`): contrato diferente, módulo próprio. Sem ele, nenhuma rubrica com juiz roda, e o débito #10 (calibração do juiz contra labels humanos) fica bloqueado a montante. Ver ADR-0009 §2.5.
20. ~~🟡 **Adaptador de LLM sem retry, timeout ou controle de custo**~~ **RESOLVIDO** (2026-08-06) — a medição que o débito exigia saiu no piloto (`scripts/piloto_camada2.py`, `reports/piloto_camada2.md`): o `gemini-2.5-pro` devolve 429 com `limit: 0` (**não tem free tier**), o `flash` atende ~1 caso e entra em 429 de RPM, e o provider manda junto quanto esperar (`Please retry in 39.6s`). A política caiu direto do dado: **esperar o que o provider mandou** (backoff cego ignoraria a informação mais confiável disponível), **não retentar 400/401/403/404/422** (não melhoram com espera), teto de 120s acumulado por chamada. `RespostaLLMInvalida` **não** é retentada de propósito — é métrica de qualidade do gerador (ADR-0004), e retentá-la por baixo dos panos a transformaria em ruído invisível. Contadores `n_chamadas`/`tentativas_gastas` expõem a taxa bruta que o backoff absorve.
21. ~~🔴 **Três contagens divergentes da zona cinzenta, e não se sabe qual vale**~~ **RESOLVIDO por reclassificação** (2026-08-06) — não eram três medições do mesmo número. **2.102** é a contagem correta e reproduzida de novo nesta sessão (`scripts/zona_cinzenta_universo.py`, determinístico contra o mesmo split/modelo) — **este é o número a usar em README, deck ou entrevista**. **2.494** não é zona cinzenta: é "casos com decisão diferente entre motor e baseline" (`reports/motor_decisao_backtest.md` §"Onde as estratégias de fato discordam"), uma população vizinha mas distinta — o Context Bridge citou o número certo para o conceito errado. **2.780** segue **sem procedência recuperável**: não existe script no repo que o produza; foi medição ad hoc de 2026-08-05, um dia antes de `zona_cinzenta_universo.py` existir (criado 2026-08-06). **Débito remanescente, agora menor:** o teto `MAX_FATORES=8` (`app/memo_credito.py`) foi calibrado por importância de permutação sobre essa população de 2.780 não reproduzível — a *conclusão* (sinal espalhado, top 15 = 81%) não depende do `n` exato, mas o teto em si nunca foi remedido contra os 2.102 atuais. Refazer a importância por permutação sobre `data/processed/zona_cinzenta.parquet` fica como item futuro, não bloqueante.
22. 🟡 **`FERRAMENTAS_SEMPRE_APLICAVEIS` é lista manual** (ADR-0010 §3). Ferramenta de caso nova precisa ser adicionada lá, ou `validar_trajetoria()` silenciosamente deixa de cobri-la — a rubrica passa a dar verde por omissão, que é o pior modo de falha de um gate.
23. 🟡 **A validação de trajetória é conservadora por construção** (ADR-0010 §3). Só pega `DEFERIR` com ferramenta *sempre aplicável* não chamada. Um `DEFERIR` que consulta as três e ainda assim alega falta de algo obtível passa batido — exigiria comparar o texto de `informacao_faltante` com o que as tools entregam, que é trabalho de juiz (débito #19), não determinístico. **Confirmado por medição, ver débito #28** — a checagem mecânica continua sem cobrir esse caso; a mitigação aplicada foi no prompt (#28), não aqui. Backstop determinístico segue em aberto.
24. 🟢 **SDK `google.generativeai` está EOL.** O próprio pacote avisa no import: *"All support for the google.generativeai package has ended"*. Migrar para `google.genai`. Não urgente — funciona hoje —, mas é dívida com prazo definido por terceiro.
25. ~~🟡 **O caminho feliz da telemetria de tokens nunca rodou contra resposta real**~~ **RESOLVIDO, e revelou bug real** (2026-08-06) — primeiro lote com billing (piloto n=25, flash) rodou o caminho feliz e achou exatamente o risco previsto: o SDK v1beta (`google-generativeai`, débito #24) não popula `thoughts_token_count`, mas `total_token_count` continha o resíduo — 41% do custo do lote (18.488 de 44.550 tokens) estava invisível. Corrigido em `_contabilizar_tokens()` com derivação por resíduo quando `total > input+output+thinking`; coberto por `test_thinking_por_residuo_quando_sdk_nao_reporta_campo` e `test_groq_nao_ganha_thinking_fantasma_por_residuo` (`tests/test_clientes_llm.py`). Custo real do lote de 25: US$ 0,2867 (US$ 0,0115/caso) — projeção para as 450 execuções do eval set (ADR-0004 §2.5): **US$ 5,16**, não os US$ 1,28 que o campo ausente teria reportado.

26. ~~🟡 **Groundedness mecânica valida "a ferramenta foi chamada", não "o número bate"**~~ **RESOLVIDO** (2026-08-06, achado na leitura manual dos 5 casos-piloto; corrigido 2026-08-09). `validar_groundedness()` (`app/agente_underwriting.py`) confere se `fonte_tool` resolve contra uma chamada real — pega alucinação de nome de ferramenta (achado real: caso `292411`, `fonte_tool` veio como `"consultar_bureau, consultar_pagamentos"`, dois nomes concatenados, nem um dos dois existe). Não conferia se o *valor numérico* citado no fato realmente aparecia no retorno daquela ferramenta. **Correção:** `validar_groundedness_numerica()` (mesmo módulo) extrai números do texto do fato e do retorno da ferramenta e confere correspondência, testando as duas escalas em que o LLM pode escrever (fração 0-1 da ferramenta vs. percentual do texto — ex.: `utilizacao=0.4712` bate com "47.1%"). **Registrada, não eliminatória** — é heurística de texto livre (tolerância de ±0,5 pra arredondamento de exibição), diferente da groundedness de ferramenta acima, que é exata. Fio para `ResultadoAnalise.suspeitos_groundedness_numerica`, mesmo tratamento de `violacoes_trajetoria`. 6 testes novos, 166/166 passando. **Não integrado ainda** à tela de rotulagem (`gerar_revisor_verificacao.py`) nem ao juiz — fica como sinal disponível pro próximo uso, não consumido automaticamente.
28. ~~🔴 **`DEFERIR` era aceito por humano em 1 de 6 casos — sempre pelo mesmo motivo**~~ **RESOLVIDO** (2026-08-06, achado na revisão manual de 20 casos via `revisor_piloto.html`). Cross-referenciando os 20 vereditos humanos: **100% dos 5 casos marcados "questionável" eram `DEFERIR`** (1/6 aceito, IC95% Wilson [3,0%; 56,4%] — `n` pequeno, sinal forte). Os 6 tinham a MESMA assinatura de dado (`consultar_bureau` e `consultar_pagamentos` retornando `tem_registro: False` — ausência **confirmada**, não "não verificado"), e `informacao_faltante` citava sistematicamente renda/emprego/patrimônio, que nenhuma ferramenta deste sistema jamais fornece — confirma por medição a previsão do débito #23 e o argumento de *Learning to Defer* do ADR-0004 (deferir sem ganho real só transfere trabalho). **Correção:** `_prompt_sistema()` (`app/clientes_llm.py`) passou a proibir citar renda/emprego/patrimônio em `informacao_faltante` e instrui decidir APROVAR/NEGAR quando bureau+pagamentos confirmam ausência total. Testado em `test_prompt_sistema_proibe_deferir_por_dado_inobtenivel`. **Validado contra os mesmos 6 casos** (`scripts/reteste_deferir.py`, controle antes/depois, não amostra nova): os 5 antes rejeitados saíram de `DEFERIR` em toda execução bem-sucedida (`268561`→APROVAR, `285827`→APROVAR, `336278`→NEGAR, `381595`→APROVAR, `398836`→APROVAR). **Risco residual:** é mitigação por instrução de prompt, não trava mecânica — o débito #23 (backstop determinístico) continua em aberto como a garantia de verdade.
27. 🟢 **Ferramenta chamada, dado retornado, e não citado em nenhum fato do memo** (2026-08-06, achado no caso `307444`). O agente chamou `consultar_historico_bureau` (3ª chamada, `n_chamadas=3`), recebeu `meses_em_dia: 35` de `38` observados — dado favorável — e nenhum `fato` do memo cita essa ferramenta como fonte. Não é violação de trajectory (a ferramenta certa foi chamada); é mais próximo de synthesis incompleta — dado coletado não chega ao parecer final. Não tem rubrica do ADR-0004 que cubra isso hoje; achado registrado para virar critério do juiz (débito #19) quando ele existir, não para ação imediata.
29. 🟡 **Rotulagem para o juiz (débitos #10/#19) em andamento — 24/87 casos, 1 incompleto** (2026-08-07). Os 9 labels parciais anteriores (débito #28, prompt pré-correção) foram **descartados de propósito** — memos regenerados do zero sob o prompt corrigido (`scripts/piloto_camada2.py --n 100 --seed 42 --modelo gemini-2.5-flash`, `gemini-2.5-pro` não está mais disponível pra novas chaves). 100 casos gerados, **87 com memo válido** (13 `memo_invalido`), custo real US$ 1,10. Ferramenta de rotulagem: `revisor_camada2.html` — Artifact publicado (não versionado por natureza; export via botão copia o JSON pro clipboard/textarea, cola no chat, e o resultado é persistido em `data/labels/task_completion_labels.json`, este sim versionado — corrige a causa raiz do débito #28 original (20 labels perdidos por só existirem num artifact). **Panorama do lote atual (n=24, 1 incompleto → 23 utilizáveis):** Groundedness 24/24 OK, Task Completion 22 OK + 1 `FALHA` (`264603`) + 1 incompleto (`181390`), Trajectory 24/24 OK, Cegueira ao score 24/24 OK — `n` pequeno demais pra IC de Wilson dizer algo (ADR-0004 §2.5). **Duas pendências no lote:** `181390` sem veredito de Task Completion (só evidência escrita); `264603` marcado `FALHA`/`recomendacao_ignora_fato` com evidência vaga, sem nomear o fato específico que a recomendação `NEGAR` teria ignorado. **Próximo passo:** continuar rotulando (sem piso fixo — construir o juiz #19 não está bloqueado em atingir 100, só a calibração formal #10 está) e então construir o juiz DeepEval (Task Completion, família Groq — `ClienteGroq` já existe) validado contra este dataset.

30. 🔴 **Saída de LLM não é regenerável, e tratá-la como tal destruiu ground truth** (2026-08-08). `piloto_camada2_memos.jsonl` morava em `data/processed/`, ignorado pelo git sob a justificativa "regenerável via script" — a mesma que vale para as features. **Não vale.** Ao reconstruir o pipeline do zero nesta máquina (dataset Kaggle → features → treino → zona cinzenta → piloto) e rodar `piloto_camada2.py --n 100 --seed 42 --modelo gemini-2.5-flash` de novo, tudo determinístico reproduziu **exatamente**: zona cinzenta de novo com 2.102 casos, AUC 0.7763. O que **não** reproduziu foi a saída do LLM: **86 memos válidos em vez de 87**, com 12 casos rotulados perdendo o memo e 11 casos novos aparecendo. Pior, entre os 8 casos rotulados `FALHA` que sobreviveram ao pareamento, **2 (`100525`, `353468`) passaram a recomendar `APROVAR`** — exatamente o que o revisor humano dissera que o agente deveria ter feito. O label "FALHA / recomendacao_ignora_fato" ficou **factualmente errado** para o memo novo. Temperatura 0 reduz variância, não a elimina; o provider nunca prometeu determinismo (já registrado em `clientes_llm.py`, mas a consequência sobre versionamento não tinha sido tirada). **Consequência medida:** calibrar o juiz (#10) contra esses labels produziria TPR sobre `n=8` com ≥25% de contaminação conhecida — número com casa decimal em cima de ground truth podre. **Correção aplicada:** `.gitignore` passou de `data/processed/` para `data/processed/*` + exceção `!data/processed/piloto_camada2_memos.jsonl` (194KB) — o padrão com `/` não permite negação porque o git não entra em diretório excluído. **Regra que fica:** artefato que serve de objeto de rotulagem humana é versionado junto com os labels, sempre. É o débito #28 (20 labels perdidos por existirem só num artifact) reaparecendo por outra porta — lá o artefato de rotulagem era volátil, aqui o objeto rotulado era.

31. 🟡 **63 dos 77 labels `OK` de Task Completion não eram julgamentos — eram conferências de número na rubrica errada** (achado 2026-08-08, quase todo o backlog recoletado 2026-08-10). Classificando a linguagem das evidências originais: dos 77 `OK` de 2026-08-08, **63 usavam linguagem de groundedness** ("tudo bate", "os valores existem"), **8 estavam vazios**, e apenas **8 julgavam de fato a recomendação**. **Causa raiz era a ferramenta**, não o revisor: `revisor_camada2.html` empilhava 4 rubricas com `textarea` visualmente idênticos, então "tudo bate" escorria pros quatro campos sem nada acusar (mesma família dos débitos #28/#30). **Correções aplicadas em 2026-08-09:** ADR-0011 (critério verificável), tela de 1 pergunta/caso (`scripts/gerar_revisor_verificacao.py`), rubricas mecânicas paradas de pedir julgamento humano. **Recoleta 2026-08-09:** 23 dos 87 casos (11 novos + 8 label frágil + 4 OK suspeito por proxy de peso) — 9 FALHA + 14 OK com evidência real. **Recoleta 2026-08-10 (o grosso do backlog):** ferramenta ganhou modo `--debito-31` (filtra só veredito atual `OK`, ignora os grupos desenhados pra outra transição que reabririam `FALHA` já sólido) — **76 casos revisados via 1 clique/caso, 75 concluídos**. Resultado: **2 vereditos viraram `FALHA`** com evidência nova (`128369`, `344012` — mesmo padrão "bom pagador, nunca atrasou" que já tinha virado `FALHA` em outros casos), **19 confirmados `OK` sem evidência nova** (a ferramenta só pede texto pra `FALHA` — ficam marcados "confirmado na recoleta #31, revisão binária" em vez de manter o texto contaminado antigo), **54 já tinham evidência real da recoleta anterior e ficaram intocados**. **Pendente:** 1 caso (`108447`) sem veredito na exportação. **Consequência para o TNR:** a classe `OK` agora é, em sua maioria, decisão deliberada revisada sob critério explícito — não mais conferência de número. A limitação remanescente é que 19 `OK` não têm evidência textual citável (só a confirmação binária), o que é aceitável pra calibrar o juiz (o veredito é o que importa) mas não pra alegar auditabilidade completa em publicação.
32. ~~🔴 **Juiz reconhece o sinal certo e ainda assim erra o veredito — bug de raciocínio, não lacuna de critério**~~ **RESOLVIDO E VALIDADO EMPIRICAMENTE** (fix 2026-08-09, validação 2026-08-10). Casos `111985` e `244626`: a evidência do próprio juiz identificava corretamente "1 sinal grave presente (utilização ≥80%)" — que pelo ADR-0011 §2.1 já basta para `NEGAR` ser defensável — e mesmo assim concluía `FALHA`, contradizendo a própria checagem (`244626`: *"a recomendação de NEGAR parece defensável devido ao sinal grave, mas... pode ser questionada"*). **Correção:** `_prompt_sistema_juiz` (`app/juiz_camada2.py`) ganhou instrução explícita — "sinal/agravante confirmado → veredito decidido, não existe segunda camada de análise". Teste de regressão `test_prompt_sistema_proibe_segunda_camada_de_analise`. **Validado contra API real em 2026-08-10** (`calibrar_juiz.py --rejulgar`, n=55): nenhum dos dois casos aparece mais na lista de discordâncias; `244626` concorda explicitamente (`juiz=OK humano=OK`). Instrução de prompt funcionou na prática para este padrão.
33. 🟡 **Juiz trata dado ausente como ausência de sinal, não como incerteza — prompt REFUTADO, validação determinística IMPLEMENTADA (ADR-0012)** (achado 2026-08-10, fix de prompt tentado e refutado no mesmo dia, validador determinístico implementado no mesmo dia). 9 casos (`117727`, `143212`, `151515`, `173954`, `205320`, `222453`, `235776`, `264603`, `417173`) têm a mesma assinatura — `utilizacao`, `pior_atraso_dias`, `deficit_medio_pct` vêm `None`/indisponíveis, e o juiz conclui "nenhum sinal grave, nenhum agravante" → `FALHA`. **Tentativa 1 (refutada):** instrução explícita em `_prompt_sistema_juiz` — ignorada pelo `llama-3.3-70b-versatile` contra API real (`calibrar_juiz.py --rejulgar`, n=55): 11 dos 12 casos de discordância no rerun repetiram o mesmo padrão, incluindo 2 casos novos (`282047`, `285827`). **Tentativa 2 (implementada):** `suspeito_dado_ausente()` (`app/juiz_camada2.py`) roda pós-resposta — confere se a evidência do juiz admite "não disponível"/`None` e confirma contra os dados brutos da trace que ao menos um campo do critério ADR-0011 é de fato `None`; se sim, marca `ResultadoJuizTaskCompletion.suspeito_dado_ausente = True`, sem sobrescrever o veredito (registrado, não eliminatório, mesmo tratamento do #26). 2 testes novos (caso sintético que replica o padrão real + caso de sinal grave legítimo que não pode ser marcado), 169/169 passando no projeto. **Em aberto:** ainda não validado contra API real — a instrução ao juiz não muda, só o pós-processamento; a expectativa é que o sinal apareça marcado nos 9+ casos do padrão no próximo `calibrar_juiz.py --rejulgar`, mas isso não foi confirmado ainda.

---

## Escopo negativo

- **Sem decisão de crédito autônoma.** O agente propõe; humano decide na tela de revisão. `DEFERIR` é ação de primeira classe, não fallback de erro.
- **Sem consulta a bureau individual** — não existe API pública no Brasil (LC 105 + LGPD).
- **Sem PII real**, em nenhuma etapa.
- **Sem afirmar aplicabilidade direta ao mercado brasileiro** — o dataset é de mercado emergente, o cenário macro é stress declarado.
- **Sem pricing** (definir taxa por cliente) — o projeto decide aprovar/negar/deferir sobre contrato dado, não precifica.
- **Sem re-treino online / feedback loop automático** — outcome de default só é observável com defasagem longa.

---

## Material de apoio

| O quê | Onde |
|---|---|
| **Dicionário de dados** (todas as colunas + as 32 features criadas, em PT-BR) | `docs/DICIONARIO_DADOS.md` |
| Spec consolidada | `docs/wayfinder/refatoracao-camada-agentica/SPEC_FINAL.md` |
| 9 tickets Wayfinder (pesquisa e decisões) | `docs/wayfinder/refatoracao-camada-agentica/` |
| Aula — valor esperado, PD/LGD/EAD | `wiki/concepts/04_business/Valor_Esperado_Decisao_Credito.md` (base de conhecimento) |
| Padrão de rigor a replicar | `PROJETOS/02_PORTFOLIO/stable-treasury/` |
