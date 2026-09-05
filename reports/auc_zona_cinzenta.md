# AUC dentro da zona cinzenta — com intervalo de confiança (débito #34)

**Gerado por:** `scripts/auc_zona_cinzenta.py`  
**Pergunta:** o AUC de 0,56 dentro da zona cinzenta é distinguível de 0,50 (acaso puro)? E ele sobrevive aos dois testes de robustez que o débito #34 registrou em prosa?

> Este script existe porque o número mais consequente do projeto era o único sem script versionado e sem intervalo — medido ad-hoc em 2026-08-12, reportado como ponto. O ponto não mudou; o que muda aqui é saber o quanto ele é preciso.

## 1. AUC calibrado — o número da headline (n=2,102, 758 defaults)

| Medição | AUC | IC95% (bootstrap) |
|---|---|---|
| **Zona cinzenta (calibrado, `p_hat`)** | **0.5612** | [0.5368; 0.5846] |
| Referência: mesmo modelo, população de teste inteira | 0.776 | ver `camada1_treino_final.md` |
| Referência: acaso puro | 0,500 | — |

**O intervalo NÃO contém 0,50** — com 2000 reamostragens, o limite inferior é 0.5368. A leitura precisa é **"o modelo discrimina fracamente, mas de forma detectável"**, não "é indistinguível de uma moeda". A diferença importa: a segunda afirmação é mais forte do que o dado sustenta.

## 2. Teste de robustez A — a calibração isotônica estava escondendo sinal?

O `p_hat` calibrado colapsa em poucos platôs dentro da zona (função em degrau da isotônica), o que poderia deprimir o AUC por empate. Refeito sobre o score **bruto do estimador base**, sem nenhum empate:

| Score | AUC | IC95% (bootstrap) |
|---|---|---|
| Calibrado (isotônica) | 0.5612 | [0.5368; 0.5846] |
| **Bruto (pré-calibração)** | **0.5643** | [0.5381; 0.5888] |

**Os intervalos se sobrepõem quase inteiramente** — a calibração não estava escondendo nada. Hipótese descartada, agora com intervalo e não só com ponto.

## 3. Teste de robustez B — a zona está desenhada larga demais?

Se a zona cinzenta misturasse casos difíceis com casos fáceis, os casos de **borda** (perto de sair da zona) seriam mais previsíveis que os do **centro** da banda de incerteza. Três fatias por tercil de distância relativa ao centro:

| Fatia | n | defaults | AUC | IC98.33% (Bonferroni) |
|---|---|---|---|---|
| centro | 1,063 | 415 | 0.5157 | [0.4862; 0.5473] |
| meio | 388 | 151 | 0.5409 | [0.4769; 0.6039] |
| borda | 651 | 192 | 0.5343 | [0.5118; 0.5569] |

> **Correção de comparações múltiplas aplicada.** Três fatias testadas para responder uma pergunta são três chances de uma parecer boa por ruído (~14% de erro familiar, não 5%). Os intervalos acima estão a 98.33%, não 95% — nível individual corrigido por Bonferroni (α = 0.05/3).

**Nenhuma fatia recupera previsibilidade.** A melhor (`meio`, AUC 0.5409) não supera nem o AUC da zona inteira (0.5612) — na verdade **as três fatias ficam abaixo dele**. Não existe sub-região oculta mais decidível; a dificuldade é uniforme. Hipótese descartada.

Nota de leitura: a fatia `borda` tem intervalo corrigido acima de 0,50, ou seja, discrimina de forma detectável. Isso **não** contradiz o parágrafo acima — detectável e útil são coisas diferentes, e nenhuma fatia chega perto de ser útil. O critério que importa aqui é a comparação com a zona inteira, não com o acaso.

> ⚠️ **Artefato metodológico esperado, declarado:** fatiar por `p_hat` restringe a amplitude de score dentro de cada fatia, e AUC cai mecanicamente com amplitude menor. Por isso as três fatias ficarem abaixo da zona inteira é o comportamento normal — o que a hipótese procurava era uma fatia que subisse **apesar** disso, e nenhuma sobe.

## Limitações

- **IC bootstrap percentil, 2000 reamostragens, seed 42.** Reamostragens degeneradas (uma classe só) são descartadas: 0 de 2000 na medição principal.
- **O bootstrap mede incerteza amostral, não erro de especificação.** Ele responde "se eu reamostrasse esta zona cinzenta, quanto o AUC oscilaria" — não responde se um modelo diferente, com dados que este dataset não tem, decidiria melhor ali.
- **A zona cinzenta é definida pela incerteza da premissa de margem, não pela incerteza do modelo** (ADR-0002 §2.6, débito #16). As fatias da seção 3 testam a largura da banda, não essa escolha de definição.
- Sub-fatias por `pd.qcut` sobre `p_hat`, que tem poucos platôs — os tercis não saem exatamente do mesmo tamanho.
- **As fatias da seção 3 não reproduzem exatamente os números ad-hoc de 2026-08-12** (registrados no `AGENTS.md` como centro 0,531 / meio 0,568 / borda 0,509). Aquela medição não deixou script, então a definição de fatia aqui é uma **reconstrução** da descrição em prosa, não a mesma conta. Os valores diferem; a conclusão (nenhuma fatia recupera previsibilidade) é a mesma nas duas. Deste relatório em diante, os números reproduzíveis são estes.
