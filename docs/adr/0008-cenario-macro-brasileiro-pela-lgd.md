# ADR-0008: Cenário macro brasileiro entra pela LGD, como stress declarado

**Data**: 2026-08-04
**Status**: Accepted
**Contexto**: PayFlow — decisão D8 da `SPEC_FINAL.md`, ticket Wayfinder [0009](../wayfinder/refatoracao-camada-agentica/0009-conflito-dataset-vs-fontes-externas.md)

---

## 1. CONTEXTO (O QUÊ?)

Os tickets 0007 e 0008 produziram duas recomendações individualmente boas e **mutuamente incoerentes**:

- **Dataset:** Home Credit — mercados emergentes (Rússia, Indonésia, Vietnã…), região anonimizada, sem país identificável por linha.
- **Fontes externas viáveis para o agente:** BCB SGS, BCB SCR.data, IBGE SIDRA — **todas brasileiras**.

Um agente que consulta SELIC e desemprego por UF para avaliar um cliente do Home Credit está inventando uma ligação que não existe. Seria o primeiro furo que um entrevistador técnico apontaria — e violaria o princípio-raiz do ADR-0006.

## 2. DECISÃO (POR QUÊ?)

**Camada 1 treinada no Home Credit (rótulo real, backtest real) + fontes brasileiras usadas exclusivamente como cenário de stress declarado, nunca como atributo do cliente.**

Framing correto, e único aceitável:

> "Esta carteira, se operada sob condições macro brasileiras de {data}, teria este ponto de corte."

Transferência de **método**, declarada. Não afirmação sobre a nacionalidade de ninguém.

### 2.1 Condições de rigor — não-negociáveis

O risco desta escolha é o cenário macro virar decoração ("consultei a SELIC para parecer moderno"). As quatro condições existem para impedir isso, e valem como **requisito de aceitação**:

1. **O cenário entra pela LGD, não pelo prompt.** SELIC/desemprego piores → premissa de recuperação piora → `ℓ` sobe dentro da faixa 70–85% → `p*` cai (ADR-0002) → casos que eram APROVAR viram zona cinzenta. **Se o número macro não altera nenhum corte, ele não deveria estar no sistema.**
2. **Separação explícita no memo.** `fatores_cliente` e `cenario_assumido` são campos distintos do schema (ADR-0003), nunca misturados numa frase.
3. **O agente nunca afirma que o cliente é brasileiro.** Nem no memo, nem na narrativa renderizada.
4. **A ferramenta é auditável.** Toda chamada a BCB/IBGE registra série, data e valor; o juiz verifica se o agente citou **apenas** valores que vieram da tool (ADR-0004, rubrica de groundedness).

### 2.2 Por que a LGD é o canal certo

A LGD é a única premissa da equação de decisão que é **legitimamente sobre o ambiente**, não sobre a pessoa: quanto se recupera de um crédito inadimplente depende de emprego, renda, custo do dinheiro e eficiência de cobrança — variáveis macro. A PD, ao contrário, é estimada do comportamento do cliente e transferi-la para o Brasil seria falsificação.

Vale, porém, dimensionar o efeito honestamente (ADR-0002 §2.4): a faixa inteira de LGD 70–85% desloca `p*` em **3,0 p.p.** Isso é real e rastreável — e é **menos** do que a variação induzida pela margem entre contratos. O cenário macro é um canal legítimo, não o principal.

### 2.3 Por que não a opção "mais honesta" (só fontes internacionais)

A alternativa A do ticket 0009 — abandonar as fontes BR e usar FRED/World Bank, ou nenhuma — foi a recomendação inicial da análise, por ser aquela em que cada peça é exatamente o que diz ser.

Foi preterida porque a opção C **preserva o rigor** (rótulo real, backtest real, stress rotulado) **e** exercita integração com API brasileira, que é sinal relevante para o alvo de carreira. A condição para isso não ser trapaça é a lista de §2.1 — sem ela, a opção A seria de fato superior.

> Registrado explicitamente: esta é a decisão do projeto em que a distância entre "rigoroso" e "conveniente" é menor. Se numa auditoria futura as condições 1–4 não estiverem sendo cumpridas, o correto é **remover o cenário macro**, não afrouxar as condições.

---

## 3. CONSEQUÊNCIAS

**Positivas:**
- Mantém rótulo real e backtest (o ganho do ADR-0001) sem inventar nacionalidade.
- Dá ao cenário macro um mecanismo de influência mensurável, em vez de retórica.
- Exercita tool-use com API pública brasileira, de forma defensável.

**Negativas / limitações:**
- **Mais difícil de explicar** que a opção A — exige um parágrafo de framing em todo lugar onde o projeto é apresentado.
- Efeito modesto: 3,0 p.p. em `p*` na faixa inteira de LGD. Honesto, mas não espetacular.
- Dependência de APIs externas (disponibilidade, defasagem de série).
- LGD 70–85% é estimativa internacional — o cenário BR desloca uma premissa que já é premissa (débito #7).

---

## 4. ALTERNATIVAS DESCARTADAS

| Opção | Por quê rejeitada |
|-------|----------------------|
| (A) Só fontes internacionais / nenhuma macro | Mais limpa, mas perde o exercício com API BR; a opção C preserva o rigor **se** as condições 1–4 forem cumpridas |
| (B) Voltar a dado brasileiro sintético | Perde o rótulo real de default — mata o backtest, que é a contribuição do projeto |
| Macro como **feature** do modelo | Falsificação direta: o cliente não é brasileiro |
| Macro só no texto do memo, sem mexer em corte | É exatamente a decoração que este ADR existe para proibir |

---

## 5. IMPACTO & VALIDAÇÃO

**Métrica de sucesso:** demonstrar, com um caso concreto, a cadeia completa: série BCB consultada → `ℓ` deslocada → `p*` recalculado → decisão que mudou de faixa. Se essa demonstração não for possível, a condição #1 falhou.

**Risco de regressão vigiado:** teste que falha se o cenário macro não produzir nenhuma mudança de decisão no lote (indicaria que virou decoração), e teste que falha se a tool de cenário for chamada por cliente (ADR-0007 §5).

---

## 6. LINKS RELACIONADOS

- Ticket `0009-conflito-dataset-vs-fontes-externas.md`
- ADR-0002 (`p*` e a faixa de LGD), ADR-0003 (`cenario_assumido` separado), ADR-0004 (groundedness), ADR-0007 (tool por lote)
