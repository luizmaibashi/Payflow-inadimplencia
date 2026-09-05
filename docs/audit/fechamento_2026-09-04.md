# Auditoria de fechamento do PayFlow

**Data:** 2026-09-04
**Escopo:** código, dados versionados, modelos, documentação, dependências, entrypoints e organização da pasta

## Parecer

O projeto está pronto para portfólio. Não está pronto para decisão bancária real, e o próprio produto deixa essa fronteira visível. Os entregáveis atuais são a demo estática V2 e o dashboard V3; ambos funcionam sem chave de API. A V3 permanece em modo `PESQUISA` porque as seis features são proxies sem prova point-in-time.

## Evidências executadas

| Gate | Resultado |
|---|---|
| Suíte completa | 301 testes passaram em 8,32 s |
| Contrato e dashboard V3 | 24 testes passaram em 3,88 s |
| Compilação | `python -m compileall -q app scripts` passou |
| Dependências instaladas | `python -m pip check` sem conflito |
| Higiene de diff | `git diff --check` sem erro |
| Segredos conhecidos | nenhum arquivo identificado por padrões de chave Gemini, Groq, OpenAI ou chave privada |

O único aviso da suíte veio do `joblib`: neste Windows ele não identificou núcleos físicos e usou núcleos lógicos. O fallback não altera dados, seed, resultado ou critério de aceite.

## Mudanças da auditoria

### Retenção de legado

| Ação | Artefatos | Motivo |
|---|---|---|
| Removido do `HEAD` | runtime Streamlit/FastAPI V1, dois modelos V1, CSV sintético e notebook V1 | nenhum consumidor atual; confundiam a versão suportada e mantinham dependências mortas |
| Preservado | `docs/LEGADO_V1.md`, três figuras históricas e histórico Git | registram a evolução e permitem recuperação sem poluir o runtime atual |
| Mantido local e ignorado | `data/raw/home_credit_stability/` | fonte necessária para reproduzir o experimento pesado; não cabe no Git |
| Mantido e versionado | snapshot V3, memos de LLM e labels humanos | necessários para demos em clone limpo; memos rotulados não são regeneráveis com identidade garantida |

### Reprodutibilidade e manutenção

- `.env.example` passou a declarar as duas chaves opcionais.
- `requests` passou a ser dependência direta; `fastapi` e `uvicorn` saíram com o runtime V1.
- devcontainer agora abre o dashboard V3.
- workflow do GitHub executa a suíte sem dados brutos nem segredos.
- specs 0001 a 0010 foram marcadas como aprovadas; a spec 0011 registra este fechamento.
- README e AGENTS foram alinhados ao estado V3.

### Falhas fail-closed corrigidas

O snapshot já rejeitava campo desconhecido, mas aceitava relações impossíveis. Agora rejeita:

- inadimplentes acima do tamanho da coorte ou faixa;
- intervalos de inadimplência ou AUC invertidos;
- métrica fora do próprio intervalo;
- gap diferente de observado menos previsto;
- faixa duplicada e limites inválidos;
- KS e delta de ausência fora do domínio;
- treino maior que a população total;
- timestamp sem fuso e data de referência inválida.

O registro de ferramentas do agente também passou a falhar fechado. Cada método público `consultar_*` precisa declarar descrição e aplicabilidade; uma ferramenta nova esquecida quebra o teste em vez de receber aprovação silenciosa.

## Auditoria PAVC

### Advogado do diabo

1. **O dashboard pode parecer produção.** Mitigação: a decisão abre em `PESQUISA`, a tela declara protótipo local e nomeia autenticação, agendamento, responsável e escalonamento como ausentes.
2. **AUC estável pode esconder probabilidade errada.** Mitigação: Brier e faixas fixas de calibração aparecem ao lado da AUC.
3. **Drift pode ser interpretado como ordem de retreino.** Mitigação: texto e política dizem que é pista de investigação, sem causalidade ou retreino automático.
4. **Snapshot versionado pode envelhecer.** Aceito para portfólio estático; em produção precisaria data de validade, execução agendada e observabilidade.
5. **Clone limpo não regenera o estudo pesado sem Kaggle.** Aceito e documentado; ele reproduz as demos a partir de artefatos agregados/versionados.

### Explicabilidade

Em termos simples, AUC confere se o modelo põe os casos em uma ordem útil. Calibração confere se o número escrito na etiqueta promete a frequência certa. Drift avisa que os clientes novos ficaram diferentes dos antigos. Nenhum desses sinais sozinho decide crédito: eles dizem ao gestor se pode continuar observando, se precisa investigar ou se deve bloquear o uso.

### Casos de borda exercitados

1. snapshot ausente ou corrompido;
2. campo novo desconhecido e versão de schema incompatível;
3. coorte ou faixa duplicada;
4. contagem, intervalo, gap ou timestamp contraditório;
5. ferramenta nova sem política explícita de aplicabilidade.

## Riscos residuais aceitos

- LGD de 70% a 85%, `EAD = AMT_CREDIT` e âncoras macro são premissas declaradas, não medições brasileiras.
- A Camada 2 não demonstrou separação de risco: no backtest final, `n=564`, NEGAR menos APROVAR foi +1,3 p.p., IC95% [-6,7 p.p.; +9,2 p.p.]. Não há ROI para ampliar o experimento neste dataset.
- O SDK legado `google.generativeai` está EOL. Ele fica restrito aos scripts opcionais e arquivados da V2. Se chamadas LLM forem reativadas, migrar para `google.genai` antes de qualquer lote.
- O monitor V3 usa proxies sem disponibilidade point-in-time comprovada. Por isso não pode sair de `PESQUISA` sem nova evidência de dados.
- O repositório não declara licença de reutilização. Isso não afeta a demonstração, mas exige decisão do autor antes de permitir uso por terceiros.

## Decisão de encerramento

Não há pendência funcional para o escopo de portfólio. Os riscos restantes dependem de dados, operação real ou decisão jurídica; inventar uma solução local daria aparência de completude sem evidência. Qualquer retomada deve nascer de uma nova tese de valor, não de continuação automática desta frente.
