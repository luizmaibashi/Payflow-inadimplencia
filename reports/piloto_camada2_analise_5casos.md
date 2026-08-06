# Analise manual do piloto Camada 2 (n=5, selecionados dos 25 do piloto)

Este arquivo tem duas partes: um exemplo resolvido (pra voce ver como se faz)
e os 5 casos reais, cada um com espaco em branco pra voce preencher.

## As 4 rubricas (ADR-0004 SS2.2)

| #   | Rubrica                         | O que pergunta                                                                                                        |
| --- | ------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| 1   | **Groundedness** (ELIMINATORIA) | O numero citado no fato existe mesmo no retorno da ferramenta apontada?                                               |
| 2   | **Task completion**             | A recomendacao (APROVAR/NEGAR/DEFERIR) e defensavel dados os fatos? Se DEFERIR, disse o que faltou de forma concreta? |
| 3   | **Trajectory**                  | O agente usou as ferramentas com eficiencia (sem repetir, sem pular a que faltava)?                                   |
| 4   | **Cegueira ao score**           | Nenhum fato menciona score/probabilidade/nota de risco?                                                               |

Groundedness e ELIMINATORIA: se falhar, o caso falhou - nao precisa julgar as
outras 3, so anote a evidencia.

## Exemplo resolvido - caso `151515`

**O que a ferramenta `consultar_bureau` devolveu de verdade:**
```
n_contratos: 18   n_ativos: 5   n_em_atraso_hoje: 0   utilizacao: 0.3205
```

**O que o memo disse, citando essa ferramenta:**
> "O cliente possui um historico de credito extenso em outras instituicoes,
> com **18 contratos** registrados, sendo **5 ativos** e **nenhum em atraso**
> atualmente." ... "A utilizacao do limite de credito ... e de aproximadamente
> **32%**"

**Cross-check:** 18 = 18 ✓ | 5 = 5 ✓ | 0 atraso = 0 ✓ | 32% ≈ 0.3205 ✓
Todos os numeros do fato aparecem, sem distorcao, no retorno bruto da
ferramenta que o memo apontou como fonte. **Groundedness: OK.**

**Recomendacao foi APROVAR, e os 4 fatos sao todos favoraveis** (nenhum
desfavoravel ou neutro) - recomendacao bate com os fatos. **Task
completion: OK.**

Isso e o nivel de checagem que se pede para cada caso abaixo: pegar o numero
do texto e achar ele (ou a conta que leva nele) no bloco "Dados brutos".

---


---
## Caso 1/5 — cliente `282047`

**Por que este caso foi escolhido:** OK limpo — todos os fatores na mesma direcao

**Desfecho automatico:** `ok` (mede so formato/mecanica - NAO substitui seu julgamento)  
**Chamadas:** 3  
**Violacoes de trajetoria (automaticas):** nenhuma  


**Dados brutos das ferramentas:**

`consultar_bureau`:
```
  tem_registro: True
  n_contratos: 12
  n_ativos: 3
  n_em_atraso_hoje: 0
  divida_total: 540013.5
  credito_total: 2276892.0
  utilizacao: 0.2372
  tem_historico_mensal: True
```
`consultar_historico_bureau`:
```
  tem_registro: True
  meses_observados: 70
  meses_em_dia: 61
  meses_em_atraso: 0
  meses_sem_informacao: 9
```
`consultar_pagamentos`:
```
  tem_registro: True
  n_parcelas: 25
  n_nunca_pagas: 0
  n_pagas_com_atraso: 2
  n_pagas_a_menor: 0
  atraso_medio_dias: -6.44
  pior_atraso_dias: 4
  dias_desde_ultimo_atraso: 337
  deficit_medio_pct: 0.0
  n_pagas_a_maior: 0
```

**Memo:**
```
Cliente:      282047
Recomendacao: APROVAR

Fatos que pesaram:
  + O cliente possui 12 contratos e 3 ativos em outras instituições, sem nenhum contrato em atraso hoje.   [fonte: consultar_bureau]
  + A utilização do limite de crédito em outras instituições é baixa, aproximadamente 23.7%.   [fonte: consultar_bureau]
  + O histórico mensal em outras instituições mostra 61 meses em dia de um total de 70 meses observados, sem registro de atrasos.   [fonte: consultar_historico_bureau]
  + Nos contratos anteriores com esta casa, o cliente pagou 23 de 25 parcelas em dia ou adiantado, com apenas 2 pagas com atraso mínimo (pior atraso de 4 dias) e o último atraso há 337 dias.   [fonte: consultar_pagamentos]
  + O atraso médio nos pagamentos anteriores com esta casa é negativo (-6.44 dias), indicando que o cliente tende a pagar adiantado.   [fonte: consultar_pagamentos]

Cenario assumido:
  Perda em caso de calote: 82%   [fonte: BCB SGS serie 432 (Selic meta), consultada em 2026-08-06]
```


