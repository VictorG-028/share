# Auto Appointment

Gera valores de apontamento (entrada, almoço, saída) por dia, com **separação clara
entre gerar números e controlar o navegador**. A geração usa o pattern GoF
**Strategy**:

- **`static`** (padrão) — 6 conjuntos memorizáveis numerados 1–6, gerados pela fórmula
  em `modules/strategy/static/generator.py`. Por dia: Seg–Sex → 1–5, fim de semana → 6
  (coringa). Não levanta erro no fim de semana.
- **`natural_random`** — horários aleatórios sob as 10 regras + histórico
  (`modules/strategy/natural_random/`).

## Estrutura

```
src/
  models/appointment.py            # modelo pydantic compartilhado (day, 4 horas, osi, week_day)
  modules/
    validation/validator.py        # as 10 regras + janela WINDOW_DAYS=7 (compartilhadas)
    history/
      loader.py                    # _load_history(file) -> list[Appointment] (CSV, confiável)
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
      playwright_controller.py     # stub (Playwright, Python puro)
      input_controller.py          # stub (framework autoral mouse/teclado)
  main.py                          # orquestrador
  test/{unit,integration,e2e}/
```

O orquestrador (`main.run`) pula fim de semana e feriado por padrão (`force=True`
aponta mesmo assim), gera os valores **uma vez** e (fase futura) os repassa para os
dois controladores de browser em sessões separadas, para comparar qual dirige melhor
o site com o mesmo input.

## Setup e execução (uv)

O projeto usa [uv](https://docs.astral.sh/uv/) para ambiente e dependências
(declaradas em `pyproject.toml`; `pydantic` em runtime, `pytest` no grupo `dev`).

```bash
uv sync                       # cria .venv e instala tudo (a partir do uv.lock)
uv run python src/main.py     # gera o apontamento de exemplo
uv run python -m pytest       # roda os testes
uv run python -m pytest src/test/unit/test_validation.py::test_valid_sample_week  # um teste
```

`uv run` executa no ambiente do projeto sem precisar ativar nada manualmente.
Para adicionar uma dependência: `uv add <pacote>` (ou `uv add --dev <pacote>`).
