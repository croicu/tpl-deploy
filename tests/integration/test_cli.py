from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
from contextlib import nullcontext
from pathlib import Path

import pytest

from tests.shared.http_transport import HttpPlayer, HttpRecorder
from tests.variables import Variables
from tpl_deploy import cli, error


class TestCLI:
    def test_list(self, tmp_path: Path, variables: Variables):
        args: list[str] = ["list"]
        debug = variables.bool("debug")
        
        if debug:
            args.append("--debug")

        # tpl list
        result, stdout, stderr = self.run_tpl(args)

        assert result == variables.int("expected_result"), \
            f"Failed to list remotes. stdout: {stdout},\nstderr:\n{stderr}"

    def test_register(self, tmp_path: Path, variables: Variables):
        args: list[str] = ["register"]
        remote_name = variables.str("remote_name")
        remote_url = variables.str("remote_url")
        recording_file_name = remote_name + "_register"
        debug = variables.bool("debug")
        play = variables.bool("play")
        record = variables.bool("record")

        if debug:
            args.append("--debug")
        args.extend([remote_name, remote_url])

        if record:
            context = HttpRecorder(recording_file_name)
        elif play:
            context = HttpPlayer(recording_file_name)
        else:
            context = nullcontext()
        
        with context:

            # tpl register test http://test.com
            result, stdout, stderr = self.run_tpl(args)

            if record:
                context.save()

        assert result == variables.int("expected_result"), \
            f"Failed to register remote '{remote_name}'." \
            f"\nstdout: {stdout},\nstderr:\n{stderr}"

    
    def test_unregister(self, tmp_path: Path, variables: Variables):
        args: list[str] = ["unregister"]
        remote_name = variables.str("remote_name")
        remote_url = variables.str("remote_url")
        debug = variables.bool("debug")

        if debug:
            args.append("--debug")
        args.append(remote_name)

        with self._register_with_capture(remote_name, remote_url, debug, unregister=False):
            # tpl unregister test
            result, stdout, stderr = self.run_tpl(args)

        assert result == variables.int("expected_result"), \
            f"Failed to unregister remote '{remote_name}'." \
            f"\nstdout: {stdout},\nstderr:\n{stderr}"

    def test_update(self, tmp_path: Path, variables: Variables):
        args: list[str] = ["update"]
        remote_name = variables.str("remote_name")
        remote_url = variables.str("remote_url")
        recording_file_name = remote_name + "_update"
        debug = variables.bool("debug")
        play = variables.bool("play")
        record = variables.bool("record")

        if debug:
            args.append("--debug")
        args.append(remote_name)

        if record:
            context = HttpRecorder(recording_file_name)
        elif play:
            context = HttpPlayer(recording_file_name)
        else:
            context = nullcontext()

        with self._register_with_capture(remote_name, remote_url, debug):
            with context:
                # tpl update test
                result, stdout, stderr = self.run_tpl(args)

                if record:
                    context.save()

        assert result == variables.int("expected_result"), \
            f"Failed to update remote '{remote_name}'." \
            f"\nstdout: {stdout},\nstderr:\n{stderr}"

    def test_unregister_last(self, tmp_path: Path, variables: Variables):
        args: list[str] = ["unregister"]
        remote_name = variables.str("remote_name")
        debug = variables.bool("debug")

        if debug:
            args.append("--debug")
        args.append(remote_name)

        # tpl unregister github
        with pytest.raises(error.InvalidConfigurationError):
            result, stdout, stderr = self.run_tpl(args)

    def test_config_show(self, tmp_path: Path, variables: Variables):
        args: list[str] = ["config", "show"]
        debug = variables.bool("debug")

        if debug:
            args.append("--debug")

        # tpl config show
        result, stdout, stderr = self.run_tpl(args, external=False, temp_path=tmp_path)

        assert result == variables.int("expected_result"), \
            f"Failed to show config values." \
            f"\nstdout: {stdout},\nstderr:\n{stderr}"
        
    def test_config_set_default_editor(self, tmp_path: Path, variables: Variables):
        args: list[str] = ["config", "set-default-editor"]
        command = variables.str("command")
        debug = variables.bool("debug")

        if debug:
            args.append("--debug")
        args.append(command)
        
        # tpl config set-default-editor <command>
        result, stdout, stderr = self.run_tpl(args, external=False, temp_path=tmp_path)

        assert result == variables.int("expected_result"), \
            f"Failed to set default editor to '{command}'."

        self.test_config_show(tmp_path, variables)

    def test_config_set_language_editor(self, tmp_path: Path, variables: Variables):
        args: list[str] = ["config", "set-editor"]
        language = variables.str("language")
        os = variables.str("os")
        command = variables.str("command")
        debug = variables.bool("debug")

        if debug:
            args.append("--debug")
        args.extend([language, os, command])

        # tpl config set-editor <language> <os> <command>
        result, stdout, stderr = self.run_tpl(args, external=False, temp_path=tmp_path)
        assert result == variables.int("expected_result"), \
            f"Failed to set editor for language '{language}' on OS '{os}' to '{command}'."

        self.test_config_show(tmp_path, variables)

    def test_config_remove_editor(self, tmp_path: Path, variables: Variables):
        args: list[str] = ["config", "remove-editor"]
        language = variables.str("language")
        os = variables.str("os")
        debug = variables.bool("debug")

        if debug:
            args.append("--debug")
        args.extend([language, os])

        # tpl config remove-editor <scope> <os>
        result, stdout, stderr = self.run_tpl(args, external=False, temp_path=tmp_path)

        assert result == variables.int("expected_result"), \
            f"Failed to remove editor for language '{language}' on OS '{os}'."

        self.test_config_show(tmp_path, variables)

    def test_config_set_alias(self, tmp_path: Path, variables: Variables):
        args: list[str] = ["config", "set-alias"]
        remote_name = variables.str("remote_name")
        template_name = variables.str("template_name")
        alias = variables.str("alias")
        debug = variables.bool("debug")

        if debug:
            args.append("--debug")
        args.extend([remote_name, template_name, alias])

        # tpl config set-alias <remote> <template_name> <alias>
        result, stdout, stderr = self.run_tpl(args, external=False, temp_path=tmp_path)

        assert result == variables.int("expected_result"), \
            f"Failed to set alias '{alias}' for '{template_name}' on remote '{remote_name}'."

        self.test_config_show(tmp_path, variables)

    def test_config_remove_alias(self, tmp_path: Path, variables: Variables):
        args: list[str] = ["config", "remove-alias"]
        remote_name = variables.str("remote_name")
        alias = variables.str("alias")
        debug = variables.bool("debug")

        if debug:
            args.append("--debug")
        args.extend([remote_name, alias])

        # tpl config remove-alias <remote> <alias>
        result, stdout, stderr = self.run_tpl(args, external=False, temp_path=tmp_path)

        assert result == variables.int("expected_result"), \
            f"Failed to remove alias '{alias}' on remote '{remote_name}'."

        self.test_config_show(tmp_path, variables)

    def test_new(self, tmp_path: Path, variables: Variables):
        args: list[str] = ["new"]
        template_alias = variables.str("template_alias")
        project_name = variables.str("project_name")
        project_path = tmp_path / project_name
        debug = variables.bool("debug")

        if debug:
            args.append("--debug")
        args.extend([template_alias, str(project_path)])

        # tpl new template_alias project_name
        with HttpPlayer("default_register"):
            result, stdout, stderr = self.run_tpl(args)

        assert result == variables.int("expected_result"), \
            f"Failed to create new project '{project_name}' from template '{template_alias}'." \
            f"\nstdout: {stdout},\nstderr:\n{stderr}"

    # Private methods

    @contextlib.contextmanager
    def _register_with_capture(
        self, 
        remote_name: str, 
        remote_url: str, 
        debug: bool, 
        unregister: bool = False
    ):
        args: list[str] = ["register"]
        recording_file_name = remote_name + "_register"

        if debug:
            args.append("--debug")
        args.extend([remote_name, remote_url])

        with HttpPlayer(recording_file_name):
            result, stdout, stderr = self.run_tpl(args)
            assert result == 0, \
                f"Failed to register remote '{remote_name}' for test setup." \
                f"\nstdout: {stdout},\nstderr:\n{stderr}"

        yield

        if unregister:
            unregister_args: list[str] = ["unregister"]
            if debug:
                unregister_args.append("--debug")
            unregister_args.append(remote_name)
            self.run_tpl(unregister_args)

    @staticmethod
    def run_tpl(
        args: list[str], 
        *, 
        external: bool = False, 
        temp_path: Path | None = None
    ) -> tuple[int, str, str]:
        
        if external:
            env = os.environ.copy()
            env["TPL_DEPLOY_USER_DATA_DIR"] = str(temp_path)
            result = subprocess.run(
                [sys.executable, "-m", "tpl_deploy", *args],
                text=True,
                capture_output=True,
                env=env,
            )

            return result.returncode, result.stdout, result.stderr
        else:
            stdout = io.StringIO()
            stderr = io.StringIO()

            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                rc = cli.main(args)

            return rc, stdout.getvalue(), stderr.getvalue()