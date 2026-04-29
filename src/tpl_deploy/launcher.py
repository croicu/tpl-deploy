from __future__ import annotations

import pathlib
import subprocess
import sys

from . import protocols


class DefaultLauncherAgent(protocols.LauncherAgent):
    def launch(self, dest_dir: pathlib.Path, command: str) -> None:
        kwargs = {
            "cwd": str(dest_dir),
            "shell": True,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if sys.platform.startswith("win"):
            # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB
            kwargs["creationflags"] = 0x08000000 | 0x00000200 | 0x01000000
        else:
            kwargs["start_new_session"] = True

        subprocess.Popen(command, **kwargs)


class Launcher:
    # Public

    @staticmethod
    def set_launcher(value: protocols.LauncherAgent | None) -> None:
        if value is None:
            if len(Launcher._sinks) > 1:
                Launcher._sinks.pop()
        else:
            Launcher._sinks.append(value)

    @staticmethod
    def launch(dest_dir: pathlib.Path, command: str) -> None:
        Launcher._sinks[-1].launch(dest_dir, command)

    @staticmethod
    def _reset() -> None:
        Launcher._sinks = [DefaultLauncherAgent()]

    # Members

    _sinks: list[protocols.LauncherAgent] = [DefaultLauncherAgent()]
