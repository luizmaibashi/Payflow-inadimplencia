---
tipo: grilling
status: resolvido
criado: 2026-08-04
---

# Ticket 0009: Conflito — dataset internacional × fontes externas brasileiras

## Bloqueio

A pesquisa do ticket 0007 produziu duas recomendações individualmente boas mas **mutuamente incoerentes**:

- **Dataset recomendado:** Home Credit Default Risk — mercados emergentes (Rússia, Indonésia, Vietnã…), região anonimizada, sem país identificável por linha.
- **Fontes externas viáveis para o agente (opção C, ticket 0008):** BCB SGS, BCB SCR.data, IBGE SIDRA — **todas brasileiras**.

Um agente que consulta SELIC/IPCA/desemprego-por-UF para contextualizar o risco de um cliente do Home Credit está inventando uma ligação que não existe. Isso violaria o próprio princípio do projeto (rigor, sem número mágico) e seria o primeiro furo que um entrevistador técnico apontaria.

## Opções

**(A) Dataset internacional + ferramentas coerentes com ele (sem Brasil)**
O agente consulta fontes macro internacionais (ex: World Bank API, FRED) ou nenhuma fonte macro — e a opção C se realiza via ferramentas sobre as *próprias tabelas relacionais* do Home Credit (bureau, previous_application, installments). Ou seja: tool-use real, multi-hop de verdade, mas dentro do dado do caso — o agente decide *quais* tabelas puxar para o cliente em análise, em vez de receber tudo pré-agregado no prompt.
→ *Vantagem:* honesto, e o multi-hop fica mais próximo de underwriting real (consultar histórico de bureau do cliente é literalmente o que um analista faz). *Custo:* perde a conexão com contexto brasileiro/Loft.

**(B) Dataset brasileiro sintético + fontes brasileiras reais**
Volta ao dado sintético (ou gera um novo, mais rigoroso, calibrado por estatísticas agregadas reais do BCB SCR.data), permitindo que o agente consulte SELIC/IBGE de forma coerente.
→ *Vantagem:* contexto Loft/Brasil preservado, agente com ferramentas reais. *Custo:* volta a ter rótulo de default sintético — perde o backtest contra inadimplência real, que era o principal ganho de trocar de dataset.

**(C) Dois níveis: modelo em dado real + camada macro brasileira como cenário declarado**
Treina a Camada 1 no Home Credit (rótulo real, backtest real) e o agente usa fontes brasileiras apenas como *stress scenario* explicitamente rotulado ("e se esta carteira operasse no Brasil de hoje, com SELIC em X?"), nunca como atributo do cliente.
→ *Vantagem:* mantém rigor do rótulo real e ainda exercita tool-use com API brasileira. *Custo:* mais complexo de explicar; risco de parecer "enfeite" se não for bem justificado.

## Recomendação

**(A)** — é a única em que cada peça é o que diz ser. O multi-hop sobre as tabelas relacionais do Home Credit (bureau + histórico de aplicações anteriores + parcelas) é tool-use genuíno e é exatamente o que a pesquisa de mercado descreveu como padrão 2026 ("agentes autônomos orquestrando underwriting multi-etapa, extração/normalização de demonstrativos"). A conexão com o Brasil/Loft se faz na *narrativa e no método* (o mesmo pipeline se aplicaria a uma carteira brasileira), não fingindo que dado emergente anonimizado é brasileiro.

## Resultado

**Decidido (2026-08-04): opção (C)** — Camada 1 treinada no Home Credit (rótulo real, backtest real) + fontes brasileiras (BCB SGS / SCR.data / IBGE) usadas **exclusivamente como cenário de stress declarado**, nunca como atributo do cliente.

### Condição de rigor (não-negociável, senão a opção C vira enfeite)

O risco desta opção — sinalizado antes da decisão — é o cenário macro virar decoração ("consultei a SELIC pra parecer moderno"). Para não virar, o cenário de stress precisa **mudar a decisão de forma rastreável**:

1. **O cenário entra pelo LGD e/ou pela PD calibrada, não pelo prompt.** Ex: SELIC/desemprego mais altos → premissa de recuperação (LGD) piora → o ponto de corte do valor esperado (ticket 0002) se desloca → casos que eram APROVAR viram REVISAR. Se o número macro não altera nenhum corte, ele não deveria estar no sistema.
2. **A separação tem que ser explícita no memo** (ticket 0003): o memo distingue "fatores do cliente" (Home Credit) de "condições de mercado assumidas" (cenário BR), sem misturar as duas origens numa frase só.
3. **O agente nunca afirma que o cliente é brasileiro.** O framing correto é: "esta carteira, se operada sob condições macro brasileiras de {data}, teria este ponto de corte" — transferência de método declarada, não atributo inventado.
4. **A ferramenta é auditável**: toda chamada a BCB/IBGE registra série, data e valor obtido, e o LLM-as-judge (ticket 0004) verifica se o agente citou apenas valores que de fato vieram da ferramenta (anti-alucinação).

### Consequência para o ticket 0008 (opção C do agente)

O agente passa a ter **duas famílias de ferramentas**:
- **Ferramentas de caso** (multi-hop dentro do Home Credit): bureau, previous_application, installments — o agente decide o que puxar para o cliente em análise. *(Esta era a essência da opção A do 0009 — mantida, porque é o multi-hop genuíno.)*
- **Ferramenta de cenário** (BCB SGS / SCR.data / IBGE): consultada uma vez por rodada de análise, para calibrar a premissa macro do lote — não por cliente.
