# ROADMAP — auto-appointment

Ordem deliberada: **fazer apontar** → **usar sem editar código** → **empacotar**.
Empacotar um app que ainda não aponta não empacota nada.

## Decisões já tomadas (2026-08-27)

| decisão | escolha | porquê |
| --- | --- | --- |
| Como dirigir o browser | **CDP num Edge já instalado**, perfil dedicado e persistente | `.exe` leve (sem navegador embutido), login/2FA resolvido uma vez só, e o Cloudflare enxerga um browser real |
| Fallback de browser | Edge primeiro, **Chrome** depois — um por vez, gravando qual subiu | ambos existem nesta máquina; outras máquinas podem ter só um |
| Playwright | **descartado como driver principal** | baixa ~150–400 MB de browsers próprios que não entram no bundle do PyInstaller |
| Login | **sempre manual**, nunca automatizado | o portal exige código do Google Authenticator (TOTP); guardar o secret seria o único jeito de automatizar, e não vamos |
| Distribuição | duas trilhas: `uv`/`pipx` para programadores **e** `.exe` para o resto | público misto |

## O alvo (sondado em 2026-08-27)

`https://portal.sysmap.com.br/wp-login.php` — WordPress atrás de Cloudflare.
O desafio do Cloudflare **passa sozinho** num browser real; a primeira leitura
pega "Executando verificação de segurança", a seguinte já traz o formulário.

Seletores da tela de login:

| campo | seletor |
| --- | --- |
| usuário | `#user_login` (já autopreenchido no perfil) |
| senha | `#user_pass` (já autopreenchida no perfil) |
| código do Google Authenticator | `#googleotp` |
| submit | `#wp-submit` |

---

## Etapa 0 — Geração de valores ✅ concluída

Strategy (static + natural_random), validação das 10 regras, histórico CSV,
feriados BR, gate de fim de semana/feriado no orquestrador. Coberto por testes.

## Etapa 1 — Sondar o site ✅ CONCLUÍDA E VALIDADA COM UM SAVE REAL

Seletores e armadilhas versionados em `src/modules/browser/ssg_selectors.json`.
Em 2026-08-27 o dia **26/08 foi apontado com sucesso** por CDP, com os valores
que o próprio `StaticStrategy` gerou, e a persistência foi confirmada com um
reload `ignoreCache` + filtro novo.

- [x] Login do portal mapeado; o Cloudflare passa sozinho num browser real
- [x] **O SSG tem sessão própria.** `ssg.sysmap.com.br/` cai no login do portal;
      a entrada válida é `index.html#/access-entry/get-list`. Aberta uma vez pelo
      usuário, a sessão fica viva no perfil de automação
- [x] Tela mapeada: **nenhum campo tem `id` ou `name`** — tudo por classe
- [x] Autocomplete de OSI resolvido: digitar o número, clicar no `li` do typeahead
- [x] **Sinal de sucesso descoberto:** o save **não** emite toast nem modal. O único
      sinal confiável é re-filtrar e contar `tr.access-record-row:not(.hide)` no dia
- [x] O selo "Sem registro" é **pista falsa** — aparece em todo dia, salvo ou não

### O gerador bate com a realidade

Comparação com o que já estava apontado à mão:

```
Seg 24/08  gerador 09:01/12:05/13:06/18:02   SSG 09:01/12:05/13:06/18:02  ✓
Ter 25/08  gerador 09:02/12:06/13:07/18:03   SSG 09:02/12:06/13:07/18:03  ✓
```

E 09:01→12:05 (3h04) + 13:06→18:02 (4h56) = **08:00**, que é o campo "Horas".
Ou seja, "Horas" é derivável — **o modelo de domínio não precisa mudar**.

### O que o sistema real pede além dos 4 horários

| campo | de onde sai |
| --- | --- |
| 2 linhas de E/S | os 4 horários, distribuídos: linha 1 = entrada+almoço, linha 2 = volta+saída |
| Horas (`08:00`) | derivado (manhã + tarde) |
| OSI | string composta, via typeahead — hoje fixa: `OSI 82695` |
| Observação | **vazia** (decisão do usuário) |
| Abono de Faltas | desmarcado |

### Fluxo completo de um dia (o que a Etapa 2 implementa)

1. filtrar o período do dia alvo (`.start-date` / `.end-date`, digitando 8 dígitos)
2. achar o `.access-entry-day` cujo texto contém `DD/MM/AAAA`
3. expandir com `.button-toggle-day` (**clique de mouse real** — `el.click()` não funciona)
4. clicar 2x em `.button-add-access-row` e 1x em `.button-add-appointment-row`,
   sempre mirando o botão **visível** (o do estado vazio some depois da 1ª linha)
5. digitar os 5 horários pela receita de campo mascarado (ver JSON), conferindo cada um
6. digitar o número da OSI e clicar no `li` do typeahead
7. **conferir os 6 campos; se algum divergir, abortar sem salvar**
8. clicar em "Salvar dias alterados"
9. re-filtrar e confirmar que o dia voltou com 2 linhas

