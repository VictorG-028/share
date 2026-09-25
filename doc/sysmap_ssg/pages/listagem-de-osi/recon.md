# Tela de listagem de OSI (`#/osi/get-list`)

Internamente chamada de **"tela de resposta lenta e inconsistente"** -- não
"bugada": ela funciona, só que com tempo de resposta alto e variável, ao
contrário do resto do site (ex.: o filtro de `access-entry` documentado em
`../apontamento/README.md` resolve em ~1,3s de forma constante).

> **Atualização de 2026-09-10 — esta tela deixou de ser o caminho.**
> O "Filtrar" desta tela envia um único `POST osi/get-by-parameters` com
> `{"UserName": "<nome>"}`, e chamar esse endpoint direto devolve a mesma
> informação em **0,645s** contra **60s+** dirigindo a tela. O contrato está
> em `../../api.md`; a tela continua documentada aqui porque é o **fallback**
> (`src/modules/browser/ssg_osi_list.py`).
>
> Duas descobertas de 2026-09-10 que só aparecem ao dirigir a tela:
>
> - **Ela cospe um alerta ao abrir**: *"Erro! Falha ao processar o serviço
>   remoto `https://services.sysmap.com.br/api/v1/users?userId=undefined`."*
>   É provavelmente a origem da fama de "bugada". Precisa ser fechado, senão o
>   backdrop engole todo clique seguinte.
> - **O DataTables recicla os `<tr>`**: depois de filtrar, as linhas antigas
>   são reaproveitadas em vez de recriadas, então o truque do marcador que
>   funciona na tela de apontamento **não funciona aqui**. O sinal confiável de
>   "terminou" é o contador *"Mostrar X até Y de **Z** registros"*.
> - O "?" de Profissional trouxe **exatamente uma opção** (o próprio usuário),
>   como esperado; selecioná-la preenche o campo.

## O que já se sabia (sondagem de 2026-08-29)

- A rota existia no menu ("Pesquisar OSI"), mas ficava dentro de submenus
  recolhidos e aninhados -- tamanho zero no DOM até expandir uma cadeia longa
  de hover/clique. Não foi tentada a fundo.

## O que se descobriu agora (sondagem de 2026-09-04)

- **O problema do menu não existe de verdade**: navegar direto para
  `https://ssg.sysmap.com.br/index.html#/osi/get-list` (mudar o hash) abre a
  tela sem precisar achar/expandir nada no menu. O SSG é uma SPA roteada por
  hash (ver `../../sessao-e-rotas.md`), então isso é esperado, mas vale
  registrar que ninguém precisa mais se preocupar com o menu aninhado para
  chegar nesta tela.
- **Título da tela**: "Listagem Ordem de Serviço Interna" -- confirma que
  "OSI" = Ordem de Serviço Interna.
- **Estado inicial**: só o painel "Filtro" aparece (campos: Código, Projeto,
  Requisito, Status, Período [Data Inicial/Final], Profissional, Gestor, e o
  botão "Filtrar"). Nenhuma tabela de resultado existe até filtrar.
- **Não precisa preencher nada para ver as próprias OSIs**: clicar em
  "Filtrar" com todos os campos vazios já traz só as OSIs do usuário logado
  (o campo "Profissional" fica em branco na tela, o filtro é implícito pela
  sessão).
- **Tempo de resposta real, medido**: depois de clicar "Filtrar", a tela
  mostra um overlay (fundo escurecido + indicador de carregamento de 3
  pontinhos) sobre o painel de filtro inteiro. Numa sondagem esse overlay
  ainda estava visível aos 12s; em outra tentativa, o resultado já estava
  pronto ao reconectar ~alguns segundos depois. Não dá pra confiar num sleep
  fixo -- qualquer automação futura precisa fazer *polling* (ex.: esperar até
  `table tbody tr` ter linhas, com timeout generoso, tipo 30s) em vez de
  `time.sleep()` de duração fixa.
- **A tabela de resultado é DataTables** (mesma stack jQuery do resto do
  site, ver `../../stack.md`): tem busca "Pesquisar:", paginação (5
  registros por página por padrão), contador "Mostrar X até Y de Z
  registros", e exportação para Excel/CSV/PDF.
- **Colunas, na ordem em que aparecem**: Ação, Verificações, Código,
  Descrição, Status, Profissional, Gestor, Esforço Orçado, Esforço
  Realizado, Custo Orçado, Data do Pedido, Nome do Projeto, Requisito, Início
  Estimado, Término Estimado.
- **"Código" é o número puro da OSI** (ex.: `82695`, o mesmo
  `DEFAULT_OSI_NUMBER` de `ssg_controller.py`) -- não a string composta que
  aparece depois de escolher no typeahead do campo de apontamento (`OSI
  <numero> | <Projeto> | <Atividade> - <id>`, ver `../apontamento/README.md`).

