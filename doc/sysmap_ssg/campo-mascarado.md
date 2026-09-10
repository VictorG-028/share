# Receita de digitação em campo mascarado

Vale pra qualquer campo de data/hora do site (`jquery.maskedinput`), em
mais de uma tela — não é específico da tela de apontamento nem da de
listagem de OSI, ambas têm campos assim (datas de filtro, horários de
entrada/saída).

Digitar direto no campo sem limpar primeiro produz lixo: `'0903'` virou
`'90:30'` numa tentativa real. A receita que funciona:

1. Clique de mouse **real** no campo (`Input.dispatchMouseEvent` press +
   release — `el.click()` não é suficiente, ver `stack.md`).
2. Esperar ~400ms.
3. `el.focus(); el.select()`.
4. Tecla `Delete`, esperar 150ms, tecla `Backspace`, esperar 150ms — o
   campo volta a `__:__` (ou equivalente) com o caret em 0.
5. Digitar **só os dígitos** (`0903`, não `09:03`), ~120ms por tecla, via
   `Input.dispatchKeyEvent` com `text`/`unmodifiedText` preenchidos (não
   basta mandar `key`/`code` sem texto).
6. Reler `el.value` e comparar com o esperado **antes** de qualquer save.

Implementação executável: `CdpPage.type_masked` em `src/modules/browser/cdp.py`.

Nota (2026-09-04): a ação `type` do `drive.mjs` da skill
`browser-edge-automation` **não** serve para estes campos -- ela manda
`keyDown`/`keyUp` sem `windowsVirtualKeyCode`, e a máscara produz o mesmo
lixo (`26082026` virou `60/82/0262`, mesmo com o campo limpo antes). Só a
receita acima, com o código de tecla, funciona.
