# AGENTS.md — PayFlow (crédito com camada agêntica de underwriting)

> **Projeto**: classificador de risco de crédito (PD) + motor de decisão por valor esperado + agente de underwriting que produz memo de crédito auditável para a zona cinzenta.
> **Stack alvo**: Python · scikit-learn · Pydantic · FastAPI · Streamlit · DeepEval · APIs BCB SGS / IBGE
> **Estado**: refatoração **especificada, não implementada**. A Camada 1 atual é do projeto antigo (dado sintético) e será substituída.

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
- `docs/adr/` — 8 ADRs (D1-D8)
- `tests/test_paridade.py` — reescrito para o esquema Home Credit (5 testes, ver débito #8)

- `app/motor_decisao.py` — motor de decisão por valor esperado (ADR-0002), testado em `tests/test_motor_decisao.py` (9 testes)
- `scripts/motor_decisao_backtest.py` — backtest pareado do motor contra o threshold legado, com IC bootstrap sobre o delta; resultado em `reports/motor_decisao_backtest.md` (ver débitos #12-14 sobre limitações)

**Alvo (a construir):**
- Camada 2 — agente de underwriting com tools de caso e de cenário (ADR-0007)
- `docs/audit/` — auditorias pós-implementação
- Eval set versionado + relatório com `n` e intervalo
- Baseline "corte único recalibrado" para isolar desenho do motor vs. calibração (débito #13)

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
| **Margem (`M`)** | Lucro esperado do contrato se o cliente pagar. Derivada dos juros implícitos (`AMT_ANNUITY × CNT_PAYMENT − AMT_CREDIT`), não arbitrada |
| **Perda esperada** | `PD × LGD × EAD` |
| **`p*` (limiar de indiferença)** | `M / (M + LGD × EAD)`. Ponto em que aprovar e negar têm o mesmo valor esperado. **Não depende do modelo** — é premissa de negócio |
| **Zona cinzenta** | Banda em torno de `p*` onde o sinal (`\|EV\|`) é menor que a incerteza somada (da premissa + da estimativa). Substitui os buckets fixos 0.40/0.65 |
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
12. **Margem/LGD do motor de decisão são proxies, não a métrica validada no Gate 0.** `application_train.csv` não tem `CNT_PAYMENT` (a fórmula `m = anuidade×prazo/crédito` do Gate 0 exige prazo, que não existe para uma aplicação ainda não decidida). `app/motor_decisao.py` usa `AMT_ANNUITY/AMT_CREDIT` como proxy de margem e `NAME_CONTRACT_TYPE` (Cash/Revolving — categorias diferentes das de `previous_application`) como proxy de LGD. Declarado em código e no relatório do backtest.
13. **Backtest do motor (`reports/motor_decisao_backtest.md`) não isola desenho de motor vs. calibração do baseline.** O delta de ~R$21 mil/caso a favor do motor de EV é majoritariamente efeito de os thresholds legados (0.40/0.65) estarem calibrados contra a escala de `p̂` de um modelo diferente (não calibrado) — contra `p̂` real, só 1% dos casos ultrapassam 0,40. Falta um terceiro braço (corte único recalibrado nesta mesma escala, otimizado no conjunto de calibração) para provar que "decidir por observação" bate um corte global bem calibrado — o que este backtest prova de fato é que threshold fixo é frágil a mudança de calibração do modelo.
14. **Banda de indiferença do motor (±3pp) é largura fixa simplificada**, não derivada da incerteza real da estimativa de PD por caso (ADR-0002 §2.6 previa isso, ainda não implementado).

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
| Spec consolidada | `docs/wayfinder/refatoracao-camada-agentica/SPEC_FINAL.md` |
| 9 tickets Wayfinder (pesquisa e decisões) | `docs/wayfinder/refatoracao-camada-agentica/` |
| Aula — valor esperado, PD/LGD/EAD | `wiki/concepts/04_business/Valor_Esperado_Decisao_Credito.md` (base de conhecimento) |
| Padrão de rigor a replicar | `PROJETOS/02_PORTFOLIO/stable-treasury/` |
