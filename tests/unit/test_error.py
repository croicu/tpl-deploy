import pytest

from tpl_deploy import error, protocols


class TestError:
    def test_error_creates_record(self):
        exc = error.TplError("something failed")
        assert exc.record.message == "something failed"
        assert exc.record.level == protocols.TelemetryLevel.WARNING

    def test_record_has_timestamp(self):
        exc = error.TplError("something failed")
        assert exc.record.timestamp is not None

    def test_session_flushes_to_logger(self, setup_test):
        with error.telemetry_session():
            error.TplError("flushed")
        assert len(setup_test._records) == 1
        assert setup_test._records[0].message == "flushed"

    def test_session_clears_pending_after_flush(self, setup_test):
        with error.telemetry_session():
            error.TplError("first")
        with error.telemetry_session():
            error.TplError("second")
        assert len(setup_test._records) == 2

    def test_level_can_be_changed(self, setup_test):
        exc = error.TplError("something failed")
        exc.record.level = protocols.TelemetryLevel.ERROR
        with error.telemetry_session():
            pass
        assert setup_test._records[0].level == protocols.TelemetryLevel.ERROR

    def test_subclass_derives_from_tpl_error(self):
        assert issubclass(error.ValidationError, error.TplError)
        assert issubclass(error.TplRuntimeError, error.TplError)

    def test_session_flushes_on_raised_exception(self, setup_test):
        with pytest.raises(error.ValidationError):
            with error.telemetry_session():
                raise error.ValidationError("invalid input")
        assert len(setup_test._records) == 1
        assert setup_test._records[0].message == "invalid input"
