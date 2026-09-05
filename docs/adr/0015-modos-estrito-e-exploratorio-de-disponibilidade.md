# ADR-0015: Modos estrito e exploratório de disponibilidade

**Data:** 2026-09-04
**Status:** Accepted
**Contexto:** PayFlow V3 — contrato point-in-time do Home Credit Stability

## Contexto

O dataset público permite pesquisar variáveis que parecem vir da proposta, mas
não fornece a evidência operacional que provaria seu instante de geração. O
proxy de seis campos teve AUC próxima de 0,61 fora do tempo, porém não é
point-in-time aprovado.

## Decisão

Adicionar dois modos ao contrato de disponibilidade:

- **ESTRITO:** aceita somente `PERMITIDA`, com evidência documentada.
- **EXPLORATORIO:** aceita `PERMITIDA` e `PROXY_SEMANTICA`, sempre rotulada como
  pesquisa e sem afirmação de produção.

`BLOQUEADA` e `DESCONHECIDA` falham nos dois modos. O padrão é `ESTRITO`.

## Consequências

- A pesquisa mede o trade-off do proxy sem confundi-lo com validação operacional.
- Uma feature proxy não atravessa para o modo estrito por esquecimento.
- Dois modos exigem testes e um rótulo visível na futura interface.

## Alternativas descartadas

| Opção | Motivo para não escolher |
|---|---|
| Bloquear todos os proxies | Impede medir o trade-off do dataset público. |
| Liberar proxy como permitida | Confunde pesquisa com validação operacional. |
| Usar só comentário de notebook | Falha quando o código é reutilizado. |

## Validação e PAVC

- O padrão estrito bloqueia `PROXY_SEMANTICA`.
- O modo exploratório libera o proxy e registra o modo no relatório.
- `DESCONHECIDA` continua bloqueada nos dois modos.
- O risco principal é uma flag permissiva vazar para produção; mitigação:
  padrão estrito e testes de regressão.

**Resultado PAVC:** aprovado para a fronteira de contrato. Os testes provam o
padrão estrito, a liberação exploratória explícita e o bloqueio de feature
desconhecida nos dois modos. A futura interface ainda precisa exibir o modo
antes de qualquer métrica ou recomendação.
