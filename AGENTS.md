# AGENTS.md — PayFlow (crédito com camada agêntica de underwriting)

> **Projeto**: classificador de risco de crédito (PD) + motor de decisão por valor esperado + agente de underwriting que produz memo de crédito auditável para a zona cinzenta.
> **Stack alvo**: Python · scikit-learn · Pydantic · FastAPI · Streamlit · DeepEval · APIs BCB SGS / IBGE
> **Estado (2026-08-12)**: Camada 1 treinada e calibrada (AUC 0,776), motor de decisão implementado/backtestado, Camada 2 (agente + juiz LLM) completa e **medida com poder estatístico** — débito #34 concluiu que o agente não separa risco real de forma detectável na zona cinzenta (AUC do próprio modelo campeão ali é 0,56, robusto a 3 ângulos de verificação). Demo estática da V2 em `app/main_v2.py` (não gera memo novo, não depende de API). Deploy legado (V1) despublicado.

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
| **Point-in-time** | Um dado só pode entrar no modelo se existia no instante em que a decisão de crédito foi tomada |
| **Contrato de disponibilidade** | Fonte de verdade que classifica cada feature como permitida, bloqueada ou desconhecida na data de decisão |
| **Coorte** | Grupo de solicitações de crédito decidido no mesmo mês ou semana, usado para medir estabilidade ao longo do tempo |
| **Drift** | Mudança no perfil dos dados ou no desempenho do modelo entre coortes |
| **KS de feature** | Maior distância entre as distribuições acumuladas do treino e da nova coorte; sinaliza mudança, mas não sua causa |
| **Drift de ausência** | Diferença na proporção de valores ausentes entre treino e coorte; detecta quebra de cobertura que o KS dos valores preenchidos não enxerga |
| **Gate fail-closed** | Nova feature sem contrato ou com regra temporal inválida é bloqueada explicitamente; nunca passa por omissão |

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
| 0013 | Exposição parcial de `EXT_SOURCE_1` ao agente — testa poder preditivo sem replicar o score inteiro | **Rejected** (mesmo dia — sinal desaparece dentro da zona cinzenta, ver §7 do ADR) |
| 0014 | Contrato point-in-time e monitoramento de confiabilidade de crédito | **Accepted** — gate e relatório de coorte implementados; integração com score pendente |
| 0015 | Modos estrito e exploratório de disponibilidade | **Accepted** — proxy semântico não atravessa para o modo estrito; fronteira testada |
| 0016 | Política de uso por coorte | **Accepted** — manter/revisar/aguardar pesquisa por evidência, não decisão individual |
| 0017 | Evidência mínima para semáforo de coorte | **Accepted** — exige tamanho, eventos, IC da AUC e Brier antes de liberar decisão |
| 0018 | KS e ausência para drift de features | **Accepted** — mede mudança de distribuição e perda de cobertura sem retreino automático |

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
11. ~~**Deploy atual (Streamlit + Render) serve o modelo legado.**~~ **RESOLVIDO por despublicação** (2026-08-11). Decisão: despublicar em vez de rotular — o app da V1 (dado sintético, sem outcome real) sob o nome do projeto V2 (dado real, agente com juiz) criava risco de leitor achar que via o estado atual. `README.md` atualizado registrando a despublicação e o motivo. Sem demo ao vivo até a V2 ter deploy próprio.
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

