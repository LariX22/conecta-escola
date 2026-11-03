# Conecta Escola (nome provisório)

Plataforma de comunicação escolar: comunicados, mensagens, agenda, autorizações digitais, enquetes, documentos e relatórios — para escolas, com suporte a múltiplas instituições no futuro.

> Este projeto está na **Fase 3 (implementação progressiva de módulos)**. A fundação técnica (Fase 2) está completa e o módulo de **cadastros** (escolas, alunos, turmas, matrículas, vínculo de responsáveis) já foi implementado. Veja o planejamento completo em [`docs/arquitetura/fase-1-planejamento.md`](docs/arquitetura/fase-1-planejamento.md).

## Módulos implementados

- **Autenticação** (`/api/v1/auth`): login (JWT) e dados do usuário autenticado.
- **Usuários** (`/api/v1/users`): **não existe cadastro público**. Contas são criadas por quem tem permissão — `admin_tecnico` cria qualquer papel; `direcao` cria secretaria, professor, coordenação, responsável e aluno da própria escola; `secretaria` cria professor, responsável e aluno da própria escola. O primeiro `admin_tecnico` nasce das variáveis `BOOTSTRAP_ADMIN_EMAIL`/`BOOTSTRAP_ADMIN_PASSWORD`.
- **Cadastros** (`/api/v1/schools`, `/api/v1/students`, `/api/v1/classrooms`): cadastro de escolas (restrito a `admin_tecnico`), alunos, turmas, matrículas, atribuição de professores a turmas e vínculo de responsáveis a alunos — com isolamento multi-tenant por `school_id` e permissões por papel aplicadas no servidor.

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

**Resultado esperado:** a documentação interativa da API (Swagger) é exibida, com os endpoints disponíveis (`/api/v1/auth/...`, `/api/v1/users`, etc.).

**Primeiro acesso:** o administrador inicial é criado na inicialização com o e-mail e a senha definidos em `BOOTSTRAP_ADMIN_EMAIL` e `BOOTSTRAP_ADMIN_PASSWORD` (no `.env`). No Swagger: use `POST /api/v1/auth/login`, copie o `access_token`, clique em **Authorize** e cole o token. Depois crie uma escola (`POST /api/v1/schools`) e o usuário de direção dela (`POST /api/v1/users`).

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

## Publicar no Render (plano gratuito)

O arquivo [`render.yaml`](render.yaml) descreve a API e o banco PostgreSQL. O Render cria os dois sozinho e já preenche `DATABASE_URL` e `SECRET_KEY`. Só pedirá o e-mail e a senha do primeiro administrador (`BOOTSTRAP_ADMIN_EMAIL` e `BOOTSTRAP_ADMIN_PASSWORD`).

1. No [Render](https://dashboard.render.com), abra **Blueprints** → **New Blueprint Instance**.
2. Escolha o repositório `conecta-escola` e clique em **Connect**.
3. Dê um nome ao projeto e clique em **Apply**. Aguarde o deploy terminar.
4. Abra `https://conecta-escola-api.onrender.com/docs` (ou a URL exibida no painel) para ver a API no ar.

**Limites do plano gratuito:**
- A API "dorme" após 15 minutos sem acessos; a primeira requisição depois disso leva cerca de 1 minuto.
- O banco gratuito **expira 30 dias após a criação** (14 dias de carência; depois é apagado) e só é permitido 1 banco gratuito por conta.
- Se já existir um serviço antigo configurado manualmente (ex.: o que falhou com erro de `package.json`), apague-o para não duplicar deploys.
- Em um serviço criado manualmente, adicione `BOOTSTRAP_ADMIN_EMAIL` e `BOOTSTRAP_ADMIN_PASSWORD` em *Environment*. Depois do primeiro login, essas duas variáveis podem ser removidas.

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
