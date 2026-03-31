"""Tests for CLI logs command."""

import subprocess
from unittest.mock import patch

import click
import pytest


# ---------------------------------------------------------------------------
# logs — gets log group from terraform output
# ---------------------------------------------------------------------------


class TestLogsCommand:
    @patch("cli.commands.logs.ensure_config_exists")
    @patch("cli.commands.logs.ensure_terraform_init")
    @patch("cli.commands.logs.select_workspace")
    @patch("cli.commands.logs.subprocess.run")
    @patch("cli.commands.logs.run_cmd_stream", return_value=0)
    @patch("cli.commands.logs.get_terraform_dir")
    def test_uses_terraform_output(
        self,
        mock_tf_dir,
        mock_stream,
        mock_run,
        mock_select,
        mock_init,
        mock_config,
        tmp_path,
    ):
        from cli.commands.logs import logs

        mock_tf_dir.return_value = tmp_path
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="/aws/lambda/boston-mcp",
            stderr="",
        )

        logs(env="staging", follow=False)

        mock_stream.assert_called_once()
        cmd = mock_stream.call_args[0][0]
        assert "/aws/lambda/boston-mcp" in cmd
        assert "--follow" not in cmd

    @patch("cli.commands.logs.ensure_config_exists")
    @patch("cli.commands.logs.ensure_terraform_init")
    @patch("cli.commands.logs.select_workspace")
    @patch("cli.commands.logs.subprocess.run")
    @patch("cli.commands.logs.run_cmd_stream", return_value=0)
    @patch("cli.commands.logs.get_terraform_dir")
    def test_follow_flag(
        self,
        mock_tf_dir,
        mock_stream,
        mock_run,
        mock_select,
        mock_init,
        mock_config,
        tmp_path,
    ):
        from cli.commands.logs import logs

        mock_tf_dir.return_value = tmp_path
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="/aws/lambda/boston-mcp",
            stderr="",
        )

        logs(env="staging", follow=True)

        cmd = mock_stream.call_args[0][0]
        assert "--follow" in cmd


# ---------------------------------------------------------------------------
# logs — falls back to tfvars when terraform output fails
# ---------------------------------------------------------------------------


class TestLogsFallback:
    @patch("cli.commands.logs.ensure_config_exists")
    @patch("cli.commands.logs.ensure_terraform_init")
    @patch("cli.commands.logs.select_workspace")
    @patch("cli.commands.logs.subprocess.run")
    @patch("cli.commands.logs.run_cmd_stream", return_value=0)
    @patch("cli.commands.logs.get_terraform_dir")
    @patch("cli.commands.logs.load_tfvars", return_value={"lambda_name": "my-func"})
    def test_constructs_log_group_from_tfvars(
        self,
        mock_tfvars,
        mock_tf_dir,
        mock_stream,
        mock_run,
        mock_select,
        mock_init,
        mock_config,
        tmp_path,
    ):
        from cli.commands.logs import logs

        mock_tf_dir.return_value = tmp_path
        # terraform output fails
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="error"
        )

        logs(env="staging", follow=False)

        cmd = mock_stream.call_args[0][0]
        assert "/aws/lambda/my-func" in cmd

    @patch("cli.commands.logs.ensure_config_exists")
    @patch("cli.commands.logs.ensure_terraform_init")
    @patch("cli.commands.logs.select_workspace")
    @patch("cli.commands.logs.subprocess.run")
    @patch("cli.commands.logs.get_terraform_dir")
    @patch("cli.commands.logs.load_tfvars", return_value={"lambda_name": ""})
    def test_exits_when_no_lambda_name(
        self,
        mock_tfvars,
        mock_tf_dir,
        mock_run,
        mock_select,
        mock_init,
        mock_config,
        tmp_path,
    ):
        from cli.commands.logs import logs

        mock_tf_dir.return_value = tmp_path
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr=""
        )

        with pytest.raises((SystemExit, click.exceptions.Exit)):
            logs(env="staging", follow=False)


# ---------------------------------------------------------------------------
# logs — stream failure
# ---------------------------------------------------------------------------


class TestLogsStreamFailure:
    @patch("cli.commands.logs.ensure_config_exists")
    @patch("cli.commands.logs.ensure_terraform_init")
    @patch("cli.commands.logs.select_workspace")
    @patch("cli.commands.logs.subprocess.run")
    @patch("cli.commands.logs.run_cmd_stream", return_value=1)
    @patch("cli.commands.logs.get_terraform_dir")
    def test_exits_on_stream_failure(
        self,
        mock_tf_dir,
        mock_stream,
        mock_run,
        mock_select,
        mock_init,
        mock_config,
        tmp_path,
    ):
        from cli.commands.logs import logs

        mock_tf_dir.return_value = tmp_path
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="/aws/lambda/test",
            stderr="",
        )

        with pytest.raises((SystemExit, click.exceptions.Exit)):
            logs(env="staging", follow=False)
