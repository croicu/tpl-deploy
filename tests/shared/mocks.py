import inspect
import logging
import os
import pathlib

from tpl_deploy import protocols

_LOG = logging.getLogger("tpl_deploy")

_LEVEL_MAP = {
    protocols.TelemetryLevel.VERBOSE: logging.DEBUG,
    protocols.TelemetryLevel.INFORMATIONAL: logging.INFO,
    protocols.TelemetryLevel.WARNING: logging.WARNING,
    protocols.TelemetryLevel.ERROR: logging.ERROR,
    protocols.TelemetryLevel.CRITICAL: logging.CRITICAL,
}

_IGNORE_FILES = {"mocks.py", "diagnostics.py", "error.py"}


def _caller_stacklevel() -> int:
    for i, frame_info in enumerate(inspect.stack()):
        if i == 0:
            continue  # skip _caller_stacklevel itself
        if os.path.basename(frame_info.filename) not in _IGNORE_FILES:
            return i
    return 1


class MockVsInfoProvider:
    def __init__(self, templates_dir: pathlib.Path, devenv: pathlib.Path):
        self._info = (templates_dir, devenv)

    def get_info(self) -> tuple[pathlib.Path, pathlib.Path]:
        return self._info


class MockLauncher(protocols.LauncherAgent):
    def __init__(self):
        self._dest_dir = None
        self._command = None

    def launch(self, dest_dir: pathlib.Path, command: str) -> None:
        self._dest_dir = dest_dir
        self._command = command

class TestLogger(protocols.LogSink):
    def __init__(self):
        self._pending: list[protocols.TelemetryRecord] = []
        self._records: list[protocols.TelemetryRecord] = []
        self._printed: list[str] = []

    def log(self, level: protocols.TelemetryLevel, message: str) -> protocols.TelemetryRecord:
        from datetime import datetime, timezone
        record = protocols.TelemetryRecord(
            timestamp=datetime.now(timezone.utc),
            level=level,
            message=message,
        )
        self._pending.append(record)
        _LOG.log(_LEVEL_MAP[level], message, stacklevel=_caller_stacklevel())
        return record

    def flush(self) -> None:
        self._records.extend(self._pending)

    def clear(self) -> None:
        self._pending.clear()

    def diagnostic(self, message: str) -> None:
        self.log(protocols.TelemetryLevel.VERBOSE, message)

    def info(self, message: str) -> None:
        self.log(protocols.TelemetryLevel.INFORMATIONAL, message)

    def warning(self, message: str) -> None:
        self.log(protocols.TelemetryLevel.WARNING, message)

    def error(self, message: str) -> None:
        self.log(protocols.TelemetryLevel.ERROR, message)

    def fatal(self, message: str) -> None:
        self.log(protocols.TelemetryLevel.CRITICAL, message)

    def drain(self) -> list[str]:
        messages = [r.message for r in self._pending]
        self._pending.clear()
        return messages

    def print(self, message: str) -> None:
        self._printed.append(message)
