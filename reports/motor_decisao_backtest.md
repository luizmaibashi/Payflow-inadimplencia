# Backtest do motor de decisão — EV × threshold legado

**Gerado por:** `scripts/motor_decisao_backtest.py`  
**Modelo:** `models/camada1_home_credit_v1.pkl` (mesmo `p̂` nas duas estratégias — isola o efeito do motor, não do modelo)
**Teste:** n=61,503 (mesmo split de `camada1_treino.py`)

## Limitações declaradas (leia antes dos números)

- **Margem = premissa global declarada de 41.4%** — mediana **medida** com a fórmula verdadeira do Gate 0 (`(anuidade×prazo − crédito)/crédito`) sobre `Cash loans` aprovados em `previous_application` (n=312.536), categoria que casa com ~90% de `application_train`. Aplicada como constante porque o prazo do contrato atual **não existe** no momento da decisão (é definido junto com a aprovação) — problema estrutural, exposto como disclaimer em vez de medição fingida (ADR-0006).
- **LGD** por `NAME_CONTRACT_TYPE` (`Cash loans`→70%, `Revolving loans`→85%) — premissa declarada; é a única fonte de variação de `p*` **por observação** que restou.
- **Valor realizado ao pagar** usa a mesma margem como fração do crédito — aproximação do lucro, não o lucro contábil real (dependeria de custo de funding, indisponível).
- **Banda de indiferença derivada** da incerteza da premissa (margem P25=26.2% a P75=65.1%), não mais ±3pp arbitrários — implementa o ADR-0002 §2.6: a zona cinzenta é a região onde a decisão **inverte** conforme a premissa de margem adotada.
- **Valores em u.m. (unidades monetárias do dataset)**, não em reais — Home Credit é de mercados emergentes, moeda não identificada.

## Distribuição de decisões (teste completo, n=61,503)

| Estratégia | APROVAR | ZONA_CINZENTA / REVISAR | NEGAR |
|---|---|---|---|
| Motor (EV) | 58,397 (94.9%) | 2,780 (4.5%) | 326 (0.5%) |
| Baseline (thresholds legados) | 60,883 (99.0%) | 604 (1.0%) | 16 (0.0%) |

## Backtest sobre a carteira inteira (n=61,503)

> **Correção metodológica (2026-08-04):** a 1ª versão comparava só os casos que **ambas** as estratégias decidem automaticamente. Parecia pareamento correto, mas as bandas são **aninhadas** (a do motor cai dentro da do baseline), então esse filtro removia **exatamente os casos em que as duas discordam** — o delta dava zero por construção, não por medição.

O desfecho dos casos deferidos a humano **não é observável** neste dataset, então o resultado vai em dois cenários-limite em vez de assumir um:

| Zona cinzenta tratada como | Motor (u.m./caso) | Baseline (u.m./caso) | Delta | IC95% bootstrap |
|---|---|---|---|---|
| NEGAR | 197,394 | 198,473 | **-1,075** | [-1,548; -616] |
| APROVAR | 198,344 | 198,019 | **323** | [150; 491] |

### Onde as estratégias de fato discordam

- Casos com decisão diferente: **3,090** de 61,503 (**5.0%**)
- Taxa real de default nesses casos: **35.3%** (contra 8.1% na carteira toda)

É nesta fatia que a escolha de estratégia importa — e é exatamente ela que alimentaria a Camada 2 (agente): casos que o motor manda deferir e o baseline aprovaria direto.

**Veredito:** No cenário conservador (zona cinzenta negada), o motor fica **abaixo** do baseline com significância. Faz sentido: deferir tem custo — cada caso deferido e negado abre mão da margem de um cliente que, na base, provavelmente pagaria. O ganho do deferral só aparece se o humano (ou o agente) decidir melhor que a regra automática — que é justamente o que a Camada 2 precisa provar.

## Por que as duas estratégias se parecem tanto agora

Com a margem **medida** (41.4% para Cash loans), o ponto de indiferença fica em `p*` ≈ 37% — muito acima da taxa real de default (8.1%). Ou seja: **com a precificação real da Home Credit, vale emprestar para quase todo mundo**, e o trabalho do modelo é achar a cauda pequena onde não vale. O threshold legado de 0,40 estava, por acaso, **próximo do ponto economicamente correto** — só 1.0% dos casos o ultrapassam.

**Isto revisa a conclusão da 1ª versão deste relatório.** Lá o motor aparecia ~21 mil u.m./caso à frente do baseline, mas aquele número vinha de um proxy de margem defeituoso — correlação de Spearman **negativa (−0,40)** com a margem real (ADR-0002 §2.8) — que tornava o motor artificialmente conservador. Corrigida a margem, a vantagem desaparece. **O que permanece válido** do achado anterior é que um threshold numérico fixo é frágil a mudanças de calibração do modelo: `p* = m/(m+ℓ)` se recalcula a partir de premissas de negócio, um número decorado não.

## Tentativa de corrigir o proxy de margem — testada e revertida (2026-08-04)

Ao revisar o débito #12 (o proxy `AMT_ANNUITY/AMT_CREDIT` confunde prazo com margem), tentamos reconstruir a fórmula do Gate 0 usando `previous_cnt_payment_mean` — o **prazo médio real dos contratos anteriores do próprio cliente**, já agregado na Camada 1, com 94,5% de cobertura. Parecia a correção certa pelo princípio do ADR-0006 (substituir premissa por medição onde há dado).

**Falhou, e o motivo é instrutivo:** a fórmula passou a produzir **margem negativa em 77% dos casos** — economicamente absurdo (implicaria emprestar esperando receber menos que o principal). Diagnóstico: o crédito **atual** precisa de ~20 meses (mediana) só para amortizar o principal, mas o histórico do cliente tem prazo mediano de **12 meses**. São **populações de contrato diferentes** — os anteriores são empréstimos pequenos de varejo/consumo; o atual é substancialmente maior. Um não estima o outro.

**Lição registrada:** "existe dado disponível" não é o mesmo que "existe dado aplicável". O prazo histórico é uma medição real, mas de um objeto diferente do que se quer medir — usá-lo teria trocado um viés conhecido e documentado por um erro maior e silencioso (a razão anuidade/crédito ao menos é sempre positiva e monotônica na intensidade de pagamento). O proxy original foi mantido, com seu viés declarado. A função `margem_via_prazo_historico_cliente()` segue em `app/motor_decisao.py` com testes, documentada como **não usada em produção** — serve de registro do experimento negativo.

**Comparação mais justa, não feita aqui:** um corte único **recalibrado** para esta mesma distribuição de `p̂` (ex: otimizado no conjunto de calibração, não no de teste, para evitar viés de otimismo) isolaria o efeito do **desenho do motor** (por observação vs. corte global) do efeito da **calibração desatualizada do baseline**. Sem esse terceiro braço, este backtest prova que 'threshold fixo quebra quando o modelo muda de escala' — uma lição real e valiosa — mas não prova que 'decidir por observação bate um corte global bem calibrado'. Débito registrado no AGENTS.md.