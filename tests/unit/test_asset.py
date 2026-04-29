# test_asset.py
from __future__ import annotations

import pathlib
import shutil
import time

import pytest

from tests.shared.config import TestConfig
from tests.shared.http_transport import HttpPlayer
from tpl_deploy import error
from tpl_deploy.asset import Asset


class _StubResponse:
    def __init__(self, status_code: int, etag: str = "", content: bytes = b""):
        self._status_code = status_code
        self._etag = etag
        self._content = content

    @property
    def status_code(self):
        return self._status_code

    @property
    def reason(self):
        return "Test"

    @property
    def etag(self):
        return self._etag

    @property
    def content(self):
        return self._content

    def json(self):
        return None

    def raise_for_status(self):
        pass


class _StubTransport:
    def __init__(self, status_code: int, etag: str = "", content: bytes = b""):
        self._response = _StubResponse(status_code, etag, content)

    def get(self, url, request_headers=None, inject_truststore=True):
        return self._response

    def get_if_modified(self, url, etag, request_headers=None, inject_truststore=True):
        return self._response


class TestAssetGet:
    def test_no_files_returns_none(self, tmp_path):
        asset = Asset("foo", "http://x/foo.zip", tmp_path / "cache")
        assert asset.get() is None

    def test_single_file_returns_name(self, tmp_path):
        cache = tmp_path / "cache"
        cache.mkdir()
        (cache / "foo.abc123.zip").touch()
        asset = Asset("foo", "http://x/foo.zip", cache)
        assert asset.get() == "foo.abc123.zip"

    def test_multiple_files_returns_newest_and_deletes_orphans(self, tmp_path):
        cache = tmp_path / "cache"
        cache.mkdir()
        old = cache / "foo.old111.zip"
        new = cache / "foo.new222.zip"
        old.touch()
        time.sleep(0.02)
        new.touch()
        asset = Asset("foo", "http://x/foo.zip", cache)
        assert asset.get() == "foo.new222.zip"
        assert not old.exists()


class TestAssetFetch:
    def test_fetch_creates_versioned_file(self, tmp_path):
        cache = tmp_path / "cache"
        asset = Asset(
            "cpp-console-project",
            "https://example.com/tpl-build/cpp-console-project.zip",
            cache,
        )
        with HttpPlayer("default_register") as player:
            result = asset.fetch(player)
        assert result == "cpp-console-project.69a75434-3ea6.zip"
        assert (cache / result).exists()

    def test_fetch_no_etag_creates_no_tag_file(self, tmp_path):
        cache = tmp_path / "cache"
        asset = Asset("foo", "http://x/foo.zip", cache)
        result = asset.fetch(_StubTransport(200, etag="", content=b"data"))
        assert result == "foo._no_tag_.zip"
        assert (cache / result).exists()

    def test_fetch_replaces_old_file(self, tmp_path):
        cache = tmp_path / "cache"
        cache.mkdir()
        old_file = cache / "cpp-console-project.old-etag.zip"
        old_file.write_bytes(b"old")
        asset = Asset(
            "cpp-console-project",
            "https://example.com/tpl-build/cpp-console-project.zip",
            cache,
        )
        with HttpPlayer("default_register") as player:
            result = asset.fetch(player)
        assert result == "cpp-console-project.69a75434-3ea6.zip"
        assert (cache / result).exists()
        assert not old_file.exists()

    def test_fetch_304_with_existing_returns_current(self, tmp_path):
        cache = tmp_path / "cache"
        cache.mkdir()
        (cache / "foo.abc123.zip").touch()
        asset = Asset("foo", "http://x/foo.zip", cache)
        result = asset.fetch(_StubTransport(304))
        assert result == "foo.abc123.zip"

    def test_fetch_304_without_existing_raises(self, tmp_path):
        cache = tmp_path / "cache"
        asset = Asset("foo", "http://x/foo.zip", cache)
        with pytest.raises(error.TplValueError):
            asset.fetch(_StubTransport(304))

    def test_fetch_error_status_raises(self, tmp_path):
        cache = tmp_path / "cache"
        asset = Asset("foo", "http://x/foo.zip", cache)
        with pytest.raises(error.TplValueError):
            asset.fetch(_StubTransport(404))


class TestAssetExtract:
    def test_extract_not_cached_raises(self, tmp_path):
        cache = tmp_path / "cache"
        cache.mkdir()
        asset = Asset("foo", "http://x/foo.zip", cache)
        with pytest.raises(error.TplValueError):
            asset.extract(tmp_path / "dest")

    def test_extract_valid_zip(self, tmp_path):
        cache = tmp_path / "cache"
        cache.mkdir()
        src = TestConfig.data_dir() / "remote" / "cpp-console-project.69a75434-3ea6.zip"
        shutil.copy(src, cache / "cpp-console-project.69a75434-3ea6.zip")
        asset = Asset("cpp-console-project", "http://x/cpp-console-project.zip", cache)
        dest = tmp_path / "dest"
        dest.mkdir()
        asset.extract(dest)
        assert any(dest.iterdir())


class TestEtagFromName:
    def _asset(self):
        return Asset("x", "http://x", pathlib.Path("."))

    def test_none_returns_none(self):
        assert self._asset()._etag_from_name(None) is None

    def test_short_name_returns_none(self):
        assert self._asset()._etag_from_name("foo.zip") is None

    def test_versioned_name_returns_etag(self):
        assert self._asset()._etag_from_name("foo.abc123.zip") == "abc123"

    def test_no_tag_returns_none(self):
        assert self._asset()._etag_from_name("foo._no_tag_.zip") is None


class TestEtagToName:
    def _asset(self):
        return Asset("x", "http://x", pathlib.Path("."))

    def test_none_returns_no_tag(self):
        assert self._asset()._etag_to_name(None) == "_no_tag_"

    def test_empty_returns_no_tag(self):
        assert self._asset()._etag_to_name("") == "_no_tag_"

    def test_plain_value(self):
        assert self._asset()._etag_to_name("abc123") == "abc123"

    def test_strips_quotes(self):
        assert self._asset()._etag_to_name('"abc123"') == "abc123"

    def test_strips_weak_prefix_and_quotes(self):
        assert self._asset()._etag_to_name('W/"abc123"') == "abc123"

    def test_sanitizes_special_chars(self):
        assert self._asset()._etag_to_name("abc/def:ghi") == "abc_def_ghi"
