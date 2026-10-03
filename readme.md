# Auto Appointment

Gera valores de apontamento (entrada, almoço, saída) por dia e, se você mandar,
os digita no SSG — com **separação clara entre gerar números e controlar o
navegador**. A geração usa o pattern GoF **Strategy**:

- **`static`** (padrão) — 6 conjuntos memorizáveis numerados 1–6, gerados pela fórmula
  em `modules/strategy/static/generator.py`. Por dia: Seg–Sex → 1–5, fim de semana → 6
  (coringa). Não levanta erro no fim de semana.
- **`natural_random`** — horários aleatórios sob as 10 regras + histórico
  (`modules/strategy/natural_random/`).

## Uso

```bash
auto-appointment                          # num terminal: abre o MENU (Apontar / Atualizar lista de OSI / Criar OSI)
auto-appointment --day 26/08/2026         # ou --day 2026-08-26 (sem argumentos fora de um terminal: ONTEM, seco)
auto-appointment --day 26/08/2026 --week  # segunda a sexta daquela semana
auto-appointment --day 26/08/2026 --fill  # abre o browser, preenche e CONFERE
auto-appointment --day 26/08/2026 --save  # grava no SSG (pergunta antes)
auto-appointment --day 26/08/2026 --fill --osi "coe tech - setembro"   # escolhe a OSI por texto
auto-appointment --refresh-osi-list       # lê a lista de OSI do site e atualiza o cache local
auto-appointment --register-new-osi       # cadastra uma OSI nova (pergunta projeto/atividade, confirma antes)
```

Há **um único executável**. Com duplo clique (ou `auto-appointment` sem
argumentos num terminal) ele abre o menu inicial; "Criar OSI" aparece como
**INTERDITADO** no menu (a flag `--register-new-osi` continua existindo).

**Teclas (iguais em todas as telas):** `[CIMA] / [BAIXO]` mudam de linha;
`[ESQ] / [DIR]` mudam o valor; `[ENTER] / [ESPACO]` avançam o valor (na linha da
OSI abrem a lista, no menu abrem a operação) e, no **último botão**, executam e
fecham; `[ESC] / [BACKSPACE] / [CTRL-C]` cancelam e fecham. O rodapé de cada
tela diz, para a linha em foco, o que cada tecla faz (`MUDA` / `ABRE` /
`EXECUTA`). Na tela Apontar, a linha **Ação** escolhe entre "Só preencher (não
grava)" — o padrão — e "GRAVAR no SSG".

**O padrão é seco:** sem `--fill` ou `--save`, nada abre o navegador e nada é
gravado. `--save` mostra o que vai gravar e pede confirmação (`--yes` pula);
sem terminal interativo, ele recusa em vez de adivinhar.

Duas regras que o programa aplica sozinho:

- **Só dias passados.** O SSG recusa hoje e qualquer data futura, então o
  gerador também recusa. `--force` **não** libera isso — ele existe só para
  apontar um fim de semana ou feriado que você realmente trabalhou.
- **Preencher não é gravar.** `--fill` digita e confere; se algum campo não
  aceitar o valor, ele para e não grava nada.
- **A OSI é escolhida, nunca adivinhada.** `--osi` aceita o rótulo que o site
  mostra ou qualquer trecho que case com uma linha só da lista daquele dia
  (o número puro continua servindo); se você não passar nada, ele usa a
  última OSI que gravou, e recusa se não houver nenhuma. Na tela interativa,
  Tab/Espaço/Enter em cima da linha da OSI abrem a lista inteira.

Códigos de saída: `0` feito, `1` erro, `2` nada a fazer (um feriado pulado não
é falha).

### Primeiro uso: o login é manual, uma vez

A automação nunca faz login — o portal pede código do Google Authenticator.
Na primeira vez o programa abre o Edge (ou Chrome) num **perfil dedicado**;
entre à mão nesse janela e abra `https://ssg.sysmap.com.br`. A sessão fica
salva no perfil e vale para as próximas execuções. Se expirar, o programa
avisa com "Login necessario" em vez de tentar digitar numa tela de login.

## Instalação

