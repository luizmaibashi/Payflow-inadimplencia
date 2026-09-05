---
tipo: pesquisa
status: resolvido
criado: 2026-09-04
---

# Ticket 0002: Inventário e disponibilidade de features

## Bloqueio

O dataset Stability contém variáveis posteriores a `date_decision`. Algumas agregações numéricas podem também esconder informação futura. Sem provar origem e instante de disponibilidade, não existe modelo point-in-time confiável.

## Resultado

O baseline exploratório usa 128 features numéricas da tabela estática:

- 69 candidatas estáticas/de aplicação, mas ainda sem prova de origem point-in-time;
- 57 candidatas históricas, que exigem prova de que a janela termina na data de decisão;
- 2 precisam de revisão obrigatória pela própria descrição: `annuitynextmonth_57A` (“valor da parcela do próximo mês”) e `avgdpdtolclosure24_3658938P` (usa data atual para contrato em aberto);
- 15 colunas diretas de data ficam bloqueadas até ter regra explícita de disponibilidade.

Todas as 128 têm definição no arquivo oficial `feature_definitions.csv`, mas definição não prova instante de disponibilidade. Portanto, o contrato inicial deve começar em **desconhecido** e só permitir uma feature após evidência documentada. O gate em modo estrito não poderá rodar um modelo point-in-time ainda; o baseline atual continuará marcado como exploratório, não produtivo.

### Experimento de proxy semântico

Foi testado um recorte deliberadamente pequeno de campos que a descrição sugere
serem da proposta atual: `annuity_780A`, `credamount_770A`, `downpmt_116A`,
`price_1097A`, `maininc_215A` e `inittransactionamount_650A`. O modelo foi
treinado até 2019-09-30 e avaliado fora do tempo:

| Coorte | n | AUC (IC95% aproximado) | Brier (IC95% aproximado) |
|---|---:|---:|---:|
| 2019-Q4 | 337.005 | 0,6147 [0,6093; 0,6201] | 0,0346 [0,0340; 0,0352] |
| 2020-H1 | 305.657 | 0,6082 [0,6027; 0,6137] | 0,0368 [0,0361; 0,0374] |
| 2020-H2 | 150.240 | 0,6180 [0,6074; 0,6285] | 0,0205 [0,0199; 0,0212] |

O sinal cai de aproximadamente 0,775 no baseline amplo para aproximadamente
0,61, mas se mantém estável nas três coortes. Isso confirma a utilidade do
monitoramento, não a permissão das seis features: o recorte é um **proxy
semântico exploratório**, pois a descrição oficial ainda não prova o momento
de geração. Ele não altera o contrato estrito nem autoriza execução produtiva.
