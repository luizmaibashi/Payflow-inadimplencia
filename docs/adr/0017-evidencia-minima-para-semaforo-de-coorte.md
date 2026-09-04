# ADR-0017: Evidência mínima para o semáforo de coorte

**Data:** 2026-09-04
**Status:** Aceita
**Proposto por:** Luiz Maibashi

## Contexto

O semáforo anterior liberava `MANTER` a partir de AUC pontual, inclusive com
amostras pequenas. Também chamava de maduro qualquer target preenchido. Isso
produz falsa confiança: duas observações podem parecer perfeitas e um rótulo
preenchido cedo não prova que a janela de inadimplência terminou.

## Decisão

O PayFlow passa a separar três contratos explícitos:

1. maturação: `data_decisao + janela` precisa ocorrer até a data de referência;
2. suficiência: mínimo de contratos e eventos é configurado pela política;
3. qualidade: AUC, intervalo de confiança e Brier devem respeitar limites
   configurados.

O orquestrador converte falha do gate em `BLOQUEAR`, preservando o motivo e sem
executar o scorer. Todas as datas são normalizadas para UTC antes da comparação.

## Consequências

**Positivas:** evita sinal verde sem evidência, torna o resultado auditável e
mostra a diferença entre monitorar e simplesmente calcular métricas.

**Negativas:** haverá mais decisões `AGUARDAR`; a instituição precisa fornecer
limites e dados temporais reais. Isso é custo deliberado de governança, não
falha do modelo.

## Alternativas descartadas

| Opção | Motivo da rejeição |
|---|---|
| Manter tolerância AUC fixa de 0,03 | Não considera tamanho da amostra, eventos ou calibração. |
| Liberar por target não nulo | Confunde rótulo precoce com desfecho observado. |
| Retreinar automaticamente ao detectar queda | Pode amplificar ruído e exige governança inexistente no dataset público. |

## Validação

O comportamento será provado por `tests/test_estabilidade_coorte.py`,
`tests/test_politica_uso_modelo.py`, `tests/test_monitoramento_coorte.py` e
`tests/test_contrato_disponibilidade.py`. A decisão operacional não deve ser
`MANTER` sem cumprir todos os contratos acima.
