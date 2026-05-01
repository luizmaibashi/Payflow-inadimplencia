.PHONY: run build stop down logs test clean

# Comandos Docker
build:
	docker compose build

run:
	docker compose up -d

stop:
	docker compose stop

down:
	docker compose down

logs:
	docker compose logs -f

# Comandos de Teste locais
test:
	pytest tests/

# Limpeza
clean:
	docker compose down -v --rmi all
	find . -type d -name "__pycache__" -exec rm -r {} +
	find . -type d -name ".pytest_cache" -exec rm -r {} +
