# PRD — @nethzzzz Community HQ

## Problema original
Crie um aplicativo web: Faça um site tematico do streamer @nethzzzz onde as pessoas podem colocar sugestoes de jogos , colocar clipes e comentarios em cada uma dessas coisas. Faça um site dificil de derrubar e coloque varias outras ideias uteis para um streamer

## Arquitetura e decisões
- Frontend React com React Router, Axios, Framer-ready CSS e ícones Lucide.
- Backend FastAPI com MongoDB Motor; respostas filtram `_id` para JSON seguro.
- Autenticação administrativa JWT com cookie httpOnly e Bearer fallback.
- API usa somente as URLs configuradas nos arquivos `.env` protegidos.

## Personas
- Membro da tropa: sugere jogos, vota, comenta, envia clipes e participa de enquetes.
- Streamer/moderador: acompanha a agenda, controla sugestões e revisa denúncias.

## Requisitos principais
- Arena de sugestões com votos, comentários, status e marcação de jogado.
- Clip hub para links e interação de likes.
- Agenda de lives, enquetes, links sociais e moderação protegida.
- Interface gamer neon, responsiva e acessível por test IDs.

## Implementado — 21/02/2026
- Home Arena com hero, estatísticas, seed data e navegação entre áreas.
- CRUD público de sugestões, clipes, comentários e votos.
- Agenda e enquetes funcionais.
- Login admin, sessão JWT, proteção da lista de denúncias e painel de moderação.
- Layout mobile sem overflow e menu primário navegável por ícones.
- Correção de serialização MongoDB em criação de clipes/comentários.

## Backlog priorizado
- P0: adicionar upload persistente de vídeo em storage de objetos.
- P1: permitir ao admin alterar status das sugestões e resolver denúncias pela UI.
- P1: adicionar perfis/apelidos persistentes da comunidade.
- P2: ranking semanal, notificações de live e integração de presença Twitch/Kick.

## Próximas tarefas
1. Conectar upload de clipes a storage de objetos.
2. Criar ações de moderação para status, exclusão e denúncias.
3. Adicionar ranking de membros ativos e badges da tropa.
