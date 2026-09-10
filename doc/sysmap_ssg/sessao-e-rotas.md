# Sessão, URLs e rotas (SSG/SysMap)

## Domínios

- `https://portal.sysmap.com.br/wp-login.php` — o portal principal, um
  WordPress atrás de Cloudflare. Ver `pages/login/README.md`.
- `https://ssg.sysmap.com.br/` — o SSG (Sistema de Suporte à Gestão) em si.
  **Não tem login próprio**: acessar a raiz cai direto no login do portal
  acima. A sessão do SSG é a mesma sessão do portal.

## Entrada válida

A URL raiz (`ssg.sysmap.com.br/`) redireciona para o login. A entrada
válida é `index.html` + rota por hash, ex.:
`https://ssg.sysmap.com.br/index.html#/access-entry/get-list`. O legado
`/new/timesheet/timesheetrecording.asp` também redireciona pra essa mesma
rota.

## É uma SPA roteada por hash

Todas as telas do SSG vivem sob `index.html#/<rota>`. Isso importa pra
automação porque **navegar direto trocando o hash funciona**, mesmo pra
telas cujo link no menu está escondido em submenus recolhidos e aninhados —
foi assim que a tela de listagem de OSI (`#/osi/get-list`) foi alcançada
sem precisar simular a cadeia de hover/clique do menu (ver
`pages/listagem-de-osi/recon.md`).

## Sessão via perfil de browser dedicado

O login nunca é automatizado — o portal pede um código do Google
Authenticator (TOTP), e nada aqui deveria gerar isso. A automação sobe um
Edge (ou Chrome) com um **perfil de usuário dedicado e persistente**; a
pessoa loga à mão uma vez nesse perfil, e a sessão (cookie) fica salva pra
sempre nas próximas execuções. Se a sessão expirar, a tela de login
reaparece e a automação deve parar e avisar, nunca tentar digitar usuário/
senha/código sozinha.
