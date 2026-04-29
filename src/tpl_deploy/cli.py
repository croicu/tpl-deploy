from __future__ import annotations

import argparse
import sys

from tpl_deploy import core
from tpl_deploy.diagnostics import Logger
from tpl_deploy.settings import OSES


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    args = argparse.Namespace()
    try:
        args = _parse_args(argv)
        return _run_command(args)
    except Exception as e:
        if getattr(args, "debug", False):
            raise
        print(f"Error: {e}", file=sys.stderr)
        return 1

VERBS = {
    "new",
    "register",
    "unregister",
    "update",
    "list",
    "config",
}

_EDITOR_TOKENS = """\
editor tokens:
  ${project_dir}   absolute path to the created project folder (quoted)
  ${project_name}  project name (safe identifier, hyphens replaced with _)
  ${open_file}     path to the file marked OpenInEditor in the template
                   (quoted; empty string if none)
  ${code}          expands to: code
  ${devenv}        expands to: full path to devenv.exe (resolved via vswhere)

examples:
  # VS Code - open folder in new window, jump to the main file:
  tpl config set-default-editor "code --new-window ${project_dir} ${open_file}"

  # Visual Studio - open project folder:
  tpl config set-editor cpp windows "${devenv} ${project_dir}"

  # Visual Studio - open project folder and jump to the main file:
  tpl config set-editor cpp windows "${devenv} ${project_dir} /edit ${open_file}"\
"""

_FMT = argparse.RawDescriptionHelpFormatter


