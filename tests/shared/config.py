import pathlib

from tests.shared.mocks import MockLauncher
from tpl_deploy.launcher import Launcher
from tpl_deploy.settings import Settings


class TestConfig:
    @classmethod
    def init(cls, test_dir: pathlib.Path, temp_dir: pathlib.Path):
        cls._test_dir = test_dir
        cls._temp_dir = temp_dir

        # Override product directories during tests.
        Settings.user_data_dir = temp_dir
        Settings.temp_dir = temp_dir
        Settings.resources_dir = cls.data_dir()
        Launcher.set_launcher(MockLauncher())

    @classmethod
    def done(cls):
        Launcher.set_launcher(None)

    @classmethod
    def data_dir(cls) -> pathlib.Path:
        return cls._test_dir / "data"

    _test_dir: pathlib.Path
    _temp_dir: pathlib.Path
