# Fase 1 — Planejamento e Arquitetura

> Status: proposta para aprovação. Nenhum código de aplicação foi escrito ainda — apenas a estrutura de pastas do repositório.

## 1. Visão geral do sistema

Plataforma web + mobile de comunicação escolar, multi-tenant (várias escolas no futuro), com perfis de Direção, Secretaria, Professores, Coordenação Pedagógica, Responsáveis, Alunos e Administrador Técnico. Módulos: comunicados com confirmação de leitura, mensagens privadas, galeria de fotos/vídeos, agenda/eventos, autorizações digitais, enquetes, notificações, documentos e relatórios. Prioriza stack open source, custo zero para começar, instalável em servidor próprio.

## 2. Nome provisório e identidade

Nome de trabalho: **Conecta Escola** (provisório, sem verificação de disponibilidade de domínio/marca).

Dez sugestões de nome (a validar disponibilidade antes de decidir):

| # | Nome | Justificativa | Pronúncia/Memorização |
|---|------|----------------|------------------------|
| 1 | Elo Escolar | "Elo" remete a vínculo família-escola | Curto, fácil |
| 2 | Vínculo Edu | Reforça conexão família-escola | Médio, claro |
| 3 | EscolaConecta | Direto, explica a função | Fácil |
| 4 | Pontte | Trocadilho com "ponte" (conexão) | Fácil, memorável |
| 5 | Mural Edu | Remete a comunicados/mural escolar | Fácil |
| 6 | Classe Viva | Transmite dinamismo da turma | Fácil |
| 7 | Rota Escolar | Sugere acompanhamento do percurso do aluno | Fácil |
| 8 | Nexo Escola | "Nexo" = conexão/ligação | Médio |
| 9 | Elo Família | Foco no vínculo familiar | Fácil |
| 10 | Avante Edu | Transmite progresso/acompanhamento | Fácil |

