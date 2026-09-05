# Experimento reproduzível — proxy temporal

**Uso:** pesquisa. As seis variáveis não têm prova point-in-time.
**Dados:** n=1,526,659; treino=733,757.
**Maturação declarada:** 90 dias; data de referência=2021-01-04.

| Coorte | n | Inadimplentes | Taxa (IC95%) | AUC (IC95%) | Brier | Decisão |
|---|---:|---:|---:|---:|---:|---|
| 2019-Q4 | 337,005 | 12147 | 3.60% [3.54%; 3.67%] | 0.6148 [0.6105; 0.6200] | 0.0346 | PESQUISA |
| 2020-H1 | 305,657 | 11771 | 3.85% [3.78%; 3.92%] | 0.6089 [0.6044; 0.6139] | 0.0368 | PESQUISA |
| 2020-H2 | 150,240 | 3175 | 2.11% [2.04%; 2.19%] | 0.6194 [0.6105; 0.6299] | 0.0206 | PESQUISA |

> A janela de maturação é uma hipótese explícita de demonstração. A competição não publica horizonte suficiente para tratá-la como política real.

## Drift das features contra o treino

| Coorte | Estáveis | Alertas | Críticas | Insuficientes | Destaque | KS | Delta ausência |
|---|---:|---:|---:|---:|---|---:|---:|
| 2019-Q4 | 5 | 0 | 1 | 0 | inittransactionamount_650A | 0.2318 | 5.64% |
| 2020-H1 | 5 | 1 | 0 | 0 | inittransactionamount_650A | 0.1905 | 2.35% |
| 2020-H2 | 3 | 3 | 0 | 0 | inittransactionamount_650A | 0.1529 | 2.08% |

> KS e ausência sinalizam mudança, mas não provam a causa nem autorizam retreino automático.

## Calibração por faixa de score

