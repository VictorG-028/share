# Tela de apontamento (Registro de E/S — `#/access-entry/get-list`)

Sondada e **validada com um save real em 2026-08-27** (dia 26/08 apontado
com sucesso via CDP, confirmado com reload `ignoreCache` + filtro novo).
Nenhum campo da tela tem `id` ou `name` — tudo é ancorado por classe. Ver
`selectors.json` para os seletores exatos, e `../../stack.md` /
`../../campo-mascarado.md` para o que é comum a outras telas do site.

## Rota

`https://ssg.sysmap.com.br/index.html#/access-entry/get-list`

## Filtro

Campos `Data Inicial`/`Data Final` (mascarados, formato `DD/MM/AAAA`,
digitar só os 8 dígitos) e `Profissional` (autocomplete). O botão
"Filtrar" é achado por texto (`'Filtrar'`), não por seletor fixo.

## Dia

Cada dia filtrado vira um painel (`div.panel.panel-default.access-entry-day`),
achado pelo texto `DD/MM/AAAA` dentro dele. Um dia sem apontamento vem
**recolhido e sem linhas** — só os templates escondidos — e precisa ser
expandido (`button.button-toggle-day`) e ter linhas adicionadas antes de
preencher qualquer coisa. O selo "Sem registro" que aparece no painel é
**pista falsa**: aparece em todo dia, salvo ou não, e não indica nada.

## Registro de E/S

Duas linhas reais por dia: linha 1 = entrada + início do almoço, linha 2 =
fim do almoço + saída. Os templates (`.access-record-row-template.hide`)
nunca devem ser preenchidos — são o molde clonado ao clicar em "adicionar
linha".

## Apontamento (horas + OSI)

Uma linha real com horas trabalhadas e o campo de OSI
(`.input-project-activity.dynamic-autocomplete`). O campo aceita duas
formas de preenchimento:

- **typeahead**: digitar só o número (ex. `82695`) abre
  `ul.typeahead.dropdown-menu` e clicar no `li` preenche o campo. Só serve
  para OSI que **tem** número, e o clique é sempre no "primeiro `li`
  visível" — não dá para saber qual sugestão foi aceita.
- **botão "?"** (o que a automação usa desde 2026-09-09): abre a "Listagem
  de Itens", cada linha tem seu `button.button-select`, e o site escreve a
  composta inteira no campo. Funciona para qualquer linha da lista, com ou
  sem número, e a linha escolhida é conhecida de antemão.

O texto composto **não tem formato garantido**. Uma OSI própria vem como
`OSI <numero> | <Projeto> | <Atividade> - <id>` (ex.: `OSI 82695 |
Faturamento Assistencial SECONCI | Carga base historica - 417293`), mas as
OSIs que o gestor abre para o time inteiro vêm **sem o prefixo `OSI <n>`**,
como `<Projeto> | <Pessoa> - <id>` (ex.: `coe tech - setembro - 2026 |
Walber Hugo da Silva - 427465`). Tratar a lista como texto livre: em
04/09/2026 vieram 16 linhas, 3 com número e 13 sem. A observação deve ficar vazia — o site
grava `;` sozinho quando fica vazia, e dias apontados à mão leem `;` do
mesmo jeito, então tratar `''` e `';'` como "sem observação".

## Salvar

O botão "Salvar dias alterados" é **global**: salva todos os dias
alterados na tela de uma vez. Não abre modal nem mostra toast de sucesso —
o único sinal confiável de que salvou é re-filtrar o período e contar
`tr.access-record-row:not(.hide)` no dia alvo (validado com reload
`ignoreCache`).

## Botão "?" da OSI (lista de itens)

Cada linha de apontamento tem um botão "?" (`.button-show-items`) ao lado do
campo de OSI. Ele abre o widget genérico do site, "Listagem de Itens"
(`.modal.modal-list-items`, com campo de busca), preenchido por um único
`GET` ao mesmo endpoint do typeahead (`get-osi-project-activity-by-term`,
com `term` vazio e `date=` do painel). Cada linha `tr.dynamic > td.col-item`
traz a string composta completa (`OSI <numero> | <Projeto> | <Atividade> -
<id>`); "Fechar" fecha limpo.

**É só leitura** — confirmado em 2026-09-04 com captura de rede via CDP
(nenhum POST/PUT) e `read_day()`/`row_counts()` idênticos antes e depois.
O modal "Perfeito! Registros alterados com sucesso" visto na sondagem de
2026-08-29 não reapareceu, com `document.elementFromPoint` confirmando que
o clique acertou o botão; ficou como clique em elemento errado naquela vez.

**A lista depende do dia** (o `date=` do painel clicado): em 03/09/2026
vieram só as OSIs válidas para aquele dia (83270 e 83174, ambas "Liberado");
a 82695, com término estimado em 30/08, não entrou, nem a 83336 ("Aprovado
Colaborador"). Em 04/09/2026 vieram 16 linhas — 83336, 83270, 83174 e mais
13 do projeto "coe tech - setembro - 2026", uma por pessoa do time. Por isso
`--refresh-osi-list` filtra os últimos 30 dias e clica no apontamento
**passado** mais recente — nunca hoje, e nunca criando linha só para ter o
botão. Seletores exatos em `selectors.json`'s `ajudaOsi`; código em
`SsgController.list_osi_help_items` e `src/modules/osi_catalog/probe.py`.

O mesmo modal é a fonte do preenchimento: `SsgController._fill_osi` abre o
"?" do dia que está sendo apontado, casa o rótulo pedido (exato, depois
substring única) e clica no `button.button-select` daquela linha. O refresh
do catálogo continua **sem** clicar em selecionar — ele só lê e fecha.

## Armadilhas

Ver `selectors.json`'s `armadilhas` para a lista completa (botão que troca
de lugar ao adicionar linhas, `el.click()` não aciona o toggle do dia, dia
vazio sem linhas, campo mascarado, observação vira `';'`, e o histórico do
botão "?" da OSI — hoje resolvido como seguro, ver a seção acima).

## Implementação

- `src/modules/browser/ssg_controller.py` — cópia executável destes
  seletores.
- `src/modules/browser/browsers.py` — acha/sobe Edge → Chrome, perfil
  dedicado.
- `src/modules/browser/cdp.py` — clique de mouse real e digitação
  tecla-a-tecla.
- Regra: `fill_appointment` preenche e confere mas **não salva**; `save_day`
  é uma chamada separada.
