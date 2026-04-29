from typing import Any

import pytest

from tests.shared.http_transport import HttpBouncer
from tests.shared.init import SharedFixtures
from tests.shared.mocks import TestLogger
from tests.variables import Variables, init_variables, load_variables
from tpl_deploy import vs_registration
from tpl_deploy.diagnostics import Logger
from tpl_deploy.http_remote import HttpRemote
from tpl_deploy.launcher import Launcher
from tpl_deploy.settings import Settings


@pytest.fixture(autouse=True)
def setup_test():
    Settings._reset(defaults_enabled=False)
    Logger._reset()
    Launcher._reset()
    HttpRemote._reset()
    HttpRemote.set_transport(HttpBouncer("fixture"))
    vs_registration._reset()
    vs_registration.set_provider(vs_registration._NullProvider())

    logger = TestLogger()
    Logger.set_logger(logger)

    yield logger

    Logger._reset()
    Launcher._reset()
    Settings._reset()
    HttpRemote._reset()
    vs_registration._reset()


@pytest.fixture(scope="function", autouse=True)
def suite_run(tmp_path, request):
    SharedFixtures.setup(request.config.rootpath  / "tests", tmp_path)

    yield # run tests
    
    SharedFixtures.teardown()

@pytest.fixture(scope="session")
def _all_test_vars() -> dict[str, Any]:
    return load_variables()

@pytest.fixture(autouse=True)
def variables(request: pytest.FixtureRequest, _all_test_vars: dict[str, Any]) -> Variables:
    _variables = init_variables(request, _all_test_vars)
    if _variables.optional("defaults", False):
        Settings.enable_defaults(True)
        
    return _variables
