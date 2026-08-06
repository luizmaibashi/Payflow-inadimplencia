# ADR-0009: Adaptadores de LLM — saída JSON estruturada, import lazy e configuração centralizada

**Data**: 2026-08-05
**Status**: Accepted
**Contexto**: PayFlow — plugagem do LLM real no `ClienteLLM` (Protocol) da Camada 2

---

## 1. CONTEXTO (O QUÊ?)

A Camada 2 foi construída inteira com o cliente LLM **injetado** (ADR-0003): orquestração, teto de chamadas, cegueira ao score e groundedness são testados contra um dublê determinístico, sem rede. Faltava o adaptador que traduz um provider real para esse contrato.

**Restrições que o desenho anterior impõe:**

- A assinatura do Protocol é `proxima_acao(contexto, ferramentas)`. Nenhum parâmetro novo pode entrar — é a garantia **estrutural** da cegueira ao score (ADR-0003 §2.1), não uma questão de disciplina.
- A suíte precisa continuar rodando sem SDK e sem chave. O teste de cegueira ao score é o mais importante do projeto; fazê-lo depender de um pacote de provider seria acoplamento errado.
- O projeto tem **quatro entrypoints** (`scripts/`, `notebooks/`, Streamlit em `app/main.py`, FastAPI em `app/api.py`). Qualquer solução de configuração que exija lembrar de uma chamada em cada um vai falhar no notebook.

**Baseline no momento da decisão:** 93 testes passando, zero dependência de LLM, `.gitignore` sem regra para `.env`.

---

## 2. DECISÃO (POR QUÊ?)

Três decisões acopladas, em `app/clientes_llm.py` e `app/config.py`.

### 2.1 Saída JSON estruturada pelo provider, não parser de texto

Ambos os providers têm modo de JSON garantido (Gemini `response_mime_type: application/json`; Groq `response_format: {"type": "json_object"}`). Delegar a garantia de formato ao provider elimina a classe de erro *"o modelo devolveu texto que quase é JSON"* antes de qualquer parser rodar.

**ROI:** o custo é zero (parâmetro de configuração) e remove a necessidade de heurística de extração — o tipo de código que falha silenciosamente, "quase acertando", e cujo defeito só aparece semanas depois no meio de um lote.

**Limite explícito:** isso garante **sintaxe**, não **semântica**. Quem garante semântica é o `MemoCredito` (ADR-0003). As duas camadas são complementares e a distinção precisa ficar clara para quem mexer depois.

### 2.2 Import do SDK é lazy (dentro do `__init__`)

O `import google.generativeai` / `from groq import Groq` acontece na construção do cliente, não no topo do módulo.

**Razão:** import no topo faria `tests/test_agente_underwriting.py` — inclusive `test_contexto_do_agente_nao_contem_o_score` — depender de ter o SDK do Google instalado. Isso inverte a relação: o invariante mais frágil do projeto passaria a ser refém de uma dependência de rede que ele não usa.

**Preço reconhecido e pago:** falha de dependência aparece só em runtime. Mitigações:

1. `try/except ImportError` → `DependenciaAusente` com o comando exato (`pip install -r requirements-llm.txt`), em vez de `ModuleNotFoundError` cru.
2. `# type: ignore[import-not-found]` documentando que a ausência é intencional para o analisador estático.
3. `requirements-llm.txt` separado, com a intenção escrita no próprio arquivo.

### 2.3 Temperatura 0 por padrão

`TEMPERATURA_PADRAO = 0.0`, parametrizável por construtor.

**Razão quantificada:** o ADR-0004 §2.5 estabelece que, com `n=100` e 80% de acerto, o IC95% vai de ~72% a ~88% — um delta de 4 p.p. entre dois prompts já é menos da metade do ruído amostral. Somar ruído de **decodificação** em cima disso tornaria qualquer comparação entre variantes de prompt não-interpretável. Não garante determinismo perfeito (nenhum provider promete), mas remove a fonte que está sob nosso controle.

### 2.4 Configuração centralizada em `app/config.py`

`load_dotenv(RAIZ / ".env", override=False)` roda uma vez, na importação do módulo. `exigir_chave(nome)` falha cedo com instrução acionável.

**`override=False` é a parte não-óbvia:** variável já presente no ambiente (CI, container, deploy) **vence** o arquivo local. Sem isso, um `.env` esquecido na máquina sobrescreveria a chave de produção injetada pelo container — falha silenciosa e difícil de rastrear.

### 2.5 O que este ADR **não** decide

`ClienteGroq` implementa `proxima_acao` — o contrato do **gerador**. Ele **não é o juiz do ADR-0004**, apesar de a chave Groq ter sido criada com esse propósito. O juiz avalia rubricas binárias sobre um memo pronto (assinatura do tipo `julgar(memo, trace) → veredito`) e ainda **não existe no código**. A chave serve aos dois papéis; a interface, não.

Manter Llama como **gerador alternativo** tem valor próprio e separado: permite medir se um resultado depende do modelo ou do desenho.

