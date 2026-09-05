# ADR-0020: Snapshot JSON e app V3 separado
**Data:** 2026-09-04
**Status:** Accepted
**Proposto por:** Luiz Maibashi
**Contexto:** dashboard de confiabilidade por coorte

## Contexto

O dashboard precisa mostrar o experimento de 1.526.659 propostas em um deploy
leve. O dataset bruto não é versionado e supera centenas de MB. A demo V2 tem
outro trabalho: navegar memos individuais da camada agêntica. Misturar as duas
histórias faria o leitor confundir avaliação de agente com monitoramento de
modelo.

## Decisão

Criar `app/monitoramento_v3.py` como aplicação independente e alimentá-la por
`data/processed/monitoramento_v3.json`. O experimento gera o snapshot com schema
versionado, apenas agregados e metadados. O app valida o contrato antes de
renderizar e não recalcula métricas.

## Consequências

### Positivas

- deploy pequeno, determinístico, gratuito e sem credenciais;
- separação narrativa entre V2 agêntica e V3 de confiabilidade;
- interface não depende de Markdown nem de arquivos Kaggle locais;
- mesmo snapshot pode ser auditado por teste e por humano.

### Negativas

- atualização exige executar o experimento e versionar novo snapshot;
- não é tempo real e precisa dizer isso com destaque;
- JSON duplica métricas já presentes no relatório Markdown.

## Alternativas descartadas

| Alternativa | Vantagem | Motivo da rejeição |
|---|---|---|
| Recalcular no Streamlit | Sempre deriva da fonte | Dataset grande, build lento e impossível no deploy atual. |
| Interpretar o Markdown | Evita novo arquivo | Contrato frágil; texto não é API de dados. |
| Adicionar abas ao `main_v2.py` | Um único endereço | Mistura produtos, dados e teses diferentes. |
| Banco/API | Atualização dinâmica | Custo e complexidade sem sinal operacional real. |

## Impacto e validação

Sem o app separado, o gestor precisa ler relatório e documentação para montar a
decisão. Com ele, `carregar_snapshot` e `resumir_coorte` devem expor a situação
de `2020-H2` em uma tela e em menos de 30 segundos de leitura. O ROI mensurável
nesta carteira pública é tempo de diagnóstico; valor financeiro não será
inventado sem carteira, LGD e política reais.

Validação: testes do schema e da seleção, teste de fumaça do Streamlit, suíte
completa e inspeção visual. Referência:
`docs/spec/0010-dashboard-estatico-de-confiabilidade.md`.
