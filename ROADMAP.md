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

## Etapa 3 — `InputController` (mouse/teclado) — só se preciso

O segundo controller do ABC, para a comparação que o projeto sempre previu.
Só vale o esforço se o CDP esbarrar em algo (iframe hostil, canvas, campo que
ignora eventos sintéticos). Frágil a resolução e foco de janela — é plano B,
não plano A.

## Etapa 4 — CLI de verdade

Hoje `main.py` roda com uma data hardcoded. Precisa de `argparse`:

```
auto-appointment --day 2026-08-27 --strategy static [--force] [--dry-run] [--week]
```

`--dry-run` imprime sem abrir browser (é o modo de hoje). Sem `--day`, hoje.

## Etapa 5 — Persistência (pré-requisito do empacotamento)

- Escrever de volta no histórico após apontar — hoje o CSV nunca cresce, e a
  Regra 4 depende dele.
- **Separar leitura de escrita.** `loader.py` e `holiday/service.py` usam
  `Path(__file__).parent / "data"`; dentro de um `.exe` onefile isso vira
  `sys._MEIPASS`, um diretório temporário recriado a cada execução — o cache de
  feriados sumiria e o histórico ficaria congelado. Leitura do bundle, escrita
  em `%LOCALAPPDATA%\auto-appointment\`.
- Decidir de onde vem a **OSI** (hoje o campo existe e ninguém preenche).

## Etapa 6 — Empacotamento

**Trilha A — programadores (barata, pode sair a qualquer momento):**
adicionar ao `pyproject.toml`

```toml
[project.scripts]
auto-appointment = "main:cli"
```

e eles rodam com `uvx --from git+<url> auto-appointment`, sem clonar.

**Trilha B — executável:** PyInstaller onefile, gerado **no Windows** (não há
cross-compile). `pydantic-core` é binário mas tem hook pronto — funciona. Como
o browser é o da máquina, não há nada pesado para embutir; o `.exe` fica na
casa dos ~15 MB. Incluir `history.csv` via `--add-data` e ler pelo caminho do
`_MEIPASS` (Etapa 5). Contar com falso-positivo de antivírus/SmartScreen em
`.exe` onefile não assinado — é normal, não é bug.

---

## Pendências menores (não bloqueiam)

- `src/test/e2e/` está vazio
- Feriados móveis (Carnaval) só com rede/cache; municipais e estaduais não existem
- Convergir (ou não) a janela da Regra 4 com a do sistema real (±4 dias corridos,
  centrada, ciente de feriado) — hoje a divergência é proposital e documentada
