# ADR-0011: Critério explícito de Task Completion — quando `NEGAR` é defensável

**Data**: 2026-08-08
**Status**: Accepted
**Contexto**: PayFlow — débito #10 (calibração do juiz) e o achado que a primeira calibração produziu

---

## 1. CONTEXTO (O QUÊ?)

O ADR-0004 §2.2 define a rubrica Task Completion como "memo cumpre o contrato do ADR-0003", e o juiz (`app/juiz_camada2.py`) a operacionaliza como *"a recomendação é defensável pelos fatos que o próprio agente levantou?"*. Nenhum dos dois diz **o que torna uma recomendação indefensável** — ficava a cargo do julgamento do revisor, caso a caso.

A primeira calibração (2026-08-08, `reports/calibracao_juiz.md`) mostrou o preço disso. Entre os casos rotulados, **15 têm assinatura idêntica nos dados brutos** — memo recomenda `NEGAR`, `n_nunca_pagas = 0`, `atraso_medio_dias < 0` — e o mesmo revisor marcou 4 como `FALHA` e 11 como `OK`.

Dois casos exemplificam a contradição:

| caso | parcelas pagas a menor | déficit médio | veredito humano |
|---|---|---|---|
| `379149` | 75 de 153 (49%) | 24,8% | FALHA — *"cliente bom que paga"* |
| `166661` | 8 de 31 (26%) | 12,9% | OK |

O cliente pior recebeu "o agente errou ao negar"; o melhor recebeu "negar foi correto".

**Consequência que motivou este ADR:** um TPR calculado contra esse ground truth não mede o juiz. Mede a distância entre um critério implícito e variável e um critério explícito e constante. Rotular mais casos sob o critério implícito aumenta o ruído em vez de estreitar o intervalo.

## 2. DECISÃO (POR QUÊ?)

### 2.1 O critério, em dois níveis

`NEGAR` é **defensável** (rubrica Task Completion = `OK`) quando houver:

- **1 sinal GRAVE**, ou
- **2 ou mais AGRAVANTES**

| Nível | Sinal | Limiar | Fonte |
|---|---|---|---|
| **GRAVE** | Utilização de crédito em outras instituições | ≥ 80% | `consultar_bureau.utilizacao` |
| **GRAVE** | Pior atraso histórico nesta casa | ≥ 30 dias | `consultar_pagamentos.pior_atraso_dias` |
| AGRAVANTE | Déficit médio de pagamento | ≥ 15% | `consultar_pagamentos.deficit_medio_pct` |
| AGRAVANTE | Contratos em atraso **hoje** no bureau | ≥ 1 | `consultar_bureau.n_em_atraso_hoje` |
| AGRAVANTE | Atraso **relevante e recente** | ≥ 15 dias, há ≤ 90 dias | `pior_atraso_dias` + `dias_desde_ultimo_atraso` |

Sem sinal grave e com no máximo 1 agravante, `NEGAR` é **indefensável** → rubrica = `FALHA`, categoria `recomendacao_ignora_fato`.

### 2.2 Por que dois níveis, e não uma soma de pontos

Três decisões de fronteira, cada uma tomada contra um caso concreto:

1. **Pagar a menor cronicamente NÃO basta para negar** (decisão do revisor, 2026-08-08). Um cliente que nunca deixou de pagar e antecipa parcelas, mas entrega 15–25% a menos, é caso de **limite menor**, não de recusa. Déficit vira agravante. *Casos que fixam a fronteira: `219448` (déficit 16%) e `379149` (déficit 25%), ambos `FALHA`.*

2. **Atraso ativo no bureau NÃO basta sozinho.** Histórico de pagamento **nesta casa** pesa mais que a situação em terceiros — a informação própria é mais confiável e mais relevante para o contrato que está sendo decidido. *Caso que fixa a fronteira: `240344`, impecável conosco (pior atraso 4 dias, déficit 0%) com 1 contrato em atraso no bureau — `FALHA`.*

3. **Utilização entre 60% e 80% não conta como agravante.** É endividamento dentro do normal; só a partir de 80% vira sinal de que o cliente está no limite. *Caso que fixa a fronteira: `379149`, utilização 67% — não somou ao déficit.*

