# tpl --- Coding Guidelines

## Purpose

This file is for contributors and coding assistants (Claude).

It defines constraints that must be preserved during implementation.

## Imports

-   For project modules: use qualified names (`import module` then `module.Type`)
-   For standard library and third-party packages: `from module import Type` is acceptable

## Hard Rules

-   Do NOT introduce abstraction layers unless required
-   Do NOT add plugin systems
-   Do NOT add background processes
-   Do NOT mutate config outside CLI commands
-   Do NOT add implicit behavior

## Protocols

-   All `Protocol` definitions live in `protocols.py`
-   Do not define protocols in other modules

## Boundaries

CLI: - parsing - resolution - editor launch

Core: - pure orchestration - no policy - no subprocess

Settings: - config + registry IO - validation

Catalog: - fetch + parse manifest

## Error Handling

-   raise typed exceptions
-   CLI maps to exit codes
-   no silent fallback

## Editor Resolution

Editor command templates support two substitution passes:

1.  Executable tokens: `${code}` (VS Code), `${vs}` (Visual Studio), `${cursor}` (Cursor) — resolved to their install paths at runtime
2.  `${project_dir}` — replaced with the absolute path of the created project

Both substitutions happen before the command is split into argv.

## Transport

-   `inject_truststore` controls whether trusted root CAs are loaded from the Windows certificate store
-   Defaults to `True`

## File I/O Retries

-   File operations (delete, write) may be retried with exponential backoff
-   Reason: antivirus software may briefly lock files on Windows
-   Network operations MUST NOT be retried

## Process Execution

-   thin wrapper over subprocess
-   no retries
-   no environment probing

## Editor Launch

-   Implemented in `launcher.py` as `Launcher`
-   Uses `subprocess.Popen` (fire and forget) — editor is a UI app, do not wait for it to exit
-   `shell=True` is used to allow editor executable tokens (`${code}`, etc.) to be resolved before the command string is passed

## Output

-   CLI is the only layer that writes directly to stdout/stderr
-   Core never prints; it emits informational results via `Logger.info()` and raises typed exceptions on failure
-   CLI reads Logger records and formats them for the user
-   Errors propagate as typed exceptions derived from `TplError`; CLI maps these to exit codes and user-facing messages

## Testing

-   test via CLI surface
-   avoid JSON snapshot coupling
-   use tmp_path
-   shared fixtures (logger, launcher, settings reset) live in `tests/conftest.py` as `autouse` fixtures
-   `TestLogger` and `TestLauncher` from `tests/shared/mocks.py` are wired up in `conftest.py` — do not repeat setup in individual test classes
-   `Settings._reset()` and `error._pending.clear()` must be called in fixture teardown to prevent state leaking between tests

## Evolution

Any change must preserve: - deterministic behavior - explicit network -
config authority
