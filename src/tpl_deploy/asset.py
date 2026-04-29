from __future__ import annotations

import time
from pathlib import Path
from zipfile import ZipFile

from . import error, protocols


class Asset:
    def __init__(self, name: str, remote_url: str, local_dir: Path):
        self._name = name
        self._remote_url = remote_url
        self._file_name: str | None = None
        self._local_dir: Path = local_dir

    def get(self) -> str | None:
        matches = list(self._local_dir.glob(f"{self._name}.*.zip"))
        if not matches:
            return None

        if len(matches) > 1:
            matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        for orphan in matches[1:]:
            self._retry(lambda: orphan.unlink(missing_ok=True))

        self._file_name = matches[0].name

        return self._file_name

    def fetch(self, transport: protocols.Transport, inject_truststore: bool = True) -> Path | None:

        current_file_name = self.get()
        current_etag = self._etag_from_name(current_file_name)

        response = self._fetch_asset(current_etag, transport, inject_truststore)
        if response.status_code != 200:
            if response.status_code == 304 and current_file_name is not None:
                return current_file_name

            raise error.TplValueError(
                f"Failed to fetch content: {response.status_code} {response.reason}"
            )

        new_file_name = f"{self._name}.{self._etag_to_name(response.etag)}.zip"
        new_file_path = self._local_dir / new_file_name

        self._local_dir.mkdir(parents=True, exist_ok=True)
        with open(new_file_path, "wb") as f:
            f.write(response.content)
        self._file_name = new_file_name

        if current_file_name is not None and current_file_name != new_file_name:
            try:
                current_file_path = self._local_dir / current_file_name
                self._retry(lambda: current_file_path.unlink(missing_ok=True))
            except Exception:
                pass

        return self._file_name

    def extract(self, dest: Path) -> None:
        file_name = self.get()
        if file_name is None:
            raise error.TplValueError(f"Asset '{self._name}' is not available locally")

        asset_file_path = self._local_dir / file_name
        if not asset_file_path.exists():
            raise error.TplValueError(f"Asset file '{asset_file_path}' does not exist")

        with ZipFile(asset_file_path, "r") as zip:
            zip.extractall(dest)

    # Private methods

    def _fetch_asset(
        self, etag: str | None, transport: protocols.Transport, inject_truststore: bool
    ) -> protocols.Response:
        request_headers = {"Accept": "*/*"}

        return transport.get_if_modified(self._remote_url, etag, request_headers, inject_truststore)

    def _retry(self, fn: callable, attempts: int = 3) -> bool:
        for i in range(attempts):
            try:
                fn()
                return True
            except OSError:
                time.sleep(0.05 * (2**i))
            except Exception:
                return False

        return False

    def _etag_from_name(self, name: str | None) -> str | None:
        if not name:
            return None

        # asset.<etag>.name -> split
        parts = name.split(".")
        if len(parts) < 3:
            return None
        if parts[len(parts) - 2] == "_no_tag_":
            return None

        return parts[len(parts) - 2]

    def _etag_to_name(self, etag: str | None) -> str:
        if not etag or etag.strip() == "":
            return "_no_tag_"

        name = etag.strip()
        if name.startswith("W/"):
            name = name[2:]
        name = name.strip('"')

        return "".join((c if c.isalnum() or c in ("-", "_", ".") else "_") for c in name)
