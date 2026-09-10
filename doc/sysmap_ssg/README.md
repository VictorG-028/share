# Conhecimento sobre o site SSG/SysMap

Recon do site que a automação dirige (`ssg.sysmap.com.br`, parte do portal
`sysmap.com.br`) — seletores, comportamento de tela, armadilhas. Isto é
conhecimento sobre um site externo, não código: nada aqui é importado por
`src/`. Se o site mudar e quebrar alguma automação, é aqui que se atualiza
antes de mexer no código.

Para a história de *como* cada descoberta aconteceu (datas, decisões,
comparação do gerador com o site real), ver `../ROADMAP.md` — este é o
histórico completo do projeto, não só do site. Os documentos abaixo são a
referência *atual*, sem a narrativa.

## Não específico de uma página

- [`stack.md`](stack.md) — jQuery/Bootstrap/maskedinput/typeahead/bootbox,
  e o que cada peça implica pra automação.
- [`sessao-e-rotas.md`](sessao-e-rotas.md) — domínios, redirects, SPA por
  hash, e como a sessão persiste via perfil de browser dedicado.
- [`campo-mascarado.md`](campo-mascarado.md) — a receita de digitação que
  funciona nos campos de data/hora mascarados, usada em mais de uma tela.

## Páginas sondadas

- [`pages/login/`](pages/login/README.md) — login do portal
  (`portal.sysmap.com.br/wp-login.php`).
- [`pages/apontamento/`](pages/apontamento/README.md) — tela de
  Registro de E/S (`#/access-entry/get-list`), onde a automação realmente
  aponta os horários, e de onde o catálogo de OSI é lido (botão "?" ao lado
  do campo de OSI). Seletores exatos em `selectors.json`.
- [`pages/listagem-de-osi/`](pages/listagem-de-osi/recon.md) — tela de
  Listagem Ordem de Serviço Interna (`#/osi/get-list`), sondada como
  possível fonte pra montar o catálogo de OSI; inclui uma proposta de
  solução alternativa em `proposta-tabela-completa.md`.
- [`pages/cadastro-de-osi/`](pages/cadastro-de-osi/README.md) — tela de
  Cadastro Ordem de Serviço Interna (`#/osi/get-form`), onde o
  `register-new-osi` cria OSIs; documenta como o período de cada atividade
  é descoberto (um Gravar recusado de propósito). Seletores em
  `selectors.json`.