## Etapa 2 — `SsgController` (Python/CDP) ✅ implementada

Arquivos: `modules/browser/cdp.py`, `modules/browser/browsers.py`,
`modules/browser/ssg_controller.py`, `modules/paths.py`.
Dependência nova: `websocket-client` (Python puro).

- [x] Sobe o Edge (fallback Chrome) com perfil dedicado em `user_data_dir()`,
      **um por vez**, e grava qual subiu em `browser.json`
- [x] Reusa um browser já em execução em vez de brigar com a sessão do usuário
- [x] Clique de mouse real e digitação tecla a tecla com a receita de máscara
- [x] Nunca loga: cair em tela de login levanta `SsgLoginRequired`
- [x] `verify()` compara os 6 campos e levanta `FieldMismatch` **antes** de salvar
- [x] Smoke test real: Edge reusado, filtro, leitura do dia 26 e `verify` OK
- [ ] O caminho de **escrita a partir do Python** (`fill_appointment` + `save_day`)
      ainda não foi exercido contra o site — não há dia elegível: 24, 25 e 26 estão
      apontados e 27 é hoje, que o SSG recusa. Fica para o próximo dia pendente

### Decisão: `fill_appointment` não salva

A ABC é respeitada, mas a escrita é um método separado (`save_day`). Preencher e
conferir é seguro; salvar é ato deliberado. `save_day` re-filtra e confirma que
as linhas voltaram do servidor, porque o site não emite toast nem modal.

### Dois achados que só apareceram ao portar para Python

1. **403 no handshake CDP.** O `websocket-client` manda header `Origin` e o
   Chromium recusa. Corrigido com `suppress_origin=True` — melhor que subir o
   browser com `--remote-allow-origins=*`, que abriria o CDP para qualquer
   página local. O WebSocket do Node não manda `Origin`, por isso os scripts de
   sondagem nunca esbarraram nisso.
2. **A observação volta como `;`.** Salvamos o dia 26 com o campo vazio e ele
   lê `;` — é o default do site, não digitação. Por isso os dias 24 e 25 também
   mostravam `;`. O portão trata `''` e `';'` como "sem observação".

## Etapa 3 — `InputController` (mouse/teclado) ⏸ dispensada por ora

Era o plano B: só valeria se o CDP esbarrasse em algo (iframe hostil, canvas,
campo que ignora evento sintético). Não esbarrou — o `SsgController` digita,
clica e salva. O stub continua no repo, e o ABC continua permitindo a
comparação, mas não há motivo para gastar esforço nele agora.

## Etapa 4 — CLI ✅ concluída

```
auto-appointment [--day DATA] [--week] [--strategy static|natural_random]
                 [--force] [--fill] [--save] [--yes] [--osi N] [--port N]
```

- **O padrão é seco:** gera e imprime, não abre browser, não grava nada.
- `--day` aceita `AAAA-MM-DD` ou `DD/MM/AAAA`; sem ele, **ontem** (hoje é recusado).
- `--fill` preenche e confere sem gravar; `--save` grava e **pergunta antes**
  (`--yes` pula), recusando quando não há terminal interativo em vez de adivinhar.
- `--fill` sem `--save` recusa mais de um dia: filtrar o dia seguinte descarta o
  preenchimento do anterior, e isso passaria despercebido.
- `--week` passa pelo `generate_week` da estratégia, não por um laço sobre `run()`,
  porque o `NaturalRandomStrategy` mantém os dias da semana únicos entre si (Regra 4).
- Códigos de saída: `0` feito, `1` erro, `2` nada a fazer (feriado pulado não é falha).

## Etapa 5 — Persistência 🔶 o essencial feito

- [x] **Leitura empacotada separada da escrita do usuário.** Leitura vem de
      `paths.bundle_dir()` (`src` em dev, diretório de extração quando congelado);
      escrita vai para `paths.user_data_dir()` (`%LOCALAPPDATA%\auto-appointment`).
- [x] Cache de feriados migrado para o diretório do usuário
- [x] `append_appointment` grava no histórico **só** o que foi realmente salvo no
      site, semeando a cópia do usuário a partir da empacotada na primeira vez, e
      recusando registrar o mesmo dia duas vezes
