# EDA — `application_train.csv` (CRISP-DM fase 2)

**Gerado por:** `scripts/eda_application.py`  
**Base:** 307,511 linhas × 122 colunas  
**Taxa de default:** 8.07%

> **Por que este relatório é tardio:** o projeto chegou à Camada 1 treinada, motor de decisão e primeira ferramenta da Camada 2 **sem exame sistemático do dado**. Os dois problemas conhecidos até aqui foram achados por tropeço. Achar dois por acaso sugere que havia outros — e havia.

## 1. Integridade

- `SK_ID_CURR` duplicado: **0**
- Linhas inteiramente duplicadas: **0**
- Colunas sem nenhum nulo: **55** de 122

## 2. 🔴 Colunas que não distinguem ninguém

**16 colunas** têm um único valor em mais de 99.5% das linhas — não separam cliente bom de ruim. **16 delas estão dentro do modelo treinado.**

| Coluna | Valor dominante | Frequência | No modelo? |
|---|---|---|---|
| `FLAG_MOBIL` | `1` | 100.00% | sim |
| `FLAG_DOCUMENT_12` | `0` | 100.00% | sim |
| `FLAG_DOCUMENT_10` | `0` | 100.00% | sim |
| `FLAG_DOCUMENT_2` | `0` | 100.00% | sim |
| `FLAG_DOCUMENT_4` | `0` | 99.99% | sim |
| `FLAG_DOCUMENT_7` | `0` | 99.98% | sim |
| `FLAG_DOCUMENT_17` | `0` | 99.97% | sim |
| `FLAG_DOCUMENT_21` | `0` | 99.97% | sim |
| `FLAG_DOCUMENT_20` | `0` | 99.95% | sim |
| `FLAG_DOCUMENT_19` | `0` | 99.94% | sim |
| `FLAG_DOCUMENT_15` | `0` | 99.88% | sim |
| `FLAG_CONT_MOBILE` | `1` | 99.81% | sim |
| `FLAG_DOCUMENT_14` | `0` | 99.71% | sim |
| `FLAG_DOCUMENT_13` | `0` | 99.65% | sim |
| `FLAG_DOCUMENT_9` | `0` | 99.61% | sim |
| `FLAG_DOCUMENT_11` | `0` | 99.61% | sim |

## 3. Ausência disfarçada de categoria

Valores que parecem categoria válida mas significam *sem informação*.

| Coluna | Código | Linhas | % |
|---|---|---|---|
| `ORGANIZATION_TYPE` | `XNA` | 55,374 | 18.01% |
| `FONDKAPREMONT_MODE` | `not specified` | 5,687 | 1.85% |
| `CODE_GENDER` | `XNA` | 4 | 0.00% |
| `NAME_FAMILY_STATUS` | `Unknown` | 2 | 0.00% |

## 4. O segmento de 18% — mesmo grupo, três codificações

- `DAYS_EMPLOYED = 365243` (≈1.000 anos): **55,374** linhas (18.01%)
- `ORGANIZATION_TYPE = XNA`: **55,374** linhas (18.01%)
- Divergência entre os dois conjuntos: **0** linhas

São **exatamente a mesma população**, e ela tem nome: pensioners (55,352 de 55,374).

**E são melhores pagadores:** default de **5.40%** contra **8.66%** no resto da base.

> Ou seja: o valor 'ausente' não era ausência — era o marcador de um segmento de **menor** risco. A informação sobrevive via `NAME_INCOME_TYPE` e `ORGANIZATION_TYPE`, então convertê-lo para nulo no treino não perdeu sinal. Mas foi sorte, não desenho.

## 5. 🔴 Outliers monetários

| Coluna | Mediana | p99 | Máximo | Máx/p99 |
|---|---|---|---|---|
| `AMT_INCOME_TOTAL` | 147,150 | 472,500 | 117,000,000 | **248×** ⚠️ |
| `AMT_CREDIT` | 513,531 | 1,854,000 | 4,050,000 | **2×** |
| `AMT_ANNUITY` | 24,903 | 70,006 | 258,026 | **4×** |
| `AMT_GOODS_PRICE` | 450,000 | 1,800,000 | 4,050,000 | **2×** |

**As três maiores rendas declaradas:**

| SK_ID_CURR | Renda | Crédito | Tipo de renda | Deu calote? |
|---|---|---|---|---|
| 114967 | 117,000,000 | 562,491 | Working | SIM |
| 336147 | 18,000,090 | 675,000 | Commercial associate | não |
| 385674 | 13,500,000 | 1,400,504 | Commercial associate | não |

> A maior renda declarada é **248× o percentil 99** e pertence a alguém classificado como *Working* que pediu um empréstimo de 562 mil — e deu calote. Renda de 117 milhões com empréstimo de 562 mil não é plausível: é erro de digitação, quase certamente zeros a mais. **Qualquer razão que use renda no denominador fica contaminada por esta linha.**

## 6. Nulos

- Colunas com **mais de 50% nulo**: **41**
- Colunas com algum nulo: 67
- Pior caso: `COMMONAREA_AVG` com 69.9%

## 7. Redundância `_AVG` / `_MODE` / `_MEDI`

Cada medida de prédio aparece em três versões. Medindo a correlação **mínima** dentro de cada trio: **14 de 14** trios têm as três versões correlacionadas acima de 95% — são a mesma informação escrita três vezes (**~28 colunas redundantes**).

| Grupo | Correlação mínima do trio |
|---|---|
| `YEARS_BUILD_*` | 0.989 |
| `FLOORSMIN_*` | 0.986 |
| `FLOORSMAX_*` | 0.986 |
| `ELEVATORS_*` | 0.979 |
| `ENTRANCES_*` | 0.978 |
| `COMMONAREA_*` | 0.977 |
| `LANDAREA_*` | 0.974 |
| `BASEMENTAREA_*` | 0.973 |

## 8. O que fazer com isto

| Achado | Gravidade | Ação |
|---|---|---|
| 16 colunas constantes dentro do modelo | Baixa (desperdício) | Remover do treino |
| Renda de 117 milhões | **Alta (corrompe razões)** | Decidir: teto, remoção ou manter declarado |
| ~28 colunas redundantes | Baixa | Manter uma versão por grupo |
| 41 colunas com >50% nulo | Média | Avaliar remoção em bloco |
| Segmento de aposentados (18%) | Informativo | Documentar — é segmento real, menor risco |

> **Nenhum destes explica a performance atual do modelo** (árvores ignoram constante e lidam com nulo). O ganho é de higiene, custo de treino e — principalmente — de **saber o que está na base antes de afirmar coisas sobre ela**.
