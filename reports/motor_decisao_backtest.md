# Backtest do motor de decisão — EV × threshold legado

**Gerado por:** `scripts/motor_decisao_backtest.py`  
**Modelo:** `models/camada1_home_credit_v1.pkl` (mesmo `p̂` nas duas estratégias — isola o efeito do motor, não do modelo)
**Teste:** n=61,503 (mesmo split de `camada1_treino.py`)

## Limitações declaradas (leia antes dos números)

- **Margem** = `AMT_ANNUITY/AMT_CREDIT` — proxy de intensidade de margem, **não** a margem total sobre a vida do contrato validada no Gate 0 (essa exige `CNT_PAYMENT`, indisponível para a aplicação corrente — o prazo é decidido junto com a aprovação, não é dado de entrada).
- **LGD** por `NAME_CONTRACT_TYPE` (`Cash loans`→70%, `Revolving loans`→85%) — único proxy disponível *neste* dataset; diferente do proxy `Consumer/Cash` usado no Gate 0 (que veio de `previous_application`, com categorias diferentes).
- **Valor realizado ao pagar** usa a mesma margem proxy como fração do crédito — aproximação do lucro, não o lucro contábil real (dependeria de prazo/custo de funding, indisponíveis).
- **Banda de indiferença fixa** (±3pp em torno de `p*`) — simplificação; não deriva da incerteza real da estimativa de PD (débito conhecido).

## Distribuição de decisões (teste completo, n=61,503)

| Estratégia | APROVAR | ZONA_CINZENTA / REVISAR | NEGAR |
|---|---|---|---|
| Motor (EV) | 20,790 (33.8%) | 23,806 (38.7%) | 16,907 (27.5%) |
| Baseline (thresholds legados) | 60,883 (99.0%) | 604 (1.0%) | 16 (0.0%) |

## Backtest pareado (n=37,093 — casos decididos automaticamente por AMBAS as estratégias)

- Valor médio realizado por caso — **Motor (EV):** R$ 11,145.29
- Valor médio realizado por caso — **Baseline (thresholds legados):** R$ -10,239.00

**Delta médio (Motor − Baseline): R$ 21,334.85 por caso, IC95% bootstrap [R$ 20,045.93; R$ 22,587.80] (n_bootstrap=1000)**

**Veredito:** O motor de EV supera o baseline com significância — o intervalo não cruza zero.

## ⚠️ Por que o delta é tão grande — investigar antes de comemorar

Com `p̂` real calibrado (média 8.0%, batendo com a taxa real de default), só **1.0%** dos casos ultrapassam 0,40 e **0.03%** ultrapassam 0,65 — por isso o baseline aprova 99% da carteira quase sem negar ou revisar nada.

**Isto não é 'o motor de EV venceu o threshold fixo' de forma limpa.** É evidência de que **os thresholds 0.40/0.65 foram calibrados contra a escala de `p̂` de um modelo diferente (provavelmente não calibrado/inflado — o mesmo mecanismo do Gate 1)**. Contra um `p̂` real e calibrado, um número fixo herdado de outra escala de probabilidade simplesmente para de fazer sentido — não é que o motor por EV seja necessariamente superior a qualquer corte único, é que **um corte numérico fixo é frágil a mudanças na calibração do modelo por trás dele**, e a fórmula `p* = m/(m+ℓ)` não é (ela se recalcula a partir de premissas de negócio, não de um número decorado).

**Comparação mais justa, não feita aqui:** um corte único **recalibrado** para esta mesma distribuição de `p̂` (ex: otimizado no conjunto de calibração, não no de teste, para evitar viés de otimismo) isolaria o efeito do **desenho do motor** (por observação vs. corte global) do efeito da **calibração desatualizada do baseline**. Sem esse terceiro braço, este backtest prova que 'threshold fixo quebra quando o modelo muda de escala' — uma lição real e valiosa — mas não prova que 'decidir por observação bate um corte global bem calibrado'. Débito registrado no AGENTS.md.