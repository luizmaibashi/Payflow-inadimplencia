# ADR-0010: Validação de trajetória — mecânica, registrada, não eliminatória

**Data**: 2026-08-06
**Status**: Accepted
**Contexto**: PayFlow — primeira execução em lote da Camada 2 contra provider real (piloto de 2026-08-06). Implementa a rubrica #4 do [ADR-0004](0004-metodologia-de-avaliacao.md).

---

## 1. CONTEXTO (O QUÊ?)

O piloto de 2026-08-06 foi a primeira vez que a Camada 2 rodou em lote contra o Gemini. Até então ela havia sido construída e testada com dublês determinísticos e executada **uma vez, à mão, contra um caso**.

O primeiro memo real produzido (caso `344012`) expôs um defeito que nenhuma rubrica existente pegava:

- o agente chamou **1** das 3 ferramentas de caso (`consultar_bureau`);
- recomendou `DEFERIR`;
- declarou como `informacao_faltante`: *"Histórico de pagamentos do cliente com esta instituição"* — que `consultar_pagamentos` entrega em uma chamada;
- preencheu os `MIN_FATORES = 3` com 4 fatos vindos todos da mesma ferramenta.

**Groundedness passou.** Todo fato citava a única tool chamada, então a rubrica eliminatória do ADR-0004 aprovou o memo. Isso demonstra empiricamente que **groundedness é necessária e não suficiente**: um memo pode ser 100% ancorado e ainda assim omisso.

O ADR-0004 §2.2 já previa a rubrica #4 (*trajectory efficiency*, determinística), mas ela nunca foi implementada. O piloto mostrou que ela não é refinamento — é o que separa deferral legítimo de omissão.

## 2. DECISÃO (POR QUÊ?)

### 2.1 A checagem é mecânica, não de juiz

`validar_trajetoria(memo, trace) -> list[str]` em `app/agente_underwriting.py`. Sem LLM, sem custo de API, sem opinião. A violação é derivável da trace mais a recomendação:

| Condição | Violação |
|---|---|
| `DEFERIR` sem ter chamado `consultar_bureau` ou `consultar_pagamentos` | sim |
| `DEFERIR` com `tem_historico_mensal=True` sem chamar `consultar_historico_bureau` | sim |
| `DEFERIR` com `tem_historico_mensal=False` sem chamar o histórico | **não** |
| `APROVAR`/`NEGAR` sem esgotar as ferramentas | **não** |

### 2.2 Por que só vale para DEFERIR

Decidir com menos informação é uma escolha legítima de um analista: se o bureau já mostra atraso corrente grave, negar sem consultar mais é eficiência, não descuido. **Alegar falta do que não se buscou** é que não é.

Em *Learning to Defer* (ADR-0004 §2.1), o deferral se paga porque o humano sabe algo que o modelo não sabe. Se a informação estava a uma chamada de distância, o deferral não agrega — só transfere trabalho e adiciona custo. Cobrar a trajetória apenas em `DEFERIR` mira exatamente esse ponto.

### 2.3 Por que o 2º salto é condicional

`consultar_historico_bureau` só faz sentido se `consultar_bureau` indicou `tem_historico_mensal=True` (ADR-0007). Exigi-la sempre penalizaria o agente **por respeitar o desenho do multi-hop** — a rubrica passaria a punir o comportamento correto.

### 2.4 A decisão central: REGISTRADA, não eliminatória

Violação de trajetória **não barra o memo**. `ResultadoAnalise` ganha `violacoes_trajetoria: list[str]`; o memo volta normalmente.

Três razões:

1. **O ADR-0004 §2.2 declara groundedness como a única eliminatória.** Promover trajetória a gate seria contrato novo, não implementação do que já foi decidido — e mudança de contrato exige ADR, que é este.
2. **Severidade diferente.** Memo com número inventado é *pior que memo nenhum* (dá confiança falsa a quem vai decidir crédito). Memo omisso é *incompleto* — o revisor humano percebe a lacuna e devolve. Tratar os dois igual apaga a distinção que justificava a eliminatória.
3. **Barrar destrói a evidência.** Se a violação virasse `memo=None`, o error analysis perderia justamente os memos que precisam ser lidos para entender o padrão de falha.

