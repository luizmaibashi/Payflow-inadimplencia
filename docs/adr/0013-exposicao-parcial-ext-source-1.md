# ADR-0013: Exposição parcial de `EXT_SOURCE_1` ao agente — testar poder preditivo sem replicar o score inteiro

**Data**: 2026-08-12
**Status**: **Rejected no mesmo dia** — ver §7. Mantido no histórico porque o raciocínio original (§1-6) é válido em si; o erro estava em generalizar importância medida na população inteira para a zona cinzenta especificamente.
**Contexto**: PayFlow — débito #34 (backtest da Camada 2), causa raiz identificada via importância por permutação

---

## 1. CONTEXTO (O QUÊ?)

O backtest do débito #34 mediu que o agente não separa risco real de forma estatisticamente detectável (`n=564`, separação NEGAR−APROVAR +1,3%, IC95% [-6,7%; +9,2%]). Investigando o porquê, a importância por permutação no modelo real da Camada 1 (`n_test=61.503`, split reproduzido com `RANDOM_STATE=42` idêntico ao treino) mostrou:

| Variável | Importância (perda de AUC ao embaralhar) |
|---|---|
| `EXT_SOURCE_2` | 0,0415 |
| `EXT_SOURCE_3` | 0,0363 |
| `EXT_SOURCE_1` | 0,0164 |
| **Soma dos 3** | **0,0942** |
| Soma das 8 variáveis de bureau/pagamento que o agente vê | 0,0043 |

`EXT_SOURCE_1/2/3` (escores de crédito externos, anonimizados, parte do dataset Home Credit) dominam a predição — **21,8× mais importantes**, combinados, que tudo que o agente hoje consegue enxergar. Confirmado por grep: nenhuma ferramenta do agente (`app/ferramentas_caso.py`) expõe essas variáveis. O agente foi arquitetado sem acesso ao sinal que mais importa neste dataset especificamente.

## 2. DECISÃO (POR QUÊ?)

**Expor `EXT_SOURCE_1` ao agente via uma ferramenta nova — e só `EXT_SOURCE_1`, não `EXT_SOURCE_2`/`EXT_SOURCE_3`.**

### 2.1 Por que só uma, e a de menor peso

`EXT_SOURCE_1` sozinha tem importância 0,0164 — real, mas a menor das três, e ainda assim **~3,8× maior** que a soma de tudo que o agente já vê hoje. Isso testa a hipótese central (dar ao agente um sinal de fato preditivo muda a separação de risco?) sem entregar de uma vez um proxy cuja soma (0,0942) se aproxima perigosamente do papel que o `p_default` cumpre — o que tensionaria o ADR-0003 §2.1 (cegueira ao score) de forma mais séria. Expor uma variável de peso moderado é um passo intermediário deliberado, não a solução final.

### 2.2 A tensão com o ADR-0003 permanece, mitigada mas não eliminada

`EXT_SOURCE_1` não é `p_default` nem derivado matemático dele (é um insumo bruto, calculado por terceiros, que entra no modelo junto com ~138 outras variáveis). O teste de cegueira do ADR-0003 (nenhum `p_default` ou derivado no contexto) continua passando literalmente. Mas é preciso reconhecer: **é o insumo mais forte que existe**, e dar acesso a ele desloca a natureza do julgamento do agente — de "leio comportamento de pagamento e julgo" pra "leio um escore de terceiro e pondero junto com o resto". Isso é uma mudança real de design, registrada aqui, não escondida atrás do tecnicismo "não é p_default".

### 2.3 Limitação de cobertura já conhecida, precisa de mitigação junto

`EXT_SOURCE_1` está **ausente em 64,5% dos casos da zona cinzenta** (pior que os 56,4% do dataset inteiro). Isso significa que a nova ferramenta vai devolver "não disponível" na maioria dos casos — e é exatamente o padrão do débito #33 (juiz/agente tratando dado ausente como ausência de risco) que acabou de ser corrigido no juiz. **A ferramenta nova precisa ser instruída, desde o prompt, que ausência de `EXT_SOURCE_1` é falta de dado do terceiro que o calcula, não sinal de risco baixo nem alto** — mesma lição do #33, aplicada preventivamente aqui em vez de descoberta depois por outro bug.

## 3. CONSEQUÊNCIAS

**Positivas:**
- Testa a hipótese central do débito #34 com controle — se a separação de risco não melhorar mesmo com um sinal real, a causa não é só "falta de sinal preditivo", abre outras hipóteses.
- Degrau intermediário, não bet-the-project: fácil de reverter (remover a ferramenta) se o resultado não justificar o risco de ancoragem.

