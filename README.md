# Conecta Escola (nome provisório)

Plataforma de comunicação escolar: comunicados, mensagens, agenda, autorizações digitais, enquetes, documentos e relatórios — para escolas, com suporte a múltiplas instituições no futuro.

> Este projeto está na **Fase 2 (fundação técnica)**. Veja o planejamento completo em [`docs/arquitetura/fase-1-planejamento.md`](docs/arquitetura/fase-1-planejamento.md).

## Estrutura do repositório

```
backend/        API em Python (FastAPI) + PostgreSQL
frontend-web/   Aplicação web em React + TypeScript (ainda não iniciada)
mobile-app/     Aplicativo móvel em React Native + Expo (ainda não iniciado)
infra/          Docker, Nginx e scripts de infraestrutura
docs/           Documentação de arquitetura, API e operação
```

## Como rodar o backend localmente (passo a passo para iniciantes)

### Pré-requisitos
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado e em execução.
- Git instalado.

### 1. Clonar/baixar o projeto
Você já está com os arquivos nesta pasta (`D:\Projeto IFMG`). Se precisar clonar em outra máquina futuramente, use:

```powershell
git clone <url-do-repositorio>
cd "Projeto IFMG"
```

### 2. Criar o arquivo de variáveis de ambiente
Copie o arquivo de exemplo e ajuste se necessário (os valores padrão já funcionam para desenvolvimento local):

```powershell
Copy-Item .env.example .env
```

**O que isso faz:** cria um arquivo `.env` com as configurações do banco de dados, segredos de desenvolvimento, etc. Esse arquivo nunca deve ser enviado ao GitHub (já está no `.gitignore`).

### 3. Subir os serviços (banco de dados, Redis e API)

```powershell
docker compose -f infra/docker/docker-compose.yml --env-file .env up --build
```

**Resultado esperado:** os contêineres `db` (PostgreSQL), `redis` e `api` (FastAPI) sobem. No final, o terminal mostra logs do Uvicorn indicando que a API está rodando em `http://localhost:8000`.

**Se der erro:** verifique se o Docker Desktop está aberto e se as portas 5432, 6379 e 8000 não estão sendo usadas por outro programa.

### 4. Aplicar as migrações do banco de dados

Em outro terminal, com os contêineres já rodando:

```powershell
docker compose -f infra/docker/docker-compose.yml exec api alembic upgrade head
```

**O que isso faz:** cria as tabelas do banco de dados conforme as migrações versionadas em `backend/migrations`.

### 5. Verificar se a API está funcionando

Abra no navegador: `http://localhost:8000/docs`

**Resultado esperado:** a documentação interativa da API (Swagger) é exibida, com os endpoints de autenticação disponíveis (`/api/v1/auth/...`).

### 6. Rodar os testes automatizados

```powershell
docker compose -f infra/docker/docker-compose.yml exec api pytest
```

**Resultado esperado:** os testes de autenticação e saúde da API passam (`X passed`).

### 7. Parar os serviços

```powershell
docker compose -f infra/docker/docker-compose.yml down
```

Para apagar também os dados do banco (recomeçar do zero):

```powershell
docker compose -f infra/docker/docker-compose.yml down -v
```

## Desenvolvimento sem Docker (opcional, para quem já tem Python instalado)

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Ajuste DATABASE_URL no .env para apontar para um Postgres local
alembic upgrade head
uvicorn app.main:app --reload
```

## Enviando alterações para o GitHub

```powershell
git add .
git commit -m "mensagem clara descrevendo a mudança"
git push
```

(O repositório remoto no GitHub ainda precisa ser criado e configurado como `origin` antes do primeiro `push`.)

## Documentação

- [Planejamento e arquitetura (Fase 1)](docs/arquitetura/fase-1-planejamento.md)
- Documentação de API: gerada automaticamente em `/docs` pela própria API (Swagger/OpenAPI).
