# Dicionário de Dados — Home Credit + features da Camada 1

> **Para que serve:** entender o que cada coluna significa **e por que ela importa para risco de crédito** — a fase *Data Understanding* do CRISP-DM.
> **Fonte das descrições originais:** `data/raw/home_credit/HomeCredit_columns_description.csv` (219 linhas, documentação oficial do Kaggle). Traduzidas e reorganizadas por tema, não por ordem alfabética.
> **Decisão registrada (2026-08-04):** os nomes das colunas **não foram renomeados** para português. Motivo: manter rastreabilidade direta com a documentação oficial e com o modelo já treinado, sem forçar retreino. Esta tradução vive aqui, não no código.

---

## Conexão com objetivo de negócio

Doc de origem: `AGENTS.md` (mapa do projeto + Linguagem Ubíqua) e `docs/adr/0001-...md`/`0002-...md`. Objetivo já estava documentado antes deste dicionário — resumo, não sabatina nova:

**Hipótese que este dataset testa:** dado real de risco de crédito (Home Credit, mercado emergente) permite treinar um classificador de PD calibrado e, a partir dele, um motor de decisão por valor esperado (`p* = M/(M+LGD·EAD)`, ADR-0002) que isole corretamente a **zona cinzenta** — os casos onde a decisão de aprovar/negar é genuinamente incerta. As colunas de `application_train` dão o retrato do pedido; as 6 tabelas relacionais (PARTE 2) dão o comportamento passado, que é onde está o sinal real de inadimplência.

