# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

The project uses **uv** for the environment and dependencies (declared in `pyproject.toml`; do not use conda or a bare `python` — on this machine bare `python` hits a Windows Store stub). Prefix everything with `uv run`:

```bash
uv sync                       # create .venv + install from uv.lock
uv run python -m pytest       # full suite (config in pytest.ini: pythonpath = src)
uv run python -m pytest src/test/unit/test_validation.py::test_valid_sample_week   # single test
uv run python -m pytest src/test/unit            # only unit tests (also: integration, e2e)
uv run auto-appointment --help                   # the CLI (installed entry point)
uv run auto-appointment --day 26/08/2026         # generate and print; opens nothing
uv add <pkg> / uv add --dev <pkg>                # add a runtime / dev dependency

# Build the Windows executable (no cross-compile; run this on Windows)
uv run pyinstaller --onefile --noconfirm --name auto-appointment --paths src \
  --add-data "src/modules/history/data;modules/history/data" src/main.py
```

There is no lint step. Runtime deps: `pydantic` (>=2), `websocket-client` (the CDP transport — pure Python, so the PyInstaller bundle stays trivial), and `prompt_toolkit` (the interactive grid-form's terminal UI — a deliberate, larger addition; see the CLI section below). Dev deps: `pytest`, `pyinstaller`. `playwright` was deliberately **not** adopted: it downloads its own browsers, which do not fit in a onefile bundle.

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
- Not every domain needs a `base.py` ABC — only when there are (or are clearly planned) multiple implementations, as in `modules/browser/` and `modules/strategy/`. `modules/osi_catalog/` and `modules/tui/` have exactly one implementation each and deliberately have no ABC.

### Invariants worth preserving
- **Generator must stay aligned with the validator.** Allowed hour ranges live in `validator.py` (`ENTRY_HOURS`, `LUNCH_START_HOURS`, `EXIT_HOURS`); `natural_random/generator.py` imports and samples from them. Changing one side without the other silently makes rules unreachable.
- **Rule 4 windowing has a single source of truth.** `validate()` trims `history` to the last `WINDOW_DAYS - 1` entries (`WINDOW_DAYS = 7`, by count) itself, so callers pass the full history and never diverge. The generator passes its whole history; do not re-window in callers. A comment in `validator.py` documents how the real system differs (centred ±4 calendar days, holiday-aware) from our simpler backward-only by-count window.
- **History is trusted, never validated on load.** `_load_history` parses the CSV but does not enforce the rules — real-world punches may legitimately break them. `history_messy.csv` exists to prove load ≠ validate.
- **Reads are packaged, writes are not.** `paths.bundle_dir()` (`src` in a checkout, the extraction dir when frozen) is where packaged data is read from; everything written — browser profile, holiday cache, the growing history — goes under `paths.user_data_dir()`. A frozen onefile recreates its extraction dir every run, so writing there loses the data silently. `loader.append_appointment` records only punches that actually landed on the site, and refuses the same day twice.
- **`NaturalRandomStrategy` is immutable.** It never mutates its stored history; `generate_week` uses a local accumulator so days in a week stay unique (Rule 4) without side effects.
- **`Appointment.week_day` is derived** from `day.weekday()` (a property, no stored state). Weekday keys: 0 = Monday … 6 = Sunday.
- **`Appointment` is a pydantic `BaseModel`:** it has no positional constructor — always build it with keyword args. Equality compares all fields (incl. `day`/`osi`); `__repr__`/`__str__` are overridden for compact `HH:MM` output.
- **Past days only.** SSG refuses the current day and any future date, so `main.run` returns `None` for `target_day >= date.today()`. This is a hard rule and `force=True` does **not** bypass it (`force` exists only for weekends and holidays).
- **Day eligibility lives in the orchestrator, not the strategies.** `main.run` skips weekends and Brazilian holidays by default; `force=True` punches anyway (used when actually asked to work). The strategies are calendar-agnostic: `StaticStrategy` no longer raises on weekends (it uses spare set 6), `NaturalRandomStrategy` generates regardless.
- **Holiday checks come from `modules/holiday/service.py`.** `is_holiday(date)` resolves national holidays via local cache → BrasilAPI (stdlib `urllib`, no dep) → offline fixed-date fallback. Pass `allow_network=False` to stay offline (tests do). The per-year cache lives under `user_data_dir()/holidays`; movable holidays (Carnaval etc.) are only covered when the API/cache is available, not by the fallback.

### Imports
`pytest.ini` puts `src` on the path, so use absolute imports rooted there (`from models.appointment import Appointment`, `from modules.strategy import get_strategy`). `src/` has **no** `__init__.py` (so pytest roots test packages at `src`); the package tree under `models/`, `modules/`, and `test/` does.

`[tool.hatch.build.targets.wheel] sources = ["src"]` strips the prefix so `main.py`, `models/` and `modules/` land at the wheel root — the same root pytest assumes. That is what keeps those absolute imports working both from a checkout and from an installed wheel; changing it breaks the CLI entry point (`main:cli`).

### CLI
`main.cli()` is the entry point. The default is **dry**: it generates and prints, opening no browser and writing nothing. `--fill` types and verifies; `--save` writes and asks for confirmation first (`--yes` skips), refusing rather than guessing when there is no tty. `--fill` without `--save` rejects more than one day on purpose — filtering the next day re-renders the screen and discards what was typed. `--week` goes through the strategy's `generate_week` rather than looping over `run()`, because `NaturalRandomStrategy` keeps a week's days unique from each other. `--refresh-osi-list` is read-only — it does only that (probes the live site, writes `osi_catalog.json` under `user_data_dir()`) and ignores every other flag. Exit codes: `0` done, `1` error, `2` nothing to do (a skipped holiday is not a failure).

- **The interactive grid-form triggers from inside `cli()`**, gated on `argv is None and len(sys.argv) == 1 and sys.stdin.isatty()` — *not* textually inside `if __name__ == "__main__":`. The installed console-script stub does `from main import cli; if __name__ == "__main__": sys.exit(cli())` — that dunder-main is the *stub's own*, not `main.py`'s, so a check placed in `main.py`'s own `if __name__ == "__main__":` block would never fire for `uv run auto-appointment`, only for the frozen `.exe` (which really does run `src/main.py` as `__main__`). Gating on `argv is None` inside `cli()` fires correctly for both, and — this is the actual invariant that matters — leaves `main.cli([])` (an explicit empty list, asserted by `test_defaults_to_yesterday`) meaning exactly "yesterday, dry mode" regardless of real `sys.argv`/isatty, since `argv is None` is `False` for an explicit `[]`. Don't move this check into `__main__` — it would silently break the `uv run` path.
- **`modules/tui/` splits pure state from `prompt_toolkit` glue.** `state.py` (the grid's focus/value logic — day/month/year/force cursor, OSI spinner, submit/cancel), `argv_builder.py`, and `render.py` (raw ANSI, no color library) import nothing from `prompt_toolkit` and are plain-pytest tested. `app.py` is the only file that imports `prompt_toolkit`; it's tested by driving the real `Application` with `prompt_toolkit.input.create_pipe_input()`/`prompt_toolkit.output.DummyOutput` (synthetic key sequences), not a real terminal — this project's tools cannot open a genuine Win32 console, and manual verification in a real PowerShell/cmd window or the double-clicked `.exe` is the only way to confirm the visuals.
- **OSI catalog is two separate files under `user_data_dir()`.** `osi_catalog.json` (the list, written only by `--refresh-osi-list`) and `osi_last_used.json` (written only by `punch()`, right after a real save succeeds — `Appointment.osi`/`history.csv` still don't record which OSI was used, so this is the only source of "last used"). `modules/osi_catalog/probe.py`'s actual live extraction is an open TODO — see `ssg_selectors.json`'s `listaOsi` key for what was tried and why it isn't safe/working yet.

### Browser layer
`modules/browser/` defines `BrowserController` (ABC: `open` / `login` / `fill_appointment` / `close`). `SsgController` is the real implementation; `PlaywrightController` and `InputController` remain stubs that raise `NotImplementedError` (`InputController` is the intended second implementation, for the comparison the project always planned).

- **We never ship a browser.** `browsers.py` drives the Edge (falling back to Chrome) already installed, over CDP, using a dedicated persistent profile under `user_data_dir()`. Whichever browser answered is remembered in `browser.json`. Keeps the future `.exe` at ~15 MB.
- **Login is never automated.** The portal asks for a Google Authenticator code. Landing on a login page raises `SsgLoginRequired`; the user signs in by hand once and the profile keeps the session.
- **Filling never saves.** `fill_appointment` types and verifies; `save_day` is a separate call. Every write to a real timekeeping system leaves a trace, so it must be deliberate. `verify` raises `FieldMismatch` before any save can happen.
- **`suppress_origin=True` is load-bearing** in `cdp.py`: `websocket-client` sends an `Origin` header and Chromium answers CDP handshakes carrying one with **403**, unless the browser was launched with `--remote-allow-origins`. Dropping the header works against a browser someone else started, without loosening the browser.
- **Site selectors and traps live in `ssg_selectors.json`**, next to the controller. Nothing on that screen has an `id` or `name`; everything is anchored by class. The constants in `ssg_controller.py` are the executable copy — change both together.