**Se você já tem Python** (via [uv](https://docs.astral.sh/uv/)):

```bash
uvx --from git+<url-do-repo> auto-appointment --day 26/08/2026   # sem clonar
```

**Se não tem:** baixe o `auto-appointment.exe` (~15 MB, Windows). Ele não
embute navegador nenhum — dirige o Edge que já está na máquina.

## Desenvolvimento

```bash
uv sync                       # cria .venv e instala tudo (a partir do uv.lock)
uv run auto-appointment --help
uv run python -m pytest       # roda os testes
uv run python -m pytest src/test/unit/test_validation.py::test_valid_sample_week  # um teste
```

Gerar o executável (só funciona no Windows, não há cross-compile):

```bash
uv run pyinstaller --onefile --noconfirm --name auto-appointment --paths src \
  --add-data "src/modules/history/data;modules/history/data" src/main.py
```

## Estrutura

```
src/
  models/appointment.py            # modelo pydantic compartilhado (day, 4 horas, osi, week_day)
  modules/
    paths.py                       # leitura empacotada vs escrita do usuário
    validation/validator.py        # as 10 regras + janela WINDOW_DAYS=7 (compartilhadas)
    history/
      loader.py                    # _load_history / append_appointment (CSV, confiável)
      data/history.csv             # 3 semanas de exemplo (válidas)
      data/history_messy.csv       # com violações (testar que load != validate)
    holiday/service.py             # is_holiday(date) BR: BrasilAPI + cache + fallback offline
    strategy/
      base.py                      # AppointmentStrategy (ABC): generate_for / generate_week
      static/{strategy.py, generator.py}   # static_times(n) p/ n em 1..6
      natural_random/{strategy.py, generator.py}
      __init__.py                  # StrategyType + factory get_strategy()
    browser/
      base.py                      # BrowserController (ABC): open/login/fill_appointment/close
      cdp.py                       # cliente CDP: clique de mouse real, digitação tecla a tecla
      browsers.py                  # acha/sobe Edge -> Chrome, perfil dedicado, lembra qual subiu
      ssg_screen.py                # SsgScreen: ciclo de vida/sessão comum a toda tela do SSG + erros
      ssg_list_modal.py            # o widget "Listagem de Itens" que todo botão "?" abre
      ssg_controller.py            # a tela de apontamento (preencher, conferir, gravar, ler OSIs)
      ssg_osi_form.py              # a tela de cadastro de OSI
      playwright_controller.py     # stub (descartado: baixa browsers próprios)
      input_controller.py          # stub (framework autoral mouse/teclado, plano B)
    osi_catalog/
      entry.py                     # OsiEntry (number/label) + from_label(), que aceita texto livre
      cache.py                     # load/save do catálogo e do "último usado", em user_data_dir()
      probe.py                     # refresh_catalog() -- lê a lista pelo "?" da tela de apontamento
    osi_register/
      window.py, description.py, effort.py   # peças puras: período aceito, descrição, esforço = 8/dia
      flow.py                      # o fluxo do formulário: prepare / discover_window / fill / submit
      cli.py                       # o fluxo de console (--register-new-osi); sem executável próprio
    tui/
      state.py, menu_state.py, refresh_state.py   # estado puro (menu, formulário, atualizar lista)
      argv_builder.py, render.py, menu_render.py, refresh_render.py   # só texto/ANSI, sem prompt_toolkit
      keys_legend.py               # o rodapé de teclas: [TECLA] / [TECLA] + MUDA/ABRE/EXECUTA, só ASCII
      app.py                       # único arquivo que importa prompt_toolkit; mapa de teclas único
  main.py                          # orquestrador + CLI + menu inicial (único entry point)
  test/{unit,integration,e2e}/
doc/
  ROADMAP.md                       # estado de cada etapa e decisões por trás delas
  sysmap_ssg/                      # conhecimento sobre o site SSG/SysMap (recon, seletores, armadilhas)
    stack.md, sessao-e-rotas.md, campo-mascarado.md   # não específico de uma tela
    pages/{login, apontamento, listagem-de-osi, cadastro-de-osi}/   # um markdown (+ selectors.json) por tela
```

O que é gravado fica em `%LOCALAPPDATA%\auto-appointment\`: o perfil do
navegador, o cache de feriados, e o histórico que cresce a cada apontamento
confirmado (é dele que a Regra 4 depende).

Veja `doc/ROADMAP.md` para o estado de cada etapa e as decisões por trás
delas, e `doc/sysmap_ssg/` para o que já se sabe sobre o site em si.
