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

### 2.5 Pré-requisito bloqueante: calibração

Toda a §2.1 assume que `p` é **probabilidade**, não score de ranqueamento.

- **AUC é invariante a transformação monotônica** — um modelo pode ranquear bem e decidir péssimo.
- **Rebalanceamento quebra a calibração.** O pipeline legado usa `imbalanced-learn`; com base rate de ~8% no Home Credit, a tentação de reamostrar é grande. Undersampling **desloca o prior e infla `p̂`** sistematicamente, e o AUC não acusa.
- **O que medir:** reliability diagram + **Brier score**, além do AUC. Corrigir com Platt/isotônica em conjunto separado.

**Sem calibração validada, este motor é aritmética sobre número sem significado.** É gate, não recomendação (débito #3).

### 2.6 Zona cinzenta derivada, não arbitrada

`p*` é uma linha, mas as premissas que a geram são incertas. A banda tem duas fontes, ambas quantificáveis:

1. **Incerteza da premissa** — a faixa de LGD 70–85% já produz `p* ∈ [17,5%; 20,5%]`. Uma decisão que **inverte** conforme a premissa não é decisão robusta: é caso para deferir.
2. **Incerteza da estimativa** — o intervalo em torno de `p̂`.

> A zona cinzenta é a região onde o sinal (`|EV|`) é menor que a incerteza somada. Não é largura chutada. É o que alimenta a Camada 2 (ADR-0003) e a fila de deferral.

---

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

**Gate 0 (antes de escrever o motor):** medir a **distribuição de `m/ℓ`** na carteira do Home Credit. Se a dispersão for estreita, o corte por observação é complexidade sem retorno — registrar isso e usar corte global derivado pela mesma fórmula. Este teste é barato e precede a implementação.

**Gate 1:** calibração da Camada 1 validada (reliability + Brier), com `n` e intervalo.

**Métrica de sucesso:** backtest de custo realizado — motor de EV × threshold fixo antigo — com **IC bootstrap** sobre o delta. Nunca reportar o delta sem intervalo.

**Risco de regressão:** testes devem travar a fórmula e as premissas (mesmo padrão do `stable-treasury`: mudar um corte quebra o teste de propósito).

---

## 6. LINKS RELACIONADOS

- Ticket `0002-origem-dos-thresholds.md`, ticket `0007` (LGD com fonte)
- Aula: `wiki/concepts/04_business/Valor_Esperado_Decisao_Credito.md` (base de conhecimento)
- ADR-0008 (cenário macro entra por `ℓ`), ADR-0003 (a zona cinzenta é o input da Camada 2)
- `app/utils.py::get_decision_thresholds` — código que este ADR aposenta
