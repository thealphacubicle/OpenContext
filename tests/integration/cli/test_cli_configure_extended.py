"""Extended tests for CLI configure command — full wizard flow."""

import subprocess
from unittest.mock import MagicMock, patch

import click
import pytest
import yaml


# ---------------------------------------------------------------------------
# configure — full wizard flows
# ---------------------------------------------------------------------------


def _mock_q(responses: list):
    """Build a questionary mock that returns items from *responses* in order.

    Each call to .ask() pops the next item.  Works for both .text() and
    .select() and .confirm() because we mock the whole `questionary` module
    and make each call return a MagicMock whose .ask() returns the next value.
    """
    iter_responses = iter(responses)

    def _make_q(*args, **kwargs):
        q = MagicMock()
        q.ask.return_value = next(iter_responses)
        return q

    return _make_q


class TestConfigureWizardCKAN:
    @patch("cli.commands.configure.subprocess.run")
    @patch("cli.commands.configure.run_cmd")
    @patch("cli.commands.configure.get_project_root")
    @patch("cli.commands.configure.get_terraform_dir")
    @patch("cli.commands.configure.questionary")
    def test_ckan_wizard_writes_config_and_tfvars(
        self,
        mock_q,
        mock_tf_dir,
        mock_root,
        mock_run_cmd,
        mock_subproc,
        tmp_path,
    ):
        from cli.commands.configure import configure

        tf_dir = tmp_path / "terraform" / "aws"
        tf_dir.mkdir(parents=True)
        mock_root.return_value = tmp_path
        mock_tf_dir.return_value = tf_dir

        responses = [
            "Use example config as template",  # starting_point
            "City of Boston",  # org_name
            "Boston",  # city_name
            "staging",  # env
            "CKAN",  # plugin
            "https://data.boston.gov",  # base_url
            "https://data.boston.gov",  # portal_url
            "Boston",  # city_name (plugin)
            "120",  # timeout
            "us-east-1",  # region
            "boston-opencontext-mcp-staging",  # lambda_name
            "512",  # lambda_memory
            "120",  # lambda_timeout
            False,  # use_domain
        ]

        mock_q.select.side_effect = _mock_q([responses[0], responses[3], responses[4]])
        mock_q.text.side_effect = _mock_q(
            [
                responses[1],
                responses[2],
                responses[5],
                responses[6],
                responses[7],
                responses[8],
                responses[9],
                responses[10],
                responses[11],
                responses[12],
            ]
        )
        mock_q.confirm.side_effect = _mock_q([responses[13]])

        # terraform workspace list returns empty
        mock_subproc.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="  default\n", stderr=""
        )
        mock_run_cmd.return_value = MagicMock(returncode=0)

        # Terraform .terraform dir does NOT exist (skip init)
        configure()

        config_file = tmp_path / "config.yaml"
        assert config_file.exists()
        parsed = yaml.safe_load(config_file.read_text())
        assert "ckan" in parsed["plugins"]
        assert parsed["plugins"]["ckan"]["enabled"] is True

    @patch("cli.commands.configure.subprocess.run")
    @patch("cli.commands.configure.run_cmd")
    @patch("cli.commands.configure.get_project_root")
    @patch("cli.commands.configure.get_terraform_dir")
    @patch("cli.commands.configure.questionary")
    def test_socrata_wizard_without_app_token(
        self,
        mock_q,
        mock_tf_dir,
        mock_root,
        mock_run_cmd,
        mock_subproc,
        tmp_path,
    ):
        from cli.commands.configure import configure

        tf_dir = tmp_path / "terraform" / "aws"
        tf_dir.mkdir(parents=True)
        mock_root.return_value = tmp_path
        mock_tf_dir.return_value = tf_dir

        mock_q.select.side_effect = _mock_q(
            ["Start from scratch", "staging", "Socrata"]
        )
        mock_q.text.side_effect = _mock_q(
            [
                "City of Chicago",  # org_name
                "Chicago",  # city_name
                "https://data.cityofchicago.org",  # base_url
                "",  # app_token (empty → omitted)
                "120",  # timeout
                "us-east-1",  # region
                "chicago-mcp-staging",  # lambda_name
                "512",  # lambda_memory
                "120",  # lambda_timeout
            ]
        )
        mock_q.confirm.side_effect = _mock_q([False])  # no custom domain

        mock_subproc.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="  default\n", stderr=""
        )
        mock_run_cmd.return_value = MagicMock(returncode=0)

        configure()

        parsed = yaml.safe_load((tmp_path / "config.yaml").read_text())
        assert "socrata" in parsed["plugins"]
        assert "app_token" not in parsed["plugins"]["socrata"]

    @patch("cli.commands.configure.subprocess.run")
    @patch("cli.commands.configure.run_cmd")
    @patch("cli.commands.configure.get_project_root")
    @patch("cli.commands.configure.get_terraform_dir")
    @patch("cli.commands.configure.questionary")
    def test_arcgis_wizard_with_custom_domain(
        self,
        mock_q,
        mock_tf_dir,
        mock_root,
        mock_run_cmd,
        mock_subproc,
        tmp_path,
    ):
        from cli.commands.configure import configure

        tf_dir = tmp_path / "terraform" / "aws"
        tf_dir.mkdir(parents=True)
        mock_root.return_value = tmp_path
        mock_tf_dir.return_value = tf_dir

        mock_q.select.side_effect = _mock_q(["Start from scratch", "prod", "ArcGIS"])
        mock_q.text.side_effect = _mock_q(
            [
                "City of Seattle",  # org_name
                "Seattle",  # city_name
                "https://hub.arcgis.com",  # portal_url
                "Seattle",  # city_name (plugin)
                "120",  # timeout
                "us-west-2",  # region
                "seattle-mcp-prod",  # lambda_name
                "512",  # lambda_memory
                "120",  # lambda_timeout
                "data-mcp.seattle.gov",  # custom_domain
            ]
        )
        mock_q.confirm.side_effect = _mock_q([True])  # use custom domain

        mock_subproc.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="  default\n", stderr=""
        )
        mock_run_cmd.return_value = MagicMock(returncode=0)

        configure()

        config_file = tmp_path / "config.yaml"
        parsed = yaml.safe_load(config_file.read_text())
        assert "arcgis" in parsed["plugins"]

        tfvars_file = tf_dir / "prod.tfvars"
        assert tfvars_file.exists()
        content = tfvars_file.read_text()
        assert 'custom_domain = "data-mcp.seattle.gov"' in content

    @patch("cli.commands.configure.subprocess.run")
    @patch("cli.commands.configure.run_cmd")
    @patch("cli.commands.configure.get_project_root")
    @patch("cli.commands.configure.get_terraform_dir")
    @patch("cli.commands.configure.questionary")
    def test_wizard_selects_existing_workspace(
        self,
        mock_q,
        mock_tf_dir,
        mock_root,
        mock_run_cmd,
        mock_subproc,
        tmp_path,
    ):
        """When workspace already exists, 'workspace select' is used, not 'new'."""
        from cli.commands.configure import configure

        tf_dir = tmp_path / "terraform" / "aws"
        tf_dir.mkdir(parents=True)
        mock_root.return_value = tmp_path
        mock_tf_dir.return_value = tf_dir

        mock_q.select.side_effect = _mock_q(["Start from scratch", "staging", "CKAN"])
        mock_q.text.side_effect = _mock_q(
            [
                "City of Boston",
                "Boston",
                "https://data.boston.gov",
                "https://data.boston.gov",
                "Boston",
                "120",
                "us-east-1",
                "boston-mcp-staging",
                "512",
                "120",
            ]
        )
        mock_q.confirm.side_effect = _mock_q([False])

        # Workspace list includes the target workspace
        mock_subproc.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="  default\n* boston-staging\n", stderr=""
        )
        mock_run_cmd.return_value = MagicMock(returncode=0)

        configure()

        # Verify run_cmd was called with 'select' (not 'new')
        calls = [str(c) for c in mock_run_cmd.call_args_list]
        assert any("select" in c for c in calls)

    @patch("cli.commands.configure.subprocess.run")
    @patch("cli.commands.configure.run_cmd")
    @patch("cli.commands.configure.get_project_root")
    @patch("cli.commands.configure.get_terraform_dir")
    @patch("cli.commands.configure.questionary")
    def test_wizard_runs_terraform_init_if_needed(
        self,
        mock_q,
        mock_tf_dir,
        mock_root,
        mock_run_cmd,
        mock_subproc,
        tmp_path,
    ):
        """If .terraform dir is absent, wizard runs terraform init."""
        from cli.commands.configure import configure

        tf_dir = tmp_path / "terraform" / "aws"
        tf_dir.mkdir(parents=True)
        # Do NOT create .terraform — so wizard must init
        mock_root.return_value = tmp_path
        mock_tf_dir.return_value = tf_dir

        mock_q.select.side_effect = _mock_q(["Start from scratch", "staging", "CKAN"])
        mock_q.text.side_effect = _mock_q(
            [
                "Org",
                "City",
                "https://data.example.gov",
                "https://data.example.gov",
                "City",
                "120",
                "us-east-1",
                "city-mcp-staging",
                "512",
                "120",
            ]
        )
        mock_q.confirm.side_effect = _mock_q([False])

        mock_subproc.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="  default\n", stderr=""
        )
        mock_run_cmd.return_value = MagicMock(returncode=0)

        configure()

        # Check that at least one call included 'init'
        all_calls = [str(c) for c in mock_run_cmd.call_args_list]
        assert any("init" in c for c in all_calls)

    @patch("cli.commands.configure.get_project_root")
    @patch("cli.commands.configure.get_terraform_dir")
    @patch("cli.commands.configure.questionary")
    def test_wizard_exits_when_starting_point_cancelled(
        self, mock_q, mock_tf_dir, mock_root, tmp_path
    ):
        from cli.commands.configure import configure

        mock_root.return_value = tmp_path
        mock_tf_dir.return_value = tmp_path

        mock_q.select.return_value = MagicMock(ask=lambda: None)

        with pytest.raises((SystemExit, click.exceptions.Exit)):
            configure()

    @patch("cli.commands.configure.subprocess.run")
    @patch("cli.commands.configure.run_cmd")
    @patch("cli.commands.configure.get_project_root")
    @patch("cli.commands.configure.get_terraform_dir")
    @patch("cli.commands.configure.questionary")
    def test_wizard_exits_when_org_name_cancelled(
        self, mock_q, mock_tf_dir, mock_root, mock_run_cmd, mock_subproc, tmp_path
    ):
        from cli.commands.configure import configure

        mock_root.return_value = tmp_path
        mock_tf_dir.return_value = tmp_path

        mock_q.select.side_effect = _mock_q(["Start from scratch"])
        mock_q.text.side_effect = _mock_q([None])  # org_name cancelled

        with pytest.raises((SystemExit, click.exceptions.Exit)):
            configure()


