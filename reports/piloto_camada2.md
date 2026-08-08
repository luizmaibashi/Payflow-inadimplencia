# Piloto da Camada 2 contra gerador real

**Gerado por:** `scripts/piloto_camada2.py`  
**Modelo:** `gemini-2.5-flash` | temperatura 0 | **sem retry** (proposital)  
**Amostra:** sorteio simples de n=100 na zona cinzenta (2,102 casos), seed=42  
**Cenario do lote:** LGD=82% (fallback=False)

## Desfechos

| Desfecho | k | proporcao | IC95% (Wilson) |
|---|---|---|---|
| `ok` | 86 | 86.0% | [77.9%; 91.5%] |
| `memo_invalido` | 9 | 9.0% | [4.8%; 16.2%] |
| `teto` | 5 | 5.0% | [2.2%; 11.2%] |

**Latencia por caso:** mediana 17.3s, total 30.6 min
**Custo de transporte:** 540 pedidos ao gerador custaram 540 idas ao provider (**0 retries**). A diferenca e a taxa de falha bruta que o backoff absorve - sem ela, o `erro_provider` abaixo subestima a instabilidade real.
**Chamadas de ferramenta por caso:** mediana 2, max 3

## Custo medido

Uso reportado pelo provider em 540 resposta(s) (a contagem e medida; so a conversao em dolar e premissa da tabela de gemini consultada em 2026-08-06).

| | tokens |
|---|---|
| input | 552,495 |
| output (visivel) | 59,164 |
| thinking (cobrado como output) | 311,303 |
| **total** | **922,962** |

**Custo deste lote:** US$ 1.0919 (**US$ 0.0109 por caso**, n=100)

**Projecao para o projeto inteiro** (450 execucoes de caso: piloto + eval set de 150-200 do ADR-0004 §2.5 + 2a rodada + folga): **US$ 4.91** no `gemini-2.5-flash`.

Razao thinking/saida visivel: **5.3x** - e o multiplicador que estimativa por contagem de caracteres nao consegue enxergar, e que domina a conta nos modelos 2.5.

> ⚠️ **Leia os intervalos, nao as proporcoes.** Com n desta ordem, o IC de Wilson e largo o bastante para que a estimativa pontual nao sustente decisao de politica sozinha (ADR-0004 §2.5). O piloto serve para detectar falha GROSSA de encanamento, nao para calibrar taxa fina.

**Memos e traces brutos:** `data\processed\piloto_camada2_memos.jsonl` (fora do git).