from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys
from dataclasses import dataclass
from xml.etree import ElementTree

from . import error
from .asset import Asset
from .settings import Settings


@dataclass
class ProjectItem:
    source_path: str
    target_path: str
    replace_parameters: bool
    open_in_editor: bool

class Project:
    def __init__(self, name: str, path: pathlib.Path, asset: Asset):
        self._name = name
        self._path = path
        self._asset = asset
        self._items: list[ProjectItem] = []

    @property
    def open_file(self) -> pathlib.Path | None:
        for item in self._items:
            if item.open_in_editor:
                return self._path / item.target_path
        return None

    # Public

    @staticmethod
    def create(
            project_name: str,
            dest: pathlib.Path,
            asset: Asset,
            params: list[str] | None
        ) -> Project:

        project = Project(project_name, dest, asset)
        project._create(params)

        return project

               
    # Private
    
    def _create(self, params: list[str] | None) -> None:
        with Settings.scratch_dir() as extract_dir:
            self._asset.extract(extract_dir)

            with Settings.scratch_dir() as staging_dir:
                values: dict[str, str] = {
                    "safeprojectname": self._name,
                    "installpath": self._find_vs_installation_path()
                }

                if params is not None:
                    for i, param in enumerate(params):
                        values[f"param{i+1}"] = param

                Project._replace_recursively(extract_dir, staging_dir, values)

                template_path = Project._find_template_file(staging_dir)
                self._items = Project._parse_vstemplate_items(template_path)

                Project._move_to_destination(staging_dir, self._path, self._items)

    @staticmethod
    def _move_to_destination(
            src: pathlib.Path, 
            dst: pathlib.Path, 
            items: list[ProjectItem]
    ) -> None:
        if dst.exists():
            raise error.DestinationExistsError(f"Destination already exists: {dst}")

        for item in items:
            src_item = src / item.source_path
            dst_item = dst / item.target_path

            dst_item.parent.mkdir(parents=True, exist_ok=True)

            shutil.copy2(src_item, dst_item)

    @staticmethod
    def _find_template_file(template_dir: pathlib.Path) -> pathlib.Path:
        template_dir = pathlib.Path(template_dir)

        files = list(template_dir.glob("*.vstemplate"))

        if not files:
            raise error.TplValueError(f"No .vstemplate file found in: {template_dir}")

        if len(files) > 1:
            names = ", ".join(f.name for f in files)
            raise error.TplValueError(
                f"Multiple .vstemplate files found in {template_dir}: {names}"
            )

        return files[0]
    
    @staticmethod
    def _replace_tokens(src: pathlib.Path, dst: pathlib.Path, values: dict[str, str]) -> None:
        try:
            text = src.read_text(encoding="utf-8-sig")

        except UnicodeDecodeError:
            # binary file → copy unchanged
            shutil.copy2(src, dst)
            return

        for key, value in values.items():
            text = text.replace(f"${key}$", value)

        dst.write_text(text, encoding="utf-8")

    @staticmethod
    def _replace_recursively(
            extract_dir: pathlib.Path, 
            staging_dir: pathlib.Path, 
            values: dict[str, str]
    ) -> None:

        for item in extract_dir.iterdir():
            if item.is_file():
                Project._replace_tokens(item, staging_dir / item.name, values)

            elif item.is_dir():
                child_dir = staging_dir / item.name
                child_dir.mkdir(parents=True, exist_ok=True)

                Project._replace_recursively(item, child_dir, values)

    @staticmethod
    def find_devenv() -> str:
        path = Project._find_vs_installation_path()
        if path:
            return path + "devenv.exe"
        return "devenv"

    @staticmethod
    def _find_vs_installation_path() -> str:
        if sys.platform != "win32":
            return ""
        
        pf86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
        pf86_dir = pathlib.Path(pf86)

        vswhere = pf86_dir / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"

        if not vswhere.exists():
            return ""

        cmd = [
            str(vswhere),
            "-latest",
            "-products", "*",
            "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
            "-property", "installationPath",
        ]

        return subprocess.check_output(cmd, text=True).strip() + "\\Common7\\IDE\\"

    @staticmethod
    def _parse_vstemplate_items(xml_path: pathlib.Path) -> list[ProjectItem]:
        items: list[ProjectItem] = []
        source_folder_stack: list[str] = []
        target_folder_stack: list[str] = []

        for event, elem in ElementTree.iterparse(xml_path, events=("start", "end")):
            tag = elem.tag.split("}")[-1]  # strip namespace if present

            if event == "start":
                if tag == "Project":
                    source_name = elem.attrib.get("File")
                    target_name = elem.attrib.get("TargetFileName")
                    items.append(ProjectItem(
                        source_path=source_name,
                        target_path=target_name,
                        replace_parameters=elem.attrib.get("ReplaceParameters", "") == "true",
                        open_in_editor=elem.attrib.get("OpenInEditor", "") == "true")
                    )

                if tag == "Folder":
                    name = elem.attrib.get("Name")
                    target = elem.attrib.get("TargetFolderName") or elem.attrib.get("Name")
                    source_folder_stack.append(name)
                    target_folder_stack.append(target)

                elif tag == "ProjectItem":
                    source_name = (elem.text or "").strip()
                    target_name = elem.attrib.get("TargetFileName") or source_name

                    items.append(ProjectItem(
                        source_path="/".join([*source_folder_stack, source_name]),
                        target_path="/".join([*target_folder_stack, target_name]),
                        replace_parameters=elem.attrib.get("ReplaceParameters", "") == "true",
                        open_in_editor=elem.attrib.get("OpenInEditor", "") == "true")
                    )

            elif event == "end":
                if tag == "Folder":
                    if source_folder_stack:
                        source_folder_stack.pop()
                    if target_folder_stack:
                        target_folder_stack.pop()
                elem.clear()

        return items