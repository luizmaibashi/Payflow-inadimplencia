# Gate 0 — Dispersão de m/ℓ na carteira Home Credit

**Gerado por:** `scripts/gate0_dispersao_m_sobre_l.py`  
**Fonte:** `previous_application.csv`, contratos `Approved`, não-revolving

## Amostra

- Contratos aprovados não-revolving com prazo/parcela válidos: **939,002**
- Descartados por `m_i` implausível (≤0 ou >300%): **1** (0.0%)
- Amostra final: **939,001**

## Distribuição de `m_i` (margem total do contrato / principal)

| Estatística | Valor |
|---|---|
| Mínimo | 1.7% |
| P5 | 8.1% |
| P25 | 13.9% |
| Mediana | 23.4% |
| Média | 31.1% |
| P75 | 40.0% |
| P95 | 84.1% |
| Máximo | 202.8% |
| Desvio padrão | 24.3% |

## Distribuição de `p*_i` (limiar de indiferença por contrato)

| Estatística | Valor |
|---|---|
| Mínimo | 2.4% |
| P5 | 10.4% |
| P25 | 16.2% |
| Mediana | 24.7% |
| Média | 26.3% |
| P75 | 34.2% |
| P95 | 50.1% |
| Máximo | 70.5% |
| Desvio padrão | 12.2% |

**Amplitude interquartil (P25-P75) de `p*`: 18.0%**
**Amplitude P5-P95 de `p*`: 39.7%**

## Histograma de `p*_i` (texto, 10 faixas)

```
0%-10%:  40,946 ########
10%-20%: 277,767 ########################################################
20%-30%: 295,966 ############################################################
30%-40%: 202,466 #########################################
40%-50%:  74,181 ###############
50%-60%:  38,979 #######
60%-70%:   8,687 #
70%-80%:       9 
80%-90%:       0 
90%-100%:       0 
```

## Checagem cruzada: `m_i` medido × `NAME_YIELD_GROUP` declarado

| NAME_YIELD_GROUP | n | m_i mediana | m_i média |
|---|---|---|---|
| low_action | 70,876 | 8.7% | 12.6% |
| low_normal | 246,076 | 14.2% | 24.0% |
| middle | 323,034 | 23.0% | 32.3% |
| high | 299,015 | 34.8% | 40.1% |

## Segmentação por garantia (proxy de ℓ: Consumer loans = garantido)

| Garantido (NAME_CONTRACT_TYPE == Consumer loans) | n | p* mediana | p* média |
|---|---|---|---|
| False | 312,536 | 32.7% | 33.8% |
| True | 626,465 | 22.6% | 22.6% |

## Veredito do Gate 0

**Critério:** IQR de `p*` menor que 3% (mesma ordem de grandeza do efeito isolado da LGD, ADR-0002 §2.4) indica que a dispersão não compensa a complexidade do motor por observação.

**Resultado: APROVADO — dispersão relevante, corte por observação pode agregar valor sobre corte global**

IQR observado: **18.0%**. Amplitude P5-P95: **39.7%**.

> ⚠️ Nota de honestidade: este Gate mede dispersão de `m/ℓ`, não a fração de clientes cujo `p̂` cai dentro da faixa de variação de `p*` — essa é a métrica final e mais afiada (ver `wiki/concepts/04_business/Valor_Esperado_Decisao_Credito.md`, Teste de Domínio P3), e só é calculável depois que a Camada 1 estiver treinada e calibrada.