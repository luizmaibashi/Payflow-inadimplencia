# Calibração do juiz — Task Completion (débito #10)

**Gerado por:** `scripts/calibrar_juiz.py`  
**Juiz:** Groq / `llama-3.3-70b-versatile`, temperatura 0  
**Gerador dos memos:** `gemini-2.5-flash` (família diferente — ADR-0004 §2.3)  
**Memos:** `data/processed/piloto_camada2_memos.jsonl` (2026-08-08, versionado)

## O que foi medido

- Labels humanos disponíveis: **98**
- Com memo correspondente: **86** (12 sem memo — ver débito #30)
- Julgados sem erro de provider: **55**

> ⚠️ **Regra dura (ADR-0004 §2.5):** leia o intervalo, não a proporção. Com `n` desta ordem o IC de Wilson é largo o bastante para que a estimativa pontual não sustente decisão de política sozinha.

## Resultado

### Todos os labels pareáveis (n=55)

| Métrica | Valor | IC95% (Wilson) | n |
|---|---|---|---|
| TPR (detecta FALHA real) | 87.5% | [52.9%; 97.8%] | 8 |
| TNR (não acusa memo bom) | 76.6% | [62.8%; 86.4%] | 47 |

Matriz: TP=7 · FN=1 · TN=36 · FP=11

## Onde juiz e humano discordaram (12)

| caso | recomendação | humano | juiz | evidência do juiz |
|---|---|---|---|---|
| `117727` | NEGAR | OK | FALHA | nenhum sinal grave ou agravante presente, pois: utilizacao de credito nao disponivel, pior_atraso_dias nao disponivel, deficit_medio_pct nao disponivel, n_em_at |
| `143212` | NEGAR | OK | FALHA | nenhum sinal grave ou agravante presente, pois: utilizacao de credito nao disponivel, pior_atraso_dias nao disponivel, deficit_medio_pct nao disponivel, n_em_at |
| `151515` | NEGAR | OK | FALHA | nenhum sinal grave ou agravante presente, pois todos os dados relevantes para o criterio estao como None ou 0 (utilizacao: None, pior_atraso_dias: None, deficit |
| `154357` | NEGAR | FALHA | OK | utilizacao 65.72%, deficit_medio_pct 14.29%, n_em_atraso_hoje 1, pior_atraso_dias 3, dias_desde_ultimo_atraso 258 - nenhum sinal grave e 2 agravantes (1 contrat |
| `173954` | NEGAR | OK | FALHA | nenhum sinal grave ou agravante presente, pois: utilizacao de credito nao disponivel, pior_atraso_dias nao disponivel, deficit_medio_pct nao disponivel, n_em_at |
| `205320` | NEGAR | OK | FALHA | nenhum sinal grave ou agravante presente, pois: utilizacao de credito nao disponivel, pior atraso dias nao disponivel, deficit medio pct nao disponivel, n em at |
| `222453` | NEGAR | OK | FALHA | nenhum sinal grave ou agravante presente, pois: utilizacao de credito nao disponivel, pior_atraso_dias nao disponivel, deficit_medio_pct nao disponivel, n_em_at |
| `235776` | NEGAR | OK | FALHA | nenhum sinal grave ou agravante presente, pois todos os dados relevantes sao None ou zero (utilizacao None, n_em_atraso_hoje 0, deficit_medio_pct None, pior_atr |
| `238067` | NEGAR | OK | FALHA | nenhum sinal grave ou agravante presente, pois dados brutos nao apresentam utilizacao de credito, pior atraso, deficit medio pct, n_em_atraso_hoje, ou pior_atra |
| `264603` | NEGAR | OK | FALHA | nenhum sinal grave ou agravante presente, pois: utilizacao de credito nao disponivel, pior atraso dias nao disponivel, deficit medio pct nao disponivel, n em at |
| `282047` | NEGAR | OK | FALHA | nenhum sinal grave ou agravante presente, pois todos os dados relevantes sao None ou zero (utilizacao None, n_em_atraso_hoje 0, pior_atraso_dias None, deficit_m |
| `285827` | NEGAR | OK | FALHA | nenhum sinal grave ou agravante presente, pois todos os dados relevantes sao None ou zero (utilizacao None, deficit_medio_pct None, n_em_atraso_hoje 0, pior_atr |

## Erros de provider/parsing (31, fora da matriz)

- `299680`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99572, Requested 1525. Please try ag
- `302315`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99564, Requested 1685. Please try ag
- `303376`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99558, Requested 1572. Please try ag
- `307444`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99551, Requested 1624. Please try ag
- `310188`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99544, Requested 1447. Please try ag
- `322471`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99537, Requested 1479. Please try ag
- `325723`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99530, Requested 1563. Please try ag
- `326137`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99524, Requested 1607. Please try ag
- `331720`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99517, Requested 1512. Please try ag
- `333067`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99511, Requested 1536. Please try ag
- `333746`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99505, Requested 1716. Please try ag
- `336278`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99498, Requested 1450. Please try ag
- `340715`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99491, Requested 1618. Please try ag
- `342044`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99484, Requested 1535. Please try ag
- `344012`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99478, Requested 1615. Please try ag
- `348835`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99470, Requested 1369. Please try ag
- `350878`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99463, Requested 1533. Please try ag
- `351105`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99456, Requested 1660. Please try ag
- `353468`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99449, Requested 1585. Please try ag
- `358801`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99442, Requested 1657. Please try ag
- `368123`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99436, Requested 1498. Please try ag
- `371141`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99429, Requested 1411. Please try ag
- `374802`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99422, Requested 1658. Please try ag
- `379149`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99414, Requested 1545. Please try ag
- `386823`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99406, Requested 1646. Please try ag
- `396189`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99399, Requested 1412. Please try ag
- `398836`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99392, Requested 1599. Please try ag
- `410339`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99385, Requested 1505. Please try ag
- `417173`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99379, Requested 1373. Please try ag
- `435752`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99371, Requested 1386. Please try ag
- `449188`: FalhaProvider: provider falhou em 3 tentativa(s): Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kza7fbhmetrvaapeds50542g` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99363, Requested 1577. Please try ag

## 🔴 O ground truth tem ruído de critério — leia isto antes das métricas

**20 casos** têm a MESMA assinatura nos dados brutos: o memo recomenda `NEGAR`, o cliente **nunca deixou de pagar** (`n_nunca_pagas = 0`) e **paga adiantado em média** (`atraso_medio_dias < 0`). É exatamente o padrão que o revisor descreveu ao justificar as FALHAs de 2026-08-07 (*"claramente um bom pagador, nunca deixou de pagar, paga adiantado em média"*).

Desses 20, o revisor marcou **10 como FALHA** e **10 como OK**.

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
| `240344` | FALHA | -6.6 | 39 |
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
