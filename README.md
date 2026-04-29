# tpl-deploy

Minimal, cross-platform template tool for deployment, registering, 
managing, and instantiating project templates from HTTP endpoints. Works with 
Visual Studio and VS Code on Windows, macOS, and Linux.

## Install

``` bash
pip install tpl-deploy
```

## Usage

``` bash
tpl <target> <project_name> [key=value ...]
```

### Examples

``` bash
tpl console my_app
tpl github:cpp.gui my_gui arch=x64
```

## Commands

### Create

``` bash
tpl new <target> <project_name> [key=value ...]
```

### Config

``` bash
tpl config show
tpl config set-default-editor "<command>"
tpl config set-editor <language> <os> "<command>"
tpl config remove-editor <language> <os>
tpl config set-alias <remote> <alias> <canonical_id>
tpl config remove-alias <remote> <alias>
```

### Remotes

``` bash
tpl register <remote> <url>
tpl unregister <remote>
tpl update <remote>
tpl list
```

## Editor configuration

Editor commands support the following tokens:

| Token | Value |
|---|---|
| `${project_dir}` | Absolute path to the created project folder |
| `${project_name}` | Project name (safe identifier) |
| `${open_file}` | Absolute path to the file marked `OpenInEditor` in the template (empty string if none) |
| `${code}` | `code` |
| `${devenv}` | `devenv` |

### Examples

``` bash
# VS Code — open folder in new window, jump to main file
tpl config set-default-editor "code --new-window ${project_dir} ${open_file}"

# Visual Studio — open solution, edit main file
tpl config set-editor cpp windows "devenv ${project_dir} /edit ${open_file}"
```

## Behavior

-   No prompts
-   No auto-numbering
-   Fails if destination exists
-   Fetches only when needed

## Philosophy

-   Deterministic
-   No hidden behavior
-   No auto-repair

## Visual Studio Integration

On Windows, `tpl` automatically registers downloaded templates with Visual Studio so they appear in the **New Project** dialog.

Registration runs on `tpl remote add` and `tpl update`. Unregistration runs on `tpl remote remove`.

### Requirements

-   Windows
-   Visual Studio 2019, 2022, or 2026 with the C++ workload installed (`vswhere` must find it)

### Template location

Templates are copied to:

```
<Documents>\<VS folder>\Templates\ProjectTemplates\<remote>.<template>.zip
```

Where `<Documents>` is resolved via the Windows shell API (handles OneDrive and folder redirects).

### Supported VS versions

| VS Version | Documents folder |
|---|---|
| Visual Studio 2019 | `Visual Studio 2019` |
| Visual Studio 2022 | `Visual Studio 2022` |
| Visual Studio 2026 | `Visual Studio 18` |

If the installed version is not in this table, registration is skipped with a warning.

---

## See also

-   ARCHITECTURE.md
-   IMPLEMENTATION.md

