# vs_registration.py
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys

from .diagnostics import Logger
from .launcher import Launcher

_VS_VERSION_MAP: dict[int, str] = {
    16: "Visual Studio 2019",
    17: "Visual Studio 2022",
    18: "Visual Studio 18",
}


def register_templates(remote_name: str, local_dir: pathlib.Path, asset_names: list[str]) -> None:
    info = _providers[-1].get_info()
    if info is None:
        return

    templates_dir, devenv = info
    templates_dir.mkdir(parents=True, exist_ok=True)

    any_copied = False
    for asset_name in asset_names:
        matches = list(local_dir.glob(f"{asset_name}.*.zip"))
        if not matches:
            Logger.warning(f"Asset '{asset_name}' not found locally — skipping VS registration.")
            continue

        matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        src = matches[0]
        dst = templates_dir / f"{remote_name}.{asset_name}.zip"
        shutil.copy2(src, dst)
        any_copied = True

    if any_copied:
        Launcher.launch(pathlib.Path.cwd(), f'"{devenv}" /InstallVSTemplates')


def unregister_templates(remote_name: str) -> None:
    info = _providers[-1].get_info()
    if info is None:
        return

    templates_dir, devenv = info
    Logger.diagnostic(f"VS templates dir: {templates_dir}")

    if not templates_dir.exists():
        Logger.diagnostic("VS templates dir does not exist — nothing to unregister.")
        return

    any_removed = False
    for f in templates_dir.glob(f"{remote_name}.*.zip"):
        Logger.diagnostic(f"Removing VS template: {f.name}")
        f.unlink(missing_ok=True)
        any_removed = True

    if any_removed:
        Launcher.launch(pathlib.Path.cwd(), f'"{devenv}" /InstallVSTemplates')
    else:
        Logger.diagnostic(f"No VS templates found for remote '{remote_name}'.")


def set_provider(provider: object | None) -> None:
    if provider is None:
        if len(_providers) > 1:
            _providers.pop()
    else:
        _providers.append(provider)


def _reset() -> None:
    _providers.clear()
    _providers.append(_SystemProvider())


# Providers

class _SystemProvider:
    def get_info(self) -> tuple[pathlib.Path, pathlib.Path] | None:
        if sys.platform != "win32":
            return None
        return _compute_vs_info()


class _NullProvider:
    def get_info(self) -> tuple[pathlib.Path, pathlib.Path] | None:
        return None


def _compute_vs_info() -> tuple[pathlib.Path, pathlib.Path] | None:
    import os
    pf86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
    vswhere = pathlib.Path(pf86) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"

    if not vswhere.exists():
        return None

    try:
        output = subprocess.check_output(
            [str(vswhere), "-latest", "-products", "*",
             "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
             "-format", "json"],
            text=True,
        )
        data = json.loads(output)
    except Exception:
        return None

    if not data:
        return None

    vs = data[0]
    version_str = vs.get("installationVersion", "")
    install_path = vs.get("installationPath", "")

    if not version_str or not install_path:
        return None

    try:
        major = int(version_str.split(".")[0])
    except (ValueError, IndexError):
        return None

    vs_folder = _VS_VERSION_MAP.get(major)
    if vs_folder is None:
        Logger.warning(
            f"Visual Studio major version {major} is not supported — skipping template registration."
        )
        return None

    documents = _get_documents_folder()
    if documents is None:
        return None

    templates_dir = documents / vs_folder / "Templates" / "ProjectTemplates"
    devenv = pathlib.Path(install_path) / "Common7" / "IDE" / "devenv.exe"
    return templates_dir, devenv


def _get_documents_folder() -> pathlib.Path | None:
    import ctypes
    from ctypes import wintypes
    buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
    if ctypes.windll.shell32.SHGetFolderPathW(0, 5, 0, 0, buf) != 0:
        return None
    path = buf.value
    return pathlib.Path(path) if path else None


_providers: list = [_SystemProvider()]
