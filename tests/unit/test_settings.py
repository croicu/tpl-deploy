# test_settings.py
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from tpl_deploy.error import TplValueError
from tpl_deploy.settings import RemoteInfo, Settings


class TestRemoteInfo:
    def test_type_https(self):
        r = RemoteInfo(name="r", url="https://example.com/manifest.json")
        assert r.type == "https"

    def test_type_http(self):
        r = RemoteInfo(name="r", url="http://example.com/manifest.json")
        assert r.type == "http"


class TestGetCurrentOs:
    def test_windows(self):
        with patch("tpl_deploy.settings.sys") as mock_sys:
            mock_sys.platform = "win32"
            assert Settings.get_current_os() == "windows"

    def test_linux(self):
        with patch("tpl_deploy.settings.sys") as mock_sys:
            mock_sys.platform = "linux"
            assert Settings.get_current_os() == "linux"

    def test_macos(self):
        with patch("tpl_deploy.settings.sys") as mock_sys:
            mock_sys.platform = "darwin"
            assert Settings.get_current_os() == "macos"

    def test_unsupported_raises(self):
        with patch("tpl_deploy.settings.sys") as mock_sys:
            mock_sys.platform = "freebsd"
            with pytest.raises(TplValueError):
                Settings.get_current_os()


class TestGetRemotes:
    def test_returns_none_when_not_configured(self):
        assert Settings.get_remotes() is None

    def test_returns_remotes(self):
        Settings._settings = {
            "remotes": [
                {
                    "name": "r",
                    "url": "https://example.com/manifest.json",
                    "inject_truststore": False,
                }
            ]
        }
        remotes = Settings.get_remotes()
        assert remotes is not None
        assert len(remotes) == 1
        assert remotes[0].name == "r"

    def test_returns_multiple_remotes(self):
        Settings._settings = {
            "remotes": [
                {
                    "name": "a",
                    "url": "https://a.example.com/manifest.json",
                    "inject_truststore": False,
                },
                {
                    "name": "b",
                    "url": "https://b.example.com/manifest.json",
                    "inject_truststore": False,
                },
            ]
        }
        assert len(Settings.get_remotes()) == 2


class TestGetRemote:
    def test_found(self):
        Settings._settings = {
            "remotes": [
                {
                    "name": "r",
                    "url": "https://example.com/manifest.json",
                    "inject_truststore": False,
                }
            ]
        }
        remote = Settings.get_remote("r")
        assert remote is not None
        assert remote.name == "r"

    def test_not_found(self):
        Settings._settings = {
            "remotes": [
                {
                    "name": "r",
                    "url": "https://example.com/manifest.json",
                    "inject_truststore": False,
                }
            ]
        }
        assert Settings.get_remote("unknown") is None

    def test_returns_none_when_no_remotes(self):
        assert Settings.get_remote("r") is None


class TestDefaultEditor:
    def test_not_set_returns_none(self):
        assert Settings.get_default_editor() is None

    def test_set_and_get(self):
        Settings.set_default_editor("code ${project_dir}")
        assert Settings.get_default_editor() == "code ${project_dir}"

    def test_overwrite(self):
        Settings.set_default_editor("code ${project_dir}")
        Settings.set_default_editor("vim")
        assert Settings.get_default_editor() == "vim"


class TestGetEditor:
    def test_language_specific_returned(self):
        Settings.set_editor("cpp", "windows", "devenv ${project_dir}")
        assert Settings.get_editor("cpp", "windows") == "devenv ${project_dir}"

    def test_falls_back_to_default(self):
        Settings.set_default_editor("code ${project_dir}")
        assert Settings.get_editor("cpp", "linux") == "code ${project_dir}"

    def test_language_specific_overrides_default(self):
        Settings.set_default_editor("code ${project_dir}")
        Settings.set_editor("cpp", "windows", "devenv ${project_dir}")
        assert Settings.get_editor("cpp", "windows") == "devenv ${project_dir}"

    def test_no_editor_no_default_returns_none(self):
        assert Settings.get_editor("cpp", "windows") is None


