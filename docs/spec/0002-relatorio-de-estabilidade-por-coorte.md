# Spec 0002 — Relatório de estabilidade por coorte

**Data:** 2026-09-04
**Status:** Implementada e aprovada em 2026-09-04
**Dono da decisão e aprovação de merge:** Luiz Maibashi

## 1. Objetivo

Medir se um modelo de crédito continua útil quando chegam novas coortes, sem
fingir que já sabemos o resultado de empréstimos recentes. Para cada mês, o
relatório deve separar três perguntas simples:

1. Quantos pedidos chegaram e receberam previsão?
2. Quantos já completaram o prazo necessário para revelar inadimplência?
3. Entre os que completaram esse prazo, o modelo continuou separando risco alto
   de risco baixo (AUC) e acertando a probabilidade média (Brier)?

O ganho de negócio é detectar perda de confiabilidade antes que um score seja
usado como se estivesse validado. Não é prova de aumento de lucro, pois o
dataset não traz preço, exposição nem decisões reais de carteira.

## 2. Escopo

### Incluído

- Relatório determinístico por coorte a partir de previsão já calculada e
  target observado.
- Total de casos, previsões válidas, targets amadurecidos e população realmente
  avaliável.
- Taxa de inadimplência com `n` e intervalo de confiança de Wilson de 95%.
- AUC ROC e Brier somente quando a coorte tiver target amadurecido, previsão
  válida e as duas classes do target.
- Estado explícito para coorte vazia, target não amadurecido, previsão ausente
  e target sem variação.

### Fora de escopo

- Gerar as previsões ou treinar o modelo. Isso só ocorre depois que o Gate de
  disponibilidade temporal aprovar as features.
- Definir limites operacionais VERDE/AMARELO/VERMELHO para bloquear modelo.
  Essa política exige uma tolerância de risco que o dataset público não fornece.
- Inferir causalidade, lucro, LGD ou estratégia de cobrança.
- Ler dados reais, PII ou credenciais.

## 3. Critérios de aceitação

1. Uma coorte com target amadurecido e duas classes retorna `n`, taxa de
   inadimplência, IC 95%, AUC e Brier.
2. Uma coorte sem target retorna `AGUARDAR_MATURACAO`, sem AUC/Brier falsos.
3. Uma coorte com uma única classe retorna `TARGET_SEM_VARIACAO`, sem AUC.
4. Um DataFrame vazio retorna `COORTE_VAZIA` em vez de erro ou métrica inventada.
5. Previsão ausente, fora de `[0, 1]` ou target fora de `{0, 1}` é recusado de
   modo explícito.
6. Os testes novos e a suíte existente continuam verdes.

## 4. Restrições e riscos

- AUC indica ordenação, não retorno financeiro; Brier indica qualidade de
  probabilidade, não política de crédito.
- Uma coorte recente pode estar com target ausente por maturação, não porque o
  modelo ficou bom ou ruim.
- Mudança de taxa de inadimplência pode ser alteração do público atendido, não
  falha do modelo. O relatório mede o sinal; investigar causa é uma etapa
  posterior.
- Dados públicos anonimizados do Home Credit permanecem fora do Git.

## 5. Input-policy-check

- **Dados sensíveis:** não. O contrato recebe apenas DataFrame anonimizado de
  experimentação.
- **Escopo autorizado:** medição pós-desfecho definida no fluxo explicado pelo
  Luiz e no Ticket 0004.
- **Aprovação:** Luiz revisa o diff e os resultados antes de merge. O agente
  não aprova a própria entrega.

## 6. Evidência esperada

- Esta spec.
- Teste inicialmente vermelho.
- Implementação mínima e testes para todos os estados de coorte.
- Resultado da suíte completa.
- Revisão humana do diff antes de merge.

**Evidência executada:** teste inicialmente vermelho por ausência do módulo;
depois 9 testes específicos passaram (97% de cobertura do módulo) e a suíte
completa passou com 212 testes.
