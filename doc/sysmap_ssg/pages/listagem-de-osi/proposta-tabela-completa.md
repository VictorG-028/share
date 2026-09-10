# Alternativa para `refresh_catalog()`: ler a tabela inteira de `#/osi/get-list`

Documento dedicado (recon de 2026-09-04), separado de `recon.md`, porque é
uma **solução candidata concreta** para `refresh_catalog()`
(`src/modules/osi_catalog/probe.py`), não só uma anotação de comportamento.

## Contexto

A solução adotada para popular o catálogo de OSI é o botão "?"
(`.button-show-items`) do campo de OSI na tela de apontamento -- rápido, em
tempo real, e confirmado somente-leitura em 2026-09-04
(`../apontamento/selectors.json`'s `armadilhas.botaoAjudaOsi` e `ajudaOsi`).
Este documento fica como a alternativa genuinamente diferente, registrada
para o caso de o site mudar aquele botão.

## A ideia

1. Abrir/navegar para `https://ssg.sysmap.com.br/index.html#/osi/get-list`
   (não precisa do menu -- ver `recon.md`).
2. Clicar em "Filtrar" com todos os campos vazios (já vem filtrado para o
   usuário logado).
3. Aguardar com *polling* (não sleep fixo -- a tela é lenta e inconsistente,
   ver notas de tempo de resposta em `recon.md`) até `table tbody tr` ter
   linhas.
4. Ler **a tabela inteira em um único `evaluate()`**: mesmo com a paginação
   do DataTables mostrando só 5 por vez, todas as linhas existem no DOM ao
   mesmo tempo -- não é preciso clicar em "Próximo" nem mudar o tamanho de
   página.
5. Cada linha dá: Código (número puro da OSI), Descrição, Status, Nome do
   Projeto, Requisito, entre outras colunas -- o suficiente para montar
   `OsiEntry` e também **filtrar por Status "Liberado"** (as utilizáveis),
   algo que o botão "?" não expõe.

## Vantagens sobre o botão "?"

- Traz o **Status** de cada OSI, não só número/nome -- dá para descartar
  automaticamente `Cancelado`/`Aprovado Colaborador`/etc. e manter só
  `Liberado` (e talvez `Finalizado`, se fizer sentido manter no cache para
  referência histórica).
- É uma tela de listagem dedicada, não um popup de ajuda ao lado de um campo
  de formulário que está sendo preenchido -- menor risco de efeito colateral
  em algo que não devia ser tocado.
- Não depende do endpoint de typeahead (`get-osi-project-activity-by-term`)
  que só dispara com tecla real e tem token que expira (ver "Tentativa
  anterior: endpoint de typeahead" em `recon.md`).

## Desvantagens

- **Lenta**: 10-20+ segundos por carga, contra "tempo real" do botão "?".
  Qualquer implementação precisa de polling com timeout generoso.
- **Inconsistente**: o próprio tempo de resposta varia entre tentativas (ver
  `recon.md`) -- não dá para calibrar um sleep fixo confiável.
- Exige navegar para uma rota separada da tela de apontamento. Não testado
  ainda se voltar para `#/access-entry/get-list` depois preserva o estado
  normalmente (não há motivo forte para achar que não, já que é só troca de
  hash na mesma SPA, mas é uma pergunta em aberto).

## Perguntas em aberto

1. O que `Aberto`, `Aprovado Gestor` e `Reprovado` significam em termos de
   "posso apontar nessa OSI ou não" -- não há exemplo real nos 29 registros
   sondados para confirmar.
2. Latência real medida com mais rigor -- só há uma amostra até agora.
3. Se navegar para esta tela e voltar depois de rodar o probe tem algum
   efeito colateral na sessão ou no estado da tela de apontamento (não
   testado).

## Decisão (2026-09-04)

Botão "?" adotado e implementado (`SsgController.list_osi_help_items` +
`modules/osi_catalog/probe.py`). Esta leitura da tabela inteira **não** foi
implementada; fica documentada como fallback -- e como a única das duas
fontes que expõe o Status de cada OSI, se um dia isso for necessário.
