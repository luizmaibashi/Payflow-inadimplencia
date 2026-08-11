# Backtest da Camada 2 — agente vs. default real (ADR-0004 §2.1)

**Gerado por:** `scripts/backtest_camada2.py`  
**Pergunta:** as recomendações do agente (APROVAR/NEGAR/DEFERIR) separam risco real (`TARGET`) na zona cinzenta?

## O que foi medido (n=86)

> ⚠️ **n=86 é pequeno demais pra separação de 10pp** (poder estatístico exige ~722). Leia o intervalo, não o ponto — não sustenta decisão de política sozinho (ADR-0004 §2.5).

### Taxa de default real por recomendação

| Recomendação | k (default) | n | Taxa | IC95% (Wilson) |
|---|---|---|---|---|
| APROVAR | 15 | 49 | 30.6% | [19.5%; 44.5%] |
| NEGAR | 14 | 37 | 37.8% | [24.1%; 53.9%] |
| DEFERIR | 0 | 0 | n/d | n/d |

### Separação NEGAR − APROVAR (IC bootstrap, ADR-0004 §2.5)

**+7.2%**, IC95% [-12.4%; +28.3%]

## Limitações declaradas

- **Comparação com o motor da Camada 1 não disponível.** `zona_cinzenta.parquet` é, por definição, o recorte onde o motor se absteve (`decisao_motor` constante). Não existe decisão real do motor pra comparar dentro deste universo.
- **DEFERIR não separa risco por construção** — é encaminhamento a humano, não uma aposta de risco. A taxa de default sob `DEFERIR` não é comparável às outras duas colunas do mesmo jeito.
- Revisor único e não especialista aplicou o critério de Task Completion (ADR-0011) aos memos — este backtest mede separação de `TARGET`, não a qualidade do julgamento humano.
