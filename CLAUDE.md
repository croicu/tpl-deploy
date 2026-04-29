# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

`tpl` is a template deployment tool. All behavior is defined by:

1. `docs/PROTOCOL.md` — authoritative spec
2. `docs/IMPLEMENTATION.md` — coding constraints
3. Existing code
4. `README.md`

On conflict: ask for clarification. Do not guess.

---

## Commands

```bash
# Install for development
pip install -e ".[dev]"

# Run all tests
pytest

# Run a single test file or test
pytest tests/unit/test_settings.py
pytest tests/unit/test_settings.py::ClassName::test_method

# Lint and format
ruff check src/ tests/
ruff format src/ tests/

# Build distribution
python -m build
```

---

## Architecture

### Module responsibilities (strict boundaries)

| Module | Responsibility |
|--------|---------------|
| `cli.py` | Arg parsing, argv rewrite (`tpl X` → `tpl new X`), editor token resolution and launch |
| `core.py` | Orchestration only — no policy, no subprocess, no config mutation |
| `catalog.py` | Remote registry (`Catalog`), fetch/parse manifest, `TemplateInfo` |
| `settings.py` | Config + registry IO/validation; `Settings` singleton, `RemoteInfo` |
| `protocols.py` | **All** `Protocol` definitions — add new ones here only |
| `error.py` | Exception hierarchy — all exceptions derive from `TplError` |
| `diagnostics.py` | `Logger` static facade + `DiagnosticsLogSink` |
| `vs_registration.py` | Windows-only VS template copy + `devenv /InstallVSTemplates` |
| `launcher.py` | Thin `subprocess.Popen` wrapper (fire-and-forget for editor launch) |

### Storage layout

Two separate files under `Settings.user_data_dir`:

- **`catalog/catalog.json`** — remote registry (names + URLs). Written only by `register`, `unregister`, and `update`.
- **`config.json`** — user customizations (editors, aliases). Not created until the first mutation; until then the bundled `defaults.json` inside the wheel is used.

Set `TPL_DEPLOY_USER_DATA_DIR` to override in tests or CI.

### Output and Logger pattern

Core never prints. It calls `Logger.info()` / `Logger.warning()`. `TplError.__init__` also logs on construction, so thrown exceptions surface in CLI output automatically. After every command, CLI calls `Logger.drain()` and prints each message.

`Logger` uses a **sink stack** (`Logger._sinks`). Tests push a `TestLogger` on top (via `conftest.py` autouse) to capture messages without printing.

### Test isolation

`conftest.py` autouse resets all stateful singletons before and after each test:
- `Settings._reset()` — clears in-memory config cache and all path overrides
- `Logger._reset()` then `TestLogger` pushed on top
- `Launcher._reset()`, `HttpRemote._reset()`, `vs_registration._reset()` — reset pluggable implementations

`HttpRemote` uses an injectable `Transport` (`HttpBouncer` in tests); `vs_registration` uses an injectable provider (`_NullProvider` in tests); `Launcher` uses a replaceable agent (`MockLauncher` when needed). Do not repeat this setup in individual test classes — `conftest.py` wires it up for all tests.

`Settings._settings` class variable is an intentional singleton cache, not a global state violation.

### Import style

- Project modules: qualified names — `import module`, then `module.Type`
- stdlib + third-party: `from module import Type` is acceptable

---

## Core Rules

- Do NOT invent behavior not in PROTOCOL.md; do not infer missing features
- Do NOT add abstraction layers, plugins, background workers, or extensibility hooks
- Do NOT mutate config outside CLI commands
- Do NOT add retries or fallbacks — **except**: file I/O (delete/write) may retry with exponential backoff because antivirus software briefly locks files on Windows; network operations must NOT retry
- Fail fast: raise typed exceptions, no silent fallback
- Only CLI prints; core emits via `Logger.info()` or raises `TplError`
- Editor launch uses `shell=True` via `Launcher.launch()` (fire-and-forget `Popen`) so executable tokens (`${code}`, `${devenv}`) are resolved by the shell before argv split

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | success |
| 2 | usage error |
| 3 | validation error |
| 4 | destination exists |
| 5 | network error |
| 6 | manifest error |
| 7 | install error |

---

## Tasks

When a task is provided, follow `docs/TASK_TEMPLATE.md`. Do not expand scope beyond the defined task.
