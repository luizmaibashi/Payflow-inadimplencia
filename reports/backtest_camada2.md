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
- **DEFERIR não separa risco por construção** — é encaminhamento a humano, não uma aposta de risco. A taxa de default sob `DEFERIR` não é comparável às outras duas colunas do mesmo jeito. **`DEFERIR` foi usado em apenas 1 dos 564 casos (0,18%)** — quase inexistente na prática, apesar de desenhado como ação de primeira classe.
- Revisor único e não especialista aplicou o critério de Task Completion (ADR-0011) aos memos — este backtest mede separação de `TARGET`, não a qualidade do julgamento humano.
- **Amostra não é independente da rodada anterior de 86 casos** — `preparar_lote()` reusa a mesma seed (42) pra embaralhar sempre a mesma população de 2.102 casos, então os 722 são uma extração determinística estendida, não uma segunda amostra aleatória somada à primeira (100 dos 722 IDs já tinham aparecido antes). Não invalida a estatística, mas descreve-la como "722 casos novos independentes" seria impreciso.
- **Atrito leve entre casos válidos e excluídos**: os 158 casos que falharam geração de memo (`memo_invalido`/`erro_provider`/`teto`) têm taxa de default real de 36,1% contra 33,3% dos válidos — diferença pequena, mas sugere que casos mais difíceis de avaliar também são levemente mais difíceis do agente formatar corretamente (missingness não completamente aleatória).
- **Robustez do bootstrap verificada**: IC95% recalculado com 5 seeds diferentes (42, 1, 7, 999, 123456) — sempre entre aproximadamente [-7,0%; +9,2%]. A conclusão de que o intervalo cruza zero não depende da seed escolhida.
- **Sem cobertura de teste automatizado** para este script — validado manualmente, sem regressão automática se for alterado no futuro.
