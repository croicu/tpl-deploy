# test_http_remote.py
from __future__ import annotations

import json
from unittest.mock import Mock, patch

import pytest
import requests

from tests.shared.http_transport import HttpPlayer
from tpl_deploy import error
from tpl_deploy.http_remote import HttpRemote, HttpTransport
from tpl_deploy.settings import RemoteInfo


@pytest.fixture(autouse=True)
def reset_truststore():
    HttpTransport._truststore_injected = False
    yield
    HttpTransport._truststore_injected = False


def _make_remote(url: str = "https://example.com/tpl-build/manifest.json") -> HttpRemote:
    return HttpRemote(RemoteInfo(name="test", url=url, inject_truststore=False))


def _mock_requests_response(status_code: int = 200, etag: str = "", content: bytes = b"{}") -> Mock:
    resp = Mock()
    resp.status_code = status_code
    resp.headers = {"ETag": etag} if etag else {}
    resp.content = content
    resp.raise_for_status = Mock()
    return resp


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
        return json.loads(self._content) if self._content else None

    def raise_for_status(self):
        pass


class _StubTransport:
    def __init__(self, status_code: int, etag: str = "", content: bytes = b""):
        self._response = _StubResponse(status_code, etag, content)

    def get(self, url, request_headers=None, inject_truststore=True):
        return self._response

    def get_if_modified(self, url, etag, request_headers=None, inject_truststore=True):
        return self._response


class TestHttpTransportGet:
    def test_success_returns_response(self):
        mock_resp = _mock_requests_response(200, etag='"abc"', content=b"data")
        with patch("tpl_deploy.http_remote.requests.get", return_value=mock_resp):
            resp = HttpTransport().get("http://example.com/foo", inject_truststore=False)
        assert resp.status_code == 200
        assert resp.etag == '"abc"'
        assert resp.content == b"data"

    def test_request_exception_raises_remote_connection_error(self):
        with patch(
            "tpl_deploy.http_remote.requests.get", side_effect=requests.exceptions.ConnectionError()
        ):
            with pytest.raises(error.RemoteConnectionError):
                HttpTransport().get("http://example.com/foo", inject_truststore=False)

    def test_ssl_error_inject_disabled_reraises(self):
        with patch(
            "tpl_deploy.http_remote.requests.get", side_effect=requests.exceptions.SSLError()
        ):
            with pytest.raises(requests.exceptions.SSLError):
                HttpTransport().get("http://example.com/foo", inject_truststore=False)

    def test_ssl_error_already_injected_reraises(self):
        HttpTransport._truststore_injected = True
        with patch(
            "tpl_deploy.http_remote.requests.get", side_effect=requests.exceptions.SSLError()
        ):
            with pytest.raises(requests.exceptions.SSLError):
                HttpTransport().get("http://example.com/foo", inject_truststore=True)


class TestHttpTransportGetIfModified:
    def test_sends_if_none_match_header(self):
        mock_resp = _mock_requests_response()
        with patch("tpl_deploy.http_remote.requests.get", return_value=mock_resp) as mock_get:
            HttpTransport().get_if_modified(
                "http://example.com/foo", "abc123", inject_truststore=False
            )
        headers = mock_get.call_args[1]["headers"]
        assert headers["If-None-Match"] == '"abc123"'

    def test_none_etag_omits_header(self):
        mock_resp = _mock_requests_response()
        with patch("tpl_deploy.http_remote.requests.get", return_value=mock_resp) as mock_get:
            HttpTransport().get_if_modified("http://example.com/foo", None, inject_truststore=False)
        headers = mock_get.call_args[1]["headers"]
        assert "If-None-Match" not in headers


class TestHttpRemoteFetch:
    def test_fetch_loads_manifest_and_assets(self, tmp_path):
        remote = _make_remote()
        with HttpPlayer("default_register"):
            result = remote.fetch()
        assert result is True
        assert remote._manifest is not None
        assert "assets" in remote._manifest

    def test_fetch_writes_asset_files(self, tmp_path):
        remote = _make_remote()
        with HttpPlayer("default_register"):
            remote.fetch()
        zips = list(remote.local_dir.glob("cpp-console-project.*.zip"))
        assert len(zips) == 1

    def test_fetch_non_200_manifest_raises(self):
        remote = _make_remote()
        HttpRemote.set_transport(_StubTransport(404))
        try:
            with pytest.raises(error.TplValueError):
                remote.fetch()
        finally:
            HttpRemote.set_transport(None)


class TestHttpRemoteLoad:
    def test_load_reads_from_cache(self, tmp_path):
        catalog_dir = tmp_path / "catalog" / "test"
        catalog_dir.mkdir(parents=True)
        manifest = {"schema": 1, "assets": ["foo"]}
        (catalog_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

        remote = _make_remote()
        assert remote.load() is True
        assert remote._manifest == manifest

    def test_load_fetches_when_no_cache(self, tmp_path):
        remote = _make_remote()
        with HttpPlayer("default_register"):
            result = remote.load()
        assert result is True
        assert remote._manifest is not None

    def test_load_is_idempotent(self, tmp_path):
        catalog_dir = tmp_path / "catalog" / "test"
        catalog_dir.mkdir(parents=True)
        (catalog_dir / "manifest.json").write_text(
            json.dumps({"schema": 1, "assets": []}), encoding="utf-8"
        )
        remote = _make_remote()
        remote.load()
        remote.load()
        assert remote._loaded is True


class TestHttpRemoteSave:
    def test_save_writes_manifest(self, tmp_path):
        remote = _make_remote()
        remote._manifest = {"schema": 1, "assets": []}
        remote.save()
        manifest_path = tmp_path / "catalog" / "test" / "manifest.json"
        assert manifest_path.exists()
        assert json.loads(manifest_path.read_text(encoding="utf-8")) == {"schema": 1, "assets": []}

    def test_save_no_manifest_is_noop(self, tmp_path):
        remote = _make_remote()
        remote.save()
        assert not (tmp_path / "catalog" / "test" / "manifest.json").exists()


class TestHttpRemoteGetAsset:
    def test_no_manifest_raises(self):
        remote = _make_remote()
        with pytest.raises(error.TplValueError):
            remote.get_asset("foo")

    def test_unknown_asset_raises(self):
        remote = _make_remote()
        remote._manifest = {"assets": ["bar"]}
        with pytest.raises(error.TplValueError):
            remote.get_asset("foo")

    def test_constructs_asset_url(self):
        remote = _make_remote("https://example.com/tpl-build/manifest.json")
        remote._manifest = {"assets": ["cpp-console-project"]}
        asset = remote.get_asset("cpp-console-project")
        assert asset._remote_url == "https://example.com/tpl-build/cpp-console-project.zip"
