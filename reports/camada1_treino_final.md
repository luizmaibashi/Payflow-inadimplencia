# Camada 1 (final) — treino sobre Home Credit com features relacionais

**Gerado por:** `scripts/camada1_treino.py`  
**Dados:** `data/processed/camada1_features_train.parquet` (307,511 linhas, 136 colunas — 122 de `application_train` + 32 agregadas de bureau/previous_application/installments/POS_CASH/credit_card)
**Split:** treino 184,506 / calibração 61,502 / teste 61,503 (estratificado, distribuição real preservada em todos — sem reamostragem)

## Resultado no conjunto de teste (n=61,503)

| Modelo | AUC | Brier |
|---|---|---|
| Base (sem calibração pós-hoc) | 0.7767 | 0.0667 |
| **Calibrado (isotônica, produção)** | **0.7762** | **0.0668** |

**IC bootstrap (n=1000 reamostragens, sobre n=61,503 casos de teste):**
- AUC: 0.7762 (IC95% 0.7698–0.7826)
- Brier: 0.0668 (IC95% 0.0654–0.0684)

## Comparação com o baseline do Gate 1 (só `application_train`, sem features relacionais)

| | Baseline Gate 1 (natural) | Camada 1 final (com features relacionais) |
|---|---|---|
| AUC | 0.7589 | 0.7762 |
| Brier | 0.0678 | 0.0668 |

**Ganho de AUC com as features relacionais: +0.0173.** 
Ganho relevante — o histórico de bureau/pagamentos agrega sinal real além do formulário de aplicação.

> ⚠️ Amostras de teste diferentes entre os dois splits (Gate 1 não usava as colunas novas) — comparação é indicativa de ordem de grandeza, não um teste pareado formal.

## Reliability diagram (10 bins por quantil, modelo calibrado)

| p̂ médio (bin) | taxa real observada | gap |
|---|---|---|
| 1.1% | 1.2% | -0.0% |
| 2.2% | 2.1% | +0.1% |
| 2.7% | 2.8% | -0.1% |
| 3.8% | 3.8% | -0.0% |
| 4.6% | 4.9% | -0.3% |
| 5.9% | 5.5% | +0.4% |
| 7.5% | 7.5% | +0.0% |
| 10.7% | 10.7% | +0.1% |
| 16.1% | 16.0% | +0.1% |
| 28.5% | 29.6% | -1.1% |

## Artefatos salvos

- `models/camada1_home_credit_v1.pkl` — modelo calibrado (produção)
- `models/camada1_home_credit_v1_colunas.pkl` — lista de colunas e categóricas esperadas (contrato de paridade treino-serving)

## O que este treino NÃO resolve (débitos que seguem abertos)

- Sem tuning de hiperparâmetros (valores padrão razoáveis, não otimizados)
- Sem seleção de features (todas as 152 features de entrada mantidas, sem remover redundância/colinearidade)
- Sem validação cruzada (só um split treino/calibração/teste)
- Calibração isotônica pode overfit em amostras pequenas por bin — vale revisitar com Platt scaling como alternativa mais suave