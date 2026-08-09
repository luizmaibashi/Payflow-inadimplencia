# Calibração do juiz — Task Completion (débito #10)

**Gerado por:** `scripts/calibrar_juiz.py`  
**Juiz:** Groq / `llama-3.3-70b-versatile`, temperatura 0  
**Gerador dos memos:** `gemini-2.5-flash` (família diferente — ADR-0004 §2.3)  
**Memos:** `data/processed/piloto_camada2_memos.jsonl` (2026-08-08, versionado)

## O que foi medido

- Labels humanos disponíveis: **87**
- Com memo correspondente: **75** (12 sem memo — ver débito #30)
- Julgados sem erro de provider: **75**

> ⚠️ **Regra dura (ADR-0004 §2.5):** leia o intervalo, não a proporção. Com `n` desta ordem o IC de Wilson é largo o bastante para que a estimativa pontual não sustente decisão de política sozinha.

## Resultado

### Todos os labels pareáveis (n=75)

| Métrica | Valor | IC95% (Wilson) | n |
|---|---|---|---|
| TPR (detecta FALHA real) | 50.0% | [21.5%; 78.5%] | 8 |
| TNR (não acusa memo bom) | 89.6% | [80.0%; 94.8%] | 67 |

Matriz: TP=4 · FN=4 · TN=60 · FP=7

### Recorte de sensibilidade — sem os labels que o débito #30 invalidou

Estes labels foram marcados `FALHA` porque o agente **negou** um cliente que os fatos mostravam bom pagador. Nos memos regerados ele passou a recomendar `APROVAR` — fez o que o revisor cobrou, então a etiqueta descreve um memo que não existe mais:

- `100525` — rotulado FALHA (agente negou bom pagador), mas o memo regerado recomenda APROVAR - a queixa original nao se aplica
- `353468` — rotulado FALHA (agente negou bom pagador), mas o memo regerado recomenda APROVAR - a queixa original nao se aplica

### Sem os 2 obsoletos (n=73)

| Métrica | Valor | IC95% (Wilson) | n |
|---|---|---|---|
| TPR (detecta FALHA real) | 66.7% | [30.0%; 90.3%] | 6 |
| TNR (não acusa memo bom) | 89.6% | [80.0%; 94.8%] | 67 |

Matriz: TP=4 · FN=2 · TN=60 · FP=7

## Onde juiz e humano discordaram (11)

| caso | recomendação | humano | juiz | evidência do juiz |
|---|---|---|---|---|
| `100525` | APROVAR | FALHA | OK |  |
| `166661` | NEGAR | OK | FALHA | O cliente não possui contratos em atraso hoje em outras instituições, utilização do crédito disponível em outras instituições é baixa (28%), possui um histórico |
| `224770` | NEGAR | OK | FALHA | atraso medio de -11 dias, 0 parcelas nunca pagas, 1 atraso de 10 dias há 125 dias e limite de crédito total de R$ 357.750,00 sem atrasos, mas recomendacao foi N |
| `244626` | NEGAR | OK | FALHA | atraso medio de -6.028985507246377 dias, 0 parcelas nunca pagas, 2 atrasos minimos (1 dia), e ultimo atraso ocorreu ha mais de 684 dias, mas recomendacao foi NE |
| `252397` | NEGAR | OK | FALHA | atraso medio de -7.7 dias e 0 parcelas nunca pagas, mas recomendacao foi NEGAR |
| `264603` | NEGAR | FALHA | OK |  |
| `295370` | NEGAR | OK | FALHA | atraso médio de -21.67 dias e 5 meses em dia sem atrasos registrados em outras instituições, mas recomendacao foi NEGAR |
| `303376` | NEGAR | OK | FALHA | atraso médio de -2.28 dias e 0 parcelas nunca pagas, mas recomendacao foi NEGAR |
| `310188` | NEGAR | FALHA | OK |  |
| `353468` | APROVAR | FALHA | OK |  |
| `417173` | NEGAR | OK | FALHA | nenhum fator desfavoravel foi citado, mas a recomendacao foi NEGAR |

## 🔴 O ground truth tem ruído de critério — leia isto antes das métricas

**15 casos** têm a MESMA assinatura nos dados brutos: o memo recomenda `NEGAR`, o cliente **nunca deixou de pagar** (`n_nunca_pagas = 0`) e **paga adiantado em média** (`atraso_medio_dias < 0`). É exatamente o padrão que o revisor descreveu ao justificar as FALHAs de 2026-08-07 (*"claramente um bom pagador, nunca deixou de pagar, paga adiantado em média"*).

Desses 15, o revisor marcou **4 como FALHA** e **11 como OK**.

| caso | veredito humano | atraso médio (dias) | dias desde último atraso |
|---|---|---|---|
| `111985` | OK | -6.5 | 93 |
| `128369` | OK | -1.3 | 1027 |
| `153799` | FALHA | -4.1 | 852 |
| `166661` | OK | -4.7 | 73 |
| `187682` | OK | -8.8 | 26 |
| `219448` | FALHA | -8.2 | 185 |
| `224770` | OK | -11.0 | 125 |
| `240344` | FALHA | -6.6 | 39 |
| `244626` | OK | -6.0 | 684 |
| `252397` | OK | -7.7 | 187 |
| `295370` | OK | -21.7 | 481 |
| `303376` | OK | -2.3 | 551 |
| `374802` | OK | -37.2 | 462 |
| `379149` | FALHA | -6.4 | 162 |
| `449188` | OK | -3.7 | 166 |

**Consequência para este relatório:** o TPR acima não mede a qualidade do juiz. Mede a distância entre um critério humano *implícito e aplicado de forma variável* e um critério de juiz *explícito e constante*. Boa parte dos 'falsos positivos' do juiz cai justamente nesses casos — o juiz aplicou a mesma régua que o revisor usou em 4 deles, aos 11 restantes.

**O que fazer antes de rerrotular qualquer coisa:** escrever o critério de Task Completion como regra verificável (o que exatamente torna uma recomendação `NEGAR` indefensável na presença de bom histórico de pagamento?) e só então rotular. Rotular mais casos com o critério implícito só aumenta o ruído — não estreita o intervalo.

## Limitações declaradas

- **O prompt do juiz embute a heurística de contagem de pesos** (`_prompt_sistema_juiz` manda marcar FALHA quando *"a recomendação contraria o peso predominante dos fatores"*). Qualquer proxy mecânico que também conte pesos vai concordar com o juiz **por construção** — isso não é confirmação independente.
- **Revisor único e não especialista** — ground truth fraco por construção (ADR-0003 §3, débito #10).
- **`n` de positivos pequeno**: o TPR é a métrica que importa (detectar a falha rara) e é justamente a de intervalo mais largo aqui.
- Os labels reaproveitados de 2026-08-07 descrevem memos regerados em 2026-08-08. A premissa é que um label `OK` sobrevive à regeração salvo regressão do agente; as duas mudanças observadas foram melhorias. Premissa **declarada**, não verificada caso a caso.