def _parse_args(argv: list[str]) -> argparse.Namespace:
    # tpl <template_name> <project_name> [...] ==> tpl new <template_name> <project_name> [...]
    argv = _add_default_command(argv)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--debug", action="store_true", help="Show full traceback on error.")

    parser = argparse.ArgumentParser(
        prog="tpl",
        description="Project template deployment tool.",
        epilog="""\
shorthand (no verb):
  tpl <target> <project_name> [key=value ...]
  is equivalent to:
  tpl new <target> <project_name> [key=value ...]

examples:
  tpl console my_app                                        create project from alias
  tpl github:cpp-console-project my_app                     create from remote:template
  tpl register myfeed https://host/manifest.json            register template repository
  tpl config set-alias github cpp-console-project console   creates an alias for a template

run 'tpl <command> --help' for details on any command.\
""",
        formatter_class=_FMT,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # tpl new <template_name> <project_name> [key=value ...]
    p_new = subparsers.add_parser(
        "new",
        help="Create a new project from a template.",
        description="Create a new project from a template.",
        epilog="""\
target formats:
  alias              short name mapped in config  (e.g. console)
  remote:template    qualified form               (e.g. github:cpp-console-project)

params format: key=value  (e.g. arch=x64)\
""",
        formatter_class=_FMT,
        parents=[common],
    )
    p_new.add_argument("template_name", metavar="target",
                       help="Alias, template name, or remote:template.")
    p_new.add_argument("project_name", help="Destination folder name (becomes the project name).")
    p_new.add_argument("params", nargs="*", metavar="key=value",
                       help="Template parameters.")

    # tpl register <name> <url>
    p_register = subparsers.add_parser(
        "register",
        help="Add or update a remote template catalog.",
        description="""\
Add a remote catalog by name and manifest URL.
If the name already exists the URL is updated and the catalog is re-fetched.
If URL is omitted the remote must already exist; the catalog is re-fetched (same as 'tpl update').\
""",
        formatter_class=_FMT,
        parents=[common],
    )
    p_register.add_argument("name", help="Short name for this remote (e.g. github).")
    p_register.add_argument("url", nargs="?", default=None,
                             help="Manifest URL. Omit to re-fetch an already-registered remote.")

    # tpl unregister <name>
    p_unregister = subparsers.add_parser(
        "unregister",
        help="Remove a remote catalog.",
        description=(
            "Remove a registered remote and its cached assets.\n"
            "At least one remote must remain."
        ),
        formatter_class=_FMT,
        parents=[common],
    )
    p_unregister.add_argument("name", help="Name of the remote to remove.")

    # tpl list
    subparsers.add_parser(
        "list",
        help="List registered remotes.",
        parents=[common],
    )

    # tpl update <name>
    p_update = subparsers.add_parser(
        "update",
        help="Re-fetch a remote catalog.",
        description="Download the latest manifest and assets from a registered remote.",
        formatter_class=_FMT,
        parents=[common],
    )
    p_update.add_argument("name", help="Name of the remote to update.")

    # tpl config <subcommand> ...
    p_config = subparsers.add_parser(
        "config",
        help="Show or modify local configuration.",
        description="""\
Show or modify local configuration.

subcommands:
  show                  print effective config
  set-default-editor    set the fallback editor command
  set-editor            set a language+OS specific editor override
  remove-editor         remove a language+OS editor override
  set-alias             map a short name to a remote:template
  remove-alias          remove an alias\
""",
        formatter_class=_FMT,
        parents=[common],
    )
    config_subparsers = p_config.add_subparsers(dest="config_command", required=True)

    # tpl config show
    config_subparsers.add_parser(
        "show",
        help="Print effective configuration.",
        parents=[common],
    )

    # tpl config set-default-editor "<command>"
    p_set_default_editor = config_subparsers.add_parser(
        "set-default-editor",
        help="Set the fallback editor command used when no language override matches.",
        description="Set the fallback editor command used when no language override matches.",
        epilog=_EDITOR_TOKENS,
        formatter_class=_FMT,
        parents=[common],
    )
    p_set_default_editor.add_argument(
        "edit_command",
        metavar="command",
        help='Quoted editor command string.',
    )

    # tpl config set-editor <language> <os> "<command>"
    p_set_editor = config_subparsers.add_parser(
        "set-editor",
        help="Set a language- and OS-specific editor override.",
        description="Set a language- and OS-specific editor override.",
        epilog=_EDITOR_TOKENS,
        formatter_class=_FMT,
        parents=[common],
    )
    p_set_editor.add_argument("language", help="Language identifier (e.g. cpp, py, cs).")
    p_set_editor.add_argument("os", choices=OSES,
                               help=f"OS key. One of: {', '.join(OSES)}.")
    p_set_editor.add_argument("edit_command", metavar="command",
                               help="Quoted editor command string.")

    # tpl config remove-editor <language> <os>
    p_remove_editor = config_subparsers.add_parser(
        "remove-editor",
        help="Remove a language+OS editor override.",
        formatter_class=_FMT,
        parents=[common],
    )
    p_remove_editor.add_argument("language", help="Language identifier.")
    p_remove_editor.add_argument("os", choices=OSES,
                                  help=f"OS key. One of: {', '.join(OSES)}.")

    # tpl config set-alias <remote> <template_name> <alias>
    p_set_alias = config_subparsers.add_parser(
        "set-alias",
        help="Map a short alias to a remote template.",
        description="Map a short alias to a template name within a remote.",
        epilog="""\
example:
  tpl config set-alias github cpp-console-project console
  afterwards 'tpl console my_app' resolves to github:cpp-console-project\
""",
        formatter_class=_FMT,
        parents=[common],
    )
    p_set_alias.add_argument("remote", help="Existing remote name.")
    p_set_alias.add_argument("template_name", help="Full template name on that remote.")
    p_set_alias.add_argument("alias", help="Short alias to create.")

    # tpl config remove-alias <remote> <alias>
    p_remove_alias = config_subparsers.add_parser(
        "remove-alias",
        help="Remove an alias.",
        formatter_class=_FMT,
        parents=[common],
    )
    p_remove_alias.add_argument("remote", help="Remote the alias belongs to.")
    p_remove_alias.add_argument("alias", help="Alias to remove.")

    return parser.parse_args(argv)


def _run_command(args: argparse.Namespace) -> int:
    if args.command == "new":
        core.new_project(args.template_name, args.project_name, args.params)
    elif args.command == "register":
        core.register_remote(args.name, args.url)
    elif args.command == "unregister":
        core.unregister_remote(args.name)
    elif args.command == "list":
        core.list_remotes()
    elif args.command == "update":
        core.update_remote(args.name)
    elif args.command == "config":
        if args.config_command == "show":
            core.get_config()
        elif args.config_command == "set-default-editor":
            core.set_default_editor(args.edit_command)
        elif args.config_command == "set-editor":
            core.set_editor(args.language, args.os, args.edit_command)
        elif args.config_command == "remove-editor":
            core.remove_editor(args.language, args.os)
        elif args.config_command == "set-alias":
            core.set_alias(args.remote, args.template_name, args.alias)
        elif args.config_command == "remove-alias":
            core.remove_alias(args.remote, args.alias)

    _display_output()
    return 0


def _display_output() -> None:
    for line in Logger.drain():
        Logger.print(line)

def _add_default_command(argv: list[str]) -> list[str]:
    if not argv:
        return ["--help"]

    # Keep -h/--help behavior for root parser
    if argv[0] in ("-h", "--help"):
        return argv

    # If first token is not a verb, treat it as <target> and rewrite to "new"
    if argv[0] not in VERBS:
        return ["new", *argv]

    return argv

if __name__ == "__main__":
    sys.exit(main())
