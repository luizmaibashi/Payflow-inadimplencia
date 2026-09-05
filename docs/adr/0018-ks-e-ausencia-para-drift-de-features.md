# ADR-0018: KS e ausência para drift de features

**Data:** 2026-09-04
**Status:** Accepted
**Contexto:** PayFlow V3, diagnóstico de mudança populacional por coorte

## Contexto

AUC e Brier informam se o modelo continua acertando depois que o target
amadurece. Eles não mostram se a população mudou antes disso. Também não
distinguem uma alteração nos valores de uma quebra na coleta que aumentou os
ausentes.

## Decisão

Usar dois sinais por feature e por coorte:

1. estatística de Kolmogorov-Smirnov sobre valores numéricos não ausentes;
2. diferença absoluta da taxa de ausência entre treino e coorte.

A política inicial do case usa KS 0,10/0,20 e diferença de ausência
0,05/0,10 para `ALERTA`/`CRITICO`. Esses valores são configuráveis e não
representam apetite de risco institucional. O p-valor do KS não será usado:
com centenas de milhares de registros, mudanças irrelevantes podem se tornar
estatisticamente significativas.

## Consequências

### Positivas

- detecta mudança antes de o target amadurecer;
- separa mudança dos valores de perda de cobertura;
- produz sinal barato, determinístico e explicável.

### Negativas

- avalia cada feature isoladamente e pode perder drift multivariado;
- KS não explica causa, sazonalidade ou impacto financeiro;
- limites genéricos podem gerar falso alarme.

## Alternativas descartadas

| Alternativa | Motivo |
|---|---|
| PSI | Exige bins e suavização, criando mais escolhas arbitrárias nesta etapa. |
| Apenas p-valor do KS | Com `n` grande, significância não equivale a relevância. |
| Great Expectations | Adiciona framework antes de existir necessidade operacional de orquestração. |
| Drift multivariado | Maior complexidade e menor explicabilidade para o primeiro artefato. |

## Impacto e validação

Sem este diagnóstico, uma queda de AUC abre investigação manual sem indicar
onde procurar. Com ele, `avaliar_drift_features` mostra quais entradas mudaram
e se a mudança veio de valores ou ausência. O ganho é tempo de diagnóstico e
redução do risco de retreinar sem entender a causa; não será inventado valor
monetário sem carteira real.

Critérios: testes sintéticos para estabilidade, alertas, criticidade, dados
inválidos e evidência insuficiente; depois execução nas três coortes reais.

## Resultado da primeira execução

No proxy de seis features, 2019-Q4 teve 1 feature crítica; 2020-H1 teve 1 em
alerta; 2020-H2 teve 3 em alerta e nenhuma crítica. Em paralelo, a AUC do
modelo permaneceu entre 0,6089 e 0,6194 nas três coortes. A leitura correta é
que há mudança populacional mensurável sem evidência, neste recorte, de queda
de discriminação. Não se conclui causalidade nem liberação operacional.

## Referências

- `docs/spec/0008-drift-de-features-por-coorte.md`
- `wiki/concepts/01_data_and_mlops/Data_Drift_Monitoring.md`
- ADR-0014 e ADR-0017
