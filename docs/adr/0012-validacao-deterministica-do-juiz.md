# ADR-0012: Validação determinística pós-resposta para falhas de raciocínio do juiz que instrução de prompt não corrige

**Data**: 2026-08-10
**Status**: Accepted
**Contexto**: PayFlow — débitos #32 e #33 (bugs de raciocínio do juiz, achados na calibração pós-ADR-0011)

---

## 1. CONTEXTO (O QUÊ?)

O juiz (`app/juiz_camada2.py::_prompt_sistema_juiz`) aplica o critério do ADR-0011 sobre dados brutos e decide se `NEGAR` é defensável. Duas falhas de raciocínio foram achadas na mesma recalibração (`reports/calibracao_juiz.md`, casos de discordância entre juiz e humano):

- **#32**: o juiz identificava corretamente um sinal grave (que já basta pelo ADR-0011 §2.1) e ainda assim marcava `FALHA`, ponderando fatores extras depois de já ter a resposta.
- **#33**: o juiz via campos `None`/"não disponível" e concluía "nenhum sinal grave, nenhum agravante" → `FALHA`, tratando ausência de dado como ausência de risco em vez de incerteza.

Os dois foram "corrigidos" da mesma forma: instrução explícita nova em `_prompt_sistema_juiz`, com teste de regressão que verifica o **texto do prompt** (não o comportamento do modelo).

**O que a validação empírica de 2026-08-10 mostrou** (`calibrar_juiz.py --rejulgar`, n=55, `llama-3.3-70b-versatile` via Groq):

| Débito | Resultado contra API real |
|---|---|
| #32 | **Validado.** Os dois casos-alvo (`111985`, `244626`) não aparecem mais nas discordâncias. |
| #33 | **Refutado.** 11 dos 12 casos de discordância do novo lote repetem o mesmo padrão, com evidência do juiz quase idêntica à anterior — incluindo 2 casos novos que nunca tinham sido julgados antes e já nascem com o defeito. |

A mesma técnica (instrução de prompt) funcionou para um padrão e falhou para outro, no mesmo modelo, no mesmo dia. Isso descarta a hipótese de que "escrever a instrução certa" é uma estratégia confiável em geral — funciona quando funciona, e o teste de regressão atual (grep no texto do prompt) não tem como distinguir os dois casos: ambos passam no teste, só um passa na prática.

## 2. DECISÃO (POR QUÊ?)

**Para o padrão do #33 (e qualquer bug futuro de raciocínio que resista a uma tentativa de correção via prompt), abandonar a correção puramente textual e adicionar uma validação determinística pós-resposta** — no mesmo padrão já usado no projeto para `validar_groundedness_numerica()` (#26) e `validar_trajetoria()` (#22/#23): ler a saída do juiz depois que ela chega, checar um padrão mecânico, e sinalizar quando bater.

Especificamente: uma função que, dado o `veredito` e a `evidencia` do juiz mais os dados brutos da trace,
1. detecta se `veredito == FALHA`,
2. detecta se a evidência do juiz cita ausência de dado ("não disponível", `None`) como justificativa para todos os sinais/agravantes do ADR-0011,
3. confirma contra os dados brutos que os campos citados são de fato `None`,
4. se as três condições baterem, marca o veredito como **suspeito** (não sobrescreve sozinho — mesmo tratamento não-eliminatório do #26).

**Por que não tentar de novo só no prompt:** já foi tentado uma vez e falhou contra a mesma classe de modelo que validou o #32 no mesmo dia. Não há evidência de que reescrever a frase resolva — e cada tentativa custa uma rodada inteira de cota Groq (24h de espera por rodada incompleta). O caminho determinístico não depende do LLM obedecer instrução nova nenhuma.

**Por que não é a resposta geral para todo bug de raciocínio:** funciona aqui porque o padrão do #33 é sintaticamente detectável (a evidência do próprio juiz nomeia os campos ausentes). Um bug de raciocínio que não deixasse rastro sintático na evidência não seria pego por essa técnica — continuaria exigindo prompt ou, na pior hipótese, mudança de modelo.

## 3. CONSEQUÊNCIAS

**Positivas:**
- Não depende de reformular prompt às cegas gastando cota Groq em cada tentativa.
- Reaproveita um padrão já validado no projeto (#22/#23/#26) em vez de introduzir mecanismo novo.
- Sinal fica registrado como `suspeitos_*` (mesmo campo de `ResultadoAnalise` do #26), não como override silencioso — mantém decisão final com o revisor humano.

**Negativas / custo:**
- Cobertura parcial por construção: só pega o padrão específico "evidência cita ausência de dado". Um juiz que inventasse outra frase pra justificar o mesmo erro passaria batido — mesma limitação já reconhecida no débito #23 para `validar_trajetoria()`.
- Mais um validador determinístico pra manter sincronizado se o vocabulário do prompt do juiz mudar (a detecção de "não disponível"/`None` na evidência é heurística de texto, como a groundedness numérica do #26).
- Não resolve #33 no sentido de "o juiz aprendeu a lidar com dado ausente" — resolve no sentido de "o pipeline não aceita cegamente esse erro específico quando ele acontece".

## 4. ALTERNATIVAS DESCARTADAS

| Opção | Vantagem | Por que rejeitada |
|---|---|---|
| Reescrever o prompt de novo (few-shot com exemplo de caso com dado ausente) | Mais simples de implementar, mesma família da tentativa atual | Já foi tentado uma vez com instrução direta e falhou; não há razão medida pra achar que few-shot generaliza melhor pra esse modelo especificamente sem testar — e testar custa uma rodada inteira de cota |
| Trocar o modelo do juiz (outro provider/tamanho) | Pode ter melhor aderência a instrução | Fora de escopo do ADR-0009 (juiz precisa ser de família diferente do gerador, mas trocar por decisão de qualidade de instruction-following é mudança maior, não resposta a um bug pontual) |
| Aceitar o TNR mais baixo e não corrigir | Zero custo de implementação | Deixa o débito #10 (calibração formal) bloqueado indefinidamente por um padrão que é mecanicamente detectável — não é limitação de fato, é preguiça de engenharia |

## 5. VALIDAÇÃO

**Métrica de sucesso:** no próximo `calibrar_juiz.py --rejulgar`, os 9+ casos do padrão "dado ausente" devem aparecer marcados como `suspeitos_dado_ausente` (ou nome equivalente) em vez de silenciosamente contarem como falso positivo no TNR.

**Não é sucesso silencioso:** a função precisa de teste unitário com um caso sintético que replica o padrão exato encontrado (evidência citando `None` para todos os campos do ADR-0011), no mesmo estilo dos testes de `validar_groundedness_numerica()`.

**Quando reabrir esta decisão:** se o padrão detectável mudar de formato (juiz passar a escrever a evidência de outro jeito) e o validador parar de pegar os casos reais — sinal de que a heurística de texto envelheceu, mesma classe de risco já assumida no #26.

## 6. REFERÊNCIAS

- Débito #32, #33 — `AGENTS.md`
- ADR-0011 — critério de Task Completion que o juiz aplica
- ADR-0004 §2.3 — juiz de família diferente do gerador
- Débito #26 — `validar_groundedness_numerica()`, mesmo padrão de validação determinística não-eliminatória
- Débito #22/#23 — `validar_trajetoria()`, mesma limitação de cobertura parcial por construção
- `reports/calibracao_juiz.md` (n=55, 2026-08-10) — evidência empírica que motivou esta decisão
