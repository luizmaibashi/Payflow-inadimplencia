# Como baixar o dataset Home Credit Default Risk

O dataset (~3,3 GB extraído) **não é versionado** (ver `.gitignore`). Para reproduzir:

1. Conta no Kaggle + aceitar as regras da competição em [kaggle.com/c/home-credit-default-risk](https://www.kaggle.com/c/home-credit-default-risk) ("I Understand and Accept").
2. Gerar token em `kaggle.com/settings` → API → Create New Token.
3. `pip install kaggle`
4. Configurar autenticação (CLI 2.x, fluxo por token):
   ```bash
   mkdir -p ~/.kaggle
   echo "SEU_TOKEN_AQUI" > ~/.kaggle/access_token
   chmod 600 ~/.kaggle/access_token
   ```
5. Baixar e extrair:
   ```bash
   python -m kaggle competitions download -c home-credit-default-risk -p data/raw/home_credit
   cd data/raw/home_credit && unzip home-credit-default-risk.zip && rm home-credit-default-risk.zip
   ```

Arquivos esperados em `data/raw/home_credit/`: `application_train.csv`, `application_test.csv`, `bureau.csv`, `bureau_balance.csv`, `previous_application.csv`, `POS_CASH_balance.csv`, `credit_card_balance.csv`, `installments_payments.csv`, `HomeCredit_columns_description.csv`, `sample_submission.csv`.
