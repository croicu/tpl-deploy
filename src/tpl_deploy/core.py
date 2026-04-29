from __future__ import annotations

import pathlib

from . import vs_registration
from .catalog import Catalog, TemplateInfo
from .diagnostics import Logger
from .error import DestinationExistsError, TplValueError, ValidationError
from .settings import RemoteInfo, Settings


def register_remote(name: str, url: str | None) -> None:
    if url is None:
        if Catalog().get_remote_info(name) is None:
            raise TplValueError(f"Remote '{name}' is not registered. Provide a URL to register it.")
        update_remote(name)
        return

    Logger.info(f"Registering remote '{name}' with URL '{url}'")

    catalog = Catalog()
    catalog.register_remote(RemoteInfo(name=name, url=url))
    catalog.save()

    Logger.info(f"Remote '{name}' registered successfully.")


def unregister_remote(name: str) -> None:
    Logger.info(f"Unregistering remote '{name}'")

    catalog = Catalog()

    remote_info = catalog.get_remote_info(name)
    if remote_info is None:
        raise TplValueError(f"Remote '{name}' not found.")

    catalog.unregister_remote(name)
    catalog.save()
    Settings.remove_remote_aliases(name)
    Settings.save()

    Logger.info(f"Remote '{name}' unregistered successfully.")


def list_remotes() -> None:
    catalog = Catalog()

    remote_info_list = catalog.get_remotes()
    if not remote_info_list:
        return

    Logger.info("Registered remotes:")
    for remote_info in remote_info_list:
        Logger.info(f"- {remote_info.name}: {remote_info.url}")


def update_remote(name: str) -> None:
    catalog = Catalog()

    remote_info = catalog.get_remote_info(name)
    if remote_info is None:
        raise TplValueError(f"Remote '{name}' not found.")

    remote = catalog.get_remote(name)
    if remote is None:
        raise TplValueError(f"Failed to load remote '{name}'.")

    remote.fetch()
    catalog.save()
    vs_registration.register_templates(
        name,
        Settings.catalog_dir / name,
        remote.get_asset_names(),
    )
    Logger.info(f"Remote '{name}' updated successfully.")


def get_config() -> None:
    settings = Settings._get_settings()
    Logger.info("Effective config:")
    for key, value in settings.items():
        if key == "remotes":
            continue
        Logger.info(f"- {key}: {value}")

    catalog = Catalog()
    for remote_info in catalog.get_remotes():
        Logger.info(f"- remote: {remote_info.name}: {remote_info.url}")
        for alias, template_name in Settings.get_remote_aliases(remote_info.name).items():
            Logger.info(f"    alias: {alias} -> {template_name}")


def set_default_editor(command) -> None:
    Settings.set_default_editor(command)

    Settings.save()


def set_editor(language, os, command) -> None:
    Settings.set_editor(language, os, command)
    Settings.save()


def remove_editor(language, os) -> None:
    Settings.remove_editor(language, os)
    Settings.save()


def set_alias(remote_name: str, template_name: str, alias: str) -> None:
    catalog = Catalog()
    if catalog.get_remote_info(remote_name) is None:
        raise TplValueError(f"Remote '{remote_name}' not found.")
    Settings.set_alias(remote_name, alias, template_name)
    Settings.save()


def remove_alias(remote_name: str, alias: str) -> None:
    catalog = Catalog()
    if catalog.get_remote_info(remote_name) is None:
        raise TplValueError(f"Remote '{remote_name}' not found.")
    Settings.remove_alias(remote_name, alias)
    Settings.save()


def new_project(template_name: str, project_name: str | None, params: list[str] | None) -> None:
    dest_dir = _get_dest_dir(template_name, project_name)

    leaf = dest_dir.name
    if leaf in {"", ".", ".."}:
        raise ValidationError(f"Invalid destination '{dest_dir}'.")

    project_name = leaf.replace("-", "_")

    if not _is_valid_token(project_name):
        raise ValidationError(f"Invalid project name '{leaf}'. Allowed: [a-zA-Z0-9_]")

    template_info = _normalize_template_name(template_name)

    catalog = Catalog()
    catalog.create_project(template_info, project_name, dest_dir, params)


# Private
def _is_valid_token(s: str) -> bool:
    return s != "" and all(ch.isalnum() or ch == "_" for ch in s)


def _get_dest_dir(name: str, dest: str | None) -> pathlib.Path:
    cwd = pathlib.Path.cwd()

    if dest is None:
        dest_dir = cwd / name
    else:
        if pathlib.Path(dest).is_absolute():
            dest_dir = pathlib.Path(dest)
        else:
            dest_dir = cwd / dest

    dest_dir = dest_dir.resolve(strict=False)

    if dest_dir.exists():
        raise DestinationExistsError(f"Destination '{dest_dir}' already exists.")

    return dest_dir


def _normalize_template_name(token: str) -> TemplateInfo:
    template_name: str | None = None
    remote_info: RemoteInfo | None = None

    if not token:
        raise TplValueError("Template name required")

    if token.count(":") > 1:
        raise TplValueError(f"Invalid template name: '{token}'")

    if ":" not in token:
        catalog = Catalog()
        for remote_info in catalog.get_remotes():
            template_name = Settings.get_template_by_alias(remote_info.name, token)
            if template_name is not None:
                break

        if template_name is None:
            raise TplValueError(f"Unknown alias: '{token}'")
    else:
        remote, name = token.split(":", 1)

        if not remote or not name:
            raise TplValueError(f"Invalid template name: '{token}'")

        catalog = Catalog()
        remote_info = catalog.get_remote_info(remote)

        if remote_info is None:
            raise TplValueError(f"Remote '{remote}' not found for template '{token}'")

        template_name = name

    return TemplateInfo(template_name, remote_info)
