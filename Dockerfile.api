# Imagem oficial e leve do Python
FROM python:3.10-slim

# Definir diretório de trabalho no container
WORKDIR /app

# Copiar arquivos de dependências e instalar (aproveitando o cache do Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo o projeto para o container
COPY . .

# Expor a porta 8000 que a FastAPI usa por padrão
EXPOSE 8000

# Comando para rodar a aplicação via Uvicorn
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