---

## 3. CONSEQUÊNCIAS

**Positivas:**

- Trocar de provider não toca a orquestração — o Protocol já isolava isso, e agora há duas implementações provando.
- CI e suíte continuam sem SDK, sem chave e sem rede: 109 testes em ~0,9 s.
- `.env` deixou de ser risco de vazamento: `.gitignore` corrigido (`.env`, `.env.*`, exceto `.env.example`). **A regra anterior só cobria `env/`, `venv/`, `.venv/` — diretórios de virtualenv. O arquivo `.env` não estava coberto.**
- Erro de configuração e de dependência falha com instrução, não com stack trace genérico.

**Negativas / débito incorrido:**

- **Sem retry nem timeout.** Falha de rede transitória derruba a rodada inteira num lote de 120 casos. Decidido **não** implementar antes de medir a taxa real de falha — política de retry escolhida sem dado é chute.
- **Memo inválido = caso perdido.** Não há segunda tentativa devolvendo o erro ao modelo, embora o agente já faça exatamente isso para erro de ferramenta. Mesma justificativa: medir antes.
- **Sem controle de custo por rodada.** Nenhum contador de tokens ou teto de gasto.
- `app/utils.py` continua lendo `RISCO_BAIXO_MAX`/`RISCO_MEDIO_MAX` direto de `os.environ`, fora do `config.py` — inconsistência conhecida, fora do escopo desta decisão.

---

## 4. ALTERNATIVAS DESCARTADAS

| Opção | Vantagem | Por quê rejeitada |
|-------|----------|-------------------|
| Import do SDK no topo do módulo | Convenção padrão; falha cedo e visível | Faria o teste de cegueira ao score depender do SDK do Google — acoplamento que inverte a prioridade do projeto |
| Parsear texto livre com regex/heurística | Funciona em qualquer modelo, sem recurso especial | Falha silenciosa: o parser "quase acerta" e ninguém percebe. Ambos os providers escolhidos suportam JSON garantido |
| `load_dotenv()` dentro do adaptador | Funciona sem ninguém lembrar de nada | Efeito colateral escondido em código de biblioteca: importar um módulo passaria a mexer no ambiente do processo, vazando entre testes |
| `load_dotenv()` só nos entrypoints | Convenção da comunidade; teste continua puro | Quatro entrypoints = quatro lugares para lembrar. O esquecido seria o notebook |
| Framework de abstração (LangChain, LiteLLM) | Troca de provider de graça, muitos providers | O Protocol já resolve a troca em 12 linhas. Dependência pesada para um problema que o desenho anterior já tinha eliminado |
| Um único provider (só Gemini) | Menos código, menos superfície | O ADR-0004 exige juiz de **família diferente** do gerador; a segunda chave precisa existir de qualquer forma |
| `except Exception` ao montar o memo | Captura qualquer falha do provider | Disfarçaria bug do próprio módulo (`AttributeError`, `TypeError`) de "modelo respondeu errado", contaminando a estatística de qualidade. Apertado para `ValidationError` |

---

## 5. IMPACTO & VALIDAÇÃO

**Métrica de sucesso:**

| Métrica | Baseline | Alvo |
|---|---|---|
| Testes passando sem SDK/chave/rede | 93 | 109 ✅ |
| Tempo da suíte | ~1,0 s | manter < 2 s ✅ |
| Chaves versionadas por acidente | risco aberto | zero ✅ (`git status` limpo com `.env` presente) |
| Taxa de memo inválido em lote real | não medida | **a medir** nos ~120 casos |
| Taxa de falha transitória de rede | não medida | **a medir** nos ~120 casos |

**Cenários de regressão (quando esta decisão falha):**

- Provider muda o formato do campo de resposta (`resposta.text`, `choices[0].message.content`) → `RespostaLLMInvalida` em 100% dos casos. Detectável na primeira rodada, não silencioso.
- Provider deixa de suportar JSON garantido → volta a classe de erro que a §2.1 eliminou.
- Rate limit do free tier num lote de 120 → sem retry, a rodada morre no meio. **Este é o risco mais provável de todos** e o débito mais urgente.
- `.env` com `GEMINI_API_KEY=` (vazio) → `ChaveAusente`, coberto por teste.

**Validação:** primeira rodada real contra os ~120 casos da zona cinzenta. Medir as duas taxas acima **antes** de decidir política de retry.

---

## 6. LINKS RELACIONADOS

- ADR-0003 (contrato do memo e cliente injetado — origem do Protocol adaptado aqui)
- ADR-0004 (metodologia de avaliação; §2.3 exige juiz de família diferente — juiz ainda não implementado)
- ADR-0006 (padrão de rigor herdado)
- Código: `app/clientes_llm.py`, `app/config.py`
- Testes: `tests/test_clientes_llm.py` (12), `tests/test_config.py` (4)
- Débitos abertos correlatos: #10 (juiz não calibrado), #11 (deploy serve modelo legado)
