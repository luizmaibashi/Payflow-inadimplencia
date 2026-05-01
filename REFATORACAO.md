# 🛠️ Plano de Refatoração: Payflow (Crédito & Inadimplência)

**Objetivo:** Eliminar a redundância de Feature Engineering e garantir que a lógica de produção seja idêntica à de treinamento.

## 🔴 Débitos Técnicos Identificados

1. **Duplicação de Feature Engineering (Grave):** A lógica de criação de features (`parcela_estimada`, `comprometimento_renda`, `intensidade_credito`) e a codificação de variáveis categóricas estão implementadas diretamente dentro do `CreditScoringService` no `app/service.py`. Isso provavelmente replica código contido no notebook de treinamento.
2. **Fragilidade na Codificação Categórica:** O mapeamento manual de `canal_aquisicao`, `regiao` e `tipo_produto` em `app/service.py` é propenso a erros se novos canais ou regiões forem adicionados ao dataset sem atualização do código da API.
3. **Ausência de `utils.py`:** Não existe um módulo compartilhado para processamento de dados. O `service.py` está assumindo responsabilidades de limpeza e transformação que deveriam ser modulares.
4. **Acoplamento de Decisão:** Os thresholds de decisão (0.40 e 0.65) estão "hardcoded" no método `predict`. Esses valores deveriam ser parâmetros de configuração.

## 📋 Lista de Tarefas (Checklist de Refatoração)

- [x] **Criação do `app/utils.py` ou `src/utils.py`:**
    - Isolar a função `preprocess_data(raw_data)` que realiza o cleaning e o feature engineering.
    - Garantir que esta função possa ser chamada tanto pelo notebook (em lote) quanto pela API (individualmente).
- [x] **Externalização de Thresholds:**
    - Mover as regras de decisão (APROVAR/REVISAR/NEGAR) para um arquivo de configuração `config.json` ou variáveis de ambiente.
- [x] **Refatoração do `app/service.py`:**
    - Simplificar o método `process_features` para apenas chamar o `utils.preprocess_data`.
- [x] **Documentação de Paridade:**
    - Adicionar um teste de validação que compare a saída do modelo no ambiente de desenvolvimento vs. produção para o mesmo input.

## 🚀 Próximos Passos

1. Extrair a lógica de cálculo financeiro para o `utils.py`.
2. Validar a API com o novo módulo centralizado.
