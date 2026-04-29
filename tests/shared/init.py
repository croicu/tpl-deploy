from __future__ import annotations

import pathlib

from tests.shared.config import TestConfig
from tests.shared.http_transport import HttpBouncer
from tpl_deploy import protocols
from tpl_deploy.http_remote import HttpRemote


class SharedFixtures:
    @staticmethod
    def setup(test_dir: pathlib.Path, temp_dir: pathlib.Path):
        TestConfig.init(test_dir, temp_dir)

        transport: protocols.Transport = HttpBouncer(test_dir)
        HttpRemote.set_transport(transport)

    @staticmethod
    def teardown():
        HttpRemote.set_transport(None)

        TestConfig.done()
