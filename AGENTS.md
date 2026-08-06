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
21. 🔴 **Três contagens divergentes da zona cinzenta, e não se sabe qual vale** (2026-08-06). `scripts/zona_cinzenta_universo.py` mediu **2.102 casos (3,4% do teste, 36,1% de default real)** ao materializar o conjunto em disco pela primeira vez. O Context Bridge registrava 2.494 (4,1%, 37,7%) e o comentário do `MAX_FATORES` em `app/memo_credito.py` cita 2.780. Saem do **mesmo modelo e mesmo split**, então pelo menos dois estão errados. Nenhum número de zona cinzenta pode ir para README, deck ou entrevista antes disso ser refeito.
22. 🟡 **`FERRAMENTAS_SEMPRE_APLICAVEIS` é lista manual** (ADR-0010 §3). Ferramenta de caso nova precisa ser adicionada lá, ou `validar_trajetoria()` silenciosamente deixa de cobri-la — a rubrica passa a dar verde por omissão, que é o pior modo de falha de um gate.
23. 🟡 **A validação de trajetória é conservadora por construção** (ADR-0010 §3). Só pega `DEFERIR` com ferramenta *sempre aplicável* não chamada. Um `DEFERIR` que consulta as três e ainda assim alega falta de algo obtível passa batido — exigiria comparar o texto de `informacao_faltante` com o que as tools entregam, que é trabalho de juiz (débito #19), não determinístico.
24. 🟢 **SDK `google.generativeai` está EOL.** O próprio pacote avisa no import: *"All support for the google.generativeai package has ended"*. Migrar para `google.genai`. Não urgente — funciona hoje —, mas é dívida com prazo definido por terceiro.
25. 🟡 **O caminho feliz da telemetria de tokens nunca rodou contra resposta real** (2026-08-06). `_contabilizar_tokens()` tem testes unitários para os formatos Gemini e Groq, e o ramo "provider não reportou uso" foi exercitado contra o provider real (429). Mas a quota esgotou antes de qualquer resposta bem-sucedida trazer `usage_metadata` — se o SDK nomear algum campo diferente do assumido, só o primeiro lote com billing revela.

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