Identidade visual proposta (conceitual, a refinar):
- Paleta: azul institucional (#1B4965) + verde-água de apoio (#5FA8D3) + laranja de destaque para alertas/urgente (#F4A261) + neutros (cinza claro, branco).
- Tipografia: fonte sem serifa, humanista (ex.: Inter ou Nunito), boa legibilidade mobile.
- Ícones: estilo outline, arredondado, consistente com Material/Lucide.
- Logotipo conceitual: símbolo que combine "elo"/conexão (dois arcos entrelaçados) com elemento escolar sutil.

## 3. Requisitos

### Funcionais (RF) — resumo por módulo
- RF01 Autenticação, recuperação de senha, convites, ativação de conta.
- RF02 Cadastro de escolas, usuários, papéis/permissões, alunos, responsáveis, turmas, vínculos.
- RF03 Comunicados com segmentação de público, anexos, agendamento, confirmação de leitura, lembretes.
- RF04 Mensagens privadas (1:1 e grupo), histórico, indicadores de entrega/leitura.
- RF05 Galeria de fotos/vídeos por turma/evento com controle de acesso.
- RF06 Agenda/eventos com confirmação de presença.
- RF07 Troca entre múltiplos filhos sem novo login.
- RF08 Autorizações digitais (criação, resposta, prazo, histórico, revogação).
- RF09 Enquetes/formulários com público-alvo e exportação controlada.
- RF10 Notificações push/e-mail configuráveis por usuário.
- RF11 Repositório de documentos privados.
- RF12 Relatórios e indicadores com filtros e exportação CSV.

### Não funcionais (RNF)
- RNF01 Autorização validada sempre no servidor (nunca só na UI).
- RNF02 Isolamento de dados entre escolas (multi-tenant).
- RNF03 Responsivo (mobile + desktop).
- RNF04 Disponível para instalação em servidor próprio via Docker.
- RNF05 Auditoria de ações sensíveis.
- RNF06 Testes automatizados para regras de negócio críticas e permissões.
- RNF07 Conformidade orientada à LGPD (dados de crianças/adolescentes).
- RNF08 Observabilidade mínima (logs estruturados, sem dados sensíveis).

## 4. Arquitetura proposta

**Monólito modular** (não microsserviços no início — complexidade desnecessária para uma equipe pequena):

```
[Cliente Web React] ─┐
[App Mobile Expo]  ──┼──> [Nginx (proxy/TLS)] ──> [API FastAPI] ──> [PostgreSQL]
                      │                              │
                      │                              ├──> [Redis] (filas/cache/sessões)
                      │                              └──> [Armazenamento de arquivos] (disco local / S3-compatível)
                      └── WebSocket (mensagens/notificações em tempo real)
```

- Backend organizado em módulos internos (auth, comunicados, mensagens, agenda, autorizações, enquetes, arquivos, notificações, relatórios), cada um com suas rotas, serviços e modelos — preparando uma eventual extração futura sem reescrever tudo.
- Multi-tenant via `school_id` em todas as tabelas relevantes + filtro obrigatório no nível de serviço/consulta (estratégia "linha compartilhada com isolamento lógico", mais simples de operar que bancos separados por escola).

## 5. Tecnologias recomendadas

| Camada | Escolha | Alternativa | Justificativa |
|---|---|---|---|
| Backend | Python + FastAPI | Django | FastAPI é leve, assíncrono, ótima documentação automática (OpenAPI) |
| Banco de dados | PostgreSQL | MySQL | Recursos avançados (JSONB, índices parciais), gratuito, maduro |
| Front-end web | React + TypeScript | Vue | Tipagem reduz erros; grande comunidade |
| Mobile | React Native + Expo | Flutter | Reaproveita conhecimento de React/TS do time |
| Tempo real | WebSockets (FastAPI) | Polling | Necessário para mensagens/notificações instantâneas |
| Filas/cache | Redis | Nenhum (só no futuro) | Simples de operar via Docker; pode ser adiado se não houver volume inicial |
| Arquivos | Armazenamento local compatível com S3 (MinIO) | Disco puro | Permite migrar para S3 real sem reescrever código |
| Proxy reverso | Nginx | Caddy | Padrão de mercado, bem documentado |
| Containers | Docker + Docker Compose | Instalação manual | Reprodutibilidade, facilita onboarding de iniciante |
| CI | GitHub Actions | Nenhum | Gratuito para repositórios públicos/dentro do limite free para privados |

## 6. Viabilidade do Docker

Recomendado: sim. Benefícios — ambiente idêntico entre máquinas, facilita setup para quem está aprendendo, simplifica deploy em servidor próprio. Custo: curva de aprendizado inicial pequena, mitigada com documentação passo a passo na Fase 2.

## 7. Estrutura inicial do repositório (já criada nesta pasta)

```
Projeto IFMG/
├── backend/
│   ├── app/{api,core,models,schemas,services,db}/
│   ├── migrations/
│   └── tests/
├── frontend-web/
│   ├── src/{components,pages,services,hooks,contexts}/
│   └── tests/
├── mobile-app/
│   └── src/
├── infra/
│   ├── docker/
│   ├── nginx/
│   └── scripts/
├── docs/
│   ├── arquitetura/   <- este arquivo
│   ├── api/
│   └── operacional/
└── .github/
    ├── workflows/
    └── ISSUE_TEMPLATE/
```
(Pastas vazias contêm `.gitkeep` para serem versionadas pelo Git; serão removidas conforme os arquivos reais forem adicionados.)

## 8. Modelo conceitual do banco de dados (entidades principais)

`schools`, `users`, `roles`, `permissions`, `user_roles`, `students`, `guardians`, `student_guardian_links`, `classrooms`, `enrollments`, `teacher_classroom_assignments`, `announcements`, `announcement_recipients`, `announcement_reads`, `conversations`, `conversation_participants`, `messages`, `events`, `event_attendance`, `authorizations`, `authorization_responses`, `surveys`, `survey_questions`, `survey_responses`, `files`, `file_permissions`, `notifications`, `notification_preferences`, `audit_logs`.

Todas as tabelas de domínio escolar incluem `school_id` (chave estrangeira) para isolamento multi-tenant.

## 9. Principais módulos de API (alto nível)

`/auth/*`, `/schools/*`, `/users/*`, `/students/*`, `/guardians/*`, `/classrooms/*`, `/announcements/*`, `/messages/*` (+ WebSocket `/ws/messages`), `/events/*`, `/authorizations/*`, `/surveys/*`, `/files/*`, `/notifications/*`, `/reports/*`.

## 10. Plano de implementação por etapas (após aprovação)

1. Fundação técnica: repositório, Docker Compose (Postgres + Redis + API + Nginx), migrações iniciais, CI básico.
2. Autenticação, usuários, papéis/permissões, multi-tenant base.
3. Cadastros (alunos, responsáveis, turmas, vínculos).
4. Comunicados + confirmação de leitura.
5. Mensagens privadas + tempo real.
6. Agenda/eventos.
7. Autorizações digitais.
8. Enquetes/formulários.
9. Documentos/arquivos.
10. Notificações (push/e-mail).
11. Relatórios/indicadores.
12. Front-end web cobrindo os módulos acima.
13. App mobile (Expo) cobrindo os fluxos essenciais.
14. Preparação para produção (HTTPS, backups, monitoramento, hardening).

## 11. Estratégia de segurança e proteção de dados

Hash de senha (bcrypt/argon2), JWT ou sessão segura com expiração curta + refresh, autorização sempre checada no servidor, validação de entrada (Pydantic), proteção contra SQL injection (ORM parametrizado), XSS/CSRF, rate limiting no login, logs sem dados pessoais sensíveis, auditoria de ações críticas, backups automatizados do Postgres, HTTPS obrigatório em produção, segredos via variáveis de ambiente (nunca no repositório). Tratamento de dados de menores conforme LGPD: minimização de dados, finalidade explícita, necessidade de autorização dos responsáveis — decisões legais específicas devem ser validadas com assessoria jurídica da instituição.

## 12. Estimativa qualitativa de custos

| Item | Gratuito para começar? | Observação |
|---|---|---|
| Repositório GitHub | Sim | Limite de minutos de Actions no plano gratuito |
| Hospedagem do código | Sim (GitHub) | Não hospeda a aplicação em produção |
| Servidor de produção | Não | Depende de VPS/servidor próprio da escola |
| Banco de dados | Sim (self-hosted) | Sem custo de licença; custo é o servidor |
| E-mail transacional | Parcial | Provedores gratuitos têm cotas baixas (ex.: 100/dia) |
| Push notification | Sim (Firebase/Expo) | Dentro de limites gratuitos para volume inicial |
| Armazenamento de arquivos | Sim (disco local) | Cresce com uso; S3 real tem custo por GB |
| Domínio | Não | Custo anual baixo, mas não gratuito |

## 13. Riscos, decisões pendentes e critérios de aceitação

**Riscos**: volume de notificações pode ultrapassar cotas gratuitas; servidor próprio exige responsabilidade de backup/manutenção pela escola; requisitos legais de autorização digital podem exigir validação jurídica.

**Decisões pendentes (aguardando você)**: nome definitivo da plataforma; confirmação da stack (FastAPI/React/Expo); se Redis entra já na Fase 2 ou é adiado; onde será o servidor de produção (VPS próprio, já disponível?).

**Critérios de aceitação da Fase 1**: este documento revisado e aprovado antes de iniciar a Fase 2 (fundação técnica).
