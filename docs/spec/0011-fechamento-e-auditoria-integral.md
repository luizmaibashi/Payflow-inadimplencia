# Spec 0011 — Fechamento e auditoria integral

**Status:** Implementada e auditada em 2026-09-04

## Objetivo

Encerrar o PayFlow como projeto de portfólio coerente, reproduzível e honesto, eliminando legado executável sem consumidor e preservando a trilha histórica útil.

## Requisitos funcionais

1. Manter dois entregáveis atuais e separados:
   - `app/main_v2.py`: demonstração estática da investigação agêntica;
   - `app/monitoramento_v3.py`: dashboard de confiabilidade por coorte.
2. Remover da árvore atual o runtime V1, seus modelos, dataset sintético e notebook, após confirmar ausência de consumidores atuais.
3. Preservar em `docs/LEGADO_V1.md`, figuras e Git o aprendizado histórico da V1, sem instrução falsa de execução.
4. Fechar os estados de revisão humana das specs 0001–0010 aprovadas ao longo da frente V3.
5. Atualizar README, AGENTS, dependências, configuração e devcontainer para apontarem apenas aos entrypoints atuais.
6. Produzir relatório de auditoria com evidência, decisões de retenção e riscos residuais.

## Requisitos de qualidade

- suíte completa verde;
- `git diff --check` limpo;
- bytecode compilável;
- dependências instaladas consistentes;
- nenhum segredo versionado detectado por busca estática;
- dashboard carrega snapshot agregado com contrato fail-closed;
- nenhuma dependência ativa de arquivo removido.

## Restrições

- não chamar rede nem API paga;
- não retreinar modelos;
- não excluir dados brutos ignorados necessários para reproduzir a V3;
- não reescrever histórico Git;
- limitações estruturais (proxy point-in-time, LGD não medida e V2 sem ganho detectável) permanecem explícitas.

## Critério de aceite

O projeto pode ser entendido e executado a partir do README; todos os testes passam; a auditoria explica com precisão o que está pronto para portfólio e por que isso não equivale a produção bancária.
