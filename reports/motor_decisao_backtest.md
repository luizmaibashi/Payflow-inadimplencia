# Backtest do motor de decisão — EV × threshold legado

**Gerado por:** `scripts/motor_decisao_backtest.py`  
**Modelo:** `models/camada1_home_credit_v1.pkl` (mesmo `p̂` nas duas estratégias — isola o efeito do motor, não do modelo)
**Teste:** n=61,503 (mesmo split de `camada1_treino.py`)

## Limitações declaradas (leia antes dos números)

- **Margem** = `AMT_ANNUITY/AMT_CREDIT` — proxy de intensidade de margem, **não** a margem total sobre a vida do contrato validada no Gate 0 (essa exige `CNT_PAYMENT`, indisponível para a aplicação corrente — o prazo é decidido junto com a aprovação). **Sabidamente enviesado: confunde prazo com margem** (débito #12). Uma tentativa de corrigir isso via prazo médio histórico do cliente foi testada e **revertida** — ver seção final.
- **LGD** por `NAME_CONTRACT_TYPE` (`Cash loans`→70%, `Revolving loans`→85%) — único proxy disponível *neste* dataset; diferente do proxy `Consumer/Cash` usado no Gate 0 (que veio de `previous_application`, com categorias diferentes).
- **Valor realizado ao pagar** usa a mesma margem como fração do crédito — aproximação do lucro, não o lucro contábil real (dependeria de custo de funding, indisponível).
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

## Tentativa de corrigir o proxy de margem — testada e revertida (2026-08-04)

Ao revisar o débito #12 (o proxy `AMT_ANNUITY/AMT_CREDIT` confunde prazo com margem), tentamos reconstruir a fórmula do Gate 0 usando `previous_cnt_payment_mean` — o **prazo médio real dos contratos anteriores do próprio cliente**, já agregado na Camada 1, com 94,5% de cobertura. Parecia a correção certa pelo princípio do ADR-0006 (substituir premissa por medição onde há dado).

**Falhou, e o motivo é instrutivo:** a fórmula passou a produzir **margem negativa em 77% dos casos** — economicamente absurdo (implicaria emprestar esperando receber menos que o principal). Diagnóstico: o crédito **atual** precisa de ~20 meses (mediana) só para amortizar o principal, mas o histórico do cliente tem prazo mediano de **12 meses**. São **populações de contrato diferentes** — os anteriores são empréstimos pequenos de varejo/consumo; o atual é substancialmente maior. Um não estima o outro.

**Lição registrada:** "existe dado disponível" não é o mesmo que "existe dado aplicável". O prazo histórico é uma medição real, mas de um objeto diferente do que se quer medir — usá-lo teria trocado um viés conhecido e documentado por um erro maior e silencioso (a razão anuidade/crédito ao menos é sempre positiva e monotônica na intensidade de pagamento). O proxy original foi mantido, com seu viés declarado. A função `margem_via_prazo_historico_cliente()` segue em `app/motor_decisao.py` com testes, documentada como **não usada em produção** — serve de registro do experimento negativo.

**Comparação mais justa, não feita aqui:** um corte único **recalibrado** para esta mesma distribuição de `p̂` (ex: otimizado no conjunto de calibração, não no de teste, para evitar viés de otimismo) isolaria o efeito do **desenho do motor** (por observação vs. corte global) do efeito da **calibração desatualizada do baseline**. Sem esse terceiro braço, este backtest prova que 'threshold fixo quebra quando o modelo muda de escala' — uma lição real e valiosa — mas não prova que 'decidir por observação bate um corte global bem calibrado'. Débito registrado no AGENTS.md.