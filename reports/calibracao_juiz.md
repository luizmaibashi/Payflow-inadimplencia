# Calibração do juiz — Task Completion (débito #10)

**Gerado por:** `scripts/calibrar_juiz.py`  
**Juiz:** Groq / `llama-3.3-70b-versatile`, temperatura 0  
**Gerador dos memos:** `gemini-2.5-flash` (família diferente — ADR-0004 §2.3)  
**Memos:** `data/processed/piloto_camada2_memos.jsonl` (2026-08-08, versionado)

## O que foi medido

- Labels humanos disponíveis: **98**
- Com memo correspondente: **86** (12 sem memo — ver débito #30)
- Julgados sem erro de provider: **52**

> ⚠️ **Regra dura (ADR-0004 §2.5):** leia o intervalo, não a proporção. Com `n` desta ordem o IC de Wilson é largo o bastante para que a estimativa pontual não sustente decisão de política sozinha.

## Resultado

### Todos os labels pareáveis (n=52)

| Métrica | Valor | IC95% (Wilson) | n |
|---|---|---|---|
| TPR (detecta FALHA real) | 100.0% | [61.0%; 100.0%] | 6 |
| TNR (não acusa memo bom) | 71.7% | [57.5%; 82.7%] | 46 |

Matriz: TP=6 · FN=0 · TN=33 · FP=13

## Onde juiz e humano discordaram (13)

| caso | recomendação | humano | juiz | evidência do juiz |
|---|---|---|---|---|
| `111985` | NEGAR | OK | FALHA | utilizacao 99.91%, deficit 17.8%, pior atraso 5d, n_em_atraso_hoje 0, dias_desde_ultimo_atraso 93 - há um sinal grave (utilizacao >= 80%) e um agravante (defici |
| `117727` | NEGAR | OK | FALHA | nenhum sinal grave ou agravante presente, pois: utilizacao de credito nao disponivel, pior_atraso_dias nao disponivel, deficit_medio_pct nao disponivel, n_em_at |
| `143212` | NEGAR | OK | FALHA | nenhum sinal grave (utilizacao de credito e pior atraso nao disponiveis), nenhum agravante (deficit_medio_pct, n_em_atraso_hoje, pior_atraso_dias e dias_desde_u |
| `151515` | NEGAR | OK | FALHA | nenhum sinal grave (utilizacao de credito e pior atraso dias nao disponiveis), nenhum agravante (deficit_medio_pct, n_em_atraso_hoje, pior_atraso_dias e dias_de |
| `173954` | NEGAR | OK | FALHA | nenhum sinal grave (utilizacao de credito e pior atraso nao disponiveis), nenhum agravante (deficit_medio_pct, n_em_atraso_hoje, pior_atraso_dias e dias_desde_u |
| `205320` | NEGAR | OK | FALHA | nenhum sinal grave e nenhum agravante presente, pois utilizacao de credito e pior atraso nao disponiveis, deficit_medio_pct nao disponivel, n_em_atraso_hoje = 0 |
| `222453` | NEGAR | OK | FALHA | nenhum sinal grave (utilizacao de credito e pior atraso dias nao disponiveis), nenhum agravante (deficit_medio_pct, n_em_atraso_hoje, pior_atraso_dias e dias_de |
| `235776` | NEGAR | OK | FALHA | nenhum sinal grave (utilizacao de credito e pior atraso dias nao disponiveis), nenhum agravante (deficit_medio_pct, n_em_atraso_hoje, pior_atraso_dias e dias_de |
| `238067` | NEGAR | OK | FALHA | nenhum sinal grave e nenhum agravante presente, pois n_en_atraso_hoje = 0, deficit_medio_pct = None, pior_atraso_dias = None, utilizacao = None |
| `240344` | NEGAR | OK | FALHA | utilizacao 47%, deficit 0%, pior atraso 4d - nenhum sinal grave e apenas 1 agravante (1 contrato em atraso no bureau), mas recomendacao foi NEGAR |
| `244626` | NEGAR | OK | FALHA | utilizacao 99.7%, deficit 0%, pior atraso 1d, n_em_atraso_hoje 0 - um sinal grave (utilizacao >= 80%) esta presente, mas como ha apenas 1 agravante (nenhum dos  |
| `264603` | NEGAR | OK | FALHA | nenhum sinal grave (utilizacao de credito e pior atraso nao disponiveis), nenhum agravante (deficit_medio_pct, n_em_atraso_hoje, pior_atraso_dias e dias_desde_u |
| `417173` | NEGAR | OK | FALHA | nenhum sinal grave e nenhum agravante presente, pois n_contratos = 0, n_em_atraso_hoje = 0, deficit_medio_pct = None, pior_atraso_dias = None, dias_desde_ultimo |

## Erros de provider/parsing (34, fora da matriz)

- `280852`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99104, Requested 1371. Please try ag
- `282047`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99097, Requested 1194. Please try ag
- `285827`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99090, Requested 1187. Please try ag
- `295370`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99084, Requested 1452. Please try ag
- `299680`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99077, Requested 1292. Please try ag
- `302315`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99070, Requested 1457. Please try ag
- `303376`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99063, Requested 1335. Please try ag
- `307444`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99056, Requested 1409. Please try ag
- `310188`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99048, Requested 1219. Please try ag
- `322471`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99040, Requested 1255. Please try ag
- `325723`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99034, Requested 1335. Please try ag
- `326137`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99028, Requested 1392. Please try ag
- `331720`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99021, Requested 1275. Please try ag
- `333067`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99013, Requested 1299. Please try ag
- `333746`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99006, Requested 1492. Please try ag
- `336278`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 98998, Requested 1231. Please try ag
- `340715`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 98992, Requested 1394. Please try ag
- `342044`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 98985, Requested 1298. Please try ag
- `344012`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 98978, Requested 1396. Please try ag
- `348835`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 98971, Requested 1154. Please try ag
- `350878`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 98965, Requested 1305. Please try ag
- `351105`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 98957, Requested 1445. Please try ag
- `353468`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 98951, Requested 1348. Please try ag
- `358801`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 98944, Requested 1433. Please try ag
- `368123`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 98937, Requested 1270. Please try ag
- `371141`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 98931, Requested 1183. Please try ag
- `374802`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 98924, Requested 1434. Please try ag
- `379149`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 98917, Requested 1308. Please try ag
- `386823`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 98909, Requested 1422. Please try ag
- `396189`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 98903, Requested 1193. Please try ag
- `398836`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 98895, Requested 1366. Please try ag
- `410339`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 98887, Requested 1286. Please try ag
- `435752`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99948, Requested 1153. Please try ag
- `449188`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99941, Requested 1353. Please try ag

## 🔴 O ground truth tem ruído de critério — leia isto antes das métricas

**20 casos** têm a MESMA assinatura nos dados brutos: o memo recomenda `NEGAR`, o cliente **nunca deixou de pagar** (`n_nunca_pagas = 0`) e **paga adiantado em média** (`atraso_medio_dias < 0`). É exatamente o padrão que o revisor descreveu ao justificar as FALHAs de 2026-08-07 (*"claramente um bom pagador, nunca deixou de pagar, paga adiantado em média"*).

Desses 20, o revisor marcou **9 como FALHA** e **11 como OK**.

| caso | veredito humano | atraso médio (dias) | dias desde último atraso |
|---|---|---|---|
| `111985` | OK | -6.5 | 93 |
| `128369` | OK | -1.3 | 1027 |
| `153799` | FALHA | -4.1 | 852 |
| `154357` | FALHA | -9.1 | 258 |
| `166661` | FALHA | -4.7 | 73 |
| `187682` | OK | -8.8 | 26 |
| `219448` | FALHA | -8.2 | 185 |
| `224770` | FALHA | -11.0 | 125 |
| `240344` | OK | -6.6 | 39 |
| `244626` | OK | -6.0 | 684 |
| `252397` | OK | -7.7 | 187 |
| `272758` | FALHA | -6.6 | 369 |
| `295370` | FALHA | -21.7 | 481 |
| `303376` | OK | -2.3 | 551 |
| `307444` | FALHA | -8.2 | 1188 |
| `333746` | FALHA | -9.8 | 592 |
| `344012` | OK | -7.5 | 1064 |
| `374802` | OK | -37.2 | 462 |
| `379149` | OK | -6.4 | 162 |
| `449188` | OK | -3.7 | 166 |

**Consequência para este relatório:** o TPR acima não mede a qualidade do juiz. Mede a distância entre um critério humano *implícito e aplicado de forma variável* e um critério de juiz *explícito e constante*. Boa parte dos 'falsos positivos' do juiz cai justamente nesses casos — o juiz aplicou a mesma régua que o revisor usou em 4 deles, aos 11 restantes.

**O que fazer antes de rerrotular qualquer coisa:** escrever o critério de Task Completion como regra verificável (o que exatamente torna uma recomendação `NEGAR` indefensável na presença de bom histórico de pagamento?) e só então rotular. Rotular mais casos com o critério implícito só aumenta o ruído — não estreita o intervalo.

## Limitações declaradas

- **O prompt do juiz embute a heurística de contagem de pesos** (`_prompt_sistema_juiz` manda marcar FALHA quando *"a recomendação contraria o peso predominante dos fatores"*). Qualquer proxy mecânico que também conte pesos vai concordar com o juiz **por construção** — isso não é confirmação independente.
- **Revisor único e não especialista** — ground truth fraco por construção (ADR-0003 §3, débito #10).
- **`n` de positivos pequeno**: o TPR é a métrica que importa (detectar a falha rara) e é justamente a de intervalo mais largo aqui.
- Os labels reaproveitados de 2026-08-07 descrevem memos regerados em 2026-08-08. A premissa é que um label `OK` sobrevive à regeração salvo regressão do agente; as duas mudanças observadas foram melhorias. Premissa **declarada**, não verificada caso a caso.