**Seu veredito:**
- [OK] 1. Groundedness: `OK` / `FALHA` — evidencia: os numeros citados no memo batem com os numeros das ferramentas
- [OK ] 2. Task completion: `OK` / `FALHA` — evidencia: a recomendacao de aprovar e defensavel dados os fatos
- [OK] 3. Trajectory: `OK` / `FALHA` — evidencia: o agente usou todas as ferramentas sem repetir e em ordem
- [OK] 4. Cegueira ao score: `OK` / `FALHA` — evidencia: 
- Nota geral: ___________________________________________________________


---
## Caso 2/5 — cliente `292411`

**Por que este caso foi escolhido:** Groundedness QUEBRADA — falha mecanica real

**Desfecho automatico:** `groundedness` (mede so formato/mecanica - NAO substitui seu julgamento)  
**Chamadas:** 2  
**Violacoes de trajetoria (automaticas):** nenhuma  


**Erro:**
```
fato cita ferramenta nao chamada: ['consultar_bureau, consultar_pagamentos']
```


**Dados brutos das ferramentas:**

`consultar_bureau`:
```
  tem_registro: False
  n_contratos: 0
  n_ativos: 0
  n_em_atraso_hoje: 0
  tem_historico_mensal: False
```
`consultar_pagamentos`:
```
  tem_registro: False
  n_parcelas: 0
  n_nunca_pagas: 0
  n_pagas_com_atraso: 0
  n_pagas_a_menor: 0
  n_pagas_a_maior: 0
```

*(sem memo — caso nao concluiu)*


**Seu veredito:**
- [FALHA] 1. Groundedness: `OK` / `FALHA` — evidencia: ___________________________
- [ ] 2. Task completion: `OK` / `FALHA` — evidencia: _________________________
- [ ] 3. Trajectory: `OK` / `FALHA` — evidencia: ______________________________
- [ ] 4. Cegueira ao score: `OK` / `FALHA` — evidencia: _______________________
- Nota geral: ___________________________________________________________


---
## Caso 3/5 — cliente `333746`

**Por que este caso foi escolhido:** memo_invalido — nao cumpriu o contrato de formato

**Desfecho automatico:** `memo_invalido` (mede so formato/mecanica - NAO substitui seu julgamento)  
**Chamadas:** —  
**Violacoes de trajetoria (automaticas):** nenhuma  


**Erro:**
```
memo nao bateu com o contrato: 1 validation error for MemoCredito
fatores_cliente
  List should have at least 3 items after validation, not 2 [type=too_short, input_value=[{'fato': 'O cliente não...'peso': 'desfavoravel'}], input_type=list]
    For further information visit https://errors.pydantic.dev/2.13/v/too_short
```


*(sem memo — caso nao concluiu)*


**Seu veredito:**
- [FALHA ] 1. Groundedness: `OK` / `FALHA` — evidencia: ___________________________
- [ ] 2. Task completion: `OK` / `FALHA` — evidencia: _________________________
- [ ] 3. Trajectory: `OK` / `FALHA` — evidencia: ______________________________
- [ ] 4. Cegueira ao score: `OK` / `FALHA` — evidencia: _______________________
- Nota geral: ___________________________________________________________


---
## Caso 4/5 — cliente `344012`

**Por que este caso foi escolhido:** DEFERIR — checar se informacao_faltante e concreta

**Desfecho automatico:** `ok` (mede so formato/mecanica - NAO substitui seu julgamento)  
**Chamadas:** 2  
**Violacoes de trajetoria (automaticas):** nenhuma  


**Dados brutos das ferramentas:**

`consultar_bureau`:
```
  tem_registro: False
  n_contratos: 0
  n_ativos: 0
  n_em_atraso_hoje: 0
  tem_historico_mensal: False
```
`consultar_pagamentos`:
```
  tem_registro: False
  n_parcelas: 0
  n_nunca_pagas: 0
  n_pagas_com_atraso: 0
  n_pagas_a_menor: 0
  n_pagas_a_maior: 0
```

