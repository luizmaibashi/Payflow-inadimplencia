# EDA — tabelas relacionais (CRISP-DM fase 2, parte 2)

**Gerado por:** `scripts/eda_tabelas_relacionais.py`

> A primeira EDA cobriu só `application_train.csv`. Estas seis tabelas (~27M linhas) alimentam as **32 features agregadas** da Camada 1 e nunca tinham sido examinadas. Cada checagem abaixo existe porque seu resultado errado **corromperia uma feature que já está no modelo**.

## `bureau.csv` — crédito em outras instituições

- Linhas: **1,716,428** | clientes distintos: 305,811
- `SK_ID_BUREAU` duplicado: **0**


### Dívida e crédito podem ser negativos?

*Feature em risco:* `bureau_divida_sobre_credito`

| Checagem | Linhas | % |
|---|---|---|
| Dívida **negativa** | 8,418 | 0.490% |
| Crédito **negativo** | 0 | 0.000% |
| Dívida **maior** que o crédito concedido | 29,642 | 1.73% |

- `CREDIT_DAY_OVERDUE`: mediana 0, p99 0, **máx 2,792 dias** (8 anos de atraso)

## `bureau_balance.csv` — histórico mês a mês do bureau

- Linhas: **27,299,925** (a maior tabela) | contratos: 817,395


### Distribuição de STATUS

*Feature em risco:* `bureau_max_severidade_historica, bureau_meses_em_atraso_total`

| STATUS | Significado | % |
|---|---|---|
| `C` | contrato encerrado | 49.99% |
| `0` | em dia | 27.47% |
| `X` | **sem informação** | 21.28% |
| `1` | atraso 1–30d | 0.89% |
| `5` | atraso >120d / write-off | 0.23% |
| `2` | atraso 31–60d | 0.09% |
| `3` | atraso 61–90d | 0.03% |
| `4` | atraso 91–120d | 0.02% |

- `X` (sem informação) responde por **21.3%** dos meses.

## `previous_application.csv` — pedidos anteriores

- Linhas: **1,670,214** | clientes: 338,857


### Sentinela de data também aqui?

*Feature em risco:* `previous_cnt_payment_mean`

- `DAYS_FIRST_DRAWING = 365243`: **934,444** linhas (**55.9%**) — o mesmo sentinela de `application_train`, em outra tabela.
- `CNT_PAYMENT = 0` (contrato sem prazo): **144,985** (8.7%)

## `installments_payments.csv` — parcelas pagas

- Linhas: **13,605,401** | clientes: 339,587


### Pagamento sem data ou sem valor

*Feature em risco:* `atraso_medio_dias, frac_parcelas_atrasadas`

| Checagem | Linhas | % |
|---|---|---|
| `DAYS_ENTRY_PAYMENT` nulo (parcela **nunca paga**) | 2,905 | 0.02% |
| `AMT_PAYMENT` nulo | 2,905 | 0.02% |
| `AMT_INSTALMENT = 0` (parcela de valor zero) | 290 | 0.002% |

- Atraso (dias): mediana **-6** (negativo = adiantado), p99 18, máx **2884**

## `POS_CASH_balance.csv` — crediário

- Linhas: **10,001,358**
- `SK_DPD` (dias em atraso): mediana 0, p99 235, **máx 4,231**


## `credit_card_balance.csv` — cartão

- Linhas: **3,840,312** | clientes: 103,558


### Divisão por limite zero

*Feature em risco:* `cc_utilizacao_media`

| Checagem | Linhas | % |
|---|---|---|
| Limite **igual a zero** (denominador da utilização) | 753,823 | 19.63% |
| Saldo **negativo** (cliente com crédito a favor) | 2,345 | 0.06% |

- Utilização: mediana **1.1%**, p99 **106.9%**, **máx 1178%**

---

## Achados que exigem decisão

- `bureau`: **8,418 dívidas negativas** — entram na soma de `bureau_credit_sum_debt_total` e reduzem artificialmente a dívida do cliente.
- `bureau_balance`: **21% dos meses têm STATUS `X` (sem informação)**. Na engenharia de features `X` cai no `fillna(0)` do mapa de severidade, ou seja, **é tratado como 'em dia'** — mês sem informação vira mês bom. Isso subestima a severidade histórica.
- `previous_application`: sentinela `365243` em **56%** de `DAYS_FIRST_DRAWING`. Não usamos essa coluna hoje, mas qualquer feature futura sobre ela nasceria corrompida.
- `installments`: **2,905 parcelas sem data de pagamento** (0.02%) — são parcelas **nunca pagas**, o sinal mais forte de inadimplência que existe, e hoje elas somem do cálculo de atraso (a subtração vira nulo). **Estamos descartando o pior caso.**
- `credit_card`: utilização máxima de **1178%** do limite — saldo muitas vezes maior que o limite. `cc_utilizacao_media` tem cauda extrema não tratada.
- `credit_card`: **753,823 linhas com limite zero** (19.63%) — divisão por zero em `cc_utilizacao_media`.