### 2.3 A recência precisa de severidade junto

`dias_desde_ultimo_atraso` sozinho gera falso sinal: um atraso de **4 dias** ocorrido há 39 dias não é risco. O agravante de recência só conta quando o atraso também foi **relevante** (≥ 15 dias). Sem esse acoplamento, o caso `240344` seria classificado como defensável e contradiria a decisão §2.2.2.

### 2.4 Escopo: só cobre `NEGAR`

O critério responde "quando negar é defensável". `APROVAR` e `DEFERIR` não têm regra equivalente aqui — `DEFERIR` já é coberto pela validação mecânica de trajetória (ADR-0010) e pela correção de prompt do débito #28. Escopo estreito de propósito: a falha medida no piloto foi de recusa indevida, não de aprovação indevida.

---

## 3. CONSEQUÊNCIAS

**Positivas:**
- O critério é **falsificável**: rotulagem nova pode derrubá-lo, coisa que "eu sei quando vejo" nunca podia.
- O prompt do juiz passa a citar limiares e nomes de campo, em vez de pedir "peso predominante dos fatores" — que era uma heurística de contagem, não um critério de crédito.
- Rotulagem futura fica mais rápida e mais consistente: o revisor confere sinais nomeados em vez de reconstruir o raciocínio do zero.

**Negativas / limitações:**
- 🔴 **Ajustado a 7 julgamentos.** Os limiares (80%, 30d, 15%, 90d) foram escolhidos para reproduzir os 7 julgamentos humanos reais disponíveis. Com `n = 7` e 5 parâmetros, **qualquer** regra caberia. Isto é hipótese formalizada, **não** critério validado — a validação exige rotulagem nova sob o critério escrito.
- Os limiares não vêm de dado de mercado nem de política de crédito real; são a leitura do revisor formalizada. Um analista de crédito sênior provavelmente mudaria todos.
- O critério ignora `n_parcelas`: um déficit de 20% em 7 parcelas e em 153 parcelas contam igual, o que é discutível.

---

## 4. ALTERNATIVAS DESCARTADAS

| Opção | Por quê rejeitada |
|-------|----------------------|
| Manter critério implícito ("o revisor sabe quando vê") | Produziu 4 `FALHA` e 11 `OK` sobre a mesma assinatura de dado — medido, não suposto |
| Soma de pontos com pesos por sinal | Mais parâmetros para ajustar aos mesmos 7 pontos; ganharia ajuste e perderia falsificabilidade |
| Contagem de pesos `favoravel`/`desfavoravel` do memo | É o que o juiz já fazia. Mede a *redação* do memo, não os fatos do cliente — o agente escolhe como rotular cada peso |
| Deixar o juiz LLM inferir o critério de exemplos (few-shot) | Sem critério escrito, não há como auditar por que o juiz reprovou um caso — e a rubrica precisa ser defensável perante um humano |

---

## 5. IMPACTO & VALIDAÇÃO

**Ajuste atual:** 7/7 dos julgamentos humanos reais de `NEGAR` (`111985`, `128369`, `153799`, `219448`, `240344`, `379149`, `449188`).

**Como falsificar:** rotular casos novos **sob o critério escrito** e medir TPR/TNR contra ele. Se o revisor discordar da regra em ≥ 20% dos casos, o critério está errado — não o revisor.

**Regressão a vigiar:** o critério lê campos brutos das ferramentas (`utilizacao`, `deficit_medio_pct`, `pior_atraso_dias`, `n_em_atraso_hoje`, `dias_desde_ultimo_atraso`). Mudança de nome ou semântica desses campos quebra o critério em silêncio.

---

## 6. LINKS RELACIONADOS

- ADR-0004 (rubrica que este critério torna verificável), ADR-0003 (contrato do memo), ADR-0010 (trajetória mecânica)
- `reports/calibracao_juiz.md` — a medição que motivou este ADR
- Débitos #10 (calibração), #30 (memos não regeneráveis), #31 (ground truth contaminado por rubrica trocada)
