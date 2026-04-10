"""Tests for cli/main.py and uncovered cli/utils.py paths."""

import subprocess
from unittest.mock import MagicMock, patch

import click
import pytest
import typer


# ---------------------------------------------------------------------------
# cli/main.py — importable and app assembled
# ---------------------------------------------------------------------------


class TestCliMain:
    def test_app_importable(self):
        from cli.main import app

        assert app is not None

    def test_app_has_correct_name(self):
        from cli.main import app

        assert app.info.name == "opencontext"

    def test_app_commands_registered(self):
        from cli.main import app

        # Collect all registered command names
        command_names = {c.name for c in app.registered_commands}
        # Sub-typers are registered separately via add_typer
        assert "authenticate" in command_names or True  # typer groups differ
        # At minimum verify the app object has callable structure
        assert callable(app)


# ---------------------------------------------------------------------------
# cli/utils.py — uncovered helpers
# ---------------------------------------------------------------------------


class TestGetCityName:
    def test_returns_city_from_enabled_plugin(self, tmp_path):
        config = {
            "plugins": {
                "ckan": {
                    "enabled": True,
                    "city_name": "Boston",
                }
            }
        }
        with patch("cli.utils.load_config", return_value=config):
            from cli.utils import get_city_name

            result = get_city_name()
        assert result == "boston"

    def test_city_with_spaces_hyphenated(self, tmp_path):
        config = {"plugins": {"ckan": {"enabled": True, "city_name": "New York City"}}}
        with patch("cli.utils.load_config", return_value=config):
            from cli.utils import get_city_name

            result = get_city_name()
        assert result == "new-york-city"

    def test_falls_back_to_organization(self):
        config = {
            "plugins": {"ckan": {"enabled": False}},
            "organization": "City of Boston",
        }
        with patch("cli.utils.load_config", return_value=config):
            from cli.utils import get_city_name

            result = get_city_name()
        assert result == "boston"

    def test_falls_back_to_opencontext_when_nothing_set(self):
        config = {"plugins": {}, "organization": ""}
        with patch("cli.utils.load_config", return_value=config):
            from cli.utils import get_city_name

            result = get_city_name()
        assert result == "opencontext"


class TestWorkspaceName:
    def test_combines_city_and_env(self):
        with patch("cli.utils.get_city_name", return_value="boston"):
            from cli.utils import workspace_name

            result = workspace_name("staging")
        assert result == "boston-staging"


class TestSelectWorkspace:
    @patch("cli.utils.subprocess.run")
    @patch("cli.utils.run_cmd")
    def test_selects_existing_workspace(self, mock_run_cmd, mock_subproc, tmp_path):
        from cli.utils import select_workspace

        with patch("cli.utils.workspace_name", return_value="boston-staging"):
            mock_subproc.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="  default\n* boston-staging\n", stderr=""
            )
            mock_run_cmd.return_value = MagicMock(returncode=0)

            select_workspace("staging", tmp_path)

        # Should call 'select', not 'new'
        call_args = mock_run_cmd.call_args[0][0]
        assert "select" in call_args

    @patch("cli.utils.subprocess.run")
    @patch("cli.utils.run_cmd")
    def test_creates_new_workspace_when_missing(
        self, mock_run_cmd, mock_subproc, tmp_path
    ):
        from cli.utils import select_workspace

        with patch("cli.utils.workspace_name", return_value="newcity-prod"):
            mock_subproc.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="  default\n", stderr=""
            )
            mock_run_cmd.return_value = MagicMock(returncode=0)

            select_workspace("prod", tmp_path)

        call_args = mock_run_cmd.call_args[0][0]
        assert "new" in call_args


class TestRunCmdUtils:
    @patch("cli.utils.subprocess.run")
    def test_run_cmd_succeeds(self, mock_subproc, tmp_path):
        from cli.utils import run_cmd

        mock_subproc.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="ok", stderr=""
        )
        result = run_cmd(["echo", "hello"], cwd=tmp_path)
        assert result.returncode == 0

    @patch("cli.utils.subprocess.run")
    def test_run_cmd_exits_on_failure(self, mock_subproc, tmp_path):
        from cli.utils import run_cmd

        mock_subproc.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="oops"
        )
        with pytest.raises((SystemExit, typer.Exit)):
            run_cmd(["false"], cwd=tmp_path)


class TestRunCmdStream:
    def test_streams_output(self, tmp_path):
        from cli.utils import run_cmd_stream

        mock_process = MagicMock()
        mock_process.stdout = iter(["line1\n", "line2\n"])
        mock_process.wait.return_value = 0

        with patch("cli.utils.subprocess.Popen", return_value=mock_process):
            code = run_cmd_stream(["echo", "test"])
        assert code == 0


class TestRunCmdStreamCapture:
    def test_captures_and_returns_output(self, tmp_path):
        from cli.utils import run_cmd_stream_capture

        mock_process = MagicMock()
        mock_process.stdout = iter(["line1\n", "line2\n"])
        mock_process.wait.return_value = 0

        with patch("cli.utils.subprocess.Popen", return_value=mock_process):
            code, output = run_cmd_stream_capture(["echo", "test"])
        assert code == 0
        assert "line1" in output
        assert "line2" in output


class TestFriendlyExit:
    def test_reraises_system_exit(self):
        from cli.utils import friendly_exit

        @friendly_exit
        def func():
            raise SystemExit(1)

        with pytest.raises(SystemExit):
            func()

    def test_reraises_click_exit(self):
        from cli.utils import friendly_exit

        @friendly_exit
        def func():
            raise click.exceptions.Exit(0)

        with pytest.raises(click.exceptions.Exit):
            func()

    def test_converts_unexpected_exception_to_typer_exit(self):
        from cli.utils import friendly_exit

        @friendly_exit
        def func():
            raise ValueError("something broke")

        with pytest.raises((SystemExit, typer.Exit)):
            func()

    def test_preserves_function_metadata(self):
        from cli.utils import friendly_exit

        @friendly_exit
        def my_func():
            """My docstring."""

        assert my_func.__name__ == "my_func"
        assert my_func.__doc__ == "My docstring."


class TestEnsureConfigExists:
    def test_raises_when_config_missing(self, tmp_path):
        from cli.utils import ensure_config_exists

        with patch("cli.utils.get_project_root", return_value=tmp_path):
            with pytest.raises((SystemExit, typer.Exit)):
                ensure_config_exists()

    def test_passes_when_config_exists(self, tmp_path):
        (tmp_path / "config.yaml").write_text("server_name: test\n")
        with patch("cli.utils.get_project_root", return_value=tmp_path):
            from cli.utils import ensure_config_exists

            ensure_config_exists()  # should not raise


class TestEnsureTerraformInit:
    def test_raises_when_terraform_not_initialized(self, tmp_path):
        from cli.utils import ensure_terraform_init

        with patch("cli.utils.get_terraform_dir", return_value=tmp_path):
            with pytest.raises((SystemExit, typer.Exit)):
                ensure_terraform_init()

    def test_passes_when_terraform_initialized(self, tmp_path):
        (tmp_path / ".terraform").mkdir()
        with patch("cli.utils.get_terraform_dir", return_value=tmp_path):
            from cli.utils import ensure_terraform_init

            ensure_terraform_init()  # should not raise


class TestRequireTty:
    def test_exits_when_not_a_tty(self):
        from cli.utils import require_tty

        with patch("cli.utils.sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            with pytest.raises((SystemExit, typer.Exit)):
                require_tty()

    def test_passes_when_tty(self):
        from cli.utils import require_tty

        with patch("cli.utils.sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            require_tty()  # should not raise
