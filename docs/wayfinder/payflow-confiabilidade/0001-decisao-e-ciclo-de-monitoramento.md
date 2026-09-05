---
tipo: tarefa-simples
status: resolvido
criado: 2026-09-04
---

# Ticket 0001: Decisão e ciclo de monitoramento

## Bloqueio

O projeto não tinha uma decisão de negócio explícita. Sem ela, um dashboard de métricas seria só enfeite.

## Resultado

O gestor de risco recebe uma nova coorte mensal e o PayFlow executa este ciclo:

1. verifica se as features existiam no dia da decisão;
2. bloqueia dados futuros ou desconhecidos;
3. roda o modelo apenas se os dados passarem;
4. quando o default amadurece, compara previsão e resultado real;
5. devolve VERDE (manter), AMARELO (revisar) ou VERMELHO (bloquear).

Confirmado pelo autor em 2026-09-04 com a frase: “devemos rodar o modelo e verificar se ele continua acertando quando chegam dados novos”.
