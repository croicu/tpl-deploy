# test_vs_registration.py
from __future__ import annotations

import pathlib

from tests.shared.mocks import MockLauncher, MockVsInfoProvider
from tpl_deploy import vs_registration
from tpl_deploy.launcher import Launcher


def _setup_provider(tmp_path: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    templates_dir = tmp_path / "templates"
    devenv = tmp_path / "devenv.exe"
    vs_registration.set_provider(MockVsInfoProvider(templates_dir, devenv))
    return templates_dir, devenv


def _setup_launcher() -> MockLauncher:
    launcher = MockLauncher()
    Launcher.set_launcher(launcher)
    return launcher


def _make_asset(local_dir: pathlib.Path, asset_name: str) -> pathlib.Path:
    local_dir.mkdir(parents=True, exist_ok=True)
    path = local_dir / f"{asset_name}.abc123.zip"
    path.write_bytes(b"fake")
    return path


class TestRegisterTemplates:
    def test_noop_when_provider_returns_none(self, tmp_path):
        # NullProvider is already installed by setup_test fixture
        local_dir = tmp_path / "remote-a"
        _make_asset(local_dir, "cpp-console")
        launcher = _setup_launcher()

        vs_registration.register_templates("remote-a", local_dir, ["cpp-console"])

        assert launcher._command is None

    def test_copies_zip_to_templates_dir(self, tmp_path):
        templates_dir, _ = _setup_provider(tmp_path)
        local_dir = tmp_path / "remote-a"
        _make_asset(local_dir, "cpp-console")

        vs_registration.register_templates("remote-a", local_dir, ["cpp-console"])

        assert (templates_dir / "remote-a.cpp-console.zip").exists()

    def test_filename_is_remote_dot_asset(self, tmp_path):
        templates_dir, _ = _setup_provider(tmp_path)
        local_dir = tmp_path / "myremote"
        _make_asset(local_dir, "gui-app")

        vs_registration.register_templates("myremote", local_dir, ["gui-app"])

        assert (templates_dir / "myremote.gui-app.zip").exists()

    def test_launches_devenv_install_vs_templates(self, tmp_path):
        _, devenv = _setup_provider(tmp_path)
        local_dir = tmp_path / "remote-a"
        _make_asset(local_dir, "cpp-console")
        launcher = _setup_launcher()

        vs_registration.register_templates("remote-a", local_dir, ["cpp-console"])

        assert launcher._command == f'"{devenv}" /InstallVSTemplates'

    def test_no_devenv_when_no_assets_found(self, tmp_path):
        _setup_provider(tmp_path)
        local_dir = tmp_path / "remote-a"
        local_dir.mkdir()
        launcher = _setup_launcher()

        vs_registration.register_templates("remote-a", local_dir, ["missing-asset"])

        assert launcher._command is None

    def test_warns_for_missing_asset(self, tmp_path, setup_test):
        _setup_provider(tmp_path)
        local_dir = tmp_path / "remote-a"
        local_dir.mkdir()

        vs_registration.register_templates("remote-a", local_dir, ["missing"])

        assert any("missing" in r.message for r in setup_test._pending)

    def test_copies_multiple_assets(self, tmp_path):
        templates_dir, _ = _setup_provider(tmp_path)
        local_dir = tmp_path / "remote-a"
        _make_asset(local_dir, "console")
        _make_asset(local_dir, "gui")

        vs_registration.register_templates("remote-a", local_dir, ["console", "gui"])

        assert (templates_dir / "remote-a.console.zip").exists()
        assert (templates_dir / "remote-a.gui.zip").exists()

    def test_picks_newest_zip_for_asset(self, tmp_path):
        templates_dir, _ = _setup_provider(tmp_path)
        local_dir = tmp_path / "remote-a"
        local_dir.mkdir()
        old = local_dir / "cpp-console.old111.zip"
        new = local_dir / "cpp-console.new222.zip"
        old.write_bytes(b"old")
        new.write_bytes(b"new")
        import time
        time.sleep(0.01)
        new.touch()

        vs_registration.register_templates("remote-a", local_dir, ["cpp-console"])

        dst = templates_dir / "remote-a.cpp-console.zip"
        assert dst.read_bytes() == b"new"


class TestUnregisterTemplates:
    def test_noop_when_provider_returns_none(self, tmp_path):
        # NullProvider installed by fixture
        launcher = _setup_launcher()
        vs_registration.unregister_templates("remote-a")
        assert launcher._command is None

    def test_removes_matching_zips(self, tmp_path):
        templates_dir, _ = _setup_provider(tmp_path)
        templates_dir.mkdir(parents=True)
        (templates_dir / "remote-a.console.zip").write_bytes(b"x")
        (templates_dir / "remote-a.gui.zip").write_bytes(b"x")
        (templates_dir / "other-remote.console.zip").write_bytes(b"x")

        vs_registration.unregister_templates("remote-a")

        assert not (templates_dir / "remote-a.console.zip").exists()
        assert not (templates_dir / "remote-a.gui.zip").exists()
        assert (templates_dir / "other-remote.console.zip").exists()

    def test_launches_devenv_after_removal(self, tmp_path):
        templates_dir, devenv = _setup_provider(tmp_path)
        templates_dir.mkdir(parents=True)
        (templates_dir / "remote-a.console.zip").write_bytes(b"x")
        launcher = _setup_launcher()

        vs_registration.unregister_templates("remote-a")

        assert launcher._command == f'"{devenv}" /InstallVSTemplates'

    def test_no_devenv_when_nothing_to_remove(self, tmp_path):
        templates_dir, _ = _setup_provider(tmp_path)
        templates_dir.mkdir(parents=True)
        launcher = _setup_launcher()

        vs_registration.unregister_templates("remote-a")

        assert launcher._command is None
