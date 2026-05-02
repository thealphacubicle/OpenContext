"""Tests for CLI deploy command — validation, packaging, plan parsing."""

from unittest.mock import MagicMock, patch
from zipfile import ZipFile

import click
import pytest


# ---------------------------------------------------------------------------
# _validate_single_plugin
# ---------------------------------------------------------------------------


class TestValidateSinglePlugin:
    def test_one_plugin_enabled(self):
        from cli.commands.deploy import _validate_single_plugin

        config = {
            "plugins": {"ckan": {"enabled": True, "base_url": "https://data.gov"}}
        }
        assert _validate_single_plugin(config) == "ckan"

    def test_no_plugins_exits(self):
        from cli.commands.deploy import _validate_single_plugin

        config = {"plugins": {"ckan": {"enabled": False}}}
        with pytest.raises((SystemExit, click.exceptions.Exit)):
            _validate_single_plugin(config)

    def test_empty_plugins_exits(self):
        from cli.commands.deploy import _validate_single_plugin

        config = {"plugins": {}}
        with pytest.raises((SystemExit, click.exceptions.Exit)):
            _validate_single_plugin(config)

    def test_multiple_plugins_exits(self):
        from cli.commands.deploy import _validate_single_plugin

        config = {
            "plugins": {
                "ckan": {"enabled": True},
                "socrata": {"enabled": True},
            }
        }
        with pytest.raises((SystemExit, click.exceptions.Exit)):
            _validate_single_plugin(config)

    def test_non_dict_plugin_ignored(self):
        from cli.commands.deploy import _validate_single_plugin

        config = {
            "plugins": {
                "ckan": {"enabled": True},
                "some_string": "not a dict",
            }
        }
        assert _validate_single_plugin(config) == "ckan"

    def test_missing_plugins_key_exits(self):
        from cli.commands.deploy import _validate_single_plugin

        with pytest.raises((SystemExit, click.exceptions.Exit)):
            _validate_single_plugin({})


# ---------------------------------------------------------------------------
# _parse_plan_summary
# ---------------------------------------------------------------------------


class TestParsePlanSummary:
    def test_parses_standard_output(self):
        from cli.commands.deploy import _parse_plan_summary

        output = "Plan: 5 to add, 2 to change, 1 to destroy.\nSome other text here."
        assert _parse_plan_summary(output) == (5, 2, 1)

    def test_zeros(self):
        from cli.commands.deploy import _parse_plan_summary

        output = "Plan: 0 to add, 0 to change, 0 to destroy."
        assert _parse_plan_summary(output) == (0, 0, 0)

    def test_no_match_returns_zeros(self):
        from cli.commands.deploy import _parse_plan_summary

        assert _parse_plan_summary("No changes. Infrastructure is up-to-date.") == (
            0,
            0,
            0,
        )

    def test_large_numbers(self):
        from cli.commands.deploy import _parse_plan_summary

        output = "Plan: 100 to add, 50 to change, 25 to destroy."
        assert _parse_plan_summary(output) == (100, 50, 25)


# ---------------------------------------------------------------------------
# _package_lambda
# ---------------------------------------------------------------------------


class TestPackageLambda:
    @patch("cli.commands.deploy.run_cmd")
    def test_creates_zip(self, mock_run_cmd, tmp_path):
        from cli.commands.deploy import _package_lambda

        # Set up minimal project structure
        (tmp_path / "requirements.txt").write_text("httpx>=0.27.0\n")
        (tmp_path / "core").mkdir()
        (tmp_path / "core" / "__init__.py").write_text("")
        (tmp_path / "core" / "interfaces.py").write_text("class Plugin: pass")
        (tmp_path / "plugins").mkdir()
        (tmp_path / "plugins" / "__init__.py").write_text("")
        (tmp_path / "server").mkdir()
        (tmp_path / "server" / "__init__.py").write_text("")

        mock_run_cmd.return_value = MagicMock(returncode=0)

        zip_path = _package_lambda(tmp_path)

        assert zip_path.exists()
        assert zip_path.name == "lambda-deployment.zip"

        with ZipFile(zip_path) as zf:
            names = zf.namelist()
            assert "core/__init__.py" in names
            assert "core/interfaces.py" in names
            assert "plugins/__init__.py" in names
            assert "server/__init__.py" in names

    @patch("cli.commands.deploy.run_cmd")
    def test_creates_custom_plugins_if_missing(self, mock_run_cmd, tmp_path):
        from cli.commands.deploy import _package_lambda

        (tmp_path / "requirements.txt").write_text("")
        (tmp_path / "core").mkdir()
        (tmp_path / "core" / "__init__.py").write_text("")
        (tmp_path / "plugins").mkdir()
        (tmp_path / "plugins" / "__init__.py").write_text("")
        (tmp_path / "server").mkdir()
        (tmp_path / "server" / "__init__.py").write_text("")

        mock_run_cmd.return_value = MagicMock(returncode=0)
        _package_lambda(tmp_path)

        assert (tmp_path / ".deploy" / "custom_plugins").exists()

    @patch("cli.commands.deploy.run_cmd")
    def test_cleans_up_old_deploy_dir(self, mock_run_cmd, tmp_path):
        from cli.commands.deploy import _package_lambda

        old_deploy = tmp_path / ".deploy"
        old_deploy.mkdir()
        (old_deploy / "stale_file.txt").write_text("old stuff")

        (tmp_path / "requirements.txt").write_text("")
        (tmp_path / "core").mkdir()
        (tmp_path / "core" / "__init__.py").write_text("")
        (tmp_path / "plugins").mkdir()
        (tmp_path / "plugins" / "__init__.py").write_text("")
        (tmp_path / "server").mkdir()
        (tmp_path / "server" / "__init__.py").write_text("")

        mock_run_cmd.return_value = MagicMock(returncode=0)
        _package_lambda(tmp_path)

        assert not (tmp_path / ".deploy" / "stale_file.txt").exists()

    @patch("cli.commands.deploy.run_cmd")
    def test_calls_uv_pip_install(self, mock_run_cmd, tmp_path):
        from cli.commands.deploy import _package_lambda

        (tmp_path / "requirements.txt").write_text("httpx>=0.27.0\n")
        for d in ["core", "plugins", "server"]:
            (tmp_path / d).mkdir()
            (tmp_path / d / "__init__.py").write_text("")

        mock_run_cmd.return_value = MagicMock(returncode=0)
        _package_lambda(tmp_path)

        mock_run_cmd.assert_called_once()
        call_args = mock_run_cmd.call_args[0][0]
        assert "uv" in call_args
        assert "pip" in call_args
        assert "install" in call_args
        assert "--python-platform" in call_args


# ---------------------------------------------------------------------------
# deploy — TTY requirement
# ---------------------------------------------------------------------------


class TestDeployTtyRequirement:
    @patch("cli.commands.deploy.require_tty", side_effect=SystemExit(1))
    def test_deploy_requires_tty(self, mock_tty):
        from cli.commands.deploy import deploy

        with pytest.raises((SystemExit, click.exceptions.Exit)):
            deploy(env="staging")

        mock_tty.assert_called_once()
