from __future__ import annotations

import importlib
import json
import os
import pathlib
import shutil
import sys
import tempfile
import urllib.parse
from contextlib import contextmanager
from dataclasses import dataclass

import platformdirs

from . import descriptors, protocols
from .descriptors import classproperty
from .error import TplValueError
from .helpers import atomic_json_dump

OSES = ("windows", "linux", "macos")


@dataclass
class RemoteInfo(protocols.RemoteReference):
    name: str
    url: str
    inject_truststore: bool = True

    @property
    def type(self) -> str:
        urlparse_result = urllib.parse.urlparse(self.url)
        return urlparse_result.scheme


class Settings(metaclass=descriptors.ClassPropertyMeta):
    # Public

    @staticmethod
    def get_current_os() -> str:
        current_os = sys.platform
        if current_os.startswith("win"):
            return OSES[0]
        elif current_os.startswith("linux"):
            return OSES[1]
        elif current_os.startswith("darwin"):
            return OSES[2]
        else:
            raise TplValueError(f"Unsupported OS: {current_os}")

    @staticmethod
    def get_remotes() -> list[RemoteInfo] | None:
        settings = Settings._get_settings()

        if "remotes" not in settings:
            return None

        return [RemoteInfo(**remote) for remote in settings["remotes"]]

    @staticmethod
    def get_remote(name: str) -> RemoteInfo | None:
        remotes: list[RemoteInfo] = Settings.get_remotes()

        if remotes is None:
            return None

        for remote in remotes:
            if remote.name == name:
                return remote

        return None

    @staticmethod
    def get_default_editor() -> str | None:
        editors = Settings._get_editors()
        return editors.get("default")

    @staticmethod
    def set_default_editor(command: str) -> None:
        editors = Settings._get_editors()
        editors["default"] = command

    @staticmethod
    def get_editor(language: str, os: str) -> str | None:
        language_editors = Settings._get_language_editors(language)

        if language_editors.get(os, None):
            return language_editors[os]

        return Settings.get_default_editor()

    @staticmethod
    def set_editor(language: str, os: str, command: str) -> None:
        language_editors = Settings._get_language_editors(language)
        language_editors[os] = command

    @staticmethod
    def remove_editor(language: str, os: str) -> None:
        language_editors = Settings._get_language_editors(language)
        language_editors.pop(os, None)

        if len(language_editors) == 0:
            groups = Settings._get_editor_groups()
            groups.pop(language, None)

            if len(groups) == 0:
                editors = Settings._get_editors()
                editors.pop("groups", None)

    @staticmethod
    def get_template_by_alias(remote_name: str, alias: str) -> str | None:
        return Settings._get_remote_aliases(remote_name).get(alias)

    @staticmethod
    def set_alias(remote_name: str, alias: str, template_name: str) -> None:
        Settings._get_remote_aliases(remote_name)[alias] = template_name

    @staticmethod
    def remove_alias(remote_name: str, alias: str) -> None:
        aliases = Settings._get_aliases()
        if remote_name not in aliases:
            return
        aliases[remote_name].pop(alias, None)
        if not aliases[remote_name]:
            aliases.pop(remote_name)
        if not aliases:
            Settings._get_settings().pop("aliases", None)

    @staticmethod
    def remove_remote_aliases(remote_name: str) -> None:
        aliases = Settings._get_aliases()
        aliases.pop(remote_name, None)
        if not aliases:
            Settings._get_settings().pop("aliases", None)

    @staticmethod
    def get_remote_aliases(remote_name: str) -> dict[str, str]:
        return dict(Settings._get_remote_aliases(remote_name))

    @staticmethod
    def save() -> None:
        settings = {k: v for k, v in Settings._get_settings().items() if k != "remotes"}

        config_path = Settings.config_path
        config_path.parent.mkdir(parents=True, exist_ok=True)

        atomic_json_dump(config_path, settings)

    @classproperty
    def app_name(cls) -> str:
        return "tpl"

    @descriptors.classproperty
    def user_data_dir(cls) -> pathlib.Path:
        if cls._user_data_dir is None:
            env_user_data_dir = os.environ.get("TPL_DEPLOY_USER_DATA_DIR")
            if env_user_data_dir is not None:
                cls._user_data_dir = pathlib.Path(env_user_data_dir)
            else:
                cls._user_data_dir = pathlib.Path(
                    platformdirs.user_data_dir(appname=cls.app_name, appauthor=False)
                )

        return cls._user_data_dir

    @user_data_dir.setter
    def user_data_dir(cls, value: str | pathlib.Path):
        cls._user_data_dir = pathlib.Path(value)

    @descriptors.classproperty
    def temp_dir(cls) -> pathlib.Path:
        if cls._temp_dir is None:
            env_temp_dir = os.environ.get("TPL_DEPLOY_TEMP_DIR")
            if env_temp_dir is not None:
                cls._temp_dir = pathlib.Path(env_temp_dir)
            else:
                cls._temp_dir = pathlib.Path(tempfile.gettempdir())

        return cls._temp_dir

    @temp_dir.setter
    def temp_dir(cls, value: str | pathlib.Path):
        cls._temp_dir = pathlib.Path(value)

    @descriptors.classproperty
    def resources_dir(cls) -> pathlib.Path:
        if cls._resources_dir is None:
            env_resources_dir = os.environ.get("TPL_DEPLOY_RESOURCES_DIR")
            if env_resources_dir is not None:
                cls._resources_dir = pathlib.Path(env_resources_dir)
            else:
                cls._resources_dir = pathlib.Path(importlib.resources.files("tpl_deploy"))

        return cls._resources_dir

    @resources_dir.setter
    def resources_dir(cls, value: str | pathlib.Path):
        cls._resources_dir = pathlib.Path(value)

    @descriptors.classproperty
    def catalog_dir(cls) -> pathlib.Path:
        return Settings.user_data_dir / "catalog"

    @descriptors.classproperty
    def config_path(cls) -> pathlib.Path:
        return Settings.user_data_dir / "config.json"

    @staticmethod
    @contextmanager
    def scratch_dir():
        scratch_dir = Settings._create_scratch_dir()
        try:
            yield scratch_dir
        finally:
            Settings._dispose_scratch_dir(scratch_dir)

    # Private

    @staticmethod
    def _create_scratch_dir() -> pathlib.Path:
        return pathlib.Path(tempfile.mkdtemp(dir=Settings.temp_dir))

    @staticmethod
    def _dispose_scratch_dir(scratch_dir: pathlib.Path) -> None:
        if scratch_dir.exists():
            shutil.rmtree(scratch_dir)

    @staticmethod
    def enable_defaults(enabled: bool) -> None:
        Settings._defaults_enabled = enabled

    @staticmethod
    def _reset(defaults_enabled: bool = True) -> None:
        Settings._settings = None
        Settings._user_data_dir = None
        Settings._resources_dir = None
        Settings._temp_dir = None
        Settings._defaults_enabled = defaults_enabled

    @staticmethod
    def _get_settings() -> dict[str, object]:
        if not Settings._settings:
            Settings._settings = Settings._load_user()
            if not Settings._settings:
                if Settings._defaults_enabled:
                    Settings._settings = Settings._load_defaults()
                else:
                    Settings._settings = {}

        return Settings._settings

    @staticmethod
    def _get_editors() -> dict:
        settings = Settings._get_settings()
        if "editors" not in settings:
            settings["editors"] = {}
        return settings["editors"]

    @staticmethod
    def _get_editor_groups() -> dict:
        editors = Settings._get_editors()
        if "groups" not in editors:
            editors["groups"] = {}
        return editors["groups"]

    @staticmethod
    def _get_language_editors(language: str) -> dict:
        groups = Settings._get_editor_groups()
        if language not in groups:
            groups[language] = {}
        return groups[language]

    @staticmethod
    def _get_os_language_editors(language: str, os: str) -> str | None:
        language_editors = Settings._get_language_editors(language)

        return language_editors.get(os, None)

    @staticmethod
    def _get_aliases() -> dict:
        settings = Settings._get_settings()
        if "aliases" not in settings:
            settings["aliases"] = {}
        return settings["aliases"]

    @staticmethod
    def _get_remote_aliases(remote_name: str) -> dict:
        aliases = Settings._get_aliases()
        if remote_name not in aliases:
            aliases[remote_name] = {}
        return aliases[remote_name]

    @staticmethod
    def _load_defaults() -> dict[str, object]:
        """
        Load packaged defaults.json from inside the wheel.
        Works for installed wheels and editable installs.
        """
        resource = Settings.resources_dir.joinpath("defaults.json")
        return json.loads(resource.read_text(encoding="utf-8"))

    @staticmethod
    def _load_user() -> dict[str, object] | None:
        config_path = Settings.config_path
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)

        return None

    @staticmethod
    def _create_scratch_dir() -> pathlib.Path:
        return pathlib.Path(tempfile.mkdtemp(dir=Settings.temp_dir))

    @staticmethod
    def _dispose_scratch_dir(scratch_dir: pathlib.Path) -> None:
        if scratch_dir.exists():
            shutil.rmtree(scratch_dir)

    # Members

    _settings: dict[str, object] | None = None
    _user_data_dir: pathlib.Path | None = None
    _resources_dir: pathlib.Path | None = None
    _temp_dir: pathlib.Path | None = None
    _defaults_enabled: bool = True