class TestRemoveEditor:
    def test_removes_entry(self):
        Settings.set_editor("cpp", "windows", "devenv ${project_dir}")
        Settings.remove_editor("cpp", "windows")
        assert Settings.get_editor("cpp", "windows") is None

    def test_removes_empty_language_group(self):
        Settings.set_editor("cpp", "windows", "devenv ${project_dir}")
        Settings.remove_editor("cpp", "windows")
        assert "cpp" not in Settings._get_editor_groups()

    def test_removes_groups_key_when_empty(self):
        Settings.set_editor("cpp", "windows", "devenv ${project_dir}")
        Settings.remove_editor("cpp", "windows")
        assert "groups" not in Settings._get_editors()

    def test_noop_when_not_set(self):
        Settings.remove_editor("cpp", "windows")
        assert Settings.get_editor("cpp", "windows") is None

    def test_does_not_remove_other_language(self):
        Settings.set_editor("cpp", "windows", "devenv")
        Settings.set_editor("py", "windows", "code")
        Settings.remove_editor("cpp", "windows")
        assert Settings.get_editor("py", "windows") == "code"


class TestSettingsAlias:
    def test_set_alias(self):
        Settings.set_alias("remote-a", "console", "cpp-console-project")
        assert Settings.get_template_by_alias("remote-a", "console") == "cpp-console-project"

    def test_set_alias_adds_to_existing(self):
        Settings.set_alias("remote-a", "a", "x")
        Settings.set_alias("remote-a", "b", "y")
        assert Settings.get_remote_aliases("remote-a") == {"a": "x", "b": "y"}

    def test_remove_alias(self):
        Settings.set_alias("remote-a", "console", "cpp-console-project")
        Settings.remove_alias("remote-a", "console")
        assert Settings.get_template_by_alias("remote-a", "console") is None

    def test_remove_alias_cleans_up_empty_remote(self):
        Settings.set_alias("remote-a", "console", "cpp")
        Settings.remove_alias("remote-a", "console")
        assert "remote-a" not in Settings._get_settings().get("aliases", {})

    def test_remove_alias_cleans_up_aliases_key_when_empty(self):
        Settings.set_alias("remote-a", "console", "cpp")
        Settings.remove_alias("remote-a", "console")
        assert "aliases" not in Settings._get_settings()

    def test_remove_alias_noop_when_not_set(self):
        Settings.remove_alias("remote-a", "console")
        assert Settings.get_template_by_alias("remote-a", "console") is None

    def test_get_template_by_alias_not_found(self):
        assert Settings.get_template_by_alias("remote-a", "unknown") is None

    def test_remove_remote_aliases(self):
        Settings.set_alias("remote-a", "console", "cpp")
        Settings.set_alias("remote-a", "gui", "cpp-gui")
        Settings.remove_remote_aliases("remote-a")
        assert Settings.get_remote_aliases("remote-a") == {}

    def test_remove_remote_aliases_cleans_up_aliases_key(self):
        Settings.set_alias("remote-a", "console", "cpp")
        Settings.remove_remote_aliases("remote-a")
        assert "aliases" not in Settings._get_settings()

    def test_get_remote_aliases_empty_when_none_set(self):
        assert Settings.get_remote_aliases("remote-a") == {}


class TestSave:
    def test_writes_config_json(self):
        Settings.set_default_editor("code ${project_dir}")
        Settings.save()
        assert Settings.config_path.exists()

    def test_round_trips_settings(self):
        Settings.set_default_editor("code ${project_dir}")
        Settings.set_editor("cpp", "windows", "devenv ${project_dir}")
        Settings.save()
        data = json.loads(Settings.config_path.read_text(encoding="utf-8"))
        assert data["editors"]["default"] == "code ${project_dir}"
        assert data["editors"]["groups"]["cpp"]["windows"] == "devenv ${project_dir}"


class TestDirs:
    def test_catalog_dir_under_user_data_dir(self, tmp_path):
        assert Settings.catalog_dir == tmp_path / "catalog"

    def test_config_path_under_user_data_dir(self, tmp_path):
        assert Settings.config_path == tmp_path / "config.json"

    def test_scratch_dir_created_and_cleaned_up(self):
        with Settings.scratch_dir() as d:
            assert d.exists()
        assert not d.exists()

    def test_scratch_dir_is_under_temp_dir(self):
        with Settings.scratch_dir() as d:
            assert d.parent == Settings.temp_dir
