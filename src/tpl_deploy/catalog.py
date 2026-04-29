# catalog.py

import json
import pathlib
import shutil
from dataclasses import asdict, dataclass, fields

from . import protocols, vs_registration
from .diagnostics import Logger
from .error import (
    InvalidConfigurationError,
    TplValueError,
    UnsupportedRemoteTypeError,
)
from .helpers import atomic_json_dump
from .http_remote import HttpRemote
from .launcher import Launcher
from .project import Project
from .settings import RemoteInfo, Settings


@dataclass(frozen=True)
class TemplateInfo:
    template_name: str
    remote: RemoteInfo

class Catalog:
    def __init__(self):
        # Registry of all remotes, loaded or not
        self._registry: list[RemoteInfo] = []
        # In-memory cache of loaded remotes, subset of the registry
        self._remotes: list[protocols.Remote] = []
        self._load_info()
        self._loaded = False

    def save(self) -> None:
        for remote in self._remotes:
            try:
                remote.save()
            except Exception as e:
                Logger.warning(f"Failed to save remote {remote.name}: {e}")
                continue

        catalog_path = Settings.catalog_dir / "catalog.json"
        catalog_path.parent.mkdir(parents=True, exist_ok=True)

        data = [asdict(remote_info) for remote_info in self._registry]
        atomic_json_dump(catalog_path, data)

    def load(self) -> bool:
        if self._loaded:
            return True

        for remote_info in self._registry:
            try:
                remote = Catalog._make_remote(remote_info)
                remote.load()

                self._remotes.append(remote)
            except Exception as e:
                Logger.warning(f"Failed to load remote {remote_info.name}: {e}")
                continue

        self._loaded = True

        return True

    def register_remote(self, remote_info: RemoteInfo, connect: bool = True) -> None:
        if remote_info.type not in ("http", "https"):
            raise UnsupportedRemoteTypeError(f"Unsupported URL scheme: {remote_info.type}")

        existing = self.get_remote_info(remote_info.name)
        if existing is not None:
            self._registry[self._registry.index(existing)] = remote_info
            self._remotes = [r for r in self._remotes if r.name != remote_info.name]
        else:
            self._registry.append(remote_info)

        remote: protocols.Remote = Catalog._make_remote(remote_info)
        if connect:
            remote.fetch()
            remote.save()

            self._remotes.append(remote)
            self.save()
            vs_registration.register_templates(
                remote_info.name,
                Settings.catalog_dir / remote_info.name,
                remote.get_asset_names(),
            )

    def unregister_remote(self, name: str) -> None:
        remote_info = self.get_remote_info(name)
        if remote_info is None:
            return

        if len(self._registry) == 1:
            raise InvalidConfigurationError(
                "Cannot unregister the last remote. At least one remote must be registered.")

        for remote in self._remotes:
            if remote.name == name:
                self._remotes.remove(remote)
                try:
                    remote.cleanup()
                except Exception as e:
                    Logger.warning(f"Failed to cleanup remote {name}: {e}")
                break

        self._registry.remove(remote_info)
        vs_registration.unregister_templates(name)

        try:
            remote_dir = Settings.catalog_dir / name
            shutil.rmtree(remote_dir, ignore_errors=True)

        except Exception:
            pass

    def get_remotes(self) -> list[RemoteInfo]:
        return self._registry

    def get_remote_info(self, name: str) -> RemoteInfo | None:
        for remote_info in self._registry:
            if remote_info.name == name:
                return remote_info
        return None
    

    def get_remote(self, name: str) -> protocols.Remote | None:
        remote_info = self.get_remote_info(name)
        if remote_info is None:
            return None

        for remote in self._remotes:
            if remote.name == name:
                return remote

        try:
            remote = Catalog._make_remote(remote_info)
            remote.load()

            self._remotes.append(remote)
        except Exception as e:
            Logger.warning(f"Failed to load remote {name}: {e}")
            return None

        return remote

    def create_project(
            self, 
            template_info: TemplateInfo, 
            project_name: str,
            dest_dir: pathlib.Path, 
            params: list[str] | None) -> None:
        
        remote: protocols.Remote | None = self.get_remote(template_info.remote.name)
        if remote is None:
            raise TplValueError(f"Remote '{template_info.remote.name}' not found.")
        
        asset = remote.get_asset(template_info.template_name)
        project = Project.create(project_name, dest_dir, asset, params)

        self._launch_editor(template_info.template_name, project_name, dest_dir, project.open_file)
    
    # Private

    def _load_info(self) -> bool:
        if self._registry and len(self._registry) > 0:
            return True

        catalog_path = Settings.catalog_dir / "catalog.json"
        if not catalog_path.exists():
            return self._setup()

        try:
            with open(catalog_path, "r", encoding="utf-8") as f:
                registry = json.load(f)
                if not isinstance(registry, list) or len(registry) == 0:
                    raise InvalidConfigurationError(
                        "Config invalid: remotes must be a non-empty list. "
                        f"Fix {catalog_path} or delete it to re-configure.")

                _known = {f.name for f in fields(RemoteInfo)}
                self._registry = [
                    RemoteInfo(**{k: v for k, v in item.items() if k in _known})
                    for item in registry
                ]

        except (json.JSONDecodeError, OSError) as e:
            raise InvalidConfigurationError(
                f"Config invalid: Fix {catalog_path} or delete it to re-configure.") from e

        return True

    def _setup(self) -> bool:
        for remote_info in (Settings.get_remotes() or []):
            self.register_remote(remote_info, False)

        if not self._registry:
            raise InvalidConfigurationError(
                "No remotes configured. Add a remote with 'tpl remote add'.")

        self._remotes = []
        return True
    
    @staticmethod
    def _make_remote(info: RemoteInfo) -> protocols.Remote:
        if info.type == "http" or info.type == "https":
            return HttpRemote(info)

        raise UnsupportedRemoteTypeError(f"Unsupported remote type: {info.type}")
    

    def _launch_editor(self, template_name: str, project_name: str,
                       dest_dir: pathlib.Path, open_file: pathlib.Path | None = None) -> None:
        language = template_name.split("-")[0]

        os = Settings.get_current_os()
        editor_command = Settings.get_editor(language, os)
        if editor_command is None:
            raise TplValueError(f"No editor configured for language '{language}' and OS '{os}'")

        def _quote(s: str) -> str:
            return f'"{s}"'

        values = {
            "code": "code",
            "devenv": _quote(Project.find_devenv()),
            "project_name": project_name,
            "project_dir": _quote(str(dest_dir)),
            "open_file": _quote(str(open_file)) if open_file else "",
        }
        editor_command = self._replace_tokens(editor_command, values)

        Launcher.launch(dest_dir, editor_command)

    def _replace_tokens(self, text: str, values: dict[str, str]) -> str:
        for key, value in values.items():
            text = text.replace(f"${{{key}}}", value)

        return text
