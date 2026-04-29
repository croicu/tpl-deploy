from __future__ import annotations

import pathlib
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .asset import Asset


class TelemetryLevel(Enum):
    VERBOSE = "verbose"
    INFORMATIONAL = "informational"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class TelemetryRecord:
    timestamp: datetime
    level: TelemetryLevel
    message: str


class Response(Protocol):
    @property
    def status_code(self) -> int: ...

    @property
    def reason(self) -> str: ...

    @property
    def etag(self) -> str: ...

    @property
    def content(self) -> bytes: ...

    def json(self) -> dict | None: ...

    def raise_for_status(self) -> None: ...

class Transport(Protocol):
    def get(
        self,
        request_url: str,
        request_headers: dict | None = None,
        inject_truststore: bool = True,
    ) -> Response: ...

    def get_if_modified(
        self,
        request_url: str,
        etag: str,
        request_headers: dict | None = None,
        inject_truststore: bool = True,
    ) -> Response: ...

class RemoteReference(Protocol):
    name: str
    url: str
    inject_truststore: bool

class Remote(Protocol):
    def fetch(self) -> bool: ...
    def load(self) -> bool: ...
    def save(self) -> None: ...
    def cleanup(self) -> None: ...

    def get_asset(self, asset_name: str) -> Asset: ...
    def get_asset_names(self) -> list[str]: ...

    @staticmethod
    def set_transport(transport: Transport) -> None: ...

class Project(Protocol):
    @staticmethod
    def create(
            project_name: str,
            dest: pathlib.Path,
            asset: "Asset",
            params: list[str] | None,
    ) -> "Project": ...

class LauncherAgent(Protocol):
    def launch(self, dest_dir: pathlib.Path, command: str) -> None: ...

class LogSink(Protocol):
    def log(self, level: TelemetryLevel, message: str) -> TelemetryRecord: ...
    def flush(self) -> None: ...
    def clear(self) -> None: ...
    def drain(self) -> list[str]: ...
    def print(self, message: str) -> None: ...
    def diagnostic(self, message: str) -> None: ...
    def info(self, message: str) -> None: ...
    def warning(self, message: str) -> None: ...
    def error(self, message: str) -> None: ...
    def fatal(self, message: str) -> None: ...
