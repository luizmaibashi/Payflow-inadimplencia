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

**16 colunas** têm um único valor em mais de 99.5% das linhas — não separam cliente bom de ruim. **0 delas estão dentro do modelo treinado.**

| Coluna | Valor dominante | Frequência | No modelo? |
|---|---|---|---|
| `FLAG_MOBIL` | `1` | 100.00% | não |
| `FLAG_DOCUMENT_12` | `0` | 100.00% | não |
| `FLAG_DOCUMENT_10` | `0` | 100.00% | não |
| `FLAG_DOCUMENT_2` | `0` | 100.00% | não |
| `FLAG_DOCUMENT_4` | `0` | 99.99% | não |
| `FLAG_DOCUMENT_7` | `0` | 99.98% | não |
| `FLAG_DOCUMENT_17` | `0` | 99.97% | não |
| `FLAG_DOCUMENT_21` | `0` | 99.97% | não |
| `FLAG_DOCUMENT_20` | `0` | 99.95% | não |
| `FLAG_DOCUMENT_19` | `0` | 99.94% | não |
| `FLAG_DOCUMENT_15` | `0` | 99.88% | não |
| `FLAG_CONT_MOBILE` | `1` | 99.81% | não |
| `FLAG_DOCUMENT_14` | `0` | 99.71% | não |
| `FLAG_DOCUMENT_13` | `0` | 99.65% | não |
| `FLAG_DOCUMENT_9` | `0` | 99.61% | não |
| `FLAG_DOCUMENT_11` | `0` | 99.61% | não |

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

## 8. Relação com o alvo — onde está o sinal

Item que faltava na 1ª versão deste relatório. Sem ele a EDA descreve a base mas não diz **o que serve para prever**.

| Bloco | Colunas | Maior correlação com `TARGET` | Coluna |
|---|---|---|---|
| Scores externos (bureau) | 3 | **0.179** | `EXT_SOURCE_3` |
| Perfil pessoal | 3 | **0.078** | `DAYS_BIRTH` |
| Trabalho e renda | 3 | **0.051** | `DAYS_ID_PUBLISH` |
| Documentos entregues | 20 | **0.044** | `FLAG_DOCUMENT_3` |
| Características do prédio | 43 | **0.044** | `FLOORSMAX_AVG` |
| Pedido (valores do contrato) | 4 | **0.040** | `AMT_GOODS_PRICE` |
| Círculo social | 4 | **0.032** | `DEF_30_CNT_SOCIAL_CIRCLE` |
| Consultas ao bureau | 6 | **0.020** | `AMT_REQ_CREDIT_BUREAU_YEAR` |

> **O sinal é muito concentrado.** O bloco mais forte (*Scores externos (bureau)*) tem correlação de 0.179; o mais fraco (*Consultas ao bureau*, com 6 colunas) tem 0.020. Ou seja: **a maior parte das 122 colunas quase não carrega sinal**, e o que carrega são scores calculados por terceiros — limitação honesta do domínio, registrada também em `DICIONARIO_DADOS.md`.

## 9. `application_train` × `application_test` — mesma população?

- Treino: **307,511** linhas · Teste: **48,744** linhas

Diferença padronizada de média (|média_treino − média_teste| ÷ desvio do treino). Acima de 0,10 costuma indicar deslocamento relevante.

| Coluna | Dif. padronizada | Dif. de % nulo |
|---|---|---|
| `FLAG_EMAIL` | 0.458 | 0.00% |
| `AMT_REQ_CREDIT_BUREAU_QRT` | 0.354 | 1.09% |
| `AMT_REQ_CREDIT_BUREAU_MON` | 0.282 | 1.09% |
| `AMT_GOODS_PRICE` | 0.205 | 0.09% |
| `AMT_CREDIT` | 0.204 | 0.00% |
| `FLAG_DOCUMENT_3` | 0.169 | 0.00% |
| `AMT_ANNUITY` | 0.160 | 0.05% |
| `AMT_REQ_CREDIT_BUREAU_WEEK` | 0.154 | 1.09% |

> **10 de 104** colunas passam de 0,10 de diferença padronizada — as duas amostras **não** são intercambiáveis.

> **Por que isso não invalida nada do projeto:** `application_test.csv` é o conjunto de submissão do Kaggle e **não tem `TARGET`**. Todo número reportado aqui (AUC, Brier, backtest do motor) vem de um split interno de `application_train`, nunca deste arquivo. O `camada1_features_test.parquet` é gerado mas **não é usado** por nenhum script de avaliação.

> **Quando isso passaria a importar:** se alguém decidir usar esse arquivo para inferência ou para submeter ao Kaggle. Aí o deslocamento acima precisa ser tratado — em especial `FLAG_EMAIL` (0,458) e as consultas ao bureau.

## 10. Datasets auxiliares e históricos

Registrado para não virar lacuna silenciosa no gate de CRISP-DM — arquivo que existe mas ninguém examina é exatamente o tipo de coisa que some do radar.

| Arquivo | Situação |
|---|---|
| `payflow_credit_risk.csv` | **Legado removido do estado atual.** Base sintética substituída pelo Home Credit no ADR-0001; narrativa preservada em `docs/LEGADO_V1.md` e artefato recuperável no histórico Git. |
| `sample_submission.csv` | Template de submissão do Kaggle, não é dado de análise. |
| `HomeCredit_columns_description.csv` | Dicionário oficial de colunas — traduzido em `docs/DICIONARIO_DADOS.md`. |

## 11. O que fazer com isto

| Achado | Gravidade | Ação |
|---|---|---|
| 0 colunas constantes dentro do modelo | Baixa (desperdício) | Remover do treino |
| Renda de 117 milhões | **Alta (corrompe razões)** | Decidir: teto, remoção ou manter declarado |
| ~28 colunas redundantes | Baixa | Manter uma versão por grupo |
| 41 colunas com >50% nulo | Média | Avaliar remoção em bloco |
| Segmento de aposentados (18%) | Informativo | Documentar — é segmento real, menor risco |

> **Nenhum destes explica a performance atual do modelo** (árvores ignoram constante e lidam com nulo). O ganho é de higiene, custo de treino e — principalmente — de **saber o que está na base antes de afirmar coisas sobre ela**.
