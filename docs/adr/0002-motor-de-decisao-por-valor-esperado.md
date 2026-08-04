# ADR-0002: Motor de decisão por valor esperado por observação

**Data**: 2026-08-04
**Status**: Accepted
**Contexto**: PayFlow — decisão D2 da `SPEC_FINAL.md`, ticket Wayfinder [0002](../wayfinder/refatoracao-camada-agentica/0002-origem-dos-thresholds.md). Substitui os buckets fixos de `app/utils.py::get_decision_thresholds`

> Este é o ADR mais sensível do projeto: os números aqui definem quanto capital fica exposto e quantos casos vão para revisão humana.

---

## 1. CONTEXTO (O QUÊ?)

`RISCO_BAIXO_MAX=0.40` e `RISCO_MEDIO_MAX=0.65` estavam hardcoded/configuráveis por env var, **sem nenhuma derivação**. O README já narrava a assimetria correta desde o início —

> "Falso Negativo = prejuízo total. Falso Positivo = custo de oportunidade."

— mas essa assimetria nunca virou cálculo. Um corte no meio da distribuição embute a premissa de que errar para os dois lados custa o mesmo. Não custa: aprovar um mau pagador queima capital; recusar um bom pagador queima margem.

## 2. DECISÃO (POR QUÊ?)

**Decisão por valor esperado, com limiar de indiferença calculado por observação.**

### 2.1 A conta

Com `p` = PD, `M` = margem esperada do contrato, `L = LGD × EAD`:

```
EV(aprovar) = (1 − p)·M − p·L
EV(negar)   = 0                    (baseline declarado)
```

Aprova quando `EV(aprovar) > 0`, o que dá o limiar de indiferença:

```
p* = M / (M + LGD × EAD)
```

**`p*` não é hiperparâmetro** — é consequência aritmética de premissas de negócio. E **não depende do modelo**: trocar o classificador não muda o corte, muda só o `p` comparado com ele. Modelo e política são artefatos separados, com cadências de mudança diferentes.

### 2.2 Premissas e suas fontes

