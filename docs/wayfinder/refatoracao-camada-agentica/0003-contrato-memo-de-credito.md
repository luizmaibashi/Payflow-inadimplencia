---
tipo: grilling
status: resolvido
criado: 2026-08-04
---

# Ticket 0003: Contrato/schema do memo de crédito (Camada 2)

## Bloqueio
A Camada 2 (agente) precisa gerar uma saída estruturada — o "memo de crédito" — para os casos na faixa REVISAR. Esse contrato não existe hoje e precisa ser decidido antes de escrever qualquer código:

1. **O que entra no memo?** Ex: resumo do caso, fatores que mais pesaram na decisão da Camada 1 (explicabilidade — via SHAP/feature importance, ou via prompt com os dados brutos?), recomendação do agente (aprovar/negar/pedir mais info), nível de confiança, citação explícita de qual regra/limite foi acionado.
2. **Formato de saída**: JSON estruturado (schema Pydantic, análogo a `app/schemas.py` já existente) vs. texto livre com seções fixas. JSON estruturado é mais fácil de avaliar por LLM-as-judge e mais fácil de auditar — provável escolha default, mas confirmar.
3. **Onde o humano entra?** O agente propõe e humano aprova/rejeita via UI (Streamlit já existe — adicionar uma tela?), ou o memo só fica registrado em log para auditoria posterior (humano decide fora do sistema)? Isso muda o escopo de UI necessário.
4. **Rastreabilidade**: cada memo gerado precisa ficar associado ao `probabilidade`/`decisao` da Camada 1 que o originou, para auditoria (nunca perder o vínculo entre score e decisão do agente).

## Resultado

**Decidido em 2026-08-04.**

### 1. Parecer independente — o agente NÃO vê a probabilidade da Camada 1

O agente analisa o caso do zero (via ferramentas de caso, ticket 0008) e emite parecer. Só **depois** o sistema confronta parecer × score.

**Por quê:** se o agente visse o score, tenderia a parafraseá-lo (ancoragem) e o eval mediria redação, não julgamento. Sem o score, dá para medir se o agente **agrega informação** sobre o modelo — que é exatamente a lacuna de literatura identificada no ticket [0004](0004-metodologia-avaliacao-llm-judge.md). Ancorado em *appropriate reliance* (Schemmer et al., IUI 2023).

**Custo assumido:** mais chamadas de ferramenta; o agente pode divergir bastante do modelo — mas a divergência vira **sinal medível**, não defeito.

### 2. Formato: JSON estrito (Pydantic) como fonte de verdade; narrativa renderizada dele

O texto do memo é gerado **a partir** dos campos tipados, nunca em paralelo — assim é impossível a narrativa contradizer os campos, e o juiz binário (ticket 0004) avalia estrutura, não prosa.

```jsonc
{
  "cliente_id": "SK_100034",
  "recomendacao": "DEFERIR",          // APROVAR | NEGAR | DEFERIR
  "fatores_cliente": [                 // origem: ferramentas de CASO
    {"fato": "3 atrasos >30d em 12m",
     "fonte_tool": "bureau_balance",
     "peso": "desfavoravel"}
  ],
  "cenario_assumido": {                // origem: ferramenta de CENÁRIO
    "lgd": 0.78,
    "fonte": "BCB SGS série 11, 2026-08-04"
  },
  "informacao_faltante": ["renda atual não verificada"],
  "narrativa": "..."                   // renderizada dos campos acima
}
```

**Separação obrigatória** (condição #2 do ticket [0009](0009-conflito-dataset-vs-fontes-externas.md)): `fatores_cliente` (Home Credit) e `cenario_assumido` (BCB/IBGE) são campos distintos. Nunca misturados numa frase.

**`fonte_tool` em todo fato** é o que torna a rubrica de *groundedness* (eliminatória) verificável: cada afirmação numérica precisa rastrear a um retorno de ferramenta.

**`DEFERIR`** é a ação de *deferral* do Learning to Defer; `informacao_faltante` é o que justifica a deferência.

### 3. Humano no loop: tela de revisão no Streamlit

Fila de casos deferidos; o analista vê o memo, aprova/rejeita/edita, e a decisão é registrada.

**Razão decisiva:** isso gera dado de concordância humano × agente — que são exatamente os **100 labels humanos** que a calibração do juiz exige (TPR/TNR com IC de Wilson, ticket 0004). Sem essa tela, a calibração do juiz não teria de onde tirar ground truth.

### 4. Rastreabilidade

Todo memo fica associado ao `probabilidade`/`decisao` da Camada 1 que originou o caso, à trace de ferramentas chamadas, e (quando houver) à decisão humana registrada. Sem esse vínculo não há backtest de custo nem calibração de juiz.
