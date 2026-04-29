# test_core.py
from __future__ import annotations

import json

import pytest

from tests.shared.http_transport import HttpPlayer
from tpl_deploy import core
from tpl_deploy.core import _normalize_template_name
from tpl_deploy.error import (
    DestinationExistsError,
    InvalidConfigurationError,
    TplValueError,
    UnsupportedRemoteTypeError,
    ValidationError,
)
from tpl_deploy.settings import Settings

_REMOTE_A = {
    "name": "remote-a",
    "url": "https://example.com/tpl-build/manifest.json",
    "inject_truststore": False,
}
_REMOTE_B = {
    "name": "remote-b",
    "url": "https://other.example.com/tpl/manifest.json",
    "inject_truststore": False,
}


def _write_catalog(*remotes: dict) -> None:
    catalog_dir = Settings.catalog_dir
    catalog_dir.mkdir(parents=True, exist_ok=True)
    (catalog_dir / "catalog.json").write_text(json.dumps(list(remotes)), encoding="utf-8")


def _write_manifest(remote_name: str, manifest: dict) -> None:
    remote_dir = Settings.catalog_dir / remote_name
    remote_dir.mkdir(parents=True, exist_ok=True)
    (remote_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _info_messages(logger) -> list[str]:
    return [r.message for r in logger._pending]


class TestRegisterRemote:
    def test_registers_and_saves_catalog(self):
        _write_catalog(_REMOTE_A)
        with HttpPlayer("test_register"):
            core.register_remote("remote-b", "https://example.com/tpl-build/manifest.json")
        data = json.loads((Settings.catalog_dir / "catalog.json").read_text(encoding="utf-8"))
        assert any(r["name"] == "remote-b" for r in data)

    def test_logs_progress(self, setup_test):
        _write_catalog(_REMOTE_A)
        with HttpPlayer("test_register"):
            core.register_remote("remote-b", "https://example.com/tpl-build/manifest.json")
        assert any("remote-b" in m for m in _info_messages(setup_test))

    def test_reregister_succeeds(self):
        _write_catalog(_REMOTE_A)
        with HttpPlayer("test_register"):
            core.register_remote("remote-a", "https://example.com/tpl-build/manifest.json")
        data = json.loads((Settings.catalog_dir / "catalog.json").read_text(encoding="utf-8"))
        assert sum(1 for r in data if r["name"] == "remote-a") == 1

    def test_register_no_url_updates_existing(self, setup_test):
        _write_catalog(_REMOTE_A)
        _write_manifest("remote-a", {"schema": 1, "assets": []})
        with HttpPlayer("test_update"):
            core.register_remote("remote-a", None)
        assert any("remote-a" in m and "updated" in m for m in _info_messages(setup_test))

    def test_register_no_url_raises_if_not_registered(self):
        _write_catalog(_REMOTE_A)
        with pytest.raises(TplValueError):
            core.register_remote("does-not-exist", None)

    def test_unsupported_scheme_raises(self):
        _write_catalog(_REMOTE_A)
        with pytest.raises(UnsupportedRemoteTypeError):
            core.register_remote("ftp-remote", "ftp://example.com/manifest.json")


class TestUnregisterRemote:
    def test_unregisters_and_saves_catalog(self):
        _write_catalog(_REMOTE_A, _REMOTE_B)
        core.unregister_remote("remote-b")
        data = json.loads((Settings.catalog_dir / "catalog.json").read_text(encoding="utf-8"))
        assert not any(r["name"] == "remote-b" for r in data)

    def test_logs_progress(self, setup_test):
        _write_catalog(_REMOTE_A, _REMOTE_B)
        core.unregister_remote("remote-b")
        assert any("remote-b" in m for m in _info_messages(setup_test))

    def test_unknown_remote_raises(self):
        _write_catalog(_REMOTE_A)
        with pytest.raises(TplValueError):
            core.unregister_remote("does-not-exist")

    def test_last_remote_raises(self):
        _write_catalog(_REMOTE_A)
        with pytest.raises(InvalidConfigurationError):
            core.unregister_remote("remote-a")


class TestListRemotes:
    def test_logs_all_remotes(self, setup_test):
        _write_catalog(_REMOTE_A, _REMOTE_B)
        core.list_remotes()
        messages = _info_messages(setup_test)
        assert any("remote-a" in m for m in messages)
        assert any("remote-b" in m for m in messages)

    def test_logs_header(self, setup_test):
        _write_catalog(_REMOTE_A)
        core.list_remotes()
        assert _info_messages(setup_test)[0] == "Registered remotes:"


class TestUpdateRemote:
    def test_unknown_remote_raises(self):
        _write_catalog(_REMOTE_A)
        with pytest.raises(TplValueError):
            core.update_remote("does-not-exist")

    def test_fetches_and_logs_success(self, setup_test):
        _write_catalog(_REMOTE_A)
        _write_manifest("remote-a", {"schema": 1, "assets": []})
        with HttpPlayer("test_update"):
            core.update_remote("remote-a")
        assert any("remote-a" in m and "updated" in m for m in _info_messages(setup_test))

    def test_saves_catalog_after_update(self):
        _write_catalog(_REMOTE_A)
        _write_manifest("remote-a", {"schema": 1, "assets": []})
        with HttpPlayer("test_update"):
            core.update_remote("remote-a")
        assert (Settings.catalog_dir / "catalog.json").exists()


class TestGetConfig:
    def test_logs_header(self, setup_test):
        _write_catalog(_REMOTE_A)
        core.get_config()
        assert _info_messages(setup_test)[0] == "Effective config:"

    def test_logs_config_entries(self, setup_test):
        _write_catalog(_REMOTE_A)
        Settings._settings = {"foo": "bar"}
        core.get_config()
        assert any("foo" in m and "bar" in m for m in _info_messages(setup_test))


class TestSetDefaultEditor:
    def test_sets_default_editor(self):
        core.set_default_editor("code ${project_dir}")
        assert Settings.get_default_editor() == "code ${project_dir}"

    def test_saves_config(self):
        core.set_default_editor("code ${project_dir}")
        assert Settings.config_path.exists()


class TestSetEditor:
    def test_sets_editor(self):
        core.set_editor("cpp", "windows", "devenv ${project_dir}")
        assert Settings.get_editor("cpp", "windows") == "devenv ${project_dir}"

    def test_saves_config(self):
        core.set_editor("cpp", "windows", "devenv ${project_dir}")
        assert Settings.config_path.exists()

    def test_falls_back_to_default(self):
        core.set_default_editor("code ${project_dir}")
        assert Settings.get_editor("cpp", "linux") == "code ${project_dir}"


class TestRemoveEditor:
    def test_removes_editor(self):
        core.set_editor("cpp", "windows", "devenv ${project_dir}")
        core.remove_editor("cpp", "windows")
        assert Settings.get_editor("cpp", "windows") is None

    def test_saves_config(self):
        core.set_editor("cpp", "windows", "devenv ${project_dir}")
        core.remove_editor("cpp", "windows")
        assert Settings.config_path.exists()


class TestSetAlias:
    def test_sets_alias_and_saves(self):
        _write_catalog(_REMOTE_A)
        core.set_alias("remote-a", "cpp-console-project", "console")
        assert Settings.get_template_by_alias("remote-a", "console") == "cpp-console-project"
        assert Settings.config_path.exists()

    def test_unknown_remote_raises(self):
        _write_catalog(_REMOTE_A)
        with pytest.raises(TplValueError):
            core.set_alias("does-not-exist", "template", "alias")


class TestRemoveAlias:
    def test_removes_alias_and_saves(self):
        _write_catalog(_REMOTE_A)
        Settings.set_alias("remote-a", "console", "cpp-console-project")
        core.remove_alias("remote-a", "console")
        assert Settings.get_template_by_alias("remote-a", "console") is None
        assert Settings.config_path.exists()

    def test_unknown_remote_raises(self):
        _write_catalog(_REMOTE_A)
        with pytest.raises(TplValueError):
            core.remove_alias("does-not-exist", "alias")


class TestNormalizeTemplateName:
    def test_empty_token_raises(self):
        with pytest.raises(TplValueError):
            _normalize_template_name("")

    def test_too_many_colons_raises(self):
        with pytest.raises(TplValueError):
            _normalize_template_name("a:b:c")

    def test_empty_remote_part_raises(self):
        with pytest.raises(TplValueError):
            _normalize_template_name(":name")

    def test_empty_name_part_raises(self):
        with pytest.raises(TplValueError):
            _normalize_template_name("remote:")

    def test_unknown_alias_raises(self):
        _write_catalog(_REMOTE_A)
        with pytest.raises(TplValueError):
            _normalize_template_name("unknown-alias")

    def test_alias_resolves(self):
        _write_catalog(_REMOTE_A)
        Settings.set_alias("remote-a", "console", "cpp-console-project")
        result = _normalize_template_name("console")
        assert result.template_name == "cpp-console-project"
        assert result.remote.name == "remote-a"

    def test_remote_colon_name_resolves(self):
        _write_catalog(_REMOTE_A)
        result = _normalize_template_name("remote-a:cpp-console-project")
        assert result.template_name == "cpp-console-project"
        assert result.remote.name == "remote-a"

    def test_unknown_remote_raises(self):
        _write_catalog(_REMOTE_A)
        with pytest.raises(TplValueError):
            _normalize_template_name("unknown-remote:template")


class TestNewProject:
    def test_destination_exists_raises(self, tmp_path):
        _write_catalog(_REMOTE_A)
        existing = tmp_path / "my_project"
        existing.mkdir()
        with pytest.raises(DestinationExistsError):
            core.new_project("remote-a:cpp-console-project", str(existing), None)

    def test_invalid_project_name_raises(self, tmp_path):
        _write_catalog(_REMOTE_A)
        with pytest.raises(ValidationError):
            core.new_project("remote-a:cpp-console-project", str(tmp_path / "my project"), None)

    def test_unknown_remote_raises(self, tmp_path):
        _write_catalog(_REMOTE_A)
        Settings._settings = {"remotes": [_REMOTE_A]}
        with pytest.raises(TplValueError):
            core.new_project("unknown:template", str(tmp_path / "my_project"), None)
