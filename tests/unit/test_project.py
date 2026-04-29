# test_project.py
from __future__ import annotations

import pathlib
import zipfile

import pytest

from tpl_deploy import error
from tpl_deploy.asset import Asset
from tpl_deploy.project import Project, ProjectItem

VSTEMPLATE = """\
<?xml version="1.0" encoding="utf-8"?>
<VSTemplate Version="3.0.0" Type="Project">
  <TemplateData><Name>Test</Name></TemplateData>
  <TemplateContent>
    <Project File="test.proj" TargetFileName="test.proj">
      <ProjectItem ReplaceParameters="true">main.cpp</ProjectItem>
      <Folder Name="src" TargetFolderName="src">
        <ProjectItem>helper.cpp</ProjectItem>
      </Folder>
    </Project>
  </TemplateContent>
</VSTemplate>
"""


def _make_test_zip(cache: pathlib.Path) -> pathlib.Path:
    zip_path = cache / "tpl-test.abc123.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("template.vstemplate", VSTEMPLATE)
        zf.writestr("test.proj", "<Project/>")
        zf.writestr("main.cpp", "// $param1$")
        zf.writestr("src/helper.cpp", "// helper")
    return zip_path


class TestFindTemplateFile:
    def test_empty_dir_raises(self, tmp_path):
        with pytest.raises(error.TplValueError):
            Project._find_template_file(tmp_path)

    def test_multiple_vstemplates_raises(self, tmp_path):
        (tmp_path / "a.vstemplate").touch()
        (tmp_path / "b.vstemplate").touch()
        with pytest.raises(error.TplValueError):
            Project._find_template_file(tmp_path)

    def test_single_vstemplate_returns_path(self, tmp_path):
        f = tmp_path / "template.vstemplate"
        f.touch()
        assert Project._find_template_file(tmp_path) == f


class TestParseVstemplateItems:
    def _items(self, tmp_path: pathlib.Path) -> list[ProjectItem]:
        f = tmp_path / "template.vstemplate"
        f.write_text(VSTEMPLATE, encoding="utf-8")
        return Project._parse_vstemplate_items(f)

    def test_parses_project_file(self, tmp_path):
        items = self._items(tmp_path)
        assert any(i.source_path == "test.proj" for i in items)

    def test_parses_root_project_item(self, tmp_path):
        items = self._items(tmp_path)
        assert any(i.source_path == "main.cpp" for i in items)

    def test_parses_folder_item_with_path_prefix(self, tmp_path):
        items = self._items(tmp_path)
        assert any(i.source_path == "src/helper.cpp" for i in items)

    def test_replace_parameters_flag(self, tmp_path):
        items = self._items(tmp_path)
        main = next(i for i in items if i.source_path == "main.cpp")
        assert main.replace_parameters is True

    def test_folder_item_no_replace_parameters(self, tmp_path):
        items = self._items(tmp_path)
        helper = next(i for i in items if i.source_path == "src/helper.cpp")
        assert helper.replace_parameters is False


class TestReplaceTokens:
    def test_token_replaced_in_text_file(self, tmp_path):
        src = tmp_path / "src.cpp"
        dst = tmp_path / "dst.cpp"
        src.write_text("Hello $name$!", encoding="utf-8")
        Project._replace_tokens(src, dst, {"name": "World"})
        assert dst.read_text(encoding="utf-8") == "Hello World!"

    def test_multiple_tokens_replaced(self, tmp_path):
        src = tmp_path / "src.cpp"
        dst = tmp_path / "dst.cpp"
        src.write_text("$a$ and $b$", encoding="utf-8")
        Project._replace_tokens(src, dst, {"a": "X", "b": "Y"})
        assert dst.read_text(encoding="utf-8") == "X and Y"

    def test_binary_file_copied_unchanged(self, tmp_path):
        src = tmp_path / "img.bin"
        dst = tmp_path / "img_out.bin"
        src.write_bytes(b"\xff\xfe\x00\x01")
        Project._replace_tokens(src, dst, {"key": "val"})
        assert dst.read_bytes() == b"\xff\xfe\x00\x01"


class TestReplaceRecursively:
    def test_processes_root_files(self, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()
        (src / "file.txt").write_text("$key$", encoding="utf-8")
        Project._replace_recursively(src, dst, {"key": "value"})
        assert (dst / "file.txt").read_text(encoding="utf-8") == "value"

    def test_processes_subdirectory_recursively(self, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        (src / "sub").mkdir(parents=True)
        dst.mkdir()
        (src / "sub" / "file.txt").write_text("$k$", encoding="utf-8")
        Project._replace_recursively(src, dst, {"k": "v"})
        assert (dst / "sub" / "file.txt").read_text(encoding="utf-8") == "v"


class TestMoveToDestination:
    def test_dest_exists_raises(self, tmp_path):
        dst = tmp_path / "dest"
        dst.mkdir()
        with pytest.raises(error.DestinationExistsError):
            Project._move_to_destination(tmp_path, dst, [])

    def test_file_copied_to_dest(self, tmp_path):
        src = tmp_path / "staging"
        dst = tmp_path / "dest"
        src.mkdir()
        (src / "main.cpp").write_text("code", encoding="utf-8")
        Project._move_to_destination(src, dst, [ProjectItem("main.cpp", "main.cpp", False, False)])
        assert (dst / "main.cpp").read_text(encoding="utf-8") == "code"

    def test_target_filename_applied(self, tmp_path):
        src = tmp_path / "staging"
        dst = tmp_path / "dest"
        src.mkdir()
        (src / "template.proj").write_text("<proj/>", encoding="utf-8")
        Project._move_to_destination(
            src, dst, [ProjectItem("template.proj", "myproject.proj", False, False)]
        )
        assert (dst / "myproject.proj").exists()
        assert not (dst / "template.proj").exists()

    def test_nested_target_path_created(self, tmp_path):
        src = tmp_path / "staging"
        dst = tmp_path / "dest"
        (src / "sub").mkdir(parents=True)
        (src / "sub" / "file.cpp").write_text("x", encoding="utf-8")
        Project._move_to_destination(
            src, dst, [ProjectItem("sub/file.cpp", "sub/file.cpp", False, False)]
        )
        assert (dst / "sub" / "file.cpp").exists()


class TestProjectCreate:
    def test_create_deploys_files(self, tmp_path):
        cache = tmp_path / "cache"
        cache.mkdir()
        _make_test_zip(cache)
        asset = Asset("tpl-test", "http://x/tpl-test.zip", cache)
        dest = tmp_path / "output"
        Project.create("myproject", dest, asset, params=["42"])
        assert dest.exists()
        assert (dest / "test.proj").exists()
        assert (dest / "main.cpp").exists()
        assert (dest / "src" / "helper.cpp").exists()

    def test_create_replaces_param_tokens(self, tmp_path):
        cache = tmp_path / "cache"
        cache.mkdir()
        _make_test_zip(cache)
        asset = Asset("tpl-test", "http://x/tpl-test.zip", cache)
        Project.create("myproject", tmp_path / "output", asset, params=["hello"])
        assert (tmp_path / "output" / "main.cpp").read_text(encoding="utf-8") == "// hello"

    def test_create_dest_exists_raises(self, tmp_path):
        cache = tmp_path / "cache"
        cache.mkdir()
        _make_test_zip(cache)
        asset = Asset("tpl-test", "http://x/tpl-test.zip", cache)
        dest = tmp_path / "output"
        dest.mkdir()
        with pytest.raises(error.DestinationExistsError):
            Project.create("myproject", dest, asset, params=None)
