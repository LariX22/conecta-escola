# Matriz de permissões

Todas as regras abaixo são aplicadas **no servidor** (nunca apenas escondendo botões na interface). Toda consulta é filtrada pela escola (`school_id`) do usuário autenticado: ninguém enxerga dados de outra escola.

Papéis: `admin_tecnico`, `direcao`, `secretaria`, `coordenacao_pedagogica`, `professor`, `responsavel`, `aluno`.

| Recurso / ação | admin_tecnico | direção | secretaria | coordenação | professor | responsável | aluno |
|---|---|---|---|---|---|---|---|
| Criar escola | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Ver escola | ✅ qualquer | ✅ própria | ✅ própria | ✅ própria | ✅ própria | ✅ própria | ✅ própria |
| Criar usuários (`POST /users`) | ✅ qualquer papel | ✅ ¹ | ✅ ² | ❌ | ❌ | ❌ | ❌ |
| Criar/editar alunos, vincular responsáveis | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Listar/consultar alunos | ❌ | ✅ todos | ✅ todos | ✅ todos | ✅ todos | ✅ só os vinculados | ❌ |
| Criar turmas, matricular, atribuir professores | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Listar turmas | ❌ | ✅ todas | ✅ todas | ✅ todas | ✅ só as suas | ❌ | ❌ |
| Publicar comunicado para a escola toda | ❌ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Publicar comunicado para turmas | ❌ | ✅ qualquer | ✅ qualquer | ✅ qualquer | ✅ só as suas | ❌ | ❌ |
| Ver comunicados | ❌ | ✅ todos (inclui agendados) | ✅ todos | ✅ todos | ✅ os seus + publicados para a escola/suas turmas | ✅ publicados e endereçados a ele | ❌ |
| Editar/apagar comunicado | ❌ | ✅ qualquer | ✅ qualquer | ✅ qualquer | ✅ só os seus | ❌ | ❌ |
| Confirmar leitura de comunicado | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| Ver quem leu (relatório) | ❌ | ✅ | ✅ | ✅ | ✅ só dos seus | ❌ | ❌ |
| Conversar por mensagem privada | ❌ | ✅ funcionários e responsáveis | ✅ funcionários e responsáveis | ✅ funcionários e responsáveis | ✅ funcionários + responsáveis dos seus alunos | ✅ gestão + professores dos seus filhos | ❌ |

¹ Direção cria: secretaria, professor, coordenação, responsável e aluno — sempre na própria escola.
² Secretaria cria: professor, responsável e aluno — sempre na própria escola.

## Observações

- **Não existe cadastro público.** O primeiro `admin_tecnico` nasce das variáveis de ambiente `BOOTSTRAP_ADMIN_EMAIL` e `BOOTSTRAP_ADMIN_PASSWORD`; as demais contas são criadas por quem tem permissão.
- **Aluno** ainda não tem acesso a nenhum módulo (limitação conhecida, será tratada com um recurso próprio de "meus dados").
- **Administrador técnico** cuida da infraestrutura e das escolas; não acessa o conteúdo pedagógico (alunos, turmas, comunicados).
- Quando o usuário não pode ver um recurso por ser de outra escola ou de outra turma, a API responde **404** (e não 403), para não revelar que o recurso existe.
- **Mensagens privadas** só são lidas pelos dois participantes (nem a direção lê conversa alheia). Responsável nunca conversa com outro responsável. A regra de contato é conferida a cada mensagem enviada.
