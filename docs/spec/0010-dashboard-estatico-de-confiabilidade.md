# Spec 0010: Dashboard estático de confiabilidade por coorte

**Data:** 2026-09-04
**Status:** Implementada e aprovada em 2026-09-04
**Dono da aprovação de merge:** Luiz Maibashi

## Objetivo

Permitir que um gestor de risco responda em menos de 30 segundos se o modelo
segue confiável em uma coorte e qual sinal exige investigação. A tela traduz
AUC, Brier, drift e calibração por faixa sem fingir operação em tempo real.

## Escopo

- criar `app/monitoramento_v3.py`, separado da demonstração da camada agêntica;
- gerar um snapshot JSON pequeno e versionado a partir do experimento canônico;
- validar o snapshot com schema fail-closed antes de renderizar;
- abrir com decisão, motivo, data do snapshot e restrição `PESQUISA`;
- mostrar uma régua temporal das três coortes;
- detalhar AUC/Brier, drift por feature e calibração por faixa da coorte
  selecionada;
- manter `n`, eventos e intervalos junto das métricas;
- incluir uma leitura guiada, em linguagem de negócio, para decisão, AUC/Brier,
  drift e calibração;
- mostrar o caminho do experimento até o gestor, distinguindo o snapshot local
  demonstrado da operação futura ainda não implementada;
- funcionar sem dataset bruto, modelo, rede, API ou credencial.

Não inclui retreino, recalibração, upload, alertas, atualização automática,
decisão individual, integração com a V2 ou alegação de carteira brasileira.

## Trabalho único da tela

Responder: **“o modelo ainda é confiável nesta coorte e o que devo
investigar?”** O teste principal usa `2020-H2`: AUC estável, três alertas de
drift, nenhuma crítica e faixa superior aproximadamente calibrada.

## Direção visual

- papel frio `#F3F6F8`, tinta `#14212B`, evidência `#2F5D7E`, investigação
  `#C58A2A`, bloqueio `#A5473E` e estabilidade `#39735A`;
- `Georgia` só na tese, `Aptos/Segoe UI` no corpo e `Consolas` nos números;
- assinatura: “régua de coortes”, como dossiês sequenciais de uma carteira;
- semáforo só comunica decisão real; não usar cor como decoração;
- sem animação: o produto é auditoria, e estabilidade visual favorece leitura.

```text
┌──────────────────────────────────────────────────────────────┐
│ PAYFLOW / LIVRO DE COORTES      SNAPSHOT · PESQUISA          │
│ O modelo segue confiável?  →  [PESQUISA] motivo explícito    │
├──────────────────────────────────────────────────────────────┤
│ 2019-Q4 ───────── 2020-H1 ───────── 2020-H2 selecionada      │
├───────────────────────┬──────────────────────────────────────┤
│ Evidência da coorte    │ O que investigar                    │
│ n · eventos · AUC      │ features em alerta/crítica          │
│ Brier · taxa + IC      │ causa não inferida                  │
├───────────────────────┴──────────────────────────────────────┤
│ Calibração: previsto × observado nas dez faixas             │
└──────────────────────────────────────────────────────────────┘
```

## Critérios de aceitação

1. Snapshot ausente, JSON inválido, versão desconhecida ou campo obrigatório
   ausente falha com mensagem acionável; nunca vira zero ou verde.
2. O JSON contém apenas métricas agregadas e metadados, sem dados individuais.
3. A coorte selecionada controla todos os detalhes exibidos.
4. `n`, inadimplentes e IC95% aparecem com taxa e AUC.
5. Drift mostra contagens e features não estáveis, separando KS de ausência.
6. Calibração mostra previsto, observado, IC, gap e estado nas dez faixas.
7. `2020-H2` comunica corretamente 3 alertas, 0 críticas e faixa 10
   `APROXIMADA` com 5,25% previsto versus 5,35% observado.
8. A tela não usa rede nem carrega os arquivos brutos do Kaggle.
9. O app passa em teste de fumaça do Streamlit e é verificado visualmente em
   desktop; layout estreito não pode esconder a decisão ou a limitação.
10. A suíte completa termina verde e `git diff --check` não encontra erro.
11. A tela explica como ler os quatro sinais e deixa explícito que o público
   final é o gestor de risco, não o cliente de crédito.
12. A tela não apresenta publicação, atualização automática, autenticação ou
   governança operacional futura como se já existissem.

## Input policy check

- dado sensível: não; somente agregados do dataset público anonimizado;
- escopo autorizado: dashboard estático de pesquisa confirmado pelo usuário;
- efeito externo: nenhum; execução local sem API;
- aprovação humana obrigatória antes de merge: Luiz Maibashi.

## PAVC pré-implementação

1. **Snapshot velho parecer ao vivo.** Mitigação: data, origem e rótulo
   `SNAPSHOT DE PESQUISA` sempre visíveis.
2. **Campo ausente virar número neutro.** Mitigação: schema versionado e
   validação fail-closed antes de renderizar.
3. **Gráfico esconder amostra ou incerteza.** Mitigação: `n`, eventos e IC no
   mesmo bloco; gráfico é apoio, não fonte única.

Casos de borda: arquivo ausente, JSON corrompido, schema incompatível, lista
vazia e coorte sem detalhe. Escala é pequena por desenho; concorrência não se
aplica ao snapshot somente leitura; temporalmente, a data de geração impede
confundir histórico com tempo real.

## Evidências de implementação

- snapshot canônico: `data/processed/monitoramento_v3.json`, schema versão 1;
- gerador e validação fail-closed: `app/snapshot_monitoramento.py`;
- tela: `app/monitoramento_v3.py`;
- testes de contrato, integração e fumaça: `tests/test_snapshot_monitoramento.py`,
  `tests/test_experimento_proxy_estabilidade.py` e
  `tests/test_monitoramento_v3_app.py`;
- inspeção visual concluída em layout estreito, preservando decisão, rótulo de
  pesquisa e data do snapshot.

## PAVC pós-implementação

O dashboard não transforma drift em causa nem em ordem de retreino. Campos
obrigatórios continuam fail-closed e as tabelas apresentam percentuais
arredondados apenas na tela; o JSON preserva os valores completos. O principal
risco residual é temporal: o arquivo só muda quando o experimento canônico é
executado novamente. Por isso, data e rótulo `SNAPSHOT DE PESQUISA` permanecem
no cabeçalho e a tela não se apresenta como monitoramento em tempo real.

### Complemento didático

Advogado do diabo: uma explicação poderia fazer uma capacidade futura parecer
já entregue, sobrecarregar a decisão com texto ou tornar a tela estreita difícil
de percorrer. Mitigações: o bloco `Hoje neste projeto` separa protótipo local de
operação futura; a decisão continua antes da leitura guiada; os passos viram uma
coluna no celular. Os casos de borda preservados são snapshot antigo, alerta sem
causa identificada, leitor que confunde `PESQUISA` com liberação e leitura por
gestor sem conhecimento de AUC. A seção responde a esses casos sem esconder
limitações ou prometer retreino automático.
