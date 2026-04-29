# tpl --- PROTOCOL (Compiler-Grade Specification)

This document is the **authoritative, exhaustive, unambiguous
specification** of `tpl`.

All implementations MUST conform exactly. Any behavior not explicitly
defined is INVALID.

------------------------------------------------------------------------

# 1. Identity

-   Executable name: `tpl`
-   Exactly one binary
-   No aliases
-   CLI layer is thin
-   Core layer is policy-free

------------------------------------------------------------------------

# 2. CLI Grammar

    tpl <target> <project_name> [key=value ...]

## 2.1 Rewrite Rule

If first token is not a known verb:

    tpl X → tpl new X

------------------------------------------------------------------------

## 2.2 Token Parsing

  Position     Meaning
  ------------ --------------
  argv\[1\]    target
  argv\[2\]    project_name
  argv\[3+\]   params

------------------------------------------------------------------------

## 2.3 Param Format

Each param MUST:

    contain exactly one '='

Validation:

    key: ^[A-Za-z0-9_]+$
    value: any string (may be empty)

Invalid → HARD ERROR

------------------------------------------------------------------------

# 3. Target Resolution Algorithm

## 3.1 Input

    target: str
    remotes: list[Remote]

------------------------------------------------------------------------

## 3.2 Qualified Case

    if ':' in target:
        remote_name, name = split(target, 1)

Algorithm:

1.  Find remote by name
2.  If not found → ERROR
3.  Resolve ONLY inside that remote
4.  No fallback

------------------------------------------------------------------------

## 3.3 Unqualified Case

For each remote in list order:

### Step 1 --- Alias Check

    if target in remote.aliases:
        return remote, remote.aliases[target]

### Step 2 --- Direct Name Check

    if snapshot missing:
        fetch(remote)

    if target in manifest:
        return remote, target

Continue until match.

If no match → ERROR

------------------------------------------------------------------------

## 3.4 Network Rules

-   Fetch ONLY when required
-   Fetch ONLY one remote at a time
-   Never prefetch
-   Never refresh globally
-   Never retry automatically

------------------------------------------------------------------------

# 4. Config Model

## 4.1 Schema

    {
      "schema": 1,
      "editors": {...},
      "remotes": [Remote]
    }

------------------------------------------------------------------------

## 4.2 Remote Structure

    Remote:
        name: str
        url: str
        aliases: dict[str, str] | None

Constraints:

-   remotes MUST be non-empty
-   names MUST be unique
-   regex: [^1]+\$
-   order defines priority
-   no timestamps
-   no priority field

------------------------------------------------------------------------

## 4.3 Bootstrap

    if config missing:
        create default config
        DO NOT fetch

    if config invalid:
        HARD ERROR

------------------------------------------------------------------------

# 5. Project Naming

## 5.1 Destination

    ./<project_name>

If exists → ERROR

------------------------------------------------------------------------

## 5.2 Internal Identity

    safeprojectname = project_name.replace("-", "_")

Validation:

    ^[A-Za-z0-9_]+$

Failure → ERROR

------------------------------------------------------------------------

# 6. Asset Model

## 6.1 Manifest

    {
      "schema": 1,
      "assets": [string]
    }

------------------------------------------------------------------------

## 6.2 Download Algorithm

    for asset in manifest.assets:
        url = base_url + "/" + asset + ".zip"

------------------------------------------------------------------------

## 6.3 Caching

### Case 1 --- ETag present

    version = normalize(etag)
    path = asset.<version>.<name>.zip

Rules:

-   immutable
-   if exists → DO NOT overwrite

------------------------------------------------------------------------

### Case 2 --- No ETag

    path = asset._no_tag_.<name>.zip

Rules:

-   overwrite always

------------------------------------------------------------------------

## 6.4 Forbidden

-   no semver
-   no timestamps

## 6.5 Cleanup and Pruning

-   cleanup and pruning of old asset files are best-effort operations
-   failures MUST NOT propagate — silently ignored

------------------------------------------------------------------------

# 7. Editor Execution

## 7.1 Input

    command_template: str
    project_dir: path

------------------------------------------------------------------------

## 7.2 Resolution

    command = template.replace("${project_dir}", project_dir)
    argv = split(command)

------------------------------------------------------------------------

## 7.3 Execution

    subprocess.run(argv)

------------------------------------------------------------------------

## 7.4 Constraints

-   command is opaque
-   must exist in PATH or absolute
-   no probing
-   no fallback
-   no retry

Failure → ERROR

------------------------------------------------------------------------

# 8. Config Commands

## 8.1 Supported

    tpl config show

    tpl config set-default-editor "<cmd>"

    tpl config set-editor <lang> <os> "<cmd>"

    tpl config remove-editor <lang> <os>

    tpl config set-alias <remote> <alias> <canonical>

    tpl config remove-alias <remote> <alias>

