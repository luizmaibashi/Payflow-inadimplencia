# Separação de risco por confiança aparente do agente (hipótese (b) do débito #34)

**Gerado por:** `scripts/separacao_por_confianca.py`  
**Pergunta:** a separação NEGAR−APROVAR aparece nos casos em que a evidência citada pelo agente era unânime, e some nos casos apertados?

> Hipótese registrada como **não testada** no débito #34 desde 2026-08-12. Custo zero de API — usa os memos já gerados.

## Por que a hipótese era plausível

Desde o débito #28 o prompt proíbe `DEFERIR` por informação inobtenível — o agente decide mesmo quando a evidência é ambígua (`DEFERIR` saiu em 1 de 564 casos). Se a separação de risco existisse só onde a evidência é clara, a média global a diluiria com os casos forçados.

## Proxy usado, e o que ele não mede

O memo não tem campo de confiança. O proxy usa `peso` (`favoravel`/`desfavoravel`) de cada item de `fatores_cliente`:

```
assimetria = |n_favoravel − n_desfavoravel| / n_fatos      ∈ [0, 1]
```

1,0 = todos os fatos apontam pro mesmo lado. 0,0 = empate perfeito.

> **Limite declarado antes de olhar o resultado:** isso mede a unanimidade da evidência que o agente **escolheu citar** — não a confiança dele nem a dificuldade real do caso. Um agente que só cita o que sustenta a decisão já tomada teria assimetria alta por viés de seleção. O proxy não separa os dois casos.

## Resultado (n=564)

**Controle — separação global (replica o `backtest_camada2.md`):**

NEGAR−APROVAR = **+1.3%**, IC95% [-6.7%; +9.2%] (`NEGAR` n=303, `APROVAR` n=260)

**Por grupo de assimetria:**

| Assimetria | n | `NEGAR` (n / taxa) | `APROVAR` (n / taxa) | Separação | IC98.33% (Bonferroni) |
|---|---|---|---|---|---|
| -0.00–0.43 | 212 | 118 / 29.7% | 93 / 33.3% | **-3.7%** | [-19.4%; +12.1%] |
| 0.43–0.67 | 168 | 108 / 37.0% | 60 / 35.0% | **+2.0%** | [-17.0%; +20.0%] |
| 0.67–1.00 | 184 | 77 / 36.4% | 107 / 30.8% | **+5.5%** | [-11.8%; +24.0%] |

> **Correção de comparações múltiplas aplicada.** 3 grupos testados para responder uma pergunta são 3 chances de um parecer bom por ruído. Os intervalos estão a 98.33%, não 95% (Bonferroni, α = 0.05/3).

## Veredito

**Hipótese (b) NÃO SUSTENTADA — mas não refutada com força.** Nenhum grupo tem separação estatisticamente detectável: todos os intervalos corrigidos contêm zero, inclusive o de evidência mais unânime (assimetria média 0.90, n=184), onde o proxy dá ao agente o cenário mais favorável possível — separação +5.5%, IC [-11.8%; +24.0%].

**O que os pontos mostram, e por que não basta.** Os três pontos crescem de forma monotônica na direção que a hipótese previa (-3.7% → +2.0% → +5.5%, da evidência mais apertada para a mais unânime). Isso é consistente com a hipótese e não deve ser omitido. Mas os intervalos têm largura média de 35% e todos cruzam zero — três pontos ordenados por acaso acontecem em 1 de 6 vezes, e nenhum deles é individualmente distinguível de zero.

**Conclusão precisa:** este teste descarta que exista um sinal **grande** escondido nos casos de evidência unânime — se houvesse separação de 20pp lá, apareceria. Ele **não** descarta um sinal pequeno: com n≈190 por grupo (contra os 722 que o próprio projeto calculou serem necessários para detectar 10pp), o estudo está cerca de 4× subdimensionado. A leitura honesta é "não achamos", não "não existe".

> Isso **não reabre** o débito #34. A conclusão central dele não vem deste teste, e sim do AUC de 0,56 do próprio modelo campeão dentro da zona (`reports/auc_zona_cinzenta.md`) — que mede o teto do previsível ali, independente de qual agente decide. Um sinal pequeno sobrevivente nos casos unânimes seria compatível com esse teto, não uma contradição dele.

## Limitações

- **IC bootstrap percentil, 2000 reamostragens, seed 42**, mesma metodologia do `backtest_camada2.py`.
- **Grupos menores que a amostra global** — cada um tem cerca de um terço do `n`, então os intervalos são mais largos por construção. Um efeito pequeno mas real poderia não ser detectável aqui mesmo existindo. O que o resultado sustenta é "não há sinal grande escondido nos casos unânimes", não "não há sinal nenhum".
- **O proxy não foi validado contra julgamento humano.** Ninguém verificou se assimetria alta de fato corresponde a caso subjetivamente fácil — seria trabalho de rotulagem, não de script.
- **A ambiguidade real do caso não é observável aqui.** O agente pode citar evidência unânime sobre um caso que, pelos dados, é indecidível — e é exatamente o que o AUC de 0,56 dentro da zona sugere (`reports/auc_zona_cinzenta.md`).
