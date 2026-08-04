# ADR-0003: Contrato do memo de crédito e agente cego ao score

**Data**: 2026-08-04
**Status**: Accepted
**Contexto**: PayFlow — decisão D3 da `SPEC_FINAL.md`, ticket Wayfinder [0003](../wayfinder/refatoracao-camada-agentica/0003-contrato-memo-de-credito.md)

---

## 1. CONTEXTO (O QUÊ?)

A Camada 2 produz um "memo de crédito" para os casos da zona cinzenta (ADR-0002 §2.6). Antes de qualquer código, quatro escolhas: o que entra no memo, em que formato, onde o humano entra, e como preservar rastreabilidade até o score que originou o caso.

Havia uma escolha silenciosa mais importante que todas: **o agente vê ou não vê a `p_default` da Camada 1?**

## 2. DECISÃO (POR QUÊ?)

### 2.1 O agente **não** vê o score — parecer independente

O agente analisa o caso do zero, via ferramentas (ADR-0007), e emite parecer. O confronto parecer × score acontece **depois**, fora do agente.

**Por quê:** se visse o score, o agente tenderia a parafraseá-lo (**ancoragem**), e o eval mediria redação, não julgamento. Cego ao score, dá para medir se o agente **agrega informação** sobre o modelo — que é exatamente a lacuna de literatura do ADR-0004. Ancorado em *appropriate reliance* (Schemmer et al., IUI 2023).

> **Regra de engenharia derivada:** qualquer vazamento do score para a Camada 2 — prompt, contexto, tool, nome de variável, ordenação da fila — **invalida o experimento inteiro**. É o invariante mais frágil do projeto.

**Custo assumido:** mais chamadas de ferramenta e divergência potencialmente grande em relação ao modelo. A divergência é **sinal medível**, não defeito (é o objeto do backtest).

### 2.2 Formato: JSON Pydantic é a fonte de verdade; a narrativa é renderizada dele

```jsonc
{
  "cliente_id": "SK_100034",
  "recomendacao": "DEFERIR",           // APROVAR | NEGAR | DEFERIR
  "fatores_cliente": [                  // origem: ferramentas de CASO
    {"fato": "3 atrasos >30d em 12m",
     "fonte_tool": "bureau_balance",
     "peso": "desfavoravel"}
  ],
  "cenario_assumido": {                 // origem: ferramenta de CENÁRIO
    "lgd": 0.78,
    "fonte": "BCB SGS série 11, 2026-08-04"
  },
  "informacao_faltante": ["renda atual não verificada"],
  "narrativa": "..."                    // renderizada dos campos acima
}
```

Três propriedades do desenho, cada uma com função:

1. **Narrativa renderizada dos campos** — impossível a prosa contradizer os dados. O juiz binário avalia estrutura, não estilo.
2. **`fonte_tool` obrigatório em todo fato** — é o que torna a rubrica de *groundedness* (eliminatória, ADR-0004) verificável mecanicamente.
3. **`fatores_cliente` e `cenario_assumido` são campos distintos** — condição de rigor #2 do ADR-0008. Nunca misturados numa frase, para que o cenário macro jamais vire atributo do cliente.

`DEFERIR` é a ação de *deferral* do Learning to Defer, e `informacao_faltante` é o que a justifica — deferir sem dizer o que falta não é decisão, é omissão.

### 2.3 Humano no loop: tela de revisão no Streamlit

Fila de casos deferidos; o analista vê o memo, aprova/rejeita/edita, e a decisão fica registrada.

**Razão decisiva (não é só UX):** essa tela é a **única fonte dos 100 labels humanos** que a calibração do juiz exige (TPR/TNR com IC de Wilson, ADR-0004). Sem ela, o juiz LLM não tem ground truth contra o qual ser calibrado — e uma métrica de juiz não calibrado não é métrica.

### 2.4 Rastreabilidade

Todo memo fica vinculado a: `p_default`/decisão da Camada 1 que originou o caso, trace completo de ferramentas chamadas, e decisão humana quando houver. **Sem esse vínculo não há backtest de custo nem calibração de juiz** — a rastreabilidade é requisito de medição, não burocracia.

Note a assimetria intencional: o **sistema** guarda o vínculo memo ↔ score; o **agente** nunca o vê.

---

## 3. CONSEQUÊNCIAS

**Positivas:**
- Permite medir informação incremental do agente sobre o modelo (a contribuição do projeto).
- Memo auditável campo a campo; groundedness verificável por construção.
- A tela de revisão paga duplo: humano no loop **e** produção de ground truth.

**Negativas / limitações:**
- Um vazamento de score sutil corrompe silenciosamente todos os resultados — exige teste explícito de "cegueira" no eval.
- Agente sem score gasta mais tokens/tools por caso (custo por decisão sobe).
- A tela de revisão é escopo de UI que não existia; e 100 labels são trabalho manual real do Luiz.
- Labels vindos de **um único revisor não-especialista** são ground truth fraco — declarar como tal (débito #10).

---

## 4. ALTERNATIVAS DESCARTADAS

| Opção | Por quê rejeitada |
|-------|----------------------|
| Agente vê o score e "revisa" a decisão | Ancoragem: mede paráfrase, não julgamento; destrói a contribuição do projeto |
| Texto livre com seções fixas | Não avaliável mecanicamente; narrativa pode contradizer os fatos |
| Narrativa e campos gerados em paralelo | Mesma contradição possível, com custo extra |
| Memo só em log, sem tela de revisão | Sem humano no loop **e** sem ground truth para calibrar o juiz |
| Explicabilidade via SHAP da Camada 1 no memo | Vazaria o modelo para o agente — mesma ancoragem por outra porta |

---

## 5. IMPACTO & VALIDAÇÃO

**Métrica de sucesso:** 100% dos memos válidos contra o schema Pydantic; 100% dos fatos numéricos com `fonte_tool` resolvível na trace; taxa de deferral reportada com `n` e intervalo.

**Teste obrigatório de cegueira:** asserção automatizada de que nem `p_default` nem qualquer derivado (bucket, rank, ordenação) aparece no contexto entregue ao agente. Este teste é o guardião do ADR inteiro.

---

## 6. LINKS RELACIONADOS

- Ticket `0003-contrato-memo-de-credito.md`
- ADR-0002 (define quais casos chegam aqui), ADR-0004 (rubricas que consomem este contrato)
- ADR-0007 (ferramentas que preenchem `fatores_cliente`), ADR-0008 (separação `cenario_assumido`)
- Schemermer et al., *Appropriate Reliance on AI Advice*, IUI 2023