**Memo:**
```
Cliente:      344012
Recomendacao: DEFERIR

Fatos que pesaram:
  . O cliente não possui histórico de crédito registrado em outras instituições financeiras, indicando ausência de dívidas ou contratos anteriores no bureau.   [fonte: consultar_bureau]
  + Não há contratos ativos ou em atraso registrados para o cliente em outras instituições.   [fonte: consultar_bureau]
  . O cliente não possui histórico de pagamentos de contratos anteriores com esta instituição.   [fonte: consultar_pagamentos]

Cenario assumido:
  Perda em caso de calote: 82%   [fonte: BCB SGS serie 432 (Selic meta), consultada em 2026-08-06]

O que faltou saber:
  - Comprovação de renda
  - Informações sobre estabilidade empregatícia
  - Dados sobre patrimônio ou outras garantias
```


**Seu veredito:**
- [OK] 1. Groundedness: `OK` / `FALHA` — evidencia: ___________________________
- [ OK] 2. Task completion: `OK` / `FALHA` — evidencia: _________________________
- [FALHA ] 3. Trajectory: `OK` / `FALHA` — evidencia: FALTA INFORMAÇÕES SOBRE PAGAMENTO  ______________________________
- [ ] 4. Cegueira ao score: `OK` / `FALHA` — evidencia: _______________________
- Nota geral: ___________________________________________________________


---
## Caso 5/5 — cliente `307444`

**Por que este caso foi escolhido:** Task completion AMBIGUO — 3 favoraveis x 2 desfavoraveis, recomendou NEGAR

**Desfecho automatico:** `ok` (mede so formato/mecanica - NAO substitui seu julgamento)  
**Chamadas:** 3  
**Violacoes de trajetoria (automaticas):** nenhuma  


**Dados brutos das ferramentas:**

`consultar_bureau`:
```
  tem_registro: True
  n_contratos: 4
  n_ativos: 3
  n_em_atraso_hoje: 0
  divida_total: 206167.5
  credito_total: 348505.245
  utilizacao: 0.5916
  tem_historico_mensal: True
```
`consultar_historico_bureau`:
```
  tem_registro: True
  meses_observados: 38
  meses_em_dia: 35
  meses_em_atraso: 0
  meses_sem_informacao: 3
```
`consultar_pagamentos`:
```
  tem_registro: True
  n_parcelas: 52
  n_nunca_pagas: 0
  n_pagas_com_atraso: 18
  n_pagas_a_menor: 36
  atraso_medio_dias: -8.2308
  pior_atraso_dias: 17
  dias_desde_ultimo_atraso: 1188
  deficit_medio_pct: 0.3462
  n_pagas_a_maior: 0
```

**Memo:**
```
Cliente:      307444
Recomendacao: NEGAR

Fatos que pesaram:
  - O cliente realizou 36 pagamentos a menor em 52 parcelas totais em contratos anteriores nesta casa, resultando em um déficit médio de 34.6% do valor devido.   [fonte: consultar_pagamentos]
  + O cliente não possui contratos em atraso atualmente com outras instituições e seu histórico de crédito externo mostra 0 meses em atraso em 38 meses observados.   [fonte: consultar_bureau]
  - Em contratos anteriores nesta casa, 18 das 52 parcelas foram pagas com atraso, com o pior atraso sendo de 17 dias.   [fonte: consultar_pagamentos]
  + O último atraso registrado em pagamentos nesta casa ocorreu há 1188 dias (mais de 3 anos), indicando uma melhora no comportamento recente.   [fonte: consultar_pagamentos]
  . A utilização de crédito em outras instituições é de aproximadamente 59% do limite total disponível.   [fonte: consultar_bureau]
  + Apesar dos pagamentos a menor e atrasos, o cliente nunca deixou de pagar completamente uma parcela em contratos anteriores nesta casa.   [fonte: consultar_pagamentos]

Cenario assumido:
  Perda em caso de calote: 82%   [fonte: BCB SGS serie 432 (Selic meta), consultada em 2026-08-06]
```


**Seu veredito:**
- [ OK] 1. Groundedness: `OK` / `FALHA` — evidencia: ___________________________
- [ OK] 2. Task completion: `OK` / `FALHA` — evidencia: _________________________
- [FALHA] 3. Trajectory: `OK` / `FALHA` — evidencia: FALTO USAR A FONTE CONSULTAR_HISTORICO_BUREAU ______________________________
- [ OK] 4. Cegueira ao score: `OK` / `FALHA` — evidencia: _______________________
- Nota geral: ___________________________________________________________



---

## Resumo (preencher por ultimo)

- Groundedness: __ / 5 OK
- Task completion: __ / 5 OK
- Trajectory: __ / 5 OK
- Cegueira ao score: __ / 5 OK

## Padroes observados

(O que se repete entre casos - nao liste cada caso, liste o PADRAO.)

-

## Casos-exemplo para virar teste

(1 exemplo concreto por rubrica que falhou: cliente_id + o que quebrou.)

-
