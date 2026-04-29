# http_remote.py
from __future__ import annotations

import json
import pathlib
from urllib import parse

import requests

from . import error, protocols
from .asset import Asset
from .helpers import atomic_json_dump
from .settings import Settings


class HttpResponse(protocols.Response):
    def __init__(self, response: requests.Response):
        self._response = response

    @property
    def status_code(self):
        return self._response.status_code

    @property
    def reason(self):
        return self._response.reason

    @property
    def etag(self):
        return self._response.headers.get("ETag", "")

    @property
    def content(self):
        return self._response.content

    def json(self):
        return self._response.json()

    def raise_for_status(self):
        self._response.raise_for_status()


class HttpTransport(protocols.Transport):
    # Public

    def get(
        self,
        request_url: str,
        request_headers: dict | None = None,
        inject_truststore: bool = True,
    ) -> protocols.Response:
        try:
            headers = {"User-Agent": "Mozilla/5.0 (compatible; TPLDeploy/1.0)"}

            if request_headers is not None:
                request_headers = {**headers, **request_headers}
            else:
                request_headers = headers

            resp = HttpResponse(requests.get(f"{request_url}", headers=request_headers, timeout=10))
            resp.raise_for_status()

        except requests.exceptions.SSLError:
            if (inject_truststore is False) or HttpTransport._truststore_injected:
                # Don't retry if truststore injection is disabled or already attempted.
                raise

            # Only retry once, and only after injecting truststore
            HttpTransport._inject_truststore_once()

            return self.get(request_url, request_headers, inject_truststore=False)

        except requests.exceptions.RequestException as e:
            raise error.RemoteConnectionError(
                f"Failed to connect to endpoint {request_url}: {e}"
            ) from e

        return resp

    def get_if_modified(
        self,
        request_url: str,
        etag: str,
        request_headers: dict | None = None,
        inject_truststore: bool = True,
    ) -> protocols.Response:
        if request_headers is None:
            request_headers = {}

        if etag is not None:
            request_headers["If-None-Match"] = f'"{etag}"'

        return self.get(request_url, request_headers, inject_truststore)

    # Private

    @staticmethod
    def _inject_truststore_once():

        if HttpTransport._truststore_injected:
            return

        try:
            import truststore
        except ImportError:
            return

        truststore.inject_into_ssl()
        HttpTransport._truststore_injected = True

    # Private class variables

    _truststore_injected = False


class HttpRemote(protocols.Remote):
    # Public

    def __init__(self, info: protocols.RemoteReference) -> None:
        self._name = info.name
        self._url = info.url
        self._inject_truststore = info.inject_truststore
        self._loaded = False
        self._manifest: dict | None = None

    @staticmethod
    def get_transport():
        return HttpRemote._transport[-1]

    @staticmethod
    def set_transport(transport: protocols.Transport | None):
        if transport is None:
            HttpRemote._transport.pop()
        else:
            HttpRemote._transport.append(transport)

    def fetch(self) -> bool:
        manifest = self._fetch_manifest()
        if manifest is None:
            return False
        self._manifest = manifest

        if not self._fetch_assets():
            return False

        return True

    def load(self) -> bool:
        if not self._loaded:
            if not self._load_manifest():
                if not self.fetch():
                    return False

            if self._manifest is None:
                return False

            self._loaded = True

        return True

    def save(self) -> None:
        if self._manifest is None:
            return

        self._save_manifest()

    def cleanup(self) -> None:
        pass

    def get_asset_names(self) -> list[str]:
        if self._manifest is None:
            return []
        return list(self._manifest.get("assets", []))

    def get_asset(self, asset_name: str) -> Asset:
        if self._manifest is None or "assets" not in self._manifest:
            raise error.TplValueError("Manifest is not loaded or does not contain assets")

        if asset_name not in self._manifest["assets"]:
            raise error.TplValueError(f"Asset '{asset_name}' not found in manifest")

        asset_url = parse.urljoin(self._url, asset_name + ".zip")
        return Asset(asset_name, asset_url, self.local_dir)

    # Public properties

    @property
    def name(self) -> str:
        return self._name

    # Private

    def _fetch_manifest(self) -> dict:
        request_headers = {
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        }

        resp = HttpRemote.get_transport().get(self._url, request_headers, self._inject_truststore)
        if resp.status_code != 200:
            raise error.TplValueError(f"Failed to fetch manifest: {resp.status_code} {resp.reason}")

        return resp.json()

    def _fetch_assets(self) -> bool:
        if (self._manifest is None) or ("assets" not in self._manifest):
            return False

        for asset_name in self._manifest.get("assets"):
            asset_file_name = asset_name + ".zip"
            asset_url = parse.urljoin(self._url, asset_file_name)

            asset = Asset(asset_name, asset_url, self.local_dir)
            asset.fetch(HttpRemote.get_transport(), self._inject_truststore)

        return True

    def _load_manifest(self) -> bool:
        manifest_path = self.local_dir / "manifest.json"
        if not manifest_path.exists():
            return False

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                self._manifest = json.load(f)
        except (json.JSONDecodeError, OSError):
            return False

        return True

    def _save_manifest(self) -> None:
        manifest_path = self.local_dir / "manifest.json"

        self.local_dir.mkdir(parents=True, exist_ok=True)
        atomic_json_dump(manifest_path, self._manifest)

    @property
    def local_dir(self) -> pathlib.Path:
        return Settings.catalog_dir / self._name

    @staticmethod
    def _reset() -> None:
        HttpRemote._transport.clear()
        HttpRemote._transport.append(HttpTransport())

    # Private class variables

    _transport: list[protocols.Transport] = [HttpTransport()]
