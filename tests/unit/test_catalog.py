# test_catalog.py
from __future__ import annotations

import json

import pytest

from tpl_deploy.catalog import Catalog
from tpl_deploy.error import (
    InvalidConfigurationError,
    UnsupportedRemoteTypeError,
)
from tpl_deploy.settings import RemoteInfo, Settings

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
    (catalog_dir / "catalog.json").write_text(
        json.dumps(list(remotes)), encoding="utf-8"
    )


def _write_manifest(remote_name: str, manifest: dict) -> None:
    remote_dir = Settings.catalog_dir / remote_name
    remote_dir.mkdir(parents=True, exist_ok=True)
    (remote_dir / "manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )


def _simple_catalog() -> Catalog:
    _write_catalog(_REMOTE_A)
    return Catalog()


class TestCatalogInit:
    def test_loads_registry_from_catalog_json(self):
        _write_catalog(_REMOTE_A)
        catalog = Catalog()
        assert len(catalog.get_remotes()) == 1
        assert catalog.get_remotes()[0].name == "remote-a"

    def test_loads_multiple_remotes(self):
        _write_catalog(_REMOTE_A, _REMOTE_B)
        catalog = Catalog()
        assert len(catalog.get_remotes()) == 2

    def test_setup_from_defaults_when_no_catalog(self):
        Settings._settings = {"remotes": [_REMOTE_A]}
        catalog = Catalog()
        assert catalog.get_remote_info("remote-a") is not None

    def test_raises_when_no_remotes_and_no_defaults(self):
        with pytest.raises(InvalidConfigurationError):
            Catalog()

    def test_raises_on_invalid_catalog_json(self):
        catalog_dir = Settings.catalog_dir
        catalog_dir.mkdir(parents=True, exist_ok=True)
        (catalog_dir / "catalog.json").write_text("{not valid json", encoding="utf-8")
        with pytest.raises(InvalidConfigurationError):
            Catalog()

    def test_raises_on_empty_remotes_list(self):
        _write_catalog()
        with pytest.raises(InvalidConfigurationError):
            Catalog()


class TestCatalogLoad:
    def test_load_populates_remotes(self):
        _write_catalog(_REMOTE_A)
        _write_manifest("remote-a", {"schema": 1, "assets": ["foo"]})
        catalog = Catalog()
        assert catalog.load() is True
        assert catalog.get_remote("remote-a") is not None

    def test_load_is_idempotent(self):
        _write_catalog(_REMOTE_A)
        _write_manifest("remote-a", {"schema": 1, "assets": []})
        catalog = Catalog()
        catalog.load()
        result = catalog.load()
        assert result is True

    def test_load_skips_failed_remote(self):
        _write_catalog(_REMOTE_A, _REMOTE_B)
        _write_manifest("remote-a", {"schema": 1, "assets": []})
        # remote-b has no manifest and no transport → load() skips it
        catalog = Catalog()
        catalog.load()
        assert catalog.get_remote("remote-a") is not None
        assert catalog.get_remote("remote-b") is None


class TestCatalogSave:
    def test_save_writes_catalog_json(self):
        _write_catalog(_REMOTE_A)
        catalog = Catalog()
        catalog.save()
        catalog_path = Settings.catalog_dir / "catalog.json"
        assert catalog_path.exists()
        data = json.loads(catalog_path.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert data[0]["name"] == "remote-a"

    def test_save_round_trips_registry(self):
        _write_catalog(_REMOTE_A, _REMOTE_B)
        catalog = Catalog()
        catalog.save()
        data = json.loads(
            (Settings.catalog_dir / "catalog.json").read_text(encoding="utf-8")
        )
        names = [r["name"] for r in data]
        assert "remote-a" in names
        assert "remote-b" in names


class TestCatalogRegisterRemote:
    def test_register_adds_to_registry(self):
        _write_catalog(_REMOTE_A)
        catalog = Catalog()
        new_remote = RemoteInfo(
            name="remote-c",
            url="https://c.example.com/manifest.json",
            inject_truststore=False,
        )
        catalog.register_remote(new_remote, connect=False)
        assert catalog.get_remote_info("remote-c") is not None

    def test_reregister_updates_url(self):
        _write_catalog(_REMOTE_A)
        catalog = Catalog()
        updated = RemoteInfo(
            name="remote-a",
            url="https://new.example.com/manifest.json",
            inject_truststore=False,
        )
        catalog.register_remote(updated, connect=False)
        assert catalog.get_remote_info("remote-a").url == "https://new.example.com/manifest.json"

    def test_reregister_keeps_single_entry(self):
        _write_catalog(_REMOTE_A)
        catalog = Catalog()
        catalog.register_remote(RemoteInfo(**_REMOTE_A), connect=False)
        assert sum(1 for r in catalog.get_remotes() if r.name == "remote-a") == 1

    def test_register_unsupported_scheme_raises(self):
        _write_catalog(_REMOTE_A)
        catalog = Catalog()
        ftp_remote = RemoteInfo(
            name="ftp-remote",
            url="ftp://example.com/manifest.json",
            inject_truststore=False,
        )
        with pytest.raises(UnsupportedRemoteTypeError):
            catalog.register_remote(ftp_remote, connect=False)

    def test_register_connect_false_does_not_fetch(self):
        _write_catalog(_REMOTE_A)
        catalog = Catalog()
        new_remote = RemoteInfo(
            name="remote-c",
            url="https://c.example.com/manifest.json",
            inject_truststore=False,
        )
        catalog.register_remote(new_remote, connect=False)
        # should be in registry but not in loaded remotes
        assert catalog.get_remote_info("remote-c") is not None
        assert not any(r.name == "remote-c" for r in catalog._remotes)


class TestCatalogUnregisterRemote:
    def test_unregister_unknown_is_noop(self):
        _write_catalog(_REMOTE_A)
        catalog = Catalog()
        catalog.unregister_remote("does-not-exist")
        assert len(catalog.get_remotes()) == 1

    def test_unregister_last_raises(self):
        _write_catalog(_REMOTE_A)
        catalog = Catalog()
        with pytest.raises(InvalidConfigurationError):
            catalog.unregister_remote("remote-a")

    def test_unregister_removes_from_registry(self):
        _write_catalog(_REMOTE_A, _REMOTE_B)
        catalog = Catalog()
        catalog.unregister_remote("remote-b")
        assert catalog.get_remote_info("remote-b") is None
        assert catalog.get_remote_info("remote-a") is not None


class TestCatalogGetRemoteInfo:
    def test_found_returns_remote_info(self):
        _write_catalog(_REMOTE_A)
        catalog = Catalog()
        info = catalog.get_remote_info("remote-a")
        assert info is not None
        assert info.name == "remote-a"

    def test_not_found_returns_none(self):
        catalog = _simple_catalog()
        assert catalog.get_remote_info("unknown") is None


