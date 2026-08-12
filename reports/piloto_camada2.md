# Piloto da Camada 2 contra gerador real

**Gerado por:** `scripts/piloto_camada2.py`  
**Modelo:** `gemini-2.5-flash` | temperatura 0 | **sem retry** (proposital)  
**Amostra:** sorteio simples de n=722 na zona cinzenta (2,102 casos), seed=42  
**Cenario do lote:** LGD=82% (fallback=False)

## Desfechos

| Desfecho | k | proporcao | IC95% (Wilson) |
|---|---|---|---|
| `ok` | 563 | 78.0% | [74.8%; 80.8%] |
| `memo_invalido` | 110 | 15.2% | [12.8%; 18.0%] |
| `erro_provider` | 25 | 3.5% | [2.4%; 5.1%] |
| `teto` | 16 | 2.2% | [1.4%; 3.6%] |
| `groundedness` | 7 | 1.0% | [0.5%; 2.0%] |
| `ok_com_violacao` | 1 | 0.1% | [0.0%; 0.8%] |

**Latencia por caso:** mediana 18.5s, total 225.6 min
**Custo de transporte:** 3786 pedidos ao gerador custaram 3841 idas ao provider (**55 retries**). A diferenca e a taxa de falha bruta que o backoff absorve - sem ela, o `erro_provider` abaixo subestima a instabilidade real.
**Chamadas de ferramenta por caso:** mediana 2, max 3

## Custo medido

Uso reportado pelo provider em 3761 resposta(s) (a contagem e medida; so a conversao em dolar e premissa da tabela de gemini consultada em 2026-08-06).

| | tokens |
|---|---|
| input | 3,828,752 |
| output (visivel) | 398,122 |
| thinking (cobrado como output) | 2,149,188 |
| **total** | **6,376,062** |

**Custo deste lote:** US$ 7.5169 (**US$ 0.0104 por caso**, n=722)

**Projecao para o projeto inteiro** (450 execucoes de caso: piloto + eval set de 150-200 do ADR-0004 §2.5 + 2a rodada + folga): **US$ 4.69** no `gemini-2.5-flash`.

Razao thinking/saida visivel: **5.4x** - e o multiplicador que estimativa por contagem de caracteres nao consegue enxergar, e que domina a conta nos modelos 2.5.

## Violacoes de trajetoria (rubrica #4, mecanica)

1 em 722 casos. Nao sao eliminatorias - o memo passou no gate de groundedness e mesmo assim tem defeito.

- `184127`: DEFERIU sem consultar ['consultar_pagamentos'] - aplicaveis a qualquer cliente

> ⚠️ **Leia os intervalos, nao as proporcoes.** Com n desta ordem, o IC de Wilson e largo o bastante para que a estimativa pontual nao sustente decisao de politica sozinha (ADR-0004 §2.5). O piloto serve para detectar falha GROSSA de encanamento, nao para calibrar taxa fina.

**Memos e traces brutos:** `data\processed\piloto_camada2_memos.jsonl` (fora do git).