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

## Implementado — 14/06/2026
- **Bloqueio total do site**: sem login só aparece a tela de login/cadastro (AuthGate)
- **Verificação de email via Resend**: código de 6 dígitos no signup + banner de verificação + reenvio (throttle 60s)
- **Recuperação de senha**: esqueci minha senha → código por email → redefinir (limpa lockout)
- **Login melhorado**: mostrar/ocultar senha, lembrar de mim (30 dias), lockout 15min após 5 falhas (HTTP 423)
- **Visual**: avatar real da Twitch (navbar, hero, gate) + subtítulo "CUIUDOS DELICIOSOS FAN CLUB"
- Resend: key configurada; SENDER_EMAIL=onboarding@resend.dev (modo teste — só entrega para o email do dono da conta). Domínio `nethzcuiudos.dev` do usuário ainda NÃO verificado no painel Resend
- Testado 12/12 (100%) frontend via testing agent (iteration_3.json)

## Implementado — 14/06/2026 (parte 2)
- **Dados fakes removidos**: seeds de jogos/clipes fakes apagados do código e do banco; votos fakes da enquete zerados; números fakes (12.4K online, 1.2K chat, 100% uptime) substituídos por contagens reais (`GET /api/stats`)
- **Ranking da Tropa**: `GET /api/ranking` — Top 10 por pontos (jogo=3, clipe=3, comentário=2, voto=1), exibido na home com link pro perfil
- **Perfil dos subs**: rota `/perfil/:nickname` + `GET /api/users/{nickname}/profile` — stats, conquistas/badges (Estrategista, Curador, Cinegrafista, Clipe Lendário, Voz Ativa, Eleitor de Elite, Verificado), jogos sugeridos e clipes; nicknames clicáveis nos cards
- **Resend com fallback**: tenta enviar do domínio `tropa@nethzcuiudos.dev`; se falhar (domínio ainda "pending" no Resend), usa `onboarding@resend.dev` automaticamente

## Implementado — 14/06/2026 (parte 3)
- **Conforto de navegação**: rolagem suave, scrollbar customizada, foco visível por teclado, respeito a `prefers-reduced-motion`, scroll-to-top automático ao trocar de rota e botão flutuante "voltar ao topo"
- **Easter egg (pegadinha)**: login com email EXATO `nethzmacio@fakecuiudo.com` + senha EXATA `cuiudomasdou` → tela preta fullscreen por 6s com legendas em sequência ("NETHZZZZZ," / "VOCÊ É" / "MACIO!!!") + áudio estourado (1x) → depois começam downloads infinitos alternando 3 imagens (a cada 500ms) até fechar o navegador; `beforeunload` avisa antes de sair
  - Mecanismo: `/app/frontend/src/prank.js` + manifesto `/app/frontend/public/prank/manifest.json`; assets em `/public/prank/` (scream.m4a) e `/public/prank/dl/` (macio1.png, macio2.png, macio3.gif)
  - ⚠️ Navegadores bloqueiam múltiplos downloads automáticos: após o 1º arquivo aparece o aviso "permitir vários downloads?" — se a vítima clicar em permitir, continua infinito
- Resend revertido para `onboarding@resend.dev` (usuário apagou o domínio nethzcuiudos.dev)
- P1: Domínio `nethzcuiudos.dev` no Resend ainda com status "pending" — usuário precisa concluir verificação DNS (fallback automático já implementado)
- P1: Upload persistente de vídeo em storage de objetos
- P2: Anti-Ban Automático (banir usuário com 3+ denúncias resolvidas)
- P2: Integração de presença Twitch/Kick
- P2: Admin criar/editar enquetes e agenda pela UI

## Credenciais de teste
- Admin: `admin@nethzzzz.gg` / `NethHQ#2026!`
- Viewer teste: `tropa1@nethzzzz.gg` / `pass1234` (criado via signup)
