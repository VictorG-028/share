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
digitar só os 8 dígitos) e `Profissional` (autocomplete). O botão "Filtrar"
tem classe própria — **`button.button-filter`** (descoberto em 2026-09-10; a
mesma classe da tela de listagem de OSI) — e o casamento por texto
(`'Filtrar'`) fica como segunda tentativa.

O campo `Profissional` (`.user-name`) já vem preenchido com o usuário logado.
Ele não é decoração: é de lá que sai o `userName` das chamadas de API
(`../../api.md`), e a API responde `userName` vazio com **sucesso e zero
itens**.

### Três armadilhas do filtro, medidas em 2026-09-10

Uma única sessão de sondagem produziu uma falha silenciosa completa — filtro
que não aconteceu, dados lidos do período anterior, nenhum erro:

1. **A máscara pode engolir teclas.** Digitar `31072026` deixou `31/07/261` no
   campo. Sempre **reler o campo e conferir** depois de digitar, como já se
   fazia com os horários.
2. **O site recusa com um bootbox que cobre a tela.** Com a data inválida veio
   *"Aviso! O campo Período é de preenchimento obrigatório."*, e enquanto ele
   está aberto **todo clique acerta o backdrop** — inclusive o clique em
   "Filtrar" da execução seguinte. Um alerta que já estava aberto precisa ser
   fechado antes de agir; um alerta que aparece **depois** da nossa ação é o
   site nos recusando e tem que virar erro.
3. **Esperar "o painel do dia X aparecer" não prova nada**, porque o painel do
   filtro anterior é idêntico. A automação marca os `.access-entry-day` atuais
   com `data-aa-stale` antes de clicar e espera por um painel **sem** a marca.

Com isso, o filtro deixou de precisar de `sleep` fixo: **responde em ~1,3s**
(o código dormia 8s).

### Mais dois bloqueadores invisíveis (2026-09-11)

O bootbox não é o único jeito de um clique "acontecer" sem efeito. Os dois
abaixo apareceram no mesmo dia, e por isso `CdpPage.click` passou a conferir
`document.elementFromPoint` antes de clicar — se outro elemento receberia o
clique, levanta `ClickBlocked` em vez de não fazer nada:

4. **O véu de "carregando" trava.** `services.runWebMethod` levanta um
   `SysMap.UI.showLoading()` e só o remove no callback da resposta — então uma
   requisição que nunca volta deixa um `div` preto `position: fixed`,
   `z-index: 10000`, **sem classe nenhuma**, cobrindo a tela inteira. Procurar
   por `.loading`/`.overlay` não acha. `SsgScreen.clear_stale_overlay()`
   detecta pela cobertura real do campo da tela e usa o
   `SysMap.UI.hideLoading()` do próprio site para removê-lo.
5. **Uma aba pode envenenar de vez.** Depois de uma sequência de requisições,
   a aba chegou a `jQuery.active == 6` — seis chamadas que o servidor nunca
   respondeu — e a partir dali **nenhum clique disparava requisição alguma**.
   Um reload completo (`ignoreCache`) **não** curou; a sessão sobreviveu (nada
   de tela de login) e mesmo assim o app seguiu morto. Abrir uma **aba nova**
   no mesmo perfil funcionou na hora. `SsgScreen.stuck_hint()` detecta
   `jQuery.active > 0` e diz isso no texto do erro.

## Dia

Cada dia filtrado vira um painel (`div.panel.panel-default.access-entry-day`),
achado pelo texto `DD/MM/AAAA` dentro dele. Um dia sem apontamento vem
**recolhido e sem linhas** — só os templates escondidos — e precisa ser
expandido (`button.button-toggle-day`) e ter linhas adicionadas antes de
preencher qualquer coisa. O selo "Sem registro" que aparece no painel é
**pista falsa**: aparece em todo dia, salvo ou não, e não indica nada.

### O cabeçalho diz se o dia é feriado

O `.panel-heading` traz, depois da data, o dia da semana em caixa alta — e
**`FERIADO` no lugar dele** quando é feriado:

```
Sem registro 09/09/2026 QUARTA-FEIRA Sobre Aviso
Sem registro 07/09/2026 FERIADO      Sobre Aviso     ← Independência
Sem registro 05/09/2026 SÁBADO       Sobre Aviso
```

Esta é a **única** fonte que conhece feriado de empresa, regional ou ponte —
um calendário nacional (o `modules/holiday/service.py`) não conhece. Por isso
`--refresh-osi-list` decide a elegibilidade do dia lendo esta palavra, e não
calculando. Quem lê é `SsgController.days_on_screen()` (cru) e quem julga é
`modules/osi_catalog/day_choice.py` (puro, testado sem browser).

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
13 do projeto "coe tech - setembro - 2026", uma por pessoa do time.
Seletores exatos em `selectors.json`'s `ajudaOsi`; código em
`SsgController.list_osi_help_items`.

### Desde 2026-09-10, o refresh não usa mais o modal

O botão "?" dispara um único `GET` que pode ser feito direto, de dentro da
página (`../../api.md`). Isso mudou três coisas:

- **0,60s** em vez de ~2,3s;
- funciona para **qualquer dia, inclusive um sem nenhuma linha** — então não é
  mais preciso "clicar no apontamento passado mais recente"; o
  `--refresh-osi-list` agora lê a lista do **dia elegível mais recente**
  (hoje inclusive), descendo para o anterior se vier vazia;
- nada é criado na tela. O caminho pelo DOM continua como fallback e, quando
  precisa criar a linha de apontamento para ter o botão, **desfaz** a linha
  depois (`SsgController.ensure_appointment_row` /
  `discard_appointment_row`) — nada é salvo em nenhum caso, mas deixar um dia
  meio preenchido na janela do usuário deixaria o "Salvar dias alterados"
  global armado com um apontamento vazio.

Código: `src/modules/browser/ssg_api.py` e `src/modules/osi_catalog/probe.py`.

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