------------------------------------------------------------------------

## 8.2 Validation

-   alias regex: [^2]+\$
-   remote must exist
-   os ∈ {windows, linux, macos}

Invalid → ERROR

------------------------------------------------------------------------

## 8.3 Forbidden

-   no key-path mutation
-   no list indexing
-   no arbitrary JSON edits

------------------------------------------------------------------------

# 9. Module Boundaries

## CLI

-   parsing
-   rewrite
-   resolution
-   editor execution

## Core

-   orchestration only
-   no policy
-   no subprocess
-   no config mutation

## Catalog

-   fetch
-   parse

## Settings

-   load/save config
-   load/save registry

------------------------------------------------------------------------

# 10. Exception Model

All failures MUST:

-   raise typed exception
-   ALL exceptions MUST derive from `TplError`
-   propagate to CLI
-   CLI maps to exit code

NO silent fallback

------------------------------------------------------------------------

# 11. Exit Codes

  Code   Meaning
  ------ --------------------
  0      success
  2      usage error
  3      validation error
  4      destination exists
  5      network error
  6      manifest error
  7      install error

------------------------------------------------------------------------

# 12. Invariants

-   deterministic execution
-   config is source of truth
-   remote order stable
-   no implicit state mutation
-   versioned assets immutable

------------------------------------------------------------------------

# 13. Forbidden Behaviors

Implementations MUST NOT:

-   add background threads
-   add plugin systems
-   introduce abstraction layers
-   mutate config implicitly
-   auto-repair state
-   retry operations silently
-   probe environment
-   add heuristics

------------------------------------------------------------------------

# 14. Determinism Guarantee

Given:

-   same config
-   same remote responses
-   same inputs

Output MUST be identical.

------------------------------------------------------------------------

# 15. Remote Management

## 15.1 Register

    tpl remote add <name> <url>

-   If the remote does not exist → add to registry, fetch manifest and assets, register VS templates
-   If the remote already exists → update URL, re-fetch, re-register VS templates
-   No error on re-registration; the command is idempotent with respect to the name

## 15.2 Unregister

    tpl remote remove <name>

-   Removes remote from registry
-   Removes VS templates for that remote
-   Removes local cached assets
-   Removes aliases for that remote from config
-   ERROR if the remote is the last one

## 15.3 Update

    tpl update <name>

-   Re-fetches manifest and assets from the remote URL
-   Re-registers VS templates

------------------------------------------------------------------------

# 16. VS Template Registration

## 16.1 Scope

-   Windows only
-   Only when Visual Studio is detected via `vswhere -latest`

------------------------------------------------------------------------

## 16.2 Triggers

VS template registration MUST run after:

-   `tpl remote add`
-   `tpl update`

VS template unregistration MUST run after:

-   `tpl remote remove`

------------------------------------------------------------------------

## 16.3 VS Version Table

Map `installationVersion` major number to Documents subfolder name:

  Major   Folder
  ------- -----------------------
  16      Visual Studio 2019
  17      Visual Studio 2022
  18      Visual Studio 18

If major version is not in table → WARNING + skip. No ERROR.

------------------------------------------------------------------------

## 16.4 Documents Folder

MUST be resolved via `SHGetFolderPathW(CSIDL_PERSONAL)`. Never hardcoded.
Handles OneDrive and folder redirects correctly.

------------------------------------------------------------------------

## 16.5 Template Path

    <Documents>/<vs_folder>/Templates/ProjectTemplates/<remote_name>.<template_name>.zip

------------------------------------------------------------------------

## 16.6 Registration Algorithm

1.  Resolve Documents folder via `SHGetFolderPathW`
2.  Map `installationVersion` major → VS folder name
3.  Create templates dir if missing
4.  For each asset in manifest:
    -   Glob `<catalog_dir>/<remote_name>/<asset_name>.*.zip`
    -   Pick newest match
    -   If no match → WARNING + skip asset
    -   Copy to `<templates_dir>/<remote_name>.<asset_name>.zip`
5.  If any file was copied → run `devenv /InstallVSTemplates` via Launcher

------------------------------------------------------------------------

## 16.7 Unregistration Algorithm

1.  Resolve templates dir
2.  Delete all `<templates_dir>/<remote_name>.*.zip`
3.  If any file was deleted → run `devenv /InstallVSTemplates` via Launcher

------------------------------------------------------------------------

## 16.8 Devenv Execution

-   Path resolved via `vswhere -property installationPath`
-   MUST use `Launcher` (mockable in tests)
-   `cwd` is the current working directory at CLI invocation time

------------------------------------------------------------------------

END OF SPEC

[^1]: A-Za-z0-9\_

[^2]: A-Za-z0-9\_