### 2.5 Metade do conserto é prompt

A checagem mecânica **detecta**; ela não corrige. `montar_contexto_inicial()` passou a instruir: apurar antes de concluir, e `DEFERIR` só vale para informação que nenhuma ferramenta disponível entrega.

Efeito medido no mesmo caso, com o mesmo modelo e temperatura 0:

| | antes | depois |
|---|---|---|
| `344012` | 1 tool → `DEFERIR` alegando falta do histórico de pagamentos | `consultar_bureau` + `consultar_pagamentos` → `DEFERIR`, **0 violações** |
| `422471` | (não chegou a rodar) | 3 tools, multi-hop completo → `NEGAR`, 0 violações |

n=2. Não é evidência de que o problema acabou — é evidência de que o conserto age na direção certa. A taxa real sai no eval set do ADR-0004 §2.5.

---

## 3. CONSEQUÊNCIAS

**Positivas:**
- Uma rubrica do ADR-0004 sai do papel sem custo de API e sem rotulagem humana.
- O defeito vira métrica contável (`ok_com_violacao` no piloto), não impressão.
- Prompt e checagem se vigiam: se o prompt regredir, a checagem acusa.

**Negativas / limitações:**
- **A checagem é conservadora por construção.** Só pega o caso em que uma tool *sempre aplicável* não foi chamada. Um `DEFERIR` que chama as três e mesmo assim alega falta de algo obtível passa batido — isso exigiria comparar o texto de `informacao_faltante` com o que as tools entregam, o que é trabalho de juiz, não determinístico.
- `FERRAMENTAS_SEMPRE_APLICAVEIS` é lista **manual**. Ferramenta de caso nova precisa ser adicionada lá, ou a rubrica silenciosamente para de cobri-la.
- Não eliminatória significa que memo defeituoso circula. Aceito: o eval conta, o humano julga.

---

## 4. ALTERNATIVAS DESCARTADAS

| Opção | Por quê rejeitada |
|-------|----------------------|
| Tornar a violação eliminatória (`memo=None`) | Muda o contrato do ADR-0004 sem necessidade, iguala severidades diferentes e destrói a evidência que o error analysis precisa ler |
| Exigir todas as 3 tools sempre | Pune o agente por respeitar o desenho condicional do multi-hop (ADR-0007) |
| Cobrar trajetória também em APROVAR/NEGAR | Decidir com menos informação é escolha legítima; o defeito é alegar falta, não decidir cedo |
| Só corrigir o prompt, sem checagem | Prompt regride em silêncio a cada troca de modelo; sem checagem, ninguém percebe |
| Delegar a rubrica ao juiz LLM | Custa API e introduz ruído numa verificação que é puramente derivável da trace |

---

## 5. IMPACTO & VALIDAÇÃO

**Métrica de sucesso:** taxa de `ok_com_violacao` no eval set do ADR-0004 §2.5, reportada com `n` e IC de Wilson.

**Risco de regressão:** 7 testes em `tests/test_agente_underwriting.py`, incluindo a regressão do caso `344012` e o teste de que a violação **não** barra o memo.

**Débito aberto:** a checagem não cobre `DEFERIR` que consultou tudo e ainda assim alega falta de informação obtível. Fica para o juiz do ADR-0004 (débito #19).

---

## 6. LINKS RELACIONADOS

- [ADR-0004](0004-metodologia-de-avaliacao.md) §2.2 (rubricas), §2.5 (amostras)
- [ADR-0003](0003-contrato-do-memo-e-agente-cego-ao-score.md) §2.2 (DEFERIR exige dizer o que falta)
- [ADR-0007](0007-familias-de-ferramentas-do-agente.md) (multi-hop condicional)
- `reports/piloto_camada2.md` (rodada que expôs o defeito)
- `app/agente_underwriting.py::validar_trajetoria`
