# Backtest da Camada 2 — agente vs. default real (ADR-0004 §2.1)

**Gerado por:** `scripts/backtest_camada2.py`  
**Pergunta:** as recomendações do agente (APROVAR/NEGAR/DEFERIR) separam risco real (`TARGET`) na zona cinzenta?

## O que foi medido (n=564)

### Taxa de default real por recomendação

| Recomendação | k (default) | n | Taxa | IC95% (Wilson) |
|---|---|---|---|---|
| APROVAR | 85 | 260 | 32.7% | [27.3%; 38.6%] |
| NEGAR | 103 | 303 | 34.0% | [28.9%; 39.5%] |
| DEFERIR | 0 | 1 | 0.0% | [0.0%; 79.3%] |

### Separação NEGAR − APROVAR (IC bootstrap, ADR-0004 §2.5)

**+1.3%**, IC95% [-6.7%; +9.2%]

## Limitações declaradas

- **Comparação com o motor da Camada 1 não disponível.** `zona_cinzenta.parquet` é, por definição, o recorte onde o motor se absteve (`decisao_motor` constante). Não existe decisão real do motor pra comparar dentro deste universo.
- **DEFERIR não separa risco por construção** — é encaminhamento a humano, não uma aposta de risco. A taxa de default sob `DEFERIR` não é comparável às outras duas colunas do mesmo jeito.
- Revisor único e não especialista aplicou o critério de Task Completion (ADR-0011) aos memos — este backtest mede separação de `TARGET`, não a qualidade do julgamento humano.