| Coorte | Faixa | Intervalo | n | Inadimplentes | Previsto | Observado (IC95%) | Gap | Estado |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 2019-Q4 | 1 | [0.00%; 1.92%] | 51,594 | 877 | 1.46% | 1.70% [1.59%; 1.81%] | +0.24% | APROXIMADA |
| 2019-Q4 | 2 | (1.92%; 2.18%] | 34,232 | 755 | 2.07% | 2.21% [2.06%; 2.37%] | +0.14% | APROXIMADA |
| 2019-Q4 | 3 | (2.18%; 2.38%] | 30,815 | 803 | 2.28% | 2.61% [2.43%; 2.79%] | +0.33% | APROXIMADA |
| 2019-Q4 | 4 | (2.38%; 2.55%] | 32,090 | 1,015 | 2.47% | 3.16% [2.98%; 3.36%] | +0.69% | APROXIMADA |
| 2019-Q4 | 5 | (2.55%; 2.70%] | 29,688 | 1,097 | 2.63% | 3.70% [3.49%; 3.92%] | +1.07% | SUBESTIMA_RISCO |
| 2019-Q4 | 6 | (2.70%; 2.85%] | 29,476 | 1,126 | 2.77% | 3.82% [3.61%; 4.04%] | +1.05% | SUBESTIMA_RISCO |
| 2019-Q4 | 7 | (2.85%; 3.05%] | 30,684 | 1,293 | 2.95% | 4.21% [3.99%; 4.44%] | +1.26% | SUBESTIMA_RISCO |
| 2019-Q4 | 8 | (3.05%; 3.25%] | 29,900 | 1,372 | 3.15% | 4.59% [4.36%; 4.83%] | +1.44% | SUBESTIMA_RISCO |
| 2019-Q4 | 9 | (3.25%; 3.76%] | 32,224 | 1,499 | 3.47% | 4.65% [4.43%; 4.89%] | +1.18% | SUBESTIMA_RISCO |
| 2019-Q4 | 10 | (3.76%; 100.00%] | 36,302 | 2,310 | 5.32% | 6.36% [6.12%; 6.62%] | +1.04% | SUBESTIMA_RISCO |
| 2020-H1 | 1 | [0.00%; 1.92%] | 33,521 | 654 | 1.49% | 1.95% [1.81%; 2.10%] | +0.46% | APROXIMADA |
| 2020-H1 | 2 | (1.92%; 2.18%] | 27,888 | 734 | 2.07% | 2.63% [2.45%; 2.83%] | +0.57% | APROXIMADA |
| 2020-H1 | 3 | (2.18%; 2.38%] | 28,531 | 807 | 2.28% | 2.83% [2.64%; 3.03%] | +0.55% | APROXIMADA |
| 2020-H1 | 4 | (2.38%; 2.55%] | 31,954 | 1,011 | 2.47% | 3.16% [2.98%; 3.36%] | +0.69% | APROXIMADA |
| 2020-H1 | 5 | (2.55%; 2.70%] | 31,332 | 1,134 | 2.63% | 3.62% [3.42%; 3.83%] | +0.99% | APROXIMADA |
| 2020-H1 | 6 | (2.70%; 2.85%] | 32,186 | 1,249 | 2.77% | 3.88% [3.68%; 4.10%] | +1.11% | SUBESTIMA_RISCO |
| 2020-H1 | 7 | (2.85%; 3.05%] | 30,474 | 1,142 | 2.95% | 3.75% [3.54%; 3.97%] | +0.79% | APROXIMADA |
| 2020-H1 | 8 | (3.05%; 3.25%] | 30,319 | 1,180 | 3.15% | 3.89% [3.68%; 4.12%] | +0.74% | APROXIMADA |
| 2020-H1 | 9 | (3.25%; 3.76%] | 28,697 | 1,344 | 3.47% | 4.68% [4.44%; 4.93%] | +1.21% | SUBESTIMA_RISCO |
| 2020-H1 | 10 | (3.76%; 100.00%] | 30,755 | 2,516 | 5.34% | 8.18% [7.88%; 8.49%] | +2.85% | SUBESTIMA_RISCO |
| 2020-H2 | 1 | [0.00%; 1.92%] | 16,166 | 188 | 1.54% | 1.16% [1.01%; 1.34%] | -0.37% | APROXIMADA |
| 2020-H2 | 2 | (1.92%; 2.18%] | 14,826 | 220 | 2.07% | 1.48% [1.30%; 1.69%] | -0.58% | APROXIMADA |
| 2020-H2 | 3 | (2.18%; 2.38%] | 15,094 | 225 | 2.28% | 1.49% [1.31%; 1.70%] | -0.79% | APROXIMADA |
| 2020-H2 | 4 | (2.38%; 2.55%] | 17,107 | 281 | 2.47% | 1.64% [1.46%; 1.84%] | -0.83% | APROXIMADA |
| 2020-H2 | 5 | (2.55%; 2.70%] | 16,341 | 303 | 2.63% | 1.85% [1.66%; 2.07%] | -0.78% | APROXIMADA |
| 2020-H2 | 6 | (2.70%; 2.85%] | 16,282 | 284 | 2.76% | 1.74% [1.55%; 1.96%] | -1.02% | SUPERESTIMA_RISCO |
| 2020-H2 | 7 | (2.85%; 3.05%] | 14,424 | 284 | 2.95% | 1.97% [1.75%; 2.21%] | -0.98% | APROXIMADA |
| 2020-H2 | 8 | (3.05%; 3.25%] | 13,690 | 312 | 3.15% | 2.28% [2.04%; 2.54%] | -0.87% | APROXIMADA |
| 2020-H2 | 9 | (3.25%; 3.76%] | 13,069 | 370 | 3.47% | 2.83% [2.56%; 3.13%] | -0.64% | APROXIMADA |
| 2020-H2 | 10 | (3.76%; 100.00%] | 13,241 | 708 | 5.25% | 5.35% [4.98%; 5.74%] | +0.10% | APROXIMADA |

> `SUBESTIMA_RISCO`: o modelo estima menos inadimplência do que ocorreu; aprovação, provisão ou preço podem ficar otimistas.
> `SUPERESTIMA_RISCO`: o modelo estima mais inadimplência do que ocorreu; o negócio pode recusar bons clientes ou reservar capital demais.
> O diagnóstico localiza o problema; não autoriza recalibração automática.