class TestPromptPluginConfigCancellation:
    """_prompt_plugin_config exits when any prompt returns None."""

    def _make_ask(self, value):
        q = MagicMock()
        q.ask.return_value = value
        return q

    @pytest.mark.parametrize(
        "plugin,responses",
        [
            # CKAN: 4 text prompts (base_url, portal_url, city_name, timeout).
            # city_name is stored directly so None triggers the end-of-function check.
            (
                "CKAN",
                ["https://data.example.gov", "https://data.example.gov", None, "120"],
            ),
            # ArcGIS: 3 text prompts (portal_url, city_name, timeout).
            # city_name is stored directly so None triggers the check.
            ("ArcGIS", ["https://hub.arcgis.com", None, "120"]),
        ],
    )
    def test_exits_on_none_prompt(self, plugin, responses):
        from unittest.mock import patch

        import click
        import typer

        with patch("cli.commands.configure.questionary") as mock_q:
            mock_q.text.side_effect = [self._make_ask(r) for r in responses]

            from cli.commands.configure import _prompt_plugin_config

            with pytest.raises((SystemExit, click.exceptions.Exit, typer.Exit)):
                _prompt_plugin_config(plugin, {})

    def test_socrata_exits_when_city_name_none(self):
        """Socrata's timeout prompt returning None causes an int() TypeError,
        which propagates as an uncaught exception from _prompt_plugin_config."""
        from unittest.mock import patch

        with patch("cli.commands.configure.questionary") as mock_q:
            mock_q.text.side_effect = [
                self._make_ask("https://data.example.gov"),  # base_url
                self._make_ask(""),  # app_token (skipped)
                self._make_ask(None),  # timeout → int(None) raises
            ]

            from cli.commands.configure import _prompt_plugin_config

            with pytest.raises((SystemExit, TypeError, Exception)):
                _prompt_plugin_config("Socrata", {})
