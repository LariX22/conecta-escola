# API de Mensagens privadas

Conversas 1:1 entre pessoas da mesma escola, com histórico, mensagens não lidas, indicador de leitura e entrega em tempo real por WebSocket. Prefixo REST: `/api/v1/messages`. Quem pode falar com quem está resumido abaixo e em [`permissoes.md`](permissoes.md).

## Regras de contato (aplicadas no servidor)

| Quem é você | Com quem pode conversar |
|---|---|
| Direção, secretaria, coordenação | Qualquer funcionário e qualquer responsável da escola |
| Professor | Demais funcionários e responsáveis de alunos matriculados em turmas às quais ele está atribuído |
| Responsável | Direção, secretaria, coordenação e professores das turmas dos seus filhos. **Nunca outro responsável** |
| Aluno / admin técnico | Sem acesso nesta fase |

- A regra é conferida também **a cada mensagem enviada**: se o filho trocar de turma, por exemplo, as novas mensagens são bloqueadas (`403`), mas o histórico continua visível aos dois.
- **Privacidade:** só os dois participantes leem uma conversa. Nem a direção acessa conversas alheias (responde `404`).

## Endpoints REST

| Método e rota | O que faz | Respostas principais |
|---|---|---|
| `GET /messages/contacts?q=` | Pessoas com quem posso conversar (filtra por nome) | `200`, `403` |
| `POST /messages/conversations` | Abre (ou reaproveita) a conversa com `{"recipient_id": "..."}` | `201` nova, `200` já existia, `403` não pode falar com essa pessoa, `404` |
| `GET /messages/conversations` | Minhas conversas com mensagens, da mais recente para a mais antiga (com `unread_count` e `last_message`) | `200` |
| `GET /messages/conversations/{id}/messages?limit=50&before=` | Histórico em ordem cronológica. `before` (data com fuso) traz mensagens mais antigas para paginar | `200`, `404`, `422` |
| `POST /messages/conversations/{id}/messages` | Envia `{"body": "..."}` (1 a 4000 caracteres, espaços nas pontas são removidos) | `201`, `403`, `404`, `422` |
| `POST /messages/conversations/{id}/read` | Marca a conversa como lida até agora | `204`, `404` |

`read_by_recipient` em cada mensagem indica que a **outra pessoa** já abriu a conversa depois dela (base para os "vistos" na interface). Abrir o histórico não marca como lida: a interface chama `/read` quando o usuário realmente vê a conversa.

## Tempo real (WebSocket)

Endereço: `ws://<servidor>/ws/messages` (ou `wss://` em produção).

1. Ao conectar, a **primeira mensagem** deve ser a autenticação: `{"type": "auth", "token": "<JWT>"}`. (O token não vai na URL para não aparecer em logs.) Sem autenticar em 10 segundos, ou com token inválido, a conexão é fechada com código `1008`.
2. O servidor responde `{"type": "ready"}`.
3. Depois chegam eventos das conversas do usuário:
   - `{"type": "message", "conversation_id": "...", "message": { ... }}`: nova mensagem (também chega às outras abas de quem enviou).
   - `{"type": "read", "conversation_id": "...", "reader_id": "...", "read_at": "..."}`: alguém marcou a conversa como lida.
4. `{"type": "ping"}` devolve `{"type": "pong"}` (útil para manter a conexão viva).

O envio continua sendo feito pela API REST; o WebSocket só **entrega eventos**. Se a conexão cair, nada se perde: a interface reconecta e recarrega a lista pela API.

## Limitações conhecidas

- As conexões ficam na memória do processo. Com **mais de uma instância** da API será preciso um canal compartilhado (Redis pub/sub, já previsto na arquitetura). Com uma instância (caso atual) funciona sem isso.
- Conversas em grupo, anexos e indicador de "entregue" (além de "enviada" e "lida") ficam para próximas etapas.
- Notificações push/e-mail para quem está offline dependem do módulo de notificações.
