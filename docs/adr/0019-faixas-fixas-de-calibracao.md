# ADR-0019: Faixas fixas de calibração derivadas do treino

**Data:** 2026-09-04
**Status:** Accepted
**Proposto por:** Luiz Maibashi
**Contexto:** PayFlow V3, confiabilidade de probabilidade por coorte

## Contexto

AUC estável prova que a ordenação relativa transferiu para as coortes futuras,
mas não prova que um score de 5% ainda represente aproximadamente 5% de
inadimplência. O Brier global pode esconder erro concentrado justamente nas
faixas que mudam decisões de crédito.

## Decisão

Criar dez faixas pelos quantis dos scores do treino e reutilizar os mesmos
limites em todas as coortes. `avaliar_calibracao_faixas` medirá, em cada faixa,
score médio, inadimplência observada, IC95% de Wilson e o gap observado menos
previsto. A classificação usará uma tolerância absoluta configurável e mínimo
de contratos/eventos.

Faixas futuras nunca serão recalculadas com dados da própria coorte. Scores
fora do contrato ou limites repetidos falham explicitamente. O diagnóstico não
recalibra nem retreina o modelo sozinho.

## Consequências

### Positivas

- cada faixa mantém o mesmo significado entre períodos;
- erro localizado deixa de desaparecer dentro do Brier agregado;
- o gestor sabe se está subestimando ou superestimando risco na região que
  afeta aprovação, provisão e preço.

### Negativas

- as faixas têm larguras diferentes;
- mudanças grandes na distribuição podem concentrar uma coorte em poucas
  faixas;
- limites e tolerância precisam ser recalibrados para uma carteira real.

## Alternativas descartadas

| Alternativa | Vantagem | Motivo da rejeição |
|---|---|---|
| Quantis recalculados por coorte | Mesmo `n` em cada período | Troca a régua e mascara mudança de composição. |
| Faixas fixas de 10 pontos percentuais | Leitura intuitiva | Com default perto de 3%, deixaria várias faixas quase vazias. |
| Apenas Brier global | Já existe no pipeline | Pode compensar erros de sinais opostos e esconder a faixa relevante. |
| Recalibração automática | Corrige o score imediatamente | Automatiza uma intervenção sem validar causa, estabilidade ou custo. |

## Impacto e validação

Sem o diagnóstico, um score numericamente errado pode alimentar valor esperado,
provisão ou política de aprovação mesmo com AUC estável. Com ele, o tempo de
investigação cai porque `avaliar_calibracao_faixas` mostra onde e em qual
direção a probabilidade se afastou do observado. Não será inventado ROI
monetário sem carteira, LGD e política reais.

Critérios: testes de contrato e casos de borda, integração com o experimento,
execução nas três coortes e revisão humana do diff. Referência:
`docs/spec/0009-calibracao-por-faixa-de-score.md`.

## Resultado observado

Os mesmos dez limites atravessaram as três coortes. Em `2020-H2`, nove faixas
ficaram dentro da tolerância absoluta de 1 p.p.; a faixa superior previu 5,25%
e observou 5,35% (IC95% [4,98%; 5,74%]). A decisão localizou uma mudança de
nível que AUC estável não mostrava: H2 ficou mais seguro no agregado, mas a
cauda superior continuou bem calibrada. Nenhuma recalibração automática foi
acionada.