## Vocabulário de Status

O campo "Status" do filtro também tem um botão "?" (`.button-show-items`) --
é o mesmo widget genérico "Listagem de Itens" do botão "?" ao lado do campo
de OSI na tela de apontamento (`../apontamento/selectors.json`'s `ajudaOsi`),
só que aqui alimentado com os valores do campo Status. Clicar neste abriu o
modal com busca, listando os 7 valores possíveis do campo:

- Aberto
- Aprovado Colaborador
- Aprovado Gestor
- Cancelado
- Finalizado
- Liberado
- Reprovado

Nos 29 registros do usuário na sondagem de 2026-09-04, só apareceram 4 desses
7: **Aprovado Colaborador** (1 registro, criado horas antes da sondagem),
**Liberado** (a maioria), **Cancelado** (2), **Finalizado** (5). Não há
exemplo confirmado ainda de "Aberto", "Aprovado Gestor" nem "Reprovado".

Hipótese de mapeamento com a terminologia informal usada em conversa (**não
confirmada** -- falta exemplo real de "Aprovado Gestor" e "Aberto" para
validar):

| termo informal | status do site (hipótese) |
|---|---|
| "criado" | `Aberto` ou `Aprovado Colaborador` (ainda não aparece no "?" de OSI do apontamento) |
| "aprovado por gestor" | `Liberado` (o estado `Aprovado Gestor` pode ser transiente e virar `Liberado` sozinho) |
| "cancelei" | `Cancelado` |
| "finalizado por mim depois de aprovado" | `Finalizado` |

## Descoberta que pode importar bastante: paginação é só visual

Mesmo com o contador mostrando "Mostrar 1 até 5 de 29 registros" e uma
paginação (1, 2, 3... "Próximo"), rodar
`document.querySelectorAll('table tbody tr')` trouxe **as 29 linhas de uma
vez**, não só as 5 "visíveis" da página atual. Ou seja, o DataTables parece
manter o dataset inteiro no DOM e só *esconder* as linhas fora da página
atual -- não precisa clicar em "Próximo" nem mudar tamanho de página para ler
tudo. Ver `proposta-tabela-completa.md` para o que isso pode significar
para `refresh_catalog()`.

## Tentativa anterior: endpoint de typeahead (via tela de apontamento)

**Desfecho (2026-09-04):** o catálogo acabou vindo do botão "?" ao lado do
campo de OSI na tela de apontamento, que chama exatamente este endpoint com
`term` vazio -- ver `../apontamento/README.md`. Os bloqueadores abaixo
valem para *digitar* no campo, não para clicar no botão, e ficam como
histórico.

Antes da sondagem de 2026-09-04, a única pista sobre como montar o catálogo
de OSI vinha de uma investigação de 2026-08-29 (então guardada em
`ssg_selectors.json`'s `listaOsi`, movida pra cá nesta reorganização):

- Endpoint real do typeahead de OSI (campo da tela de **apontamento**, não
  desta tela): `GET https://ssg.sysmap.com.br/api/<id>/timesheet-recording/
  get-osi-project-activity-by-term?current-page=<...>&term=<termo>&userName=
  <nome>&date=<DD/MM/AAAA>` -- confirmado via DevTools com digitação humana
  real. Um `term` vazio também é chamado pelo próprio app (parece popular a
  lista default ao criar a linha).
- Bloqueadores: só dispara com tecla de verdade -- `Input.dispatchKeyEvent`
  sintético (que funciona pros campos mascarados de hora/data a semana
  toda) não aciona esse endpoint, confirmado sem nenhum request no domínio
  Network do CDP durante digitação sintética. Depende também de uma
  sessão/token que pode expirar independente da navegação normal --
  `ReturnCode: INVALID_TOKEN_4` foi observado numa chamada real, e um
  reload da página **não** resolve com segurança: uma tentativa de reload
  derrubou a sessão inteira (foi parar na tela de login do portal).
- O `rotaDedicada` (menu recolhido) que esse `listaOsi` descrevia como
  obstáculo está **superado**: ver "O que se descobriu agora" acima --
  navegação direta por hash resolve isso sozinha.
- Próxima tentativa sugerida (ainda válida se o endpoint de typeahead for
  revisitado no lugar da leitura desta tela): entender por que o
  `dispatchKeyEvent` não aciona o listener desse campo específico
  (diferente dos campos mascarados), ou chamar o endpoint direto com um
  token/cookie já validado, sem depender de reload.

## Screenshots

Capturados durante a sondagem, mas ficaram fora do repositório (scratchpad de
sessão, não versionado): tela vazia (só filtro) e tela após "Filtrar" com o
overlay de carregamento ainda visível aos 12s. Se precisar reproduzir, é só
repetir a navegação + filtro descritos acima.
