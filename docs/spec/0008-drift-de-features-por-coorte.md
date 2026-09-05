# Spec 0008: Drift de features por coorte

**Data:** 2026-09-04
**Status:** Implementada e aprovada em 2026-09-04
**Dono da aprovação de merge:** Luiz Maibashi

## Objetivo

Mostrar se a população recebida pelo modelo mudou em relação ao treino, para
ajudar o gestor a distinguir mudança dos dados de deterioração do desempenho.

## Escopo

- comparar cada uma das seis features do proxy entre treino e coorte futura;
- calcular estatística KS apenas sobre valores numéricos não ausentes;
- medir taxa de ausência em cada lado e a diferença absoluta;
- classificar cada feature como `ESTAVEL`, `ALERTA`, `CRITICO` ou
  `INSUFICIENTE` por uma política explícita;
- incorporar o resumo de drift ao relatório reproduzível da spec 0007.

Não inclui p-valor, explicação causal, drift multivariado, retreino automático,
PSI, champion/challenger ou autorização de uso operacional.

## Critérios de aceitação

1. Feature ausente em qualquer lado falha com o nome da coluna.
2. Valor não numérico ou infinito falha explicitamente.
3. Amostra não nula abaixo do mínimo recebe `INSUFICIENTE`, nunca `ESTAVEL`.
4. KS ou ausência acima do limite de alerta recebe `ALERTA`.
5. KS ou ausência acima do limite crítico recebe `CRITICO`.
6. A maior gravidade vence quando KS e ausência discordam.
7. O relatório mostra, por coorte, quantas features ficaram em cada estado e
   quais apresentaram a maior mudança.
8. Testes devem falhar antes da implementação e a suíte completa deve passar.

## Restrições e riscos

Os dados Home Credit são anonimizados e locais; não há PII ou rede. A
estatística KS detecta mudança univariada, mas não diz a causa nem prova queda
de risco. Os limites são política de demonstração configurável. Uma instituição
deve calibrá-los com histórico, sazonalidade e custo de falso alarme.

## Input policy check

- dado sensível: não;
- escopo autorizado: monitoramento do dataset público já aceito e baixado;
- efeito externo: nenhum;
- aprovação humana obrigatória antes de merge: Luiz Maibashi.

## Evidência parcial

- TDD: o módulo inexistente e a integração ausente falharam antes do código.
- Testes focados: 19 passaram.
- Suíte completa: 256 passaram.
- `git diff --check`: sem erro.
- Predição antes da medição: 4 alertas e 2 críticas em 2020-H2.

## Execução real

| Coorte | Estáveis | Alertas | Críticas | Insuficientes | Destaque |
|---|---:|---:|---:|---:|---|
| 2019-Q4 | 5 | 0 | 1 | 0 | `inittransactionamount_650A`, KS 0,2318 |
| 2020-H1 | 5 | 1 | 0 | 0 | `inittransactionamount_650A`, KS 0,1905 |
| 2020-H2 | 3 | 3 | 0 | 0 | `inittransactionamount_650A`, KS 0,1529 |

O palpite para 2020-H2 superestimou a severidade: o observado foi 3 alertas e
nenhuma crítica. As features em alerta foram:

| Feature | Sinal | Evidência |
|---|---|---|
| `annuity_780A` | distribuição | KS 0,1369; ausência estável em 0,00% |
| `price_1097A` | cobertura | ausência 14,39% → 21,26%, diferença de 6,87 p.p. |
| `inittransactionamount_650A` | distribuição | KS 0,1529; ausência já alta, 88,91% → 90,99% |

## PAVC após execução

| Pilar | Resultado | Evidência |
|---|---|---|
| Advogado do diabo | Aprovado com limites | Drift não prova perda de AUC; AUC/Brier seguem no boletim separado. Limites são configuráveis e não disparam retreino. |
| Falsificabilidade | Aprovado | Coorte vazia, amostra insuficiente, constante, não numérico, infinito, feature ausente e limites inválidos possuem testes. A execução real processou 1.526.659 casos. |
| Explicabilidade | Aprovado com ajuste didático | O autor identificou que comportamento e dados mudam ao longo do tempo. Ajuste registrado: AUC estável não significa novo equilíbrio do modelo; significa que a ordenação aprendida no treino transferiu para a coorte, apesar do drift. |