**Negativas / custo:**
- Qualquer medição real exige regenerar memos contra a API (Gemini) — **bloqueado no momento**: faturamento do GCP foi desvinculado deliberadamente em 2026-08-12 (ver `AGENTS.md`, seção de custo). Precisa ser revinculado antes de validar.
- Cobertura de 35,5% na zona cinzenta limita o quanto essa mudança pode mover a agulha, mesmo se funcionar — a maioria dos casos não tem o dado novo disponível.
- Mais uma ferramenta pra manter sincronizada com `FERRAMENTAS_SEMPRE_APLICAVEIS` e a lista de validação de trajetória (débito #22 já registra esse risco de lista manual).

## 4. ALTERNATIVAS DESCARTADAS

| Opção | Vantagem | Por que não agora |
|---|---|---|
| Expor `EXT_SOURCE_1/2/3` juntas | Resolve o poder preditivo de uma vez (0,0942 de importância) | Soma se aproxima do papel do score — risco de ancoragem alto demais pra um primeiro teste |
| Não expor nada, aceitar o resultado negativo | Mais simples, ADR-0003 sem ambiguidade | Descarta a causa raiz mais forte já identificada sem testar — deixa a pergunta central sem resposta completa |
| Criar uma variável derivada/discretizada de `EXT_SOURCE_1` (ex.: "score externo: baixo/médio/alto") em vez do valor bruto | Menos "parecido" com um score contínuo | Adiciona complexidade de design (onde cortar os buckets?) sem mudar a substância do problema — ainda é o mesmo insumo, só ofuscado |

## 5. VALIDAÇÃO (pendente — depende de billing do GCP)

**Métrica de sucesso:** rodar `piloto_camada2.py` de novo sobre uma amostra (tamanho a decidir — não precisa ser 722 de novo, um lote menor já indica direção) com a ferramenta nova disponível, rodar `backtest_camada2.py`, comparar a separação NEGAR−APROVAR contra a medição atual (+1,3%, IC [-6,7%; +9,2%]).

**Não é sucesso silencioso:** se a separação não mudar de forma perceptível mesmo com `EXT_SOURCE_1` disponível, isso é evidência de que o problema não é só "falta de sinal preditivo" — pode ser o próprio mecanismo de decisão do agente (como ele pondera fatores), não só quais fatores ele vê.

**Quando revisar esta decisão:** se o resultado justificar, decidir se vale escalar pra `EXT_SOURCE_2`/`EXT_SOURCE_3` (e aí sim enfrentar de vez a tensão com o ADR-0003 em profundidade) ou se o ganho marginal não compensa o risco de ancoragem.

## 6. REFERÊNCIAS

- Débito #34 — `AGENTS.md`, causa raiz completa com números
- ADR-0003 — cegueira ao score, invariante mais frágil do projeto
- ADR-0011 — critério de Task Completion (o que este ADR não muda)
- Débito #33 / ADR-0012 — mesma lição de "dado ausente ≠ ausência de risco", aplicada preventivamente aqui
- Débito #22 — lista manual de ferramentas, risco de nova ferramenta ser esquecida na validação de trajetória

## 7. CORREÇÃO (2026-08-12, mesmo dia — antes de qualquer implementação)

**O erro:** a importância por permutação de `EXT_SOURCE_1/2/3` (§1) foi medida sobre `X_test` inteiro (`n=61.503`) — a população geral, incluindo os casos "fáceis" fora da zona cinzenta. A decisão deste ADR generalizou essa importância pra zona cinzenta sem checar se ela se mantém **especificamente ali**, que é onde o agente de fato opera.

**A checagem que faltava, feita depois de o usuário pedir revisão antes de implementar:** correlação de `EXT_SOURCE_1/2/3` com `TARGET` **dentro da zona cinzenta** (`n=2.102`):

| Variável | Correlação — dataset inteiro | Correlação — **dentro da zona cinzenta** | Disponibilidade na zona cinzenta |
|---|---|---|---|
| `EXT_SOURCE_1` | -0,155 | **-0,031** | 35,5% |
| `EXT_SOURCE_2` | -0,160 | **-0,038** | 99,8% |
| `EXT_SOURCE_3` | -0,179 | **-0,019** | 72,8% |

**O sinal praticamente desaparece dentro da zona cinzenta** — do mesmo tamanho de ruído que os sinais de bureau/pagamento que o débito #34 já tinha descartado (-0,073 a +0,029). Isso faz sentido estrutural: a zona cinzenta é definida **como** a região onde o modelo (dominado por `EXT_SOURCE`) fica incerto — por construção, é quase certo que o sinal dominante já foi "consumido" ali e não sobra poder de separação residual.

**Consequência:** expor `EXT_SOURCE_1` ao agente não deveria mudar o resultado do backtest de forma perceptível. Gastar API real pra testar isso repetiria o mesmo erro metodológico que a Hipótese A do débito #34 já expôs — só que com uma variável nova, sem necessidade. **Este ADR não vira implementação.**

**Achado que sobra, mais importante que o original:** a zona cinzenta pode ser uma região onde **nenhum sinal disponível — nem os do agente, nem o do modelo campeão — separa risco de forma detectável**. Isso não é uma lacuna de ferramenta a corrigir; é evidência de que a incerteza ali pode ser genuína e estrutural, não um problema de informação faltando. Registrado como extensão do débito #34 no `AGENTS.md` — muda o que vale a pena tentar a seguir (não é "dar mais dado ao agente", é questionar se dá pra separar risco nessa fatia específica com qualquer método, humano ou não).
