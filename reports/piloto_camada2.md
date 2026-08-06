# Piloto da Camada 2 contra gerador real

**Gerado por:** `scripts/piloto_camada2.py`  
**Modelo:** `gemini-2.5-flash` | temperatura 0 | **sem retry** (proposital)  
**Amostra:** sorteio simples de n=25 na zona cinzenta (2,102 casos), seed=42  
**Cenario do lote:** LGD=82% (fallback=False)

## Desfechos

| Desfecho | k | proporcao | IC95% (Wilson) |
|---|---|---|---|
| `ok` | 21 | 84.0% | [65.3%; 93.6%] |
| `groundedness` | 2 | 8.0% | [2.2%; 25.0%] |
| `memo_invalido` | 2 | 8.0% | [2.2%; 25.0%] |

**Latencia por caso:** mediana 20.0s, total 9.0 min
**Custo de transporte:** 133 pedidos ao gerador custaram 133 idas ao provider (**0 retries**). A diferenca e a taxa de falha bruta que o backoff absorve - sem ela, o `erro_provider` abaixo subestima a instabilidade real.
**Chamadas de ferramenta por caso:** mediana 2, max 3

## Custo medido

Uso reportado pelo provider em 133 resposta(s) (a contagem e medida; so a conversao em dolar e premissa da tabela de gemini consultada em 2026-08-06).

| | tokens |
|---|---|
| input | 107,869 |
| output (visivel) | 13,566 |
| thinking (cobrado como output) | 88,159 |
| **total** | **209,594** |

**Custo deste lote:** US$ 0.2867 (**US$ 0.0115 por caso**, n=25)

**Projecao para o projeto inteiro** (450 execucoes de caso: piloto + eval set de 150-200 do ADR-0004 §2.5 + 2a rodada + folga): **US$ 5.16** no `gemini-2.5-flash`.

Razao thinking/saida visivel: **6.5x** - e o multiplicador que estimativa por contagem de caracteres nao consegue enxergar, e que domina a conta nos modelos 2.5.

> ⚠️ **Leia os intervalos, nao as proporcoes.** Com n desta ordem, o IC de Wilson e largo o bastante para que a estimativa pontual nao sustente decisao de politica sozinha (ADR-0004 §2.5). O piloto serve para detectar falha GROSSA de encanamento, nao para calibrar taxa fina.

**Memos e traces brutos:** `data\processed\piloto_camada2_memos.jsonl` (fora do git).