**Por que Home Credit e não dado brasileiro:** transferência de **método**, declarada — não existe base pública de crédito pessoal brasileira do mesmo porte. Nunca afirmar que o cliente do dataset é brasileiro (débito #9, escopo negativo do `AGENTS.md`).

**Vale ainda?** Sim — nenhuma decisão em ADR-0001/0002 mudou desde que foram escritas (2026-08-04). Se isso mudar, atualizar aqui e nos ADRs, não sobrescrever calado.

---

## Como ler os nomes (o padrão por trás da bagunça aparente)

Os nomes parecem confusos, mas seguem prefixos consistentes. Sabendo os prefixos, 80% da confusão some:

| Prefixo | Significa | Exemplo |
|---|---|---|
| `SK_ID_` | Chave de identificação (ID) | `SK_ID_CURR` = ID do pedido atual |
| `AMT_` | *Amount* — valor monetário | `AMT_CREDIT` = valor do empréstimo |
| `CNT_` | *Count* — contagem | `CNT_CHILDREN` = número de filhos |
| `DAYS_` | Dias **relativos à data do pedido**, quase sempre **negativos** (passado) | `DAYS_BIRTH = -12000` → nasceu há 12.000 dias |
| `FLAG_` | Sim/não (1/0) | `FLAG_OWN_CAR` = tem carro? |
| `NAME_` | Categoria textual | `NAME_EDUCATION_TYPE` = escolaridade |
| `RATE_` | Taxa/percentual normalizado | `RATE_DOWN_PAYMENT` = taxa de entrada |
| `EXT_SOURCE_` | Score de bureau externo, já normalizado 0–1 | `EXT_SOURCE_2` |
| `_AVG` / `_MODE` / `_MEDI` | Média / moda / mediana da mesma medida | `APARTMENTS_AVG` |
| `DPD` | *Days Past Due* — dias em atraso | `SK_DPD` |

> ⚠️ **A pegadinha do `DAYS_`:** são negativos porque contam para trás a partir do pedido. `DAYS_EMPLOYED = -2000` significa "está empregado há 2.000 dias". Quanto **mais negativo**, mais tempo — o que inverte a intuição de "número maior = mais".

---

## As 7 tabelas e como se conectam

```
application_train.csv  (1 linha por PEDIDO — é aqui que está o TARGET)
        │  SK_ID_CURR
        ├──────────► bureau.csv  (empréstimos em OUTROS bancos)
        │                 │  SK_ID_BUREAU
        │                 └──────► bureau_balance.csv  (status mês a mês)
        │
        └──────────► previous_application.csv  (pedidos anteriores na Home Credit)
                          │  SK_ID_PREV
                          ├──────► installments_payments.csv  (parcelas pagas)
                          ├──────► POS_CASH_balance.csv  (saldo de crediário)
                          └──────► credit_card_balance.csv  (saldo de cartão)
```

**A ideia central:** a tabela principal tem só o retrato do momento do pedido. Todo o **comportamento passado** está nas outras seis — e é justamente isso que a engenharia de features traz para a linha do cliente.

---

# PARTE 1 — Colunas originais (`application_train.csv`)

## Colunas (pós-limpeza)

Detalhadas por bloco temático abaixo. `application_test.csv` segue o mesmo esquema de `application_train.csv`, **sem `TARGET`** — é o conjunto de submissão do Kaggle. Nenhuma métrica deste projeto (AUC, Brier, backtest do motor) vem desse arquivo; `camada1_features_test.parquet` é gerado pelo pipeline mas não é consumido por nenhum script de avaliação (deslocamento de distribuição medido entre as duas amostras: `reports/eda_application.md` item 9 — só passaria a importar se alguém decidisse submeter ao Kaggle).

`payflow_credit_risk.csv` é o dataset **sintético do V1 legado** (pré-ADR-0001) — não é coberto por este dicionário, que documenta só a Camada 1 atual (Home Credit real). Status do V1: legado a substituir, não a estender (ver débito #11 do `AGENTS.md`).

## 1.1 Identificação e alvo

| Coluna | O que é | Por que importa |
|---|---|---|
| `SK_ID_CURR` | ID do pedido de empréstimo | Chave para juntar todas as outras tabelas. **Não é feature** — foi removida do treino |
| `TARGET` | **1** = cliente teve dificuldade de pagamento (atrasou mais de X dias em pelo menos uma das primeiras Y parcelas); **0** = todos os outros casos | É o que o modelo prevê. **8,07%** da base é 1 — desbalanceamento que causou toda a discussão de calibração (Gate 1) |

> **Nota crítica sobre o `TARGET`:** ele não é "deu calote e sumiu". É um marcador de **dificuldade precoce de pagamento**. Isso importa na hora de traduzir o modelo para negócio: prever `TARGET=1` não é prever perda total.

## 1.2 O pedido em si (a economia do contrato)

| Coluna | O que é | Por que importa |
|---|---|---|
| `NAME_CONTRACT_TYPE` | `Cash loans` (dinheiro livre) ou `Revolving loans` (rotativo/cartão) | **Usado no motor de decisão** como proxy de LGD: rotativo tem recuperação mais difícil (85%) que parcelado (70%) |
| `AMT_CREDIT` | Valor total do empréstimo concedido | É o **EAD** (exposição) da fórmula de valor esperado |
| `AMT_ANNUITY` | Valor da parcela (anuidade) | Junto com `AMT_CREDIT`, forma o proxy de margem do motor |
| `AMT_GOODS_PRICE` | Para crédito de consumo, o preço do bem financiado | Sinaliza compra vinculada a um bem (garantia implícita) |
| `AMT_INCOME_TOTAL` | Renda declarada do cliente | Base do comprometimento de renda — quanto da renda a parcela consome |

> ⚠️ **O que falta aqui, e mudou o projeto:** não existe `CNT_PAYMENT` (prazo) nesta tabela. O prazo é decidido **junto** com a aprovação, então não é dado de entrada. Foi isso que obrigou o motor de decisão a usar um proxy de margem (ver ADR-0002 §2.7).

## 1.3 Quem é o cliente (perfil pessoal)

| Coluna | O que é | Por que importa para crédito |
|---|---|---|
| `DAYS_BIRTH` | Idade em dias (negativo) | Idade correlaciona com estabilidade financeira |
| `CODE_GENDER` | Gênero | ⚠️ **Variável sensível** — ver alerta de fairness no fim |
| `CNT_CHILDREN` / `CNT_FAM_MEMBERS` | Filhos / membros da família | Pressão sobre o orçamento familiar |
| `NAME_FAMILY_STATUS` | Estado civil | Proxy de estabilidade e de renda dupla |
| `NAME_EDUCATION_TYPE` | Escolaridade máxima | Correlaciona com renda futura e estabilidade |
| `NAME_HOUSING_TYPE` | Situação de moradia (aluguel, casa própria, com os pais…) | Custo fixo mensal e patrimônio |
| `FLAG_OWN_CAR` / `OWN_CAR_AGE` | Tem carro / idade do carro | Patrimônio e capacidade de pagamento |
| `FLAG_OWN_REALTY` | Tem imóvel | Patrimônio — e potencial garantia |

## 1.4 Trabalho e renda

| Coluna | O que é | Por que importa |
|---|---|---|
| `DAYS_EMPLOYED` | Dias no emprego atual (negativo) | **Estabilidade de renda** — um dos sinais mais fortes em crédito |
| `NAME_INCOME_TYPE` | Origem da renda (assalariado, empresário, pensionista…) | Renda de pensão é estável; renda de negócio é volátil |
| `OCCUPATION_TYPE` | Profissão | Estabilidade e faixa de renda típica |
| `ORGANIZATION_TYPE` | Tipo de empresa onde trabalha | Setor público vs. privado, setor cíclico vs. estável |

> 🔧 **Armadilha real que tratamos no código:** `DAYS_EMPLOYED = 365243` (≈1.000 anos) aparece em ~18% dos casos. **Não é erro de digitação — é um valor sentinela** para "não empregado" (aposentado/desempregado). Deixá-lo como número faria o modelo achar que essas pessoas têm mil anos de emprego. Em `scripts/camada1_treino.py` ele é convertido para nulo.

## 1.5 Scores externos — as colunas mais preditivas da base

| Coluna | O que é | Por que importa |
|---|---|---|
| `EXT_SOURCE_1`, `EXT_SOURCE_2`, `EXT_SOURCE_3` | Scores normalizados (0–1) de fontes externas de crédito | São, de longe, **as features mais preditivas** do dataset inteiro. Equivalem ao "score do Serasa" — já são um modelo de risco pronto, embutido como variável |

> **Reflexão que vale para o projeto:** boa parte do poder preditivo vem de scores que **outra pessoa** calculou. Isso é normal no mercado, mas é bom saber que o modelo não está descobrindo risco do zero — está, em grande medida, reaproveitando um julgamento externo.

## 1.6 Consistência de endereço (sinal de fraude/instabilidade)

| Coluna | O que é |
|---|---|
| `REG_REGION_NOT_LIVE_REGION`, `REG_REGION_NOT_WORK_REGION`, `LIVE_REGION_NOT_WORK_REGION` | Endereço de cadastro ≠ de contato ≠ de trabalho (nível região) |
| `REG_CITY_NOT_LIVE_CITY`, `REG_CITY_NOT_WORK_CITY`, `LIVE_CITY_NOT_WORK_CITY` | Mesma ideia, nível cidade |
| `REGION_RATING_CLIENT`, `REGION_RATING_CLIENT_W_CITY` | Nota da região onde mora (1, 2, 3), atribuída pela própria Home Credit |
| `REGION_POPULATION_RELATIVE` | População normalizada da região |

**Por que importa:** divergência de endereços é sinal clássico de instabilidade ou de dado inconsistente — ambos correlacionam com risco.

## 1.7 Contato e documentos

| Coluna | O que é | Por que importa |
|---|---|---|
| `FLAG_MOBIL`, `FLAG_EMP_PHONE`, `FLAG_WORK_PHONE`, `FLAG_CONT_MOBILE`, `FLAG_PHONE`, `FLAG_EMAIL` | Forneceu cada tipo de contato? | **Contactabilidade** — quem é difícil de achar é difícil de cobrar (impacta diretamente a recuperação, ou seja, a LGD) |
| `FLAG_DOCUMENT_2` … `FLAG_DOCUMENT_21` | Entregou o documento N? (20 colunas) | Completude cadastral. A maioria é quase sempre 0 — pouco sinal individual |
| `DAYS_LAST_PHONE_CHANGE` | Há quantos dias trocou de telefone | Troca recente pode indicar instabilidade |
| `DAYS_REGISTRATION`, `DAYS_ID_PUBLISH` | Há quantos dias mudou o cadastro / o documento | Mesma lógica de estabilidade |

## 1.8 Consultas ao bureau (o cliente está "batendo em muitas portas"?)

| Coluna | Janela |
|---|---|
| `AMT_REQ_CREDIT_BUREAU_HOUR` | Última hora |
| `AMT_REQ_CREDIT_BUREAU_DAY` | Último dia |
| `AMT_REQ_CREDIT_BUREAU_WEEK` | Última semana |
| `AMT_REQ_CREDIT_BUREAU_MON` | Último mês |
| `AMT_REQ_CREDIT_BUREAU_QRT` | Últimos 3 meses |
| `AMT_REQ_CREDIT_BUREAU_YEAR` | Último ano |

**Por que importa muito:** alguém consultado por vários credores em poucos dias provavelmente está pedindo crédito em vários lugares ao mesmo tempo — sinal clássico de **desespero financeiro** (*credit hunger*).

## 1.9 Círculo social

| Coluna | O que é |
|---|---|
| `OBS_30_CNT_SOCIAL_CIRCLE` / `OBS_60_CNT_SOCIAL_CIRCLE` | Quantos conhecidos do cliente são observáveis com atraso de 30/60 dias |
| `DEF_30_CNT_SOCIAL_CIRCLE` / `DEF_60_CNT_SOCIAL_CIRCLE` | Quantos conhecidos **de fato** entraram em default a 30/60 dias |

**Por que importa:** inadimplência tem correlação de rede — o entorno do cliente carrega informação. ⚠️ Também levanta questão ética: penalizar alguém pelo comportamento de terceiros é defensável?

## 1.10 Características do prédio (47 colunas, pouco sinal)

`APARTMENTS_*`, `BASEMENTAREA_*`, `YEARS_BUILD_*`, `COMMONAREA_*`, `ELEVATORS_*`, `ENTRANCES_*`, `FLOORSMAX_*`, `FLOORSMIN_*`, `LANDAREA_*`, `LIVINGAPARTMENTS_*`, `LIVINGAREA_*`, `NONLIVINGAPARTMENTS_*`, `NONLIVINGAREA_*`, `TOTALAREA_MODE`, `HOUSETYPE_MODE`, `WALLSMATERIAL_MODE`, `FONDKAPREMONT_MODE`, `EMERGENCYSTATE_MODE`

Cada medida aparece em três versões: `_AVG` (média), `_MODE` (moda), `_MEDI` (mediana).

**Por que existem:** proxy de padrão socioeconômico da moradia. **Por que valem pouco:** têm **50% a 70% de valores faltantes** (as piores da base) e são altamente redundantes entre si. Candidatas naturais a remoção numa futura seleção de features.

---

# PARTE 2 — As 32 features que NÓS criamos

## Features criadas

> Definidas em [`app/feature_engineering_home_credit.py`](../app/feature_engineering_home_credit.py), testadas em [`tests/test_paridade.py`](../tests/test_paridade.py).
> **Motivação geral:** a tabela principal é uma *fotografia* do momento do pedido. Estas features trazem o *filme* — o comportamento passado do cliente, que é onde está o sinal de crédito de verdade.
> **Resultado medido:** AUC subiu de 0,759 → **0,776** ao adicioná-las (`reports/camada1_treino_final.md`).

## Convenção de nulos (decisão consciente, regra de dados do projeto)

- **Contagens (`n_*`) → preenchidas com 0.** "Cliente sem histórico de bureau" é um **fato medido** (ele não tem contratos), não uma estimativa.
- **Frações e médias → deixadas nulas (`NaN`).** Não existe "fração de parcelas atrasadas" para quem nunca teve parcela. O modelo (`HistGradientBoosting`) trata nulo nativamente, e "sem dado" é diferente de "zero".

Essa distinção é o que evita **imputação injustificada** — preencher fração com 0 diria ao modelo "esse cliente tem 0% de atraso", que é uma afirmação falsa sobre alguém de quem não sabemos nada.

## 2.1 Bureau externo — crédito em outras instituições

| Feature | O que mede | Cobertura | Por que foi criada |
|---|---|---|---|
| `n_bureau_contratos` | Quantos contratos o cliente tem/teve em outros bancos | 100% | Volume de relacionamento de crédito no mercado |
| `n_bureau_ativos` | Quantos ainda estão ativos | 100% | Endividamento **corrente**, não histórico |
| `frac_bureau_ativos` | Proporção dos contratos que seguem ativos | 85,7% | Distingue "muitos contratos já quitados" (bom) de "muitos contratos abertos" (risco) |
| `n_bureau_atrasados_hoje` | Contratos com atraso **neste momento** | 100% | Sinal mais forte que existe: já está em dificuldade agora |
| `bureau_credit_sum_total` | Soma do crédito concedido por outros bancos | 85,7% | Exposição total no mercado |
| `bureau_credit_sum_debt_total` | Soma do saldo devedor atual | 85,7% | Quanto ainda deve, não quanto já pegou |
| `bureau_divida_sobre_credito` | Dívida ÷ crédito total | 85,3% | **Utilização de crédito** — o cliente está no limite ou tem folga? |
| `bureau_max_severidade_historica` | Pior status já registrado (0=em dia … 5=atraso severo) | 30,0% | Pior momento histórico do cliente |
| `bureau_meses_em_atraso_total` | Quantos meses acumulados em atraso | 85,7% | **Cronicidade** — atrasar uma vez ≠ atrasar sempre |

> **Nota de honestidade:** `bureau_max_severidade_historica` tem só **30% de cobertura** porque depende de `bureau_balance`, que não existe para todos os contratos. É a feature mais esburacada do conjunto.

## 2.2 Pedidos anteriores na própria Home Credit

| Feature | O que mede | Cobertura | Por que foi criada |
|---|---|---|---|
| `n_previous_aplicacoes` | Quantas vezes já pediu crédito aqui | 100% | Relacionamento com a instituição |
| `n_previous_aprovadas` / `frac_previous_aprovadas` | Quantas/que proporção foram aprovadas | 100% / 94,6% | **A própria empresa já confiou nesse cliente antes?** |
| `n_previous_recusadas` / `frac_previous_recusadas` | Quantas/que proporção foram recusadas | 100% / 94,6% | Recusa passada é julgamento de risco anterior já embutido |
| `previous_amt_credit_mean` | Valor médio dos créditos anteriores | 94,6% | Porte típico das operações do cliente |
| `previous_amt_annuity_mean` | Parcela média anterior | 94,5% | Capacidade de pagamento demonstrada |
| `previous_cnt_payment_mean` | **Prazo médio** dos contratos anteriores (meses) | 94,5% | Criada para caracterizar o perfil de produto. ⚠️ Tentamos usá-la para reconstruir a margem do motor de decisão e **falhou** — o prazo dos contratos antigos (mediana 12 meses) não estima o prazo do atual (~20 meses). Ver ADR-0002 §2.7 |

## 2.3 Comportamento real de pagamento (o sinal mais direto)

| Feature | O que mede | Cobertura | Por que foi criada |
|---|---|---|---|
| `n_parcelas_historico` | Total de parcelas já processadas | 100% | Volume de histórico disponível |
| `n_parcelas_atrasadas` / `frac_parcelas_atrasadas` | Quantas/que proporção foram pagas com atraso | 100% / 94,8% | **Comportamento revelado** — não o que ele declara, o que ele fez |
| `atraso_medio_dias` | Média de dias de atraso (**negativo = pagou adiantado**) | 94,8% | Mediana da base é **−9,5 dias**: o cliente típico paga com 9 dias de antecedência |
| `atraso_max_dias` | Pior atraso já registrado | 94,8% | Cauda do comportamento, não a média |
| `n_parcelas_pagas_a_menor` / `frac_parcelas_pagas_a_menor` | Pagou menos que o devido | 100% / 94,8% | Pagamento parcial é sinal de aperto de caixa |
| `deficit_pagamento_medio_pct` | % médio do valor que faltou pagar | 94,8% | Intensidade do aperto, não só a ocorrência |

> **Por que este bloco é o mais valioso:** todas as outras features são *proxies* de capacidade de pagamento. Estas são o **registro do comportamento efetivo** — o cliente pagou ou não pagou, no prazo ou fora dele.

## 2.4 Crediário / POS (empréstimos parcelados anteriores)

| Feature | O que mede | Cobertura | Por que foi criada |
|---|---|---|---|
| `n_pos_contratos` | Contratos de crediário anteriores | 100% | Volume |
| `pos_max_dpd` | Pior atraso em dias (*Days Past Due*) | 94,1% | Severidade máxima |
| `pos_meses_em_atraso` | Meses em que esteve em atraso | 94,1% | Cronicidade |

## 2.5 Cartão de crédito

| Feature | O que mede | Cobertura | Por que foi criada |
|---|---|---|---|
| `n_cc_contratos` | Cartões anteriores na Home Credit | 100% | Mediana é **0** — a maioria não tem cartão aqui |
| `cc_utilizacao_media` | Saldo ÷ limite (média) | **28,0%** | Utilização alta de limite é sinal clássico de estresse financeiro |
| `cc_max_dpd` | Pior atraso no cartão | 28,3% | Severidade |
| `cc_meses_em_atraso` | Meses em atraso no cartão | 28,3% | Cronicidade |

> ⚠️ **Cobertura de só ~28%** — apenas 103.558 clientes têm histórico de cartão. Para 72% da base essas colunas são nulas. Sinal potencialmente forte, mas disponível para a minoria.

---

# PARTE 3 — Alertas para usar estes dados com responsabilidade

## 3.1 Variáveis sensíveis (fairness / discriminação)

A base contém `CODE_GENDER`, e indiretamente idade (`DAYS_BIRTH`), estado civil e número de filhos. **No Brasil, usar gênero ou estado civil para negar crédito levanta risco jurídico e ético real.** Um modelo pode também discriminar indiretamente, via proxies (região, profissão), mesmo sem a variável explícita.

Isto **não foi auditado** neste projeto até agora — é um débito honesto, não uma omissão silenciosa. Ver [`wiki/concepts/01_data_and_mlops/Fairness_Discriminacao_ML.md`](../../../../wiki/concepts/01_data_and_mlops/Fairness_Discriminacao_ML.md) na base de conhecimento.

## 3.2 O que este dataset NÃO é

- **Não é brasileiro.** É de mercados emergentes (Rússia, Indonésia, Vietnã…), com região anonimizada. Nunca afirmar que o cliente é brasileiro (ADR-0008).
- **Não é atual.** Os dados são de 2018.
- **`TARGET` não é "calote total"** — é dificuldade de pagamento precoce (atraso em uma das primeiras parcelas).

## 3.3 Vazamento temporal (data leakage)

Todas as features criadas usam **apenas dados anteriores ao pedido** (`DAYS_*` negativos, contratos prévios). Isso é intencional: usar qualquer informação posterior à decisão criaria vazamento e um modelo que parece ótimo no papel e falha em produção.

---

## Referências

| O quê | Onde |
|---|---|
| Descrições oficiais originais | `data/raw/home_credit/HomeCredit_columns_description.csv` |
| Código das features criadas | [`app/feature_engineering_home_credit.py`](../app/feature_engineering_home_credit.py) |
| Testes das agregações | [`tests/test_paridade.py`](../tests/test_paridade.py) |
| Resultado do treino | [`reports/camada1_treino_final.md`](../reports/camada1_treino_final.md) |
| Glossário de negócio do projeto | [`AGENTS.md`](../AGENTS.md) (Linguagem Ubíqua) |
| Por que a margem virou proxy | [`docs/adr/0002-motor-de-decisao-por-valor-esperado.md`](adr/0002-motor-de-decisao-por-valor-esperado.md) §2.7 |
