# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

The project uses **uv** for the environment and dependencies (declared in `pyproject.toml`; do not use conda or a bare `python` — on this machine bare `python` hits a Windows Store stub). Prefix everything with `uv run`:

```bash
uv sync                       # create .venv + install from uv.lock
uv run python -m pytest       # full suite (config in pytest.ini: pythonpath = src)
uv run python -m pytest src/test/unit/test_validation.py::test_valid_sample_week   # single test
uv run python -m pytest src/test/unit            # only unit tests (also: integration, e2e)
uv run python src/main.py     # run the orchestrator (prints a generated appointment)
uv add <pkg> / uv add --dev <pkg>                # add a runtime / dev dependency
```

There is no build/lint step. Runtime dep: `pydantic` (>=2). Dev dep: `pytest`. `playwright` is added only when the browser layer is implemented.

## Architecture

A generator of workday "appointment" punch times (entry / lunch start / lunch end / exit), with a hard separation between **producing numbers** and **driving a browser**. The orchestrator (`src/main.py`) is the only place that wires them together: it loads history, picks a strategy via the factory, generates values **once**, and (future phase) replays the *same* values on each browser controller so the two can be compared on equal input.

Generation uses the GoF **Strategy** pattern:
- **`StaticStrategy`** (the default) — six memorizable sets numbered 1..6, produced by the formula in `modules/strategy/static/generator.py` (`static_times(n)`). `generate_for(day)` maps the weekday to a set: Mon..Fri → 1..5, weekend → 6 (the spare). It does **not** raise on weekends.
- **`NaturalRandomStrategy`** — random times retried until they satisfy `modules/validation/validator.py`, constrained by injected history.

Strategies are selected through `get_strategy(StrategyType, history=...)` in `modules/strategy/__init__.py` (`DEFAULT_STRATEGY = StrategyType.STATIC`).

### Layout convention (deliberate)
- `models/` holds only what is **shared across modules** — currently the `Appointment` pydantic model (`BaseModel`; construct with keyword args, fields validated on creation).
- `modules/` holds implementations grouped by domain; each domain's **ABC lives inside its own module** (`modules/strategy/base.py`, `modules/browser/base.py`), not in `models/`.
- The strategy primitive is `generate_for(day: date)`; `generate_week()` is a helper built on it.

### Invariants worth preserving
- **Generator must stay aligned with the validator.** Allowed hour ranges live in `validator.py` (`ENTRY_HOURS`, `LUNCH_START_HOURS`, `EXIT_HOURS`); `natural_random/generator.py` imports and samples from them. Changing one side without the other silently makes rules unreachable.
- **Rule 4 windowing has a single source of truth.** `validate()` trims `history` to the last `WINDOW_DAYS - 1` entries (`WINDOW_DAYS = 7`, by count) itself, so callers pass the full history and never diverge. The generator passes its whole history; do not re-window in callers. A comment in `validator.py` documents how the real system differs (centred ±4 calendar days, holiday-aware) from our simpler backward-only by-count window.
- **History is trusted, never validated on load.** `_load_history` parses the CSV but does not enforce the rules — real-world punches may legitimately break them. `history_messy.csv` exists to prove load ≠ validate.
- **`NaturalRandomStrategy` is immutable.** It never mutates its stored history; `generate_week` uses a local accumulator so days in a week stay unique (Rule 4) without side effects.
- **`Appointment.week_day` is derived** from `day.weekday()` (a property, no stored state). Weekday keys: 0 = Monday … 6 = Sunday.
- **`Appointment` is a pydantic `BaseModel`:** it has no positional constructor — always build it with keyword args. Equality compares all fields (incl. `day`/`osi`); `__repr__`/`__str__` are overridden for compact `HH:MM` output.
- **Day eligibility lives in the orchestrator, not the strategies.** `main.run` skips weekends and Brazilian holidays by default; `force=True` punches anyway (used when actually asked to work). The strategies are calendar-agnostic: `StaticStrategy` no longer raises on weekends (it uses spare set 6), `NaturalRandomStrategy` generates regardless.
- **Holiday checks come from `modules/holiday/service.py`.** `is_holiday(date)` resolves national holidays via local cache → BrasilAPI (stdlib `urllib`, no dep) → offline fixed-date fallback. Pass `allow_network=False` to stay offline (tests do). The cache (`modules/holiday/data/*.json`) is gitignored; movable holidays (Carnaval etc.) are only covered when the API/cache is available, not by the fallback.

### Imports
`pytest.ini` puts `src` on the path, so use absolute imports rooted there (`from models.appointment import Appointment`, `from modules.strategy import get_strategy`). `src/` has **no** `__init__.py` (so pytest roots test packages at `src`); the package tree under `models/`, `modules/`, and `test/` does.

### Browser layer (future)
`modules/browser/` defines `BrowserController` (ABC: `open` / `login` / `fill_appointment` / `close`). `PlaywrightController` (Playwright, pure Python) and `InputController` (home-grown mouse/keyboard) are stubs that raise `NotImplementedError` — both will implement the same contract intentionally, to compare which drives the site better.
