---
tipo: grilling
status: resolvido
criado: 2026-08-04
---

# Ticket 0008: Escopo da Camada 2 — agente com busca de contexto externo (opção C)

## Bloqueio
**Decidido (2026-08-04):** expandir para a **opção C** — o agente não só propõe decisão para casos em zona cinzenta, mas busca **contexto externo** antes de recomendar (tool-use/retrieval real, não só prompt sobre os dados do formulário).

Isso é escopo maior que o assistente simples (opção B) e ainda tem incógnitas:

1. **Quais fontes externas** o agente consulta — em pesquisa no ticket 0007. Candidatos honestos (públicos e gratuitos): BCB SGS (SELIC, inflação, inadimplência agregada do SFN), IBGE (desemprego e renda por região). Dados individuais de bureau (Serasa/SPC) **não** são acessíveis — o agente não pode fingir consultá-los.
2. **Risco de honestidade**: se o dataset escolhido for internacional (ex: EUA), consultar indicadores macro brasileiros é incoerente. A escolha de fonte externa está acoplada à escolha de dataset (ticket 0007) — resolver 0007 antes de fechar este.
3. **Como avaliar**: o LLM-as-judge precisa verificar não só a coerência da recomendação, mas se o agente usou a ferramenta certa na hora certa (trajectory quality, na terminologia do paper KDD'26 citado na pesquisa de mercado desta sessão) e se não alucinou dado externo que não veio da ferramenta.
4. **Validação com backtest**: com dado real rotulado, dá para medir se as recomendações do agente na faixa cinzenta batem com o default que de fato ocorreu — evidência muito mais forte que eval puramente sintético. Isso vale independentemente de B ou C.

## Resultado

**Fechado em 2026-08-04**, após tickets [0007](0007-dataset-lgd-fontes-externas.md) e [0009](0009-conflito-dataset-vs-fontes-externas.md).

O agente tem **duas famílias de ferramentas**, com papéis distintos:

| Família | Ferramentas | Granularidade | Papel |
|---|---|---|---|
| **Caso** (multi-hop real) | Tabelas relacionais do Home Credit: `bureau`, `bureau_balance`, `previous_application`, `installments_payments`, `credit_card_balance` | Por cliente | O agente decide *o que puxar* para o cliente em análise — é o que um analista de crédito faz de fato. Não recebe tudo pré-agregado no prompt. |
| **Cenário** (stress declarado) | BCB SGS (SELIC/IPCA), BCB SCR.data, IBGE SIDRA | Por rodada/lote, não por cliente | Calibra a premissa macro (via LGD → ponto de corte). Nunca vira atributo do cliente. |

Os pontos 1-4 do ticket 0009 (condição de rigor) valem como requisito de aceitação desta camada.
