# PRD — @nethzzzz Community HQ

## Problema original
Faça um site temático do streamer @nethzzzz onde as pessoas podem colocar sugestões de jogos, clipes e comentários. Difícil de derrubar, com várias ideias úteis para um streamer.

## Arquitetura
- FastAPI + Motor (MongoDB) + JWT (cookie httpOnly + Bearer fallback)
- React (React Router + Axios) com AuthContext global
- Rate-limiting natural via idempotência (coleção `votes` com chave composta)

## Personas
- Membro da tropa (viewer): cadastra-se, sugere jogos, vota, comenta, envia clipes, denuncia
- Streamer (admin): modera, resolve denúncias, vê contas e exporta CSV/TXT

## Requisitos principais
- Cadastro/login com email + senha + nickname (nickname único, 3-24 chars)
- IP tracking (creation_ip, last_ip, last_login) atualizado a cada login
- Sugestões, clipes, comentários, enquetes com voto único por usuário
- Botão de denúncia em sugestões e clipes
- Painel admin: contas (email, nickname, data, IPs), exportação CSV/TXT sem senha, denúncias com resolver/descartar
- UI dark neon com fontes Space Grotesk + DM Mono

## Implementado — 22/02/2026
- Autenticação viewer + admin com JWT + rastreamento de IP
- Cadastro e login com nickname único e validação de senha (mínimo 6)
- CRUD protegido para sugestões/clipes/comentários/reports
- Idempotência de voto/like/poll por usuário (coleção `votes`)
- Painel admin: lista de usuários, exportação CSV/TXT sem `password_hash`, resolução de denúncias
- Botão de denúncia em sugestões e clipes
- Testado 27/27 (100%) no backend testing agent

## Backlog priorizado
- P1: Verificação de email via Resend (aguardando API key do usuário)
- P1: Upload persistente de vídeo em storage de objetos
- P1: Página de perfil pública do viewer (badges, jogos sugeridos)
- P2: Ranking semanal + notificações de live
- P2: Enum de status para reports (Resolvido/Descartado/Em análise)
- P2: Integração de presença Twitch/Kick

## Credenciais de teste
- Admin: `admin@nethzzzz.gg` / `NethHQ#2026!`
- Viewer teste: `tropa1@nethzzzz.gg` / `pass1234` (criado via signup)
