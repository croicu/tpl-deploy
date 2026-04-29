from contextlib import contextmanager

from .diagnostics import Logger
from .protocols import TelemetryLevel, TelemetryRecord


@contextmanager
def telemetry_session():
    try:
        yield
    finally:
        Logger.flush()
        Logger.clear()


class TplError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.record: TelemetryRecord = Logger.log(TelemetryLevel.WARNING, message)


class TplRuntimeError(TplError): ...


class TplValueError(TplError): ...


class UsageError(TplError): ...


class ValidationError(TplError): ...


class DestinationExistsError(TplError): ...


class RemoteConnectionError(TplError): ...


class ManifestError(TplError): ...


class InstallError(TplError): ...


class UnsupportedRemoteTypeError(TplError): ...


class InvalidConfigurationError(TplError): ...
