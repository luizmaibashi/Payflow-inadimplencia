# PayFlow — como contar essa história

> Dois formatos prontos pra usar: parágrafo curto (currículo/LinkedIn) e roteiro falado (entrevista). Números e nomes exatos batem com `README.md` e `AGENTS.md` — se algum débito mudar de status, atualizar aqui também.

---

## Parágrafo curto (currículo / LinkedIn / bio de projeto)

> Construí um agente de crédito que decide onde um classificador de risco (AUC 0,776) fica em dúvida, e depois medi — com poder estatístico real, não uma amostra pequena que parecia boa — se ele decide melhor que o acaso. A resposta foi não, e a parte que mais me orgulha não é o "não": é ter descoberto por quê. Investigando os dados, achei que o próprio classificador campeão do projeto cai pra AUC 0,56 (quase acaso) exatamente na fatia onde o agente opera — ou seja, a região é estruturalmente difícil de prever com os dados disponíveis, não uma falha do agente. No caminho, testei e descartei publicamente uma das minhas próprias hipóteses (achei que faltava um sinal específico ao agente; os dados mostraram que esse sinal também não funciona ali) antes de gastar dinheiro confirmando algo que já estava refutado de graça.

**Versão de uma linha, pra bullet de currículo:**
> Projetou e mediu um agente de underwriting com LLM contra desfecho real (Home Credit), incluindo backtest com poder estatístico calculado a priori (n=564, bootstrap) e investigação de causa raiz até o limite de previsibilidade dos dados (AUC 0,56).

---

## Roteiro pra entrevista ("me conta sobre um projeto desafiador")

**Abertura — a pergunta, não a resposta:**
"Construí um agente de IA que decide crédito nos casos que um modelo de risco não consegue classificar com confiança — a 'zona cinzenta'. A pergunta que eu queria responder era simples de falar e difícil de responder direito: esse agente decide melhor que jogar uma moeda?"

*(pausa)*

**O primeiro número, e por que não confiei nele:**
"A primeira medição, com uma amostra pequena, deu uma separação de risco de +7 pontos percentuais entre quem o agente aprovava e negava. Parecia bom. Mas o intervalo de confiança cruzava zero — ou seja, estatisticamente, aquilo podia ser só coincidência de quem deu calote ou não naquela amostra específica."

**A decisão de gastar dinheiro de propósito:**
"Em vez de aceitar o número bonito, calculei quantos casos eu precisaria pra ter confiança de verdade — poder estatístico de 80%, pra detectar uma separação de 10 pontos. Deu setecentos e vinte e dois casos. Rodei, pagando a API do zero, de propósito."

**O resultado real:**
"Com a amostra certa, a separação caiu pra 1,3 pontos percentuais. O intervalo cruzava zero com folga. O agente não separava risco de forma detectável."

**O que fiz depois — essa é a parte que importa:**
"Podia ter parado aí. Em vez disso, investiguei o porquê. Primeiro achei que os sinais que o agente usava pra justificar a recomendação simplesmente não correlacionavam com o desfecho real — e não correlacionavam mesmo, correlação praticamente zero. Depois pensei: talvez o agente só não tivesse acesso à variável certa — o modelo campeão do projeto era dominado por três variáveis de escore externo que o agente nunca via. Escrevi até uma proposta de arquitetura pra expor uma dessas variáveis a ele."

*(pausa, mudança de tom)*

"E antes de implementar, testei a hipótese contra os dados que eu já tinha — de graça, sem gastar API. Aquela variável, que dominava a predição no dataset inteiro, praticamente não tinha correlação nenhuma **especificamente** na fatia onde o agente opera. Rejeitei minha própria proposta no mesmo dia."

**O achado final, o mais forte de todos:**
"Isso me levou ao teste mais direto possível: peguei o melhor modelo que o projeto tinha — não o agente, o classificador de verdade, treinado com todas as variáveis, de forma não-linear — e medi o AUC dele **só** dentro dessa fatia difícil. Deu 0,56. Pra comparação, 0,50 é jogar moeda, e 0,776 era o AUC do mesmo modelo na população inteira."

**A conclusão, dita sem rodeio:**
"Isso significa que a fatia onde eu queria que o agente decidisse bem está estruturalmente perto do limite do que dá pra prever com os dados que existem. Não é que o agente decide mal — é que praticamente nada decide bem ali, nem o melhor modelo do projeto. E eu só sei disso porque medi com rigor em vez de aceitar o primeiro número que parecia bom."

**Fechamento (se perguntarem "e daí, o projeto falhou?"):**
"Do jeito que a pergunta original foi feita — 'o agente decide melhor que o acaso' — a resposta é não, e é uma resposta bem sustentada. Mas o projeto não parou em 'não funcionou'. Ele constrói o instrumento de medição certo, mede com poder estatístico, e quando uma hipótese própria não se sustenta, eu descarto ela publicamente em vez de forçar. Prefiro chegar numa entrevista com isso do que com um resultado positivo que eu não teria certeza se era real."

---

## Se a pergunta seguinte for "o que você faria diferente / o que vem depois"

Resposta honesta, já registrada no projeto (débito #34, `AGENTS.md`):
- Não tentaria mais "dar mais sinal ao agente" — já testei e não é isso.
- Investigaria se a definição da zona cinzenta em si (a faixa de incerteza do modelo) é a correta, ou se está capturando junto casos genuinamente irredutíveis com casos onde ainda sobraria sinal — isso também já foi testado (segmentação por distância ao centro da banda) e descartado, então a resposta honesta é "já chequei essa também".
- O próximo movimento real seria em outro dataset ou com dado adicional (ex.: variáveis alternativas de crédito não presentes no Home Credit) — fora do escopo atual, mas é a hipótese que sobrou depois de eliminar as outras.
