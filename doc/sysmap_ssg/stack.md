# Stack do front-end (SSG/SysMap)

Confirmado nas duas telas já sondadas (apontamento e listagem de OSI) —
não é algo específico de uma tela, é a base de todo o SPA:

**jQuery 2.1 + Bootstrap 3 + jquery.maskedinput + bootstrap3-typeahead +
bootbox**

Consequências práticas pra automação (detalhes em cada doc de página):

- `el.click()` programático não aciona os handlers reais do jQuery em
  botões que dependem de evento de mouse de verdade — precisa de um clique
  sintético via CDP (`Input.dispatchMouseEvent`), não `element.click()`.
- Campos de data/hora usam `jquery.maskedinput` — digitar direto sem limpar
  o campo produz lixo (ver `campo-mascarado.md`).
- Autocomplete usa `bootstrap3-typeahead` (o dropdown de sugestões,
  `ul.typeahead.dropdown-menu`).
- Confirmações usam `bootbox` (modais tipo `alert`/`confirm` construídos em
  cima do Bootstrap). Os botões "?" ao lado de campos abrem outro widget, o
  "Listagem de Itens" (`.modal.modal-list-items`), que é só leitura -- ver
  `pages/apontamento/selectors.json`'s `ajudaOsi`.

## Armadilha: janela minimizada congela os modais (medido em 2026-09-09)

Bootstrap 3 abre e fecha modal com transição CSS: `show()` põe
`display:block` e depois adiciona a classe `in`; `hide()` tira o `in` e só
põe `display:none` quando a transição termina. Se a janela do navegador
estiver **minimizada ou totalmente coberta**, o Chromium reporta
`document.visibilityState === 'hidden'`, para de rodar transições, e o
modal fica travado no meio do caminho: `display:block`, sem `in`, e o
"Fechar" parece não funcionar.

O sintoma engana: o clique **acerta** o botão (confirmado com
`document.elementFromPoint`, que devolve o próprio `button.button-close`),
e nem `el.click()`, nem o X do cabeçalho, nem `jQuery(m).modal('hide')`
fecham — porque nenhum deles termina a transição. Nesse estado o modal
continua pintado por cima da tela e engole os cliques seguintes.

Solução adotada: `browsers.launch` sobe o navegador com
`--disable-backgrounding-occluded-windows`, `--disable-renderer-backgrounding`
e `--disable-background-timer-throttling`; com elas a aba segue `visible`
mesmo minimizada. `Page.bringToFront` **não** resolve (testado). Contra um
navegador que outra pessoa subiu sem essas flags o problema volta, e por
isso `ssg_list_modal` acrescenta a dica sobre aba congelada quando o modal
não abre ou não fecha e `document.hidden` é verdadeiro.
