"""Tests for CLI shared utilities (cli/utils.py)."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import click
import pytest
import yaml


# ---------------------------------------------------------------------------
# get_project_root
# ---------------------------------------------------------------------------


class TestGetProjectRoot:
    def test_finds_project_root(self):
        from cli.utils import get_project_root

        root = get_project_root()
        assert (root / "pyproject.toml").exists()

    def test_returns_path_object(self):
        from cli.utils import get_project_root

        assert isinstance(get_project_root(), Path)


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_loads_valid_config(self, tmp_path):
        config_data = {
            "server_name": "Test MCP",
            "plugins": {"ckan": {"enabled": True, "base_url": "https://example.com"}},
        }
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        with patch("cli.utils.get_project_root", return_value=tmp_path):
            from cli.utils import load_config

            result = load_config()
            assert result["server_name"] == "Test MCP"
            assert result["plugins"]["ckan"]["enabled"] is True

    def test_exits_when_missing(self, tmp_path):
        with patch("cli.utils.get_project_root", return_value=tmp_path):
            from cli.utils import load_config

            with pytest.raises((SystemExit, click.exceptions.Exit)):
                load_config()


# ---------------------------------------------------------------------------
# load_tfvars
# ---------------------------------------------------------------------------


class TestLoadTfvars:
    def test_parses_string_and_numeric_values(self, tmp_path):
        tf_dir = tmp_path / "terraform" / "aws"
        tf_dir.mkdir(parents=True)
        (tf_dir / "staging.tfvars").write_text(
            'lambda_name   = "boston-opendata-mcp-staging"\n'
            'stage_name    = "staging"\n'
            'aws_region    = "us-east-1"\n'
            'config_file   = "config.yaml"\n'
            'custom_domain = "data-mcp.boston.gov"\n'
        )

        with patch("cli.utils.get_terraform_dir", return_value=tf_dir):
            from cli.utils import load_tfvars

            result = load_tfvars("staging")
            assert result["lambda_name"] == "boston-opendata-mcp-staging"
            assert result["stage_name"] == "staging"
            assert result["aws_region"] == "us-east-1"
            assert result["custom_domain"] == "data-mcp.boston.gov"

    def test_skips_comments_and_empty_lines(self, tmp_path):
        tf_dir = tmp_path / "terraform" / "aws"
        tf_dir.mkdir(parents=True)
        (tf_dir / "prod.tfvars").write_text(
            '# This is a comment\n\nlambda_name = "my-func"\n'
        )

        with patch("cli.utils.get_terraform_dir", return_value=tf_dir):
            from cli.utils import load_tfvars

            result = load_tfvars("prod")
            assert result == {"lambda_name": "my-func"}

    def test_exits_when_missing(self, tmp_path):
        tf_dir = tmp_path / "terraform" / "aws"
        tf_dir.mkdir(parents=True)

        with patch("cli.utils.get_terraform_dir", return_value=tf_dir):
            from cli.utils import load_tfvars

            with pytest.raises((SystemExit, click.exceptions.Exit)):
                load_tfvars("staging")

    def test_handles_empty_string_values(self, tmp_path):
        tf_dir = tmp_path / "terraform" / "aws"
        tf_dir.mkdir(parents=True)
        (tf_dir / "staging.tfvars").write_text('custom_domain = ""\n')

        with patch("cli.utils.get_terraform_dir", return_value=tf_dir):
            from cli.utils import load_tfvars

            result = load_tfvars("staging")
            assert result["custom_domain"] == ""


# ---------------------------------------------------------------------------
# workspace_name / get_city_name
# ---------------------------------------------------------------------------


class TestWorkspaceName:
    def test_staging_workspace(self, tmp_path):
        config_data = {
            "organization": "City of Boston",
            "plugins": {"ckan": {"enabled": True, "city_name": "Boston"}},
        }
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        with patch("cli.utils.get_project_root", return_value=tmp_path):
            from cli.utils import workspace_name

            assert workspace_name("staging") == "boston-staging"

    def test_prod_workspace(self, tmp_path):
        config_data = {
            "plugins": {"socrata": {"enabled": True, "city_name": "Chicago"}},
        }
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        with patch("cli.utils.get_project_root", return_value=tmp_path):
            from cli.utils import workspace_name

            assert workspace_name("prod") == "chicago-prod"

    def test_multi_word_city(self, tmp_path):
        config_data = {
            "plugins": {"ckan": {"enabled": True, "city_name": "New York"}},
        }
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        with patch("cli.utils.get_project_root", return_value=tmp_path):
            from cli.utils import workspace_name

            assert workspace_name("staging") == "new-york-staging"

    def test_fallback_to_organization(self, tmp_path):
        config_data = {
            "organization": "City of Denver",
            "plugins": {"ckan": {"enabled": True}},
        }
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        with patch("cli.utils.get_project_root", return_value=tmp_path):
            from cli.utils import workspace_name

            assert workspace_name("prod") == "denver-prod"


# ---------------------------------------------------------------------------
# require_tty
# ---------------------------------------------------------------------------


class TestRequireTty:
    def test_exits_when_not_tty(self):
        from cli.utils import require_tty

        with patch("cli.utils.sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = False
            with pytest.raises((SystemExit, click.exceptions.Exit)):
                require_tty()

    def test_passes_when_tty(self):
        from cli.utils import require_tty

        with patch("cli.utils.sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = True
            require_tty()


# ---------------------------------------------------------------------------
# ensure_config_exists / ensure_terraform_init
# ---------------------------------------------------------------------------


class TestEnsureChecks:
    def test_ensure_config_exists_passes(self, tmp_path):
        (tmp_path / "config.yaml").write_text("server_name: test")

        with patch("cli.utils.get_project_root", return_value=tmp_path):
            from cli.utils import ensure_config_exists

            ensure_config_exists()

    def test_ensure_config_exists_exits_when_missing(self, tmp_path):
        with patch("cli.utils.get_project_root", return_value=tmp_path):
            from cli.utils import ensure_config_exists

            with pytest.raises((SystemExit, click.exceptions.Exit)):
                ensure_config_exists()

    def test_ensure_terraform_init_passes(self, tmp_path):
        tf_dir = tmp_path / "terraform" / "aws"
        tf_dir.mkdir(parents=True)
        (tf_dir / ".terraform").mkdir()

        with patch("cli.utils.get_terraform_dir", return_value=tf_dir):
            from cli.utils import ensure_terraform_init

            ensure_terraform_init()

    def test_ensure_terraform_init_exits_when_missing(self, tmp_path):
        tf_dir = tmp_path / "terraform" / "aws"
        tf_dir.mkdir(parents=True)

        with patch("cli.utils.get_terraform_dir", return_value=tf_dir):
            from cli.utils import ensure_terraform_init

            with pytest.raises((SystemExit, click.exceptions.Exit)):
                ensure_terraform_init()


# ---------------------------------------------------------------------------
# run_cmd
# ---------------------------------------------------------------------------


class TestRunCmd:
    @patch("cli.utils.subprocess.run")
    def test_returns_result_on_success(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["echo", "hi"], returncode=0, stdout="hi\n", stderr=""
        )

        from cli.utils import run_cmd

        result = run_cmd(["echo", "hi"], spinner_msg="Testing")
        assert result.stdout == "hi\n"

    @patch("cli.utils.subprocess.run")
    def test_exits_on_failure(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["bad"], returncode=1, stdout="", stderr="error msg"
        )

        from cli.utils import run_cmd

        with pytest.raises((SystemExit, click.exceptions.Exit)):
            run_cmd(["bad"], spinner_msg="Testing")


# ---------------------------------------------------------------------------
# friendly_exit decorator
# ---------------------------------------------------------------------------


class TestFriendlyExit:
    def test_passes_through_on_success(self):
        from cli.utils import friendly_exit

        @friendly_exit
        def good_func():
            return 42

        assert good_func() == 42

    def test_catches_exceptions(self):
        from cli.utils import friendly_exit

        @friendly_exit
        def bad_func():
            raise ValueError("something broke")

        with pytest.raises((SystemExit, click.exceptions.Exit)):
            bad_func()

    def test_reraises_system_exit(self):
        from cli.utils import friendly_exit

        @friendly_exit
        def exit_func():
            raise SystemExit(0)

        with pytest.raises(SystemExit) as exc_info:
            exit_func()
        assert exc_info.value.code == 0

    def test_preserves_function_metadata(self):
        from cli.utils import friendly_exit

        @friendly_exit
        def my_func():
            """My docstring."""

        assert my_func.__name__ == "my_func"
        assert my_func.__doc__ == "My docstring."
