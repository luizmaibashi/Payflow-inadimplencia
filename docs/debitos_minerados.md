# Débitos minerados no fechamento

**Data:** 2026-09-04

Este arquivo registra apenas débitos com aprendizado transferível para outros projetos. Limitações específicas do PayFlow permanecem no `AGENTS.md` e no relatório de auditoria.

## Débito #22: allowlist de gate que falhava aberta

- **Classificação:** estrutural.
- **Instância local:** `FERRAMENTAS_SEMPRE_APLICAVEIS` podia ficar desatualizada e aprovar trajetória por omissão.
- **Proteção local:** ADR-0022, registro único de descrição/aplicabilidade e teste reflexivo contra todos os métodos `consultar_*`.
- **Proteção na base:** regra “lista de cobertura falha aberta” já existe no `AGENTS.md` raiz. O teste local passa a ser a implementação concreta do princípio.

## Débito #30: saída não determinística tratada como regenerável

- **Classificação:** estrutural.
- **Instância local:** memos de LLM regenerados romperam o vínculo com labels humanos.
- **Proteção local:** memo e label são versionados juntos; `.gitignore` contém exceção explícita.
- **Proteção na base:** regra “saída não determinística usada como ground truth não é regenerável” já existe no protocolo raiz.

## Itens mantidos como específicos do projeto

LGD não medida, `EAD = AMT_CREDIT`, âncoras macro demonstrativas, teto de previsibilidade da zona cinzenta e ausência de ganho detectável da Camada 2 dependem do domínio e dos dados do PayFlow. Não foram generalizados como regra universal.