| Premissa | Valor | Origem |
|---|---|---|
| **LGD** | 70–85% (recuperação 15–30%) | Literatura empírica de crédito ao consumidor não garantido (ScienceDirect, 2023), contrastada com piso Basel FIRB (45% sênior não garantido). **Não existe LGD pública do BCB para crédito pessoal brasileiro** |
| **EAD** | `AMT_CREDIT` | Simplificação conservadora — ignora amortização (o default raramente ocorre em `t=0`). Declarada, não medida (débito #6) |
| **Margem `M`** | Juros implícitos do contrato: `AMT_ANNUITY × CNT_PAYMENT − AMT_CREDIT`, líquidos de custo de funding | Derivada do próprio contrato, **não arbitrada** — ver §2.4 |

### 2.3 A pegadinha: `p*` é invariante ao EAD

Se `M` e `L` são ambos proporcionais ao principal, o EAD **se cancela**:

```
p* = (m·EAD) / (m·EAD + ℓ·EAD) = m / (m + ℓ)
```

Exemplo: R$ 20.000 com LGD 75% e margem 18% → `p* = 3.600/18.600 = 19,4%`. R$ 2.000 nas mesmas condições → `p* = 360/1.860 = 19,4%`. **Idêntico.**

> **Consequência não-negociável:** "corte por observação" só se paga quando a razão `m/ℓ` **varia entre contratos**. Se a carteira tiver taxa e LGD homogêneas, este motor reproduz exatamente um corte global — complexidade sem retorno.

O que faz `m/ℓ` variar de fato no Home Credit:

| Fonte | Como aparece |
|---|---|
| Taxa/prazo por contrato | `AMT_ANNUITY × CNT_PAYMENT / AMT_CREDIT` — driver principal |
| Colateral | `AMT_GOODS_PRICE` sinaliza compra vinculada → LGD menor |
| Custo fixo de originação/cobrança | Não escala com EAD → derruba o `p*` do ticket pequeno |
| Cenário macro | Desloca `ℓ` dentro de 70–85% (ADR-0008) |

### 2.4 Sensibilidade — onde o rigor tem que ser gasto

Derivando em `m = 0,18`, `ℓ = 0,75`:

```
∂p*/∂m = ℓ/(m+ℓ)² ≈ +0,87        ∂p*/∂ℓ = −m/(m+ℓ)² ≈ −0,21
```

| Premissa | Faixa | `p*` | Amplitude |
|---|---|---|---|
| LGD (`ℓ`) | 70% – 85% | 20,5% – 17,5% | 3,0 p.p. |
| Margem (`m`) | 18% – 40% | 19,4% – 34,8% | **15,4 p.p.** |

**Um ponto percentual de erro na margem move `p*` ~4× mais que um ponto na LGD.**

> **Correção de rota registrada (2026-08-04):** a spec original ancorou a LGD em literatura (ticket 0007) e deixou a margem **sem fonte nenhuma** — rigor gasto na alavanca menor. Por isso `M` passa a ser **derivada do contrato**, não arbitrada, e o custo de funding usado no líquido precisa estar declarado como premissa própria.

### 2.4.1 Gate 0 executado (2026-08-04) — resultado: dispersão real, motor por observação justificado

Medição em `previous_application.csv` (939.001 contratos aprovados, não-revolving, com prazo/parcela reais), `scripts/gate0_dispersao_m_sobre_l.py`, relatório em `reports/gate0_dispersao_m_sobre_l.md`:

| Métrica de `p*_i` | Valor |
|---|---|
| IQR (P25–P75) | **18,0 p.p.** |
| Amplitude P5–P95 | **39,7 p.p.** |
| Mediana | 24,7% |

**Critério do gate:** IQR < 3 p.p. (mesma ordem do efeito isolado da LGD) reprovaria o motor por observação. IQR real de 18 p.p. é 6× o limiar — **aprovado**.

**Checagem cruzada que valida a derivação de `m_i`:** a margem medida cresce monotonicamente com `NAME_YIELD_GROUP` — a categoria de faixa de juros que a própria Home Credit já declara (`low_action` 8,7% → `low_normal` 14,2% → `middle` 23,0% → `high` 34,8%, medianas). Se a derivação estivesse errada, não haveria por que bater com um rótulo independente do dataset.

**Achado de qualidade de dado durante a execução:** a primeira tentativa usou `AMT_GOODS_PRICE > 0` como proxy de garantia (colateral) e deu 100% "garantido" — porque, após filtrar para contratos `Approved` com `CNT_PAYMENT` válido, o Home Credit preenche `AMT_GOODS_PRICE` mesmo em `Cash loans` (0% nulo nos dois tipos). O proxy correto é `NAME_CONTRACT_TYPE` diretamente (`Consumer loans` = vinculado a bem; `Cash loans` = sem colateral), que produz a segregação esperada: `p*` mediano de 22,6% (garantido) contra 32,7% (não garantido) — 10 p.p. de diferença, coerente com a lógica de negócio.

**Limite do que este gate prova:** mede dispersão de `m/ℓ`, não a fração de clientes cujo `p̂` cai dentro da faixa em que a decisão muda de lado — essa é a métrica final (Teste de Domínio P3 da aula, `wiki/concepts/04_business/Valor_Esperado_Decisao_Credito.md`) e só é calculável após a Camada 1 estar treinada e calibrada (§2.5).

### 2.5 Pré-requisito bloqueante: calibração

Toda a §2.1 assume que `p` é **probabilidade**, não score de ranqueamento.

- **AUC é invariante a transformação monotônica** — um modelo pode ranquear bem e decidir péssimo.
- **Rebalanceamento quebra a calibração.** O pipeline legado usa `imbalanced-learn`; com base rate de ~8% no Home Credit, a tentação de reamostrar é grande. Undersampling **desloca o prior e infla `p̂`** sistematicamente, e o AUC não acusa.
- **O que medir:** reliability diagram + **Brier score**, além do AUC. Corrigir com Platt/isotônica em conjunto separado.

**Sem calibração validada, este motor é aritmética sobre número sem significado.** É gate, não recomendação (débito #3).

**Gate 1 demonstrado empiricamente (2026-08-04)** — `scripts/camada1_baseline_e_gate1_calibracao.py`, baseline diagnóstico sobre `application_train.csv` (307.511 linhas). Três variantes avaliadas no mesmo conjunto de teste (distribuição real, 8,07% de TARGET=1):

| Variante | AUC | Brier | `p̂` médio | Gap vs. taxa real |
|---|---|---|---|---|
| Natural (sem reamostragem) | 0,7589 | 0,0678 | 8,03% | −0,04 p.p. |
| Undersample (não calibrado) | 0,7537 | 0,2018 | 42,41% | **+34,33 p.p.** |
| Undersample + isotônica | 0,7531 | 0,0683 | 8,00% | −0,08 p.p. |

**AUC praticamente idêntico entre as três** confirma exatamente o previsto: undersampling não piora o ranqueamento, então **AUC sozinho nunca detectaria o problema**. O reliability diagram da variante não calibrada mostra gap de até **+51 p.p.** no bin de maior risco — um `p*` comparado contra esse `p̂` aprovaria sistematicamente menos do que deveria (o inverso do medo original de "aprovar demais"; ver correção registrada na aula, `wiki/concepts/04_business/Valor_Esperado_Decisao_Credito.md`). A isotônica recupera o Brier ao nível do modelo natural sem alterar o AUC. Relatório completo em `reports/gate1_calibracao.md`.

> Este é um baseline diagnóstico (features cruas de `application_train.csv`, sem as tabelas relacionais do ADR-0001), não a Camada 1 final — mas fecha o Gate 1 com evidência empírica de que o mecanismo é real e de que a recalibração o corrige.

### 2.6 Zona cinzenta derivada, não arbitrada

`p*` é uma linha, mas as premissas que a geram são incertas. A banda tem duas fontes, ambas quantificáveis:

1. **Incerteza da premissa** — a faixa de LGD 70–85% já produz `p* ∈ [17,5%; 20,5%]`. Uma decisão que **inverte** conforme a premissa não é decisão robusta: é caso para deferir.
2. **Incerteza da estimativa** — o intervalo em torno de `p̂`.

> A zona cinzenta é a região onde o sinal (`|EV|`) é menor que a incerteza somada. Não é largura chutada. É o que alimenta a Camada 2 (ADR-0003) e a fila de deferral.

---

## 2.7 Execução (2026-08-04) — motor implementado e testado, backtest com achado importante

`app/motor_decisao.py` implementa `calcular_p_estrela`, `classificar_decisao` (APROVAR/ZONA_CINZENTA/NEGAR) e os dois proxies necessários, testados em `tests/test_motor_decisao.py` (9 testes, incluindo o caso exato da aula: R$20k e R$2k na mesma taxa/LGD dão o mesmo `p*` de 19,35%).

**Achado que obrigou um desvio da fórmula original:** `application_train.csv` (a aplicação corrente que a Camada 1 pontua) **não tem `CNT_PAYMENT`** — só existe em `previous_application.csv` (contratos já fechados, usados no Gate 0). Na prática, o prazo é uma variável que o Home Credit decide **junto** com a aprovação, não um dado que chega pronto antes da decisão. Solução adotada (decisão explícita, não silenciosa): margem vira `AMT_ANNUITY/AMT_CREDIT` e LGD vira `NAME_CONTRACT_TYPE` (`Cash loans`→70%, `Revolving loans`→85% — categorias diferentes das de `previous_application`).

**Revisão crítica do proxy de margem (2026-08-04, a pedido do Luiz — "acredita que escolhemos a melhor opção?"):** a resposta honesta é não sem ressalva. `AMT_ANNUITY/AMT_CREDIT` não é só "menos preciso" que a métrica do Gate 0 — **confunde prazo com margem**. Dois contratos com a mesma margem real e prazos diferentes têm razões anuidade/crédito bem diferentes (prazo curto infla a razão; prazo longo a reduz), sem diferença real de rentabilidade. E, diferente do Gate 0 (onde `m_i` foi validado contra `NAME_YIELD_GROUP`, um sinal independente do próprio Home Credit), **este proxy nunca foi validado contra nada** — `application_train` não tem um campo equivalente para cruzar. Consequência: a dispersão de `p*` que alimenta o backtest abaixo pode estar parcialmente inflada por variação de **prazo**, não só de margem/LGD genuínas. Isso não invalida o achado de calibração (que não depende do proxy), mas enfraquece qualquer alegação futura de que "decidir por observação" tem valor incremental real — motivo pelo qual o débito #13 agora cobre dois braços de correção, não um (ver AGENTS.md).

**Backtest pareado contra o threshold legado** (`scripts/motor_decisao_backtest.py`, mesmo `p̂` calibrado nas duas estratégias, n=37.093 casos decididos por ambas):

| Estratégia | Valor médio realizado/caso |
|---|---|
| Motor (EV) | R$ 11.145,29 |
| Baseline (thresholds legados 0.40/0.65) | −R$ 10.239,00 |
| **Delta (bootstrap, n=1000)** | **R$ 21.334,85, IC95% [R$ 20.045,93; R$ 22.587,80]** |

**Investigação obrigatória antes de aceitar o número — e o que ela revelou:** com `p̂` real calibrado, só 1% dos casos ultrapassa 0,40 (o baseline aprova 99% da carteira quase sem negar/revisar nada). **Isto não isola "motor de EV bate corte global"** — é evidência de que **thresholds fixos são frágeis a mudança de calibração do modelo por trás deles**: 0.40/0.65 foram tunados contra a escala de `p̂` de um modelo diferente (não calibrado), e contra um `p̂` real e calibrado simplesmente param de fazer sentido. `p* = m/(m+ℓ)` não sofre desse problema porque se recalcula a partir de premissas de negócio, não de um número decorado — mas o backtest, como está, não prova que "decidir por observação" bate um **corte único recalibrado** nesta mesma escala. Esse terceiro braço de comparação é débito registrado (#13), não implementado nesta sessão.

Relatório completo com todas as limitações declaradas: `reports/motor_decisao_backtest.md`.

## 3. CONSEQUÊNCIAS

**Positivas:**
- Todo corte tem derivação auditável — defensável em entrevista e em comitê.
- Desacopla retreino de mudança de política de risco.
- Dá ao cenário macro um canal real de influência (ADR-0008), em vez de decoração.
- A zona cinzenta ganha semântica: "incerteza maior que o sinal", não "faixa do meio".

**Negativas / limitações:**
- Mais difícil de explicar no memo que "score acima de 0,65".
- Depende de três premissas (`m`, `ℓ`, EAD) — trocou um número mágico por três premissas rotuladas. É progresso, não perfeição.
- `EAD = AMT_CREDIT` superestima a perda de quem já amortizou (débito #6).
- Baseline `EV(negar) = 0` ignora custo de oportunidade de relacionamento e custo de capital — simplificação declarada.
- Sem calibração, não funciona. Acopla este ADR ao sucesso da Camada 1.

---

## 4. ALTERNATIVAS DESCARTADAS

| Opção | Por quê rejeitada |
|-------|----------------------|
| Manter buckets 0.40/0.65 | Números sem derivação; a assimetria FN×FP fica só na prosa do README |
| Corte global único otimizado na curva ROC/PR | Melhor que hoje, mas joga fora a variação de `m/ℓ` entre contratos — e continua sem responder "por que esse número?" fora da amostra |
| Otimizar limiar direto por métrica (F1, Youden) | Métrica simétrica ou arbitrária; não fala a língua do dinheiro |
| Custo esperado com matriz FN/FP fixa em unidades abstratas | Não usa o valor do contrato; volta a ser corte global disfarçado |

---

## 5. IMPACTO & VALIDAÇÃO

**Gate 0 (antes de escrever o motor):** medir a **distribuição de `m/ℓ`** na carteira do Home Credit. Se a dispersão for estreita, o corte por observação é complexidade sem retorno — registrar isso e usar corte global derivado pela mesma fórmula. Este teste é barato e precede a implementação. **Executado em 2026-08-04 — ver §2.4.1: aprovado, IQR de 18 p.p.**

**Gate 1:** calibração da Camada 1 validada (reliability + Brier), com `n` e intervalo.

**Métrica de sucesso:** backtest de custo realizado — motor de EV × threshold fixo antigo — com **IC bootstrap** sobre o delta. Nunca reportar o delta sem intervalo.

**Risco de regressão:** testes devem travar a fórmula e as premissas (mesmo padrão do `stable-treasury`: mudar um corte quebra o teste de propósito).

---

## 6. LINKS RELACIONADOS

- Ticket `0002-origem-dos-thresholds.md`, ticket `0007` (LGD com fonte)
- Aula: `wiki/concepts/04_business/Valor_Esperado_Decisao_Credito.md` (base de conhecimento)
- ADR-0008 (cenário macro entra por `ℓ`), ADR-0003 (a zona cinzenta é o input da Camada 2)
- `app/utils.py::get_decision_thresholds` — código que este ADR aposenta
