"""Tests for CLI destroy command — human consent guardrails."""

from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# destroy — TTY requirement
# ---------------------------------------------------------------------------


class TestDestroyTtyRequirement:
    @patch("cli.commands.destroy.require_tty", side_effect=SystemExit(1))
    def test_destroy_requires_tty(self, mock_tty):
        from cli.commands.destroy import destroy

        with pytest.raises(SystemExit):
            destroy(env="staging")

        mock_tty.assert_called_once()


# ---------------------------------------------------------------------------
# destroy — confirmation mismatch aborts
# ---------------------------------------------------------------------------


class TestDestroyConfirmation:
    @patch("cli.commands.destroy.require_tty")
    @patch("cli.commands.destroy.ensure_config_exists")
    @patch("cli.commands.destroy.ensure_terraform_init")
    @patch("cli.commands.destroy.select_workspace")
    @patch("cli.commands.destroy.workspace_name", return_value="boston-staging")
    @patch("cli.commands.destroy.get_terraform_dir")
    @patch("cli.commands.destroy.questionary")
    def test_wrong_confirmation_aborts(
        self,
        mock_q,
        mock_tf_dir,
        mock_ws,
        mock_select,
        mock_init,
        mock_config,
        mock_tty,
        tmp_path,
    ):
        from cli.commands.destroy import destroy

        tf_dir = tmp_path / "terraform" / "aws"
        tf_dir.mkdir(parents=True)
        (tf_dir / "staging.tfvars").write_text('lambda_name = "test"\n')
        mock_tf_dir.return_value = tf_dir

        # User types "prod" instead of "staging"
        mock_q.text.return_value.ask.return_value = "prod"

        with pytest.raises(SystemExit) as exc_info:
            destroy(env="staging")
        assert exc_info.value.code == 0

    @patch("cli.commands.destroy.require_tty")
    @patch("cli.commands.destroy.ensure_config_exists")
    @patch("cli.commands.destroy.ensure_terraform_init")
    @patch("cli.commands.destroy.select_workspace")
    @patch("cli.commands.destroy.workspace_name", return_value="boston-staging")
    @patch("cli.commands.destroy.get_terraform_dir")
    @patch("cli.commands.destroy.questionary")
    def test_none_confirmation_aborts(
        self,
        mock_q,
        mock_tf_dir,
        mock_ws,
        mock_select,
        mock_init,
        mock_config,
        mock_tty,
        tmp_path,
    ):
        from cli.commands.destroy import destroy

        tf_dir = tmp_path / "terraform" / "aws"
        tf_dir.mkdir(parents=True)
        (tf_dir / "staging.tfvars").write_text('lambda_name = "test"\n')
        mock_tf_dir.return_value = tf_dir

        # User cancels (Ctrl+C)
        mock_q.text.return_value.ask.return_value = None

        with pytest.raises(SystemExit) as exc_info:
            destroy(env="staging")
        assert exc_info.value.code == 0

    @patch("cli.commands.destroy.require_tty")
    @patch("cli.commands.destroy.ensure_config_exists")
    @patch("cli.commands.destroy.ensure_terraform_init")
    @patch("cli.commands.destroy.select_workspace")
    @patch("cli.commands.destroy.workspace_name", return_value="boston-staging")
    @patch("cli.commands.destroy.get_terraform_dir")
    @patch("cli.commands.destroy.questionary")
    @patch("cli.commands.destroy.run_cmd_stream", return_value=0)
    def test_correct_confirmation_proceeds(
        self,
        mock_stream,
        mock_q,
        mock_tf_dir,
        mock_ws,
        mock_select,
        mock_init,
        mock_config,
        mock_tty,
        tmp_path,
    ):
        from cli.commands.destroy import destroy

        tf_dir = tmp_path / "terraform" / "aws"
        tf_dir.mkdir(parents=True)
        (tf_dir / "staging.tfvars").write_text('lambda_name = "test"\n')
        mock_tf_dir.return_value = tf_dir

        mock_q.text.return_value.ask.return_value = "staging"

        destroy(env="staging")

        mock_stream.assert_called_once()
        call_args = mock_stream.call_args[0][0]
        assert "terraform" in call_args
        assert "destroy" in call_args

    @patch("cli.commands.destroy.require_tty")
    @patch("cli.commands.destroy.ensure_config_exists")
    @patch("cli.commands.destroy.ensure_terraform_init")
    @patch("cli.commands.destroy.get_terraform_dir")
    def test_missing_tfvars_exits(
        self, mock_tf_dir, mock_init, mock_config, mock_tty, tmp_path
    ):
        from cli.commands.destroy import destroy

        tf_dir = tmp_path / "terraform" / "aws"
        tf_dir.mkdir(parents=True)
        mock_tf_dir.return_value = tf_dir

        with pytest.raises(SystemExit):
            destroy(env="staging")


# ---------------------------------------------------------------------------
# destroy — no --yes flag exposed
# ---------------------------------------------------------------------------


class TestDestroyNoAutoApprove:
    def test_no_yes_parameter(self):
        """Verify the destroy function signature has no auto-approve parameter."""
        import inspect
        from cli.commands.destroy import destroy

        # Get the wrapped function if decorated
        func = getattr(destroy, "__wrapped__", destroy)
        sig = inspect.signature(func)
        param_names = set(sig.parameters.keys())

        forbidden = {"yes", "auto_approve", "force", "y", "auto"}
        assert param_names & forbidden == set(), (
            f"destroy must not have auto-approve params, found: {param_names & forbidden}"
        )


# ---------------------------------------------------------------------------
# deploy — no --yes flag exposed
# ---------------------------------------------------------------------------


class TestDeployNoAutoApprove:
    def test_no_yes_parameter(self):
        """Verify the deploy function signature has no auto-approve parameter."""
        import inspect
        from cli.commands.deploy import deploy

        func = getattr(deploy, "__wrapped__", deploy)
        sig = inspect.signature(func)
        param_names = set(sig.parameters.keys())

        forbidden = {"yes", "auto_approve", "force", "y", "auto"}
        assert param_names & forbidden == set(), (
            f"deploy must not have auto-approve params, found: {param_names & forbidden}"
        )
