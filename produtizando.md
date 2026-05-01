# 🚀 Estratégia de Produtização e MLOps: Payflow

Este documento define a arquitetura e os próximos passos para colocar o sistema Payflow em ambiente de produção com nível profissional de maturidade (MLOps Nível 1+), seguindo o rigor do Framework Maibashi.

## 🏗️ 1. Arquitetura de Deploy (Desacoplada)

Para garantir estabilidade e escalabilidade, o sistema adota uma arquitetura em duas camadas (Frontend + Backend), isoladas em containers Docker.

### A. Backend (Inteligência & API)
*   **Tecnologia:** FastAPI (Python 3.10)
*   **Servidor:** Uvicorn
*   **Função:** Servir o modelo `.pkl` e aplicar as regras de negócio via `utils.py`.
*   **Escalabilidade:** Pronta para Load Balancing na Nuvem (Render, AWS ECS, GCP Cloud Run).

### B. Frontend (Interface & Simulador)
*   **Tecnologia:** Streamlit
*   **Função:** Interface didática e interativa para o usuário final (C-Level / Analista).
*   **Comunicação:** Faz requisições HTTP RESTful para o Backend.

---

## 🐳 2. Estratégia de Conteinerização (Docker)

Atualmente, o projeto possui um `Dockerfile` que serve a API. Para uma orquestração profissional, utilizaremos o **Docker Compose**.

**Plano de Ação:**
1.  **`Dockerfile.api`**: Responsável pelo ambiente FastAPI (porta 8000).
2.  **`Dockerfile.front`**: Responsável pelo ambiente Streamlit (porta 8501).
3.  **`docker-compose.yml`**: Orquestrador que sobe as duas máquinas simultaneamente, criando uma rede interna para a comunicação entre a interface e o cérebro preditivo.

---

## 🔁 3. MLOps e Automação (CI/CD)

### Continuous Integration (CI)
Toda nova feature ou mudança de modelo passará pelos seguintes testes (ex: GitHub Actions):
*   **Testes Unitários:** `pytest` rodando a suíte `test_paridade.py` para evitar Training-Serving Skew.
*   **Qualidade de Código:** Validação com `flake8` ou `black`.

### Monitoramento e Prevenção de Drift
Para evitar degradação do modelo ao longo do tempo:
*   **Data Drift:** Implementar no futuro um log de predições (salvar entradas e saídas em um banco/S3).
*   **Configuração Dinâmica:** `RISCO_BAIXO_MAX` e `RISCO_MEDIO_MAX` serão passados via variáveis de ambiente (`.env`), permitindo ajuste de apetite de risco em tempo real sem rebuild do container.

---

## 🏁 4. Checklist para Nuvem

- [x] Criar `docker-compose.yml` e isolar Dockerfiles.
- [x] Parametrizar a URL da API no Streamlit (`app/main.py`) usando variáveis de ambiente.
- [x] Configurar um `Makefile` ou `.sh` para facilidade de execução local (`docker compose up --build`).
- [ ] Escolher plataforma de Deploy (ex: Render para API + Streamlit Community Cloud para Frontend, ou AWS ECS para ambos).
