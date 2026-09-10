# Tela de cadastro de OSI (`#/osi/get-form`)

Sondada em 2026-09-05. Seletores exatos em `selectors.json`; código em
`src/modules/browser/ssg_osi_form.py` (driver da tela) e
`src/modules/osi_register/flow.py` (a ordem do fluxo). É a única tela em
que a automação **escreve** algo além de apontamentos.

## Rota

`https://ssg.sysmap.com.br/index.html#/osi/get-form` — abre direto pelo
hash, como as outras (ver `../../sessao-e-rotas.md`). Título: "Cadastro
Ordem de Serviço Interna". Painéis: Detalhes da OSI, Atividade (uma linha),
Verificações, Resultado.

## O fluxo, na ordem em que funciona

1. **Profissional** — "?" (o widget "Listagem de Itens", ver
   `../apontamento/README.md`), 1 opção; selecionar preenche, fecha o modal
   e libera o "?" de Atividade (que depende de `data-employee-name`).
2. **Projeto** — "?", os projetos do usuário (um por mês/projeto, ex.
   `49179 / FASSECONCI / Faturamento Assistencial SECONCI`). **É a escolha
   do usuário.** Selecionar grava `data-project-name` no campo de
   atividade; não mexe no requisito.
3. **Descrição** — textarea, digitação normal. Padrão do programa:
   `Criando OSI do mes <mês do início estimado>`.
4. **Requisito** — "?", 1 opção (`0 | Requisito Geral`).
5. **Atividade** — "?", as atividades do projeto (1 em 2026-09-05). **É a
   outra escolha do usuário**, mas só dá para escolher sabendo o período
   aceito (abaixo).
6. **Início/Término Estimado** — campos mascarados com datepicker: receita
   de `../../campo-mascarado.md`, e o datepicker se fecha **clicando em
   outro lugar** — Escape limpa o campo.
7. **Esforço Orçado** — AutoNumeric: digitar não entra; só
   `jQuery(el).autoNumeric('set', ...)` + `trigger('change')`. O site
   calcula "Esforço Orçado por Dia Útil (H)" (= esforço / dias úteis do
   período, pelo calendário dele) num `span`; o programa preenche 40, lê o
   valor, recalcula o total que dá 8/dia e confere de novo antes de gravar.
8. **Gravar** (`.button-save-osi`) — `POST .../osi/save`.

## Como o período de cada atividade é descoberto

O site não publica o período aceito de uma atividade em lugar nenhum (o
GET do "?" não traz datas). Ele só aparece **recusando um Gravar**: com
Início = hoje − 1 ano e Término = hoje + 1 ano (nunca passa), esforço 40 e o
checkbox "Validar data de início e término estimado da OSI?" marcado (vem
marcado; `ValidateDateOsi=Y`), o site responde HTTP 200 e abre um alerta
bootbox:

> Erro! O período permitido para estimar o Início e Término Estimado da
> atividade é de 01/09/2025 à 30/09/2025.

(`parse_window` em `src/modules/osi_register/window.py` lê as duas datas.)
Depois do OK o formulário continua preenchido, na mesma rota — dá para
sondar a próxima atividade sem recarregar. Cada atividade custa um Gravar
recusado; o usuário aceita o risco de uma OSI fantasma se um dia o site
deixar passar (ele cancela em outra tela), e o fluxo aborta com erro se
o Gravar de sondagem **não** for recusado.

## Armadilhas

- **Escape no datepicker limpa a data.** Fechar clicando fora.
- **Esforço vazio no blur abre "Erro! O campo Esforço Orçado (H) é de
  preenchimento obrigatório!"** sem clicar em Gravar — por isso o campo
  nunca é focado/desfocado vazio; só o `autoNumeric('set')`.
- **Digitar no esforço não entra** (AutoNumeric ignora `dispatchKeyEvent`,
  mesmo com `windowsVirtualKeyCode`).
- **"Gravar" é um `<a>`**, não `<button>` — `.button-save-osi` sem tag.
- Alertas são `.bootbox`; o widget dos "?" é `.modal.modal-list-items`.
  Nunca confundir os dois ao esperar "o modal".

## A confirmar na primeira criação real

O caminho de sucesso (datas dentro do período) ainda não foi exercitado
pelo programa. O usuário relata que aparece um popup pedindo uma **segunda
descrição** (pode repetir a primeira); há um modal escondido na tela com
`textarea.status-coment` e botões Cancelar/Gravar (`button-status-change`)
que deve ser esse. O sinal de sucesso (alerta "Perfeito! ...", redirect,
ou o "Código:" preenchido no topo) também está por confirmar —
`flow.submit` aceita qualquer um dos três e falha se nenhum aparecer.