31. ~~🔴 **63 dos 77 labels `OK` de Task Completion não eram julgamentos — eram conferências de número na rubrica errada**~~ **RESOLVIDO** (achado 2026-08-08, backlog inteiro recoletado 2026-08-10). Classificando a linguagem das evidências originais: dos 77 `OK` de 2026-08-08, **63 usavam linguagem de groundedness** ("tudo bate", "os valores existem"), **8 estavam vazios**, e apenas **8 julgavam de fato a recomendação**. **Causa raiz era a ferramenta**, não o revisor: `revisor_camada2.html` empilhava 4 rubricas com `textarea` visualmente idênticos, então "tudo bate" escorria pros quatro campos sem nada acusar (mesma família dos débitos #28/#30). **Correções aplicadas em 2026-08-09:** ADR-0011 (critério verificável), tela de 1 pergunta/caso (`scripts/gerar_revisor_verificacao.py`), rubricas mecânicas paradas de pedir julgamento humano. **Recoleta 2026-08-09:** 23 dos 87 casos (11 novos + 8 label frágil + 4 OK suspeito por proxy de peso) — 9 FALHA + 14 OK com evidência real. **Recoleta 2026-08-10 (fechou o backlog):** ferramenta ganhou modo `--debito-31` (filtra só veredito atual `OK`, ignora os grupos desenhados pra outra transição que reabririam `FALHA` já sólido) — **77 casos revisados no total** (76 no lote + `108447` fechado à parte). Resultado: **2 vereditos viraram `FALHA`** com evidência nova (`128369`, `344012` — mesmo padrão "bom pagador, nunca atrasou" que já tinha virado `FALHA` em outros casos), **20 confirmados `OK` sem evidência textual nova** (`108447` incluso — recomendação `APROVAR` sob ADR-0011 §2.4 não exige a régua de sinal/agravante, só checagem de contradição, e nenhuma foi achada; a ferramenta só pede texto pra `FALHA` nos demais 19), **54 já tinham evidência real da recoleta anterior e ficaram intocados**. **Consequência para o TNR:** a classe `OK` agora é, em sua totalidade, decisão deliberada sob critério explícito — não mais conferência de número. **Limitação remanescente, não bloqueante:** 19 `OK` não têm evidência textual citável (só confirmação binária), suficiente pra calibrar o juiz mas não pra alegar auditabilidade completa em publicação.
32. ~~🔴 **Juiz reconhece o sinal certo e ainda assim erra o veredito — bug de raciocínio, não lacuna de critério**~~ **RESOLVIDO E VALIDADO EMPIRICAMENTE** (fix 2026-08-09, validação 2026-08-10). Casos `111985` e `244626`: a evidência do próprio juiz identificava corretamente "1 sinal grave presente (utilização ≥80%)" — que pelo ADR-0011 §2.1 já basta para `NEGAR` ser defensável — e mesmo assim concluía `FALHA`, contradizendo a própria checagem (`244626`: *"a recomendação de NEGAR parece defensável devido ao sinal grave, mas... pode ser questionada"*). **Correção:** `_prompt_sistema_juiz` (`app/juiz_camada2.py`) ganhou instrução explícita — "sinal/agravante confirmado → veredito decidido, não existe segunda camada de análise". Teste de regressão `test_prompt_sistema_proibe_segunda_camada_de_analise`. **Validado contra API real em 2026-08-10** (`calibrar_juiz.py --rejulgar`, n=55): nenhum dos dois casos aparece mais na lista de discordâncias; `244626` concorda explicitamente (`juiz=OK humano=OK`). Instrução de prompt funcionou na prática para este padrão.
33. ~~🟡 **Juiz trata dado ausente como ausência de sinal, não como incerteza — prompt REFUTADO, validação determinística IMPLEMENTADA (ADR-0012)**~~ **VALIDADO EMPIRICAMENTE** (achado 2026-08-10, prompt refutado no mesmo dia, detector implementado no mesmo dia, validado 2026-08-11). **Tentativa 1 (refutada):** instrução explícita em `_prompt_sistema_juiz` — ignorada pelo `llama-3.3-70b-versatile` contra API real. **Tentativa 2 (implementada e validada):** `suspeito_dado_ausente()` (`app/juiz_camada2.py`) roda pós-resposta, confere se a evidência do juiz admite ausência de dado e confirma contra a trace bruta. **Resultado do rerun de 2026-08-11** (`calibrar_juiz.py --rejulgar`, n=69, ground truth agora 100% recoletado sob ADR-0011 — ver débito #31): dos 13 casos de discordância com o padrão "dado ausente", **12 vieram marcados `⚠️ suspeito #33?`** no relatório. Só `238067` escapou — evidência usa "dados brutos não apresentam" em vez de "não disponível"/`None`, variação de vocabulário fora da lista `_TERMOS_DADO_AUSENTE`. **Decisão 2026-08-11:** não ampliar o vocabulário — 12/13 já valida a abordagem determinística (a mesma limitação declarada no ADR-0012 desde o início: heurística de texto envelhece se o vocabulário do juiz mudar). TPR/TNR deste rerun (n=69): TPR 81,8% [52,3%; 94,9%], TNR 77,6% [65,3%; 86,4%] — ver `reports/calibracao_juiz.md`.
34. 🔴 **Backtest da Camada 2 contra `TARGET` real — MEDIDO COM PODER ESTATÍSTICO: o agente NÃO separa risco de forma detectável** (implementado 2026-08-11, medição final 2026-08-11). `scripts/backtest_camada2.py` era esqueleto puro (5 funções com `NotImplementedError`) desde 2026-08-08 — a medição que o ADR-0004 §2.1 chama de "a contribuição do projeto" nunca tinha sido escrita, só uma conta ad-hoc no docstring. **Implementado e validado contra os 86 casos existentes antes de gastar API** (reproduziu a conta ad-hoc quase exatamente — confirma que a implementação está correta). **`comparar_com_motor` documentada como não implementável com os dados atuais** (não só deixada em branco): `zona_cinzenta.parquet` tem `decisao_motor` constante (`"ZONA_CINZENTA"` em 100% das linhas) — esse arquivo já É o recorte onde o motor se absteve, não existe decisão real do motor pra comparar dentro desse universo.

**Piloto de 722 casos rodado (2026-08-11, ~US$7,52, US$0,0104/caso):** 563 memos válidos (78% de aproveitamento — 15,2% `memo_invalido`, 3,5% `erro_provider` no rate limit do fim do lote, 2,2% `teto`). **Resultado do backtest com `n=564` (poder estatístico real, não mais ad-hoc):**

| Recomendação | k (default) | n | Taxa | IC95% (Wilson) |
|---|---|---|---|---|
| APROVAR | 85 | 260 | 32,7% | [27,3%; 38,6%] |
| NEGAR | 103 | 303 | 34,0% | [28,9%; 39,5%] |

**Separação NEGAR − APROVAR: +1,3%, IC95% [-6,7%; +9,2%] (bootstrap, 2000 reamostragens).** O intervalo cruza zero com folga — e o ponto central despencou de +7,2pp (amostra pequena, `n=86`) pra +1,3pp com `n=564`. **Isso não é ruído de amostra pequena escondendo um efeito real — é evidência de que o efeito real é próximo de zero.** A taxa de default é essencialmente igual entre clientes que o agente aprovou e negou na zona cinzenta.

**Leitura honesta:** com o critério e os dados atuais, **o agente não demonstra separar risco real de forma estatisticamente detectável** dentro da zona cinzenta — a pergunta central do ADR-0004 §2.1 tem resposta, e a resposta não é a que o projeto esperava. Isso não invalida a arquitetura (o agente ainda produz memo auditável, groundado, cego ao score — propriedades valiosas por si), mas invalida qualquer alegação de que "o agente decide melhor que o acaso" sem qualificação.

**Hipóteses investigadas em 2026-08-12 (com dados existentes, sem gastar API nova):**

- **(a) CONFIRMADA COM DADOS, CAUSA RAIZ IDENTIFICADA — o agente nunca teve acesso ao sinal que mais importa neste dataset.** Extraí os campos brutos (`utilizacao`, `pior_atraso_dias`, `deficit_medio_pct`, `n_em_atraso_hoje`) dos 564 casos e cruzei com `TARGET` real: correlação essencialmente zero em todos (`utilizacao` -0,073, `pior_atraso_dias` -0,049, `deficit_medio_pct` +0,001, `n_em_atraso_hoje` +0,029). "Sinal grave" presente (que pelo ADR-0011 justificaria `NEGAR`) tem taxa de default **menor** (30,8%, n=78) que sem sinal (33,7%, n=486) — o oposto do esperado se fosse preditivo.

  **Confirmado com importância por permutação no modelo real da Camada 1** (2026-08-12, `data/processed/camada1_features_train.parquet`, split reproduzido com `RANDOM_STATE=42` idêntico ao treino, `n_repeats=3`, `scoring=roc_auc`, `n_test=61.503`): as 3 variáveis que dominam a predição são `EXT_SOURCE_2` (0,0415), `EXT_SOURCE_3` (0,0363), `EXT_SOURCE_1` (0,0164) — escores de crédito externos, anonimizados, do dataset Home Credit. Somadas: **0,0942** de importância. As 8 variáveis de bureau/pagamento que as ferramentas do agente (`consultar_bureau`, `consultar_pagamentos`) expõem somam **0,0043** — **21,8× menos**. Confirmado por grep em `app/ferramentas_caso.py`: **`EXT_SOURCE_1/2/3` nunca aparecem em nenhuma ferramenta do agente.**

  **Isso é a causa raiz, não só uma correlação fraca**: o agente foi arquitetado com um kit de ferramentas (histórico de pagamento "nesta casa", situação no bureau) que soa razoável pra um humano subscritor, mas no Home Credit especificamente, o que prediz default de verdade são escores de crédito externos que o agente **nunca viu, por desenho**. Os débitos #32/#33 garantiram que o agente aplica o critério corretamente — o problema nunca foi a aplicação, foi o critério apontar pro lugar errado.

  **Tensão de design levantada, e RESOLVIDA por refutação empírica no mesmo dia (não por implementação)**: a ideia inicial (ADR-0013, expor `EXT_SOURCE_1` sozinha) supunha que a importância medida na população inteira (0,0942 pras 3 juntas) se aplicaria à zona cinzenta. **Checagem que faltava, feita antes de implementar**: correlação de `EXT_SOURCE_1/2/3` com `TARGET` **dentro da zona cinzenta especificamente** (`n=2.102`) — `EXT_SOURCE_1` -0,031 (35,5% disponível), `EXT_SOURCE_2` -0,038 (99,8% disponível), `EXT_SOURCE_3` -0,019 (72,8% disponível). **O sinal praticamente desaparece dentro da zona cinzenta** — do mesmo tamanho de ruído que os sinais de bureau já descartados. Faz sentido estrutural: a zona cinzenta é definida **como** a região onde o modelo (dominado por `EXT_SOURCE`) fica incerto — por construção, esse sinal já foi consumido ali. ADR-0013 registrado como **Rejected** no mesmo dia, sem implementação, evitando gastar API repetindo o mesmo erro metodológico com uma variável diferente.

  **Achado decisivo, confirmado por dois checks adicionais no mesmo dia (2026-08-12):**

  **(1) Varredura de correlação em todas as 131 variáveis numéricas do modelo**, dentro da zona cinzenta especificamente (`n=2.102`): **nenhuma** tem `|correlação|` acima de 0,10 com `TARGET`. A maior é `previous_amt_annuity_mean` (0,060). Sete variáveis passam de 0,05; o resto é ruído. Limitação declarada: correlação só pega relação linear — não descarta que uma combinação não-linear de variáveis carregue sinal (é literalmente o que o gradient boosting faz na população inteira).

  **(2) Por isso, o teste definitivo: AUC do próprio modelo campeão (`HistGradientBoostingClassifier` calibrado, todas as 131+ variáveis, relações não-lineares incluídas) calculado só dentro da zona cinzenta, usando `p_hat` já salvo em `zona_cinzenta.parquet`.** Resultado: **AUC = 0,5612** (`n=2.102`). Para contexto: 0,50 é acaso puro, 0,776 é o AUC do mesmo modelo no conjunto de teste inteiro. **O melhor classificador que este projeto já construiu, com acesso a tudo, mal bate a moeda especificamente na fatia onde o agente decide.**

  Isso fecha o argumento com o instrumento mais forte disponível — não é mais "o agente tem a ferramenta errada" (Hipótese A original) nem "falta um sinal específico como `EXT_SOURCE`" (ADR-0013, rejeitado). É evidência de que **a zona cinzenta, definida pelos dados do Home Credit disponíveis, está genuinamente perto do limite do que é previsível**. Nenhum agente — humano ou IA — deveria conseguir separar risco de forma forte numa região onde o melhor classificador possível do projeto já está quase cego.

  **Duas hipóteses adicionais testadas e descartadas no mesmo dia, fechando o assunto:**
  - **"A calibração isotônica está escondendo sinal"** (achado lateral: `zona_cinzenta_universo.py` já documentava que o `p_hat` calibrado colapsa em só **15 platôs** dentro da zona, um único valor concentrando 40,6% dos casos — função em degrau da regressão isotônica). Testado usando o score **bruto, pré-calibração** (2.102 valores distintos, sem empate nenhum): AUC = **0,5643** — praticamente idêntico ao calibrado (0,5612). **Descartada**: a calibração não estava escondendo nada, o modelo de base já não discrimina ali.
  - **"A zona cinzenta está definida larga demais, misturando casos fáceis com difíceis"**: dividida em 3 fatias por distância ao centro da banda de incerteza (`p_estrela_inf`/`p_estrela_sup`). AUC interno: centro 0,531, meio 0,568, borda 0,509 — **nenhuma fatia recupera previsibilidade meaningful**, nem os casos "mais fáceis" (borda). **Descartada**: não existe sub-região oculta mais decidível dentro da zona.

  Com essas duas descartadas, a conclusão fica robusta a três ângulos de ataque diferentes (correlação linear, importância não-linear do modelo completo, resolução do score em cada sub-fatia): **a zona cinzenta está estruturalmente perto do limite do previsível com os dados disponíveis — não é lacuna de ferramenta, não é artefato de calibração, não é definição de fronteira mal desenhada.**
- **(b) REFRAMED — `DEFERIR` quase inexistente (0,18%, 1/564) é decisão deliberada anterior, não descuido.** O prompt do agente (`app/clientes_llm.py`) já proíbe `DEFERIR` por informação inobtenível desde o débito #28 (2026-08-06) — medido na época que o revisor humano aceitava só 1 de 6 `DEFERIR` do piloto, os outros 5 eram o agente adiando decisão citando renda/emprego, que nenhuma ferramenta fornece. A correção "se bureau e pagamentos confirmam ausência total, decida — não adie" está funcionando exatamente como desenhada. **A pergunta certa não é "por que não usa DEFERIR"** — é se forçar decisão em casos genuinamente ambíguos (não só "dado obtível não buscado", mas incerteza real) dilui a separação de risco nos casos onde o agente teria sinal de verdade. Não testado ainda: segmentar os 564 casos por "confiança aparente" do agente (proporção de fatos favoráveis vs. desfavoráveis citados) e ver se a separação aparece nos casos "confiantes" e desaparece nos "forçados".
- **(c) FUNDIDA COM (a)** — "o prompt pesa fatores não preditivos" é a mesma explicação que (a) já confirmou com dados, vista de outro ângulo. Não é uma causa adicional independente.

**Verificação adicional (2026-08-12), antes de usar este resultado externamente:**
- **Sem duplicatas**: `zona_cinzenta.parquet` (2.102 linhas) e `piloto_camada2_memos.jsonl` (722 linhas) têm `SK_ID_CURR` 100% únicos cada um — `n=564` não é inflado por join errado.
- **Bootstrap estável entre seeds**: testado com 5 seeds diferentes (42, 1, 7, 999, 123456) — IC95% sempre entre aproximadamente `[-6,3% a -7,0%; +8,7% a +9,2%]`. A conclusão "cruza zero" não é artefato da seed 42, é robusta.
- **A amostra de 722 NÃO é independente da de 86 anterior — é a mesma extração determinística, estendida.** `preparar_lote()` reusa `seed=42` pra embaralhar sempre a mesma população de 2.102; `--n 722` e `--n 86` tiram os primeiros N da mesma sequência embaralhada. 100 dos 722 IDs já tinham aparecido no lote de 86. **Não invalida a estatística** (ainda é uma amostra válida de 564 casos únicos), mas a descrição correta é "amostra estendida por reprodutibilidade determinística", não "722 casos novos independentes" — importa pra descrever o método com precisão.
- **Viés de atrito leve, não dominante**: os 158 casos excluídos (`memo_invalido`/`erro_provider`/`teto`) têm taxa de default real de 36,1% contra 33,3% dos 564 válidos — diferença pequena (~2,8pp, `n=158` no grupo excluído), sugere leve tendência de casos mais difíceis também confundirem a geração do memo (MNAR técnico). Não muda a conclusão central, mas é limitação real, não silenciada.
- **Sem teste automatizado para `backtest_camada2.py`.** Validado manualmente (contra os 86 grátis, contra 5 seeds), mas zero regressão automática — débito remanescente se o script for tocado de novo no futuro. **Parcialmente endereçado em 2026-09-01:** `tests/test_analise_zona_cinzenta.py` (22 testes) cobre as funções puras dos dois scripts de análise novos; `backtest_camada2.py` em si segue sem teste, mas `separacao_por_confianca.py` replica sua separação global como controle (+1,3% IC95% [-6,7%; +9,2%], idêntico) — uma regressão nele apareceria como divergência ali.

**Fechamento do #34 — auditoria de 2026-09-01 (custo zero de API, só dado local).** Revisão pediu duas coisas: (1) o número da headline não tinha script nem intervalo, quebrando a regra do próprio projeto; (2) a hipótese (b) seguia registrada como não testada. As duas fechadas.

**(1) `scripts/auc_zona_cinzenta.py` + `reports/auc_zona_cinzenta.md`** — o AUC dentro da zona agora é reproduzível e tem intervalo:

| Medição | AUC | IC95% (bootstrap, 2000×) |
|---|---|---|
| Zona cinzenta, calibrado (`p_hat`) | **0,5612** | **[0,5368; 0,5846]** |
| Zona cinzenta, score bruto pré-calibração | 0,5643 | [0,5381; 0,5888] |
| Referência: mesmo modelo, teste inteiro | 0,776 | ver `camada1_treino_final.md` |

**Achado que muda uma afirmação publicada: o IC não contém 0,50.** A leitura correta é *"o modelo discrimina fracamente, mas de forma detectável"*, não *"é indistinguível de acaso"*. O ponto (0,5612) e o teste de robustez do score bruto (0,5643) reproduziram **exatamente** os valores ad-hoc de 2026-08-12 — a conta original estava certa, só não era reproduzível nem tinha precisão declarada.

⚠️ **As sub-fatias NÃO reproduziram os números ad-hoc.** Registrado antes: centro 0,531 / meio 0,568 / borda 0,509. Reconstruído por script: centro 0,5157 / meio 0,5409 / borda 0,5343 (IC a 98,33%, Bonferroni para 3 comparações). A medição de 2026-08-12 não deixou script, então a definição de fatia aqui é reconstrução da descrição em prosa, não a mesma conta. **A conclusão é a mesma nas duas versões** (nenhuma fatia recupera previsibilidade — as três ficam *abaixo* do AUC da zona inteira), mas **os números reproduzíveis são os novos**. Não citar os antigos daqui em diante.

**(2) `scripts/separacao_por_confianca.py` + `reports/separacao_por_confianca.md`** — hipótese (b) testada. Proxy de confiança: `assimetria = |n_favoravel − n_desfavoravel| / n_fatos` sobre `fatores_cliente` (`neutro` no denominador — fato neutro não sustenta lado nenhum). Separação NEGAR−APROVAR por tercil de assimetria (IC a 98,33%, Bonferroni):

| Assimetria | n | Separação | IC98,33% |
|---|---|---|---|
| 0,00–0,43 (evidência apertada) | 212 | −3,7% | [−19,4%; +12,1%] |
| 0,43–0,67 | 168 | +2,0% | [−17,0%; +20,0%] |
| 0,67–1,00 (evidência unânime) | 184 | +5,5% | [−11,8%; +24,0%] |

**Hipótese (b) não sustentada, mas não refutada com força.** Nenhum grupo separa de forma detectável — nem o de evidência unânime, o cenário mais favorável possível ao agente. **Porém os pontos crescem monotonicamente na direção prevista** (−3,7 → +2,0 → +5,5pp), e omitir isso seria desonesto: três pontos ordenados por acaso acontecem em 1 de 6 vezes. Os intervalos têm ~30pp de largura, e com n≈190 por grupo (contra os 722 que o próprio projeto calculou para detectar 10pp) o estudo está **~4× subdimensionado**. **Conclusão precisa: descarta sinal grande escondido nos casos unânimes, não descarta sinal pequeno.** É "não achamos", não "não existe".

**Isso não reabre o #34.** A conclusão central dele vem do teto de previsibilidade da zona (AUC 0,56 do modelo campeão, que independe de qual agente decide), não deste teste. Um sinal pequeno sobrevivente nos casos unânimes seria compatível com esse teto, não uma contradição dele.

**Achado lateral de contrato, pego por guarda:** a primeira versão de `assimetria_evidencia()` assumia dois pesos (`favoravel`/`desfavoravel`) e levantou exceção em vez de ignorar o desconhecido — revelando que `app/memo_credito.py::Peso` tem **três** valores, com `neutro` em 447 dos 2.885 fatos (15,5%). Se a guarda fosse um `continue` silencioso, o denominador encolheria e a assimetria seria inflada sem ninguém notar. É a regra de guarda silenciosa do `AGENTS.md` da base funcionando na prática.

**Hipótese remanescente, agora a única em aberto:** segmentar por confiança com `n` suficiente para detectar 10pp por grupo (~722 casos **por grupo**, ~2.200 no total). Custo estimado ~US$23 de API, e exigiria revincular o faturamento do GCP. **Não recomendado**: o teto de previsibilidade da zona (0,56) limita o que qualquer sinal encontrado ali poderia valer, então o retorno esperado não paga o custo. Registrado para não parecer que a possibilidade passou despercebida.

---

## Custo acumulado — Gemini/GCP (reconstruído 2026-08-12)

Todo gasto de API real deste projeto passa pela chave `GEMINI_API_KEY`, faturada num projeto GCP. Nenhum outro serviço GCP é usado (sem Cloud Storage, BigQuery, Vertex AI — confirmado por grep no código, 2026-08-12). Reconstrução do que os relatórios documentam:

| Quando | O quê | Custo |
|---|---|---|
| 2026-08-06 | Piloto n=25 (débito #25, achou o bug de telemetria de thinking tokens) | US$ 0,2867 |
| ~2026-08-07/08 | Piloto n=100, 87 memos válidos (débito #29, gerou o ground truth original) | US$ 1,10 |
| 2026-08-11 | Smoke test n=5 (validação do pipeline antes do lote grande) | US$ 0,0482 |
| 2026-08-11 | Piloto n=722, 563 memos válidos (débito #34, backtest final) | US$ 7,5169 |
| **Total documentado** | | **≈ US$ 8,95** |

Se o faturamento do GCP mostrar um valor diferente de ~US$8,95 convertido, a diferença provavelmente é câmbio na hora exata de cada cobrança, taxas do provedor, ou chamadas de desenvolvimento/teste anteriores a 2026-08-06 (antes da telemetria de custo existir) que não geraram relatório. Este é o piso reconstruível a partir dos artefatos versionados, não uma reconciliação exata linha a linha com o extrato do GCP.

> ⚠️ **Faturamento do GCP desvinculado deliberadamente em 2026-08-12** (fechamento de custo em R$61, decisão do usuário — não tinha mais nada planejado que exigisse a chave no momento). **`GEMINI_API_KEY` não funciona até a conta de faturamento ser revinculada no console do GCP.** Qualquer script que chame `ClienteGemini`/`piloto_camada2.py` vai falhar com erro de billing, não é bug do código — é esperado. `GROQ_API_KEY` (usada pelo juiz, débito #10) é conta separada, não afetada por essa decisão.

**Não há trabalho planejado que exija gastar mais nessa chave no momento** — os próximos passos do débito #34 (feature importance da Camada 1, segmentação por confiança) usam dado e modelo já salvos localmente, sem chamada de API nova. O débito #10 (calibração do juiz) usa Groq, cobrança separada, não afetada por decisões sobre o faturamento do GCP.

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