- [ ] De onde vem a **OSI**: hoje é uma constante (`82695`), sobrescrevível por
      `--osi`. Sondado em 2026-08-29 (ver `ssg_selectors.json`'s `listaOsi`):
      a rota dedicada `#/osi/get-list` existe mas fica presa em submenus
      recolhidos; o botão de ajuda ao lado do campo **não é seguro** (produziu
      um modal de "sucesso" ao ser clicado); o endpoint real do typeahead foi
      encontrado (`GET .../get-osi-project-activity-by-term`) mas só responde
      a digitação de verdade, não a teclas sintéticas via CDP, e depende de um
      token que um reload não renova com segurança. `--refresh-osi-list` e o
      cache (`osi_catalog.json`) já existem; a extração em si
      (`modules/osi_catalog/probe.py`) fica como TODO explícito

## Etapa 6 — Empacotamento ✅ concluída

**Trilha A — quem já tem Python.** `pyproject.toml` ganhou `[project.scripts]`,
`[build-system]` (hatchling) e:

```toml
[tool.hatch.build.targets.wheel]
sources = ["src"]
only-include = ["src"]
```

`sources = ["src"]` remove o prefixo, então `main.py`, `models/` e `modules/`
caem na raiz do wheel — a mesma raiz que o `pytest.ini` assume, o que é
exatamente o que mantém os imports absolutos funcionando dos dois lados.

Terceiros rodam com `uvx --from git+<url> auto-appointment`, sem clonar.

**Trilha B — executável.** Build (só no Windows; não há cross-compile):

```bash
uv run pyinstaller --onefile --noconfirm --name auto-appointment --paths src \
  --add-data "src/modules/history/data;modules/history/data" src/main.py
```

Resultado: **15 MB**, porque não há navegador embutido — dirigimos o Edge da
máquina. Verificado: `dist/auto-appointment.exe --day 26/08/2026` imprime o
mesmo que a versão instalada (o que já prova que o `history.csv` empacotado é
lido, pois `run()` carrega o histórico antes de gerar), hoje é recusado com
código 2, e `websocket`, `pydantic_core` e os dois CSVs estão no bundle.

Avisos de `missing module named pydantic.BaseModel` no log do PyInstaller são
falso-positivo com reexports lazy — o exe constrói `Appointment` normalmente.
SmartScreen/antivírus reclamarem de `.exe` onefile não assinado é esperado.

**Não verificado ainda:** dirigir o browser *a partir do exe congelado*
(`--fill`). Os módulos estão no bundle, mas o caminho não foi exercido.

## Etapa 7 — UI interativa (grid-form) ✅ implementada

Double-clicar o `.exe` (ou rodar `auto-appointment` sem argumentos, num
terminal de verdade) abre uma tela única em grid (`modules/tui/`) em vez do
modo seco padrão: Dia/Mês/Ano/Force navegados e editados só com setas (e
WASD), um seletor de OSI (spinner sobre o cache da Etapa 5), e um toggle
Salvar Y/N que substitui o prompt de confirmação em texto livre. Ao submeter,
monta a mesma lista de argv que já seria digitada e chama `cli()` normalmente
— nada de lógica nova em `punch()`/`run()`.

- [x] Trigger em `cli()` (gated em `argv is None`, não no bloco
      `if __name__ == "__main__":` -- o stub do console-script do `uv run`
      chama `cli()` sob o **seu próprio** `__main__`, então o bloco de
      `main.py` nunca roda nesse caminho; ver comentário no código)
- [x] `main.cli([])` continua significando exatamente "ontem, modo seco"
- [x] Rollover de calendário real no Dia; clamp de mês/ano (`calendar.monthrange`)
- [x] Validação ao vivo reaproveitando `skip_reason()` (vermelho = hoje/futuro,
      nunca libera; amarelo = fim de semana/feriado, libera com Force)
- [x] Navegação só-pra-frente (Right avança e dá a volta; Left nunca troca de
      linha) -- decisão explícita, não é um grid simétrico
- [x] Testado com `create_pipe_input()`/`DummyOutput` (sem terminal real) para
      a lógica de teclas; lógica pura (estado/argv/render) testada à parte,
      sem importar `prompt_toolkit`
- [ ] Confirmação visual num terminal de verdade (PowerShell/cmd/duplo-clique)
      ainda depende do usuário -- os testes automatizados não têm como abrir um
      console Win32 de verdade

Dependência nova: `prompt_toolkit` (+ `wcwidth`). Aumenta o bundle do `.exe`
de propósito -- ver decisão registrada na memória do projeto
(`ui-interativa-grid-form`). Uma reescrita em stdlib puro, pra reduzir o
bundle de novo, fica pra depois, como entrega separada.

**Fora de escopo por ora:** `--week`/`--strategy`/`--port` não entram na tela
(regra de gerência nova proibiu apontamento semanal em lote -- uso agora é
dia a dia); criar/salvar novos projetos OSI de dentro do software (tela nova,
aprovação de gestor) é uma feature grande, só anotada.

---

## Pendências menores (não bloqueiam)

- `src/test/e2e/` está vazio
- Feriados móveis (Carnaval) só com rede/cache; municipais e estaduais não existem
- Convergir (ou não) a janela da Regra 4 com a do sistema real (±4 dias corridos,
  centrada, ciente de feriado) — hoje a divergência é proposital e documentada
- `save_day` a partir do Python nunca rodou contra o site: não houve dia elegível
  (24, 25 e 26 apontados; 27 é hoje). O caminho equivalente foi provado via Node
