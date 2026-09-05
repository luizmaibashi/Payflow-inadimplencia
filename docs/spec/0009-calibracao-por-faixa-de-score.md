# Spec 0009: Calibração por faixa de score

**Data:** 2026-09-04
**Status:** Implementada; revisão humana aprovada em 2026-09-04
**Dono da aprovação de merge:** Luiz Maibashi

## Objetivo

Verificar se a probabilidade prevista continua correspondendo à inadimplência
observada dentro de faixas comparáveis de risco. O resultado deve permitir ao
gestor distinguir um modelo que ainda ordena bem de um modelo que atribui
probabilidades economicamente enganosas.

## Escopo

- criar dez faixas pelos quantis do score do treino;
- congelar esses limites e reutilizá-los em todas as coortes futuras;
- reportar por faixa `n`, inadimplentes, score médio, taxa observada com IC95%,
  diferença observado menos previsto e estado de calibração;
- classificar como `APROXIMADA`, `SUBESTIMA_RISCO`, `SUPERESTIMA_RISCO` ou
  `INSUFICIENTE` por uma política explícita;
- incorporar o diagnóstico ao experimento reproduzível e ao relatório.

Não inclui recalibração automática, mudança do semáforo de uso, dashboard,
escolha de apetite de risco institucional ou autorização operacional.

## Critérios de aceitação

1. Os limites são derivados somente dos scores do treino e permanecem iguais
   entre as coortes.
2. Scores ausentes, não numéricos, infinitos ou fora de `[0, 1]` falham
   explicitamente.
3. Limites repetidos, que impedem formar as dez faixas, falham em vez de
   reduzir silenciosamente a granularidade.
4. Toda faixa reporta quantidade de propostas e inadimplentes.
5. Toda proporção observada vem com IC95% de Wilson.
6. Faixa abaixo do mínimo de observações ou eventos recebe `INSUFICIENTE`.
7. Diferença absoluta dentro da tolerância recebe `APROXIMADA`; acima dela, o
   sinal informa se o modelo subestima ou superestima o risco.
8. O relatório permite localizar as faixas de maior score e traduz o sinal
   para ação de negócio sem recomendar recalibração automática.
9. Os testes falham antes da implementação e a suíte completa termina verde.

## Restrições e riscos

As seis features continuam em `PROXY_SEMANTICA`; portanto, o diagnóstico é de
pesquisa. Quantis equilibram o número de propostas por faixa, mas produzem
intervalos de score com larguras diferentes. A tolerância inicial é parâmetro
de demonstração, não apetite de risco de uma instituição.

## Input policy check

- dado sensível: não; dataset público e anonimizado;
- escopo autorizado: diagnóstico local do modelo já treinado;
- efeito externo: nenhum;
- aprovação humana obrigatória antes de merge: Luiz Maibashi.

## Predição antes da medição

Luiz prevê que, em `2020-H2`, as probabilidades acertarão aproximadamente a
inadimplência observada, sobretudo nas faixas de maior score.

## PAVC pré-implementação

1. **Faixas móveis poderiam esconder drift.** Mitigação: limites congelados a
   partir do treino.
2. **Amostra enorme poderia transformar diferença minúscula em alerta.**
   Mitigação: IC95% para incerteza e tolerância absoluta separada para decisão.
3. **Poucos eventos poderiam produzir falsa confiança nas faixas baixas.**
   Mitigação: mínimo explícito de observações e inadimplentes.

Casos de borda obrigatórios: entrada vazia, score constante, score inválido,
faixa sem eventos e observação exatamente no limite entre faixas. Concorrência
não se aplica ao fluxo local e somente leitura; temporalmente, nenhum limite
pode ser recalculado com a coorte futura.

## Evidência de execução

- TDD vermelho: import do módulo inexistente falhou antes da implementação.
- Testes focados: 25 passaram após a revisão.
- Suíte completa final: 275 passaram.
- Execução real: 1.526.659 propostas, com limites derivados de 733.757 casos
  de treino e aplicados sem alteração às três coortes.
- Relatório: `reports/proxy_estabilidade_com_calibracao.md`.

### Resultado de 2020-H2

Nove das dez faixas ficaram dentro da tolerância prática de 1 p.p. A faixa 6
superestimou o risco por 1,02 p.p., apenas 0,02 p.p. além do limite. Na faixa
de maior score, a previsão média foi 5,25% e a inadimplência observada foi
5,35% (708 eventos em 13.241 propostas; IC95% [4,98%; 5,74%]), gap de +0,10
p.p. A predição de Luiz foi confirmada para a região de maior risco.

O resultado não diz que a calibração foi idêntica em todos os períodos.
`2019-Q4` subestimou risco nas faixas 5 a 10; `2020-H1`, nas faixas 6, 9 e 10.
Em `2020-H2`, a queda da taxa agregada para 2,11% tornou o modelo conservador
na maior parte da escala, enquanto a faixa superior permaneceu alinhada.

## PAVC pós-execução

| Pilar | Resultado | Evidência |
|---|---|---|
| Advogado do diabo | Aprovado com limites | Faixas congeladas impediram troca de régua; tolerância prática evitou tratar todo desvio estatístico como material; nenhuma ação automática foi adicionada. |
| Falsificabilidade | Aprovado | Vazio, score constante/inválido, poucos eventos, fronteira de faixa e as três coortes reais foram testados. |
| Explicabilidade | Aprovado após aula e reexplicação | O autor explicou que recalcular quantis cria faixas diferentes entre períodos e que a ordem pode permanecer correta mesmo com as probabilidades, as "etiquetas", erradas. Ajuste final: os valores podem mudar sem trocar a ordem dos clientes. |
