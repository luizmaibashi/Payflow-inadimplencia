# Gate 1 — Calibração da Camada 1 (baseline diagnóstico)

**Gerado por:** `scripts/camada1_baseline_e_gate1_calibracao.py`  
**Fonte:** `application_train.csv` (307,511 linhas, TARGET=1 em 8.07%)
**Split:** treino 184,506 / calibração 61,502 / teste 61,503 (estratificado, distribuição real preservada em calibração e teste)

## Resultado — mesmo conjunto de teste (distribuição real) para as 3 variantes

| Variante | n treino | AUC | Brier | p̂ médio | Taxa real (teste) | Gap (p̂ − real) |
|---|---|---|---|---|---|---|
| Natural (sem reamostragem) | 184,506 | 0.7589 | 0.0678 | 8.03% | 8.07% | -0.04% |
| Undersample (nao calibrado) | 29,790 | 0.7537 | 0.2018 | 42.41% | 8.07% | +34.33% |
| Undersample + isotonica | 29,790 | 0.7531 | 0.0683 | 8.00% | 8.07% | -0.08% |

## Reliability diagram por variante (10 bins por quantil de p̂)

### Natural (sem reamostragem)

| p̂ médio (bin) | taxa real observada | gap |
|---|---|---|
| 1.7% | 1.3% | +0.5% |
| 2.4% | 1.8% | +0.6% |
| 3.1% | 2.8% | +0.3% |
| 3.8% | 3.5% | +0.4% |
| 4.8% | 4.8% | -0.1% |
| 5.9% | 7.0% | -1.1% |
| 7.6% | 7.2% | +0.3% |
| 10.0% | 9.9% | +0.1% |
| 14.3% | 15.0% | -0.6% |
| 26.6% | 27.4% | -0.8% |

### Undersample (nao calibrado)

| p̂ médio (bin) | taxa real observada | gap |
|---|---|---|
| 15.9% | 1.3% | +14.5% |
| 21.6% | 2.1% | +19.5% |
| 26.4% | 2.6% | +23.8% |
| 31.4% | 3.8% | +27.6% |
| 36.6% | 4.8% | +31.8% |
| 42.4% | 6.6% | +35.9% |
| 49.2% | 7.8% | +41.3% |
| 56.9% | 10.0% | +46.9% |
| 66.0% | 15.2% | +50.9% |
| 77.7% | 26.6% | +51.1% |

### Undersample + isotonica

| p̂ médio (bin) | taxa real observada | gap |
|---|---|---|
| 1.3% | 1.4% | -0.1% |
| 2.3% | 2.2% | +0.0% |
| 3.0% | 2.7% | +0.3% |
| 3.7% | 4.0% | -0.3% |
| 5.1% | 4.8% | +0.3% |
| 6.3% | 6.7% | -0.5% |
| 8.1% | 7.9% | +0.2% |
| 11.3% | 10.5% | +0.8% |
| 14.7% | 15.3% | -0.6% |
| 26.8% | 27.6% | -0.8% |

## Veredito do Gate 1

**AUC praticamente igual entre as 3 variantes** (0.7589 / 0.7537 / 0.7531) — confirma o que a sabatina previu: o undersampling não piora o ranqueamento.

**Brier muito pior na variante undersample não calibrada** (0.0678 natural vs. 0.2018 undersample) — a probabilidade absoluta piora mesmo com AUC igual.

**`p̂` médio inflado em +34.3% na variante undersample** contra a taxa real de teste — é exatamente o deslocamento de prior que a P2 da sabatina descreveu, agora medido com dado real, não hipotético.

**Recalibração isotônica corrige**: Brier volta a 0.0683 (próximo do natural), sem alterar o AUC — a isotônica remapeia a escala de `p̂`, não a ordem dos casos.

**Conclusão para o motor de EV (ADR-0002 §2.5):** usar `p̂` de um modelo treinado com reamostragem, sem recalibrar, produziria um `p*` sistematicamente errado na direção do gap medido acima. Este gate fica **satisfeito** quando o pipeline de produção incluir a etapa de recalibração — o que ainda **não está implementado**, só demonstrado aqui em escala de baseline diagnóstico.

> ⚠️ Este NÃO é a Camada 1 final. É um baseline com features cruas de `application_train.csv`, sem as tabelas relacionais (bureau, previous_application etc. — ADR-0001) e sem tuning. Serve só para fechar o Gate 1 com evidência empírica, não para produção.