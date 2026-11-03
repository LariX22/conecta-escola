# API de Comunicados

Comunicados são avisos da escola para os responsáveis, com público-alvo (escola toda ou turmas), agendamento e confirmação de leitura. Prefixo: `/api/v1/announcements`. Todas as rotas exigem login (`Authorization: Bearer <token>`). Quem pode fazer o quê está em [`permissoes.md`](permissoes.md).

## Como funciona

- **Público-alvo (`audience`)**
  - `"school"`: todos os responsáveis da escola. Apenas direção, secretaria e coordenação podem usar.
  - `"classrooms"`: responsáveis de alunos com matrícula **ativa** nas turmas informadas em `classroom_ids`. Professores só podem escolher turmas às quais estão atribuídos.
- **Destinatários calculados na consulta**: não há uma lista copiada no momento da publicação. Um responsável vinculado depois passa a ver os comunicados da turma do filho, e uma matrícula encerrada tira o comunicado dele.
- **Agendamento (`publish_at`)**: data/hora **com fuso horário** (ex.: `2026-11-10T08:00:00-03:00`). Omitido ou no passado = publica agora. Enquanto for futuro, o `status` é `"scheduled"` e só o autor e a gestão enxergam.
- **Confirmação de leitura**: o responsável chama `POST /{id}/read`. É idempotente: a primeira vez devolve `201`; repetir devolve `200` com a mesma data. O campo `requires_confirmation` indica que o autor quer a confirmação explícita (a interface pode destacar o botão "Li e estou ciente").

## Endpoints

| Método e rota | O que faz | Respostas principais |
|---|---|---|
| `POST /announcements` | Publica (ou agenda) um comunicado | `201`, `403` (sem permissão para o público), `404` (turma inexistente na escola), `422` |
| `GET /announcements` | Lista os comunicados que o usuário pode ver, do mais recente ao mais antigo | `200` (inclui `my_read_at` para responsáveis), `403` |
| `GET /announcements/{id}` | Detalhe de um comunicado | `200`, `404` |
| `PATCH /announcements/{id}` | Altera `title` e/ou `body` (autor ou gestão) | `200`, `403`, `404`, `422` |
| `DELETE /announcements/{id}` | Apaga o comunicado e suas confirmações (autor ou gestão) | `204`, `403`, `404` |
| `POST /announcements/{id}/read` | Responsável confirma a leitura | `201` primeira vez, `200` repetida, `403`, `404` |
| `GET /announcements/{id}/reads` | Relatório: destinatários, quem leu e quem falta (autor ou gestão) | `200`, `403`, `404` |

## Exemplos

Publicar para duas turmas, com confirmação, agendado:

```json
POST /api/v1/announcements
{
  "title": "Reunião de pais",
  "body": "Sexta-feira, às 19h, no auditório.",
  "audience": "classrooms",
  "classroom_ids": ["<id da turma 5A>", "<id da turma 5B>"],
  "requires_confirmation": true,
  "publish_at": "2026-11-10T08:00:00-03:00"
}
```

Relatório de leitura (`GET /announcements/{id}/reads`):

```json
{
  "announcement_id": "...",
  "requires_confirmation": true,
  "recipient_count": 30,
  "read_count": 18,
  "pending_count": 12,
  "recipients": [
    { "guardian_id": "...", "guardian_name": "Ana Souza", "read_at": "2026-11-10T11:32:10Z" },
    { "guardian_id": "...", "guardian_name": "Bruno Lima", "read_at": null }
  ]
}
```

## Ainda não incluído

- **Anexos**: virão com o módulo de documentos/arquivos.
- **Lembretes automáticos** para quem não confirmou e **notificações push/e-mail**: dependem do módulo de notificações.
- **Cópia da lista de destinatários** (para auditoria histórica): avaliar junto com os logs de auditoria.
- A interface deve exibir `title` e `body` sempre como **texto** (nunca como HTML), para evitar XSS.
