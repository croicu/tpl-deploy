# tpl --- Architecture (Full Spec)

## Identity

Single executable: `tpl` CLI is thin. Core owns mechanics.

## CLI Grammar

tpl `<target>`{=html} `<project_name>`{=html} \[key=value ...\]

Implicit rewrite: tpl `<target>`{=html} → tpl new `<target>`{=html}

target = alias \| canonical \| remote:name

## Resolution

Unqualified: - scan remotes in order - alias match first - direct name
match second

Qualified: - remote:name only in that remote

## Network

-   lazy fetch only
-   no global refresh
-   no background activity

## Config

-   remotes: ordered list
-   order = priority
-   non-empty
-   authoritative

## Persistent Storage

Two separate files with distinct responsibilities:

**`catalog.json`** — mirror of server state. Written only by `register`, `unregister`, and `update`.
Contains: registered remote names and URLs.
Never contains user preferences.

**`config.json`** — user customizations. Written by all other mutating commands
(`set-default-editor`, `set-editor`, `remove-editor`, `set-alias`, `remove-alias`, `unregister`).
Contains: editors, aliases.
Aliases are keyed by remote name: `{"aliases": {"remote": {"alias": "template"}}}`.
On first run `config.json` does not exist; defaults are loaded from `defaults.json` (bundled).
Once any mutating command runs, `config.json` is written and defaults are no longer consulted.

## Naming

safeprojectname = project_name.replace("-", "\_") must match [^1]+\$

## Assets

-   zip only
-   ETag → immutable
-   no ETag → overwrite

## Editor

-   CLI owned
-   command string with \${project_dir}
-   no discovery

## Modules

cli.py core.py catalog.py settings.py exceptions.py process.py output.py

## Principles

-   deterministic
-   fail early
-   no silent mutation
-   no cleverness

[^1]: A-Za-z0-9\_
