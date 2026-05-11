"""Extended tests for CLI deploy command — full deploy flow, cert status, outputs."""

import json
import subprocess
from unittest.mock import MagicMock, patch

import click
import pytest


# ---------------------------------------------------------------------------
# _print_cert_status
# ---------------------------------------------------------------------------


class TestPrintCertStatus:
    @patch("cli.commands.deploy.subprocess.run")
    def test_pending_validation_prints_message(self, mock_run):
        from cli.commands.deploy import _print_cert_status

        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {
                    "CertificateSummaryList": [
                        {
                            "DomainName": "data-mcp.boston.gov",
                            "Status": "PENDING_VALIDATION",
                        }
                    ]
                }
            ),
            stderr="",
        )
        # Must not raise
        _print_cert_status("data-mcp.boston.gov", "staging")

    @patch("cli.commands.deploy.subprocess.run")
    def test_issued_cert_prints_active_message(self, mock_run):
        from cli.commands.deploy import _print_cert_status

        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {
                    "CertificateSummaryList": [
                        {"DomainName": "data-mcp.boston.gov", "Status": "ISSUED"}
                    ]
                }
            ),
            stderr="",
        )
        _print_cert_status("data-mcp.boston.gov", "staging")

    @patch("cli.commands.deploy.subprocess.run")
    def test_domain_not_found_prints_fallback(self, mock_run):
        from cli.commands.deploy import _print_cert_status

        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({"CertificateSummaryList": []}),
            stderr="",
        )
        _print_cert_status("missing.gov", "staging")

    @patch("cli.commands.deploy.subprocess.run")
    def test_aws_failure_swallowed_silently(self, mock_run):
        from cli.commands.deploy import _print_cert_status

        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="error"
        )
        # Exception is caught inside _print_cert_status
        _print_cert_status("data-mcp.boston.gov", "staging")

    @patch("cli.commands.deploy.subprocess.run")
    def test_exception_swallowed_silently(self, mock_run):
        from cli.commands.deploy import _print_cert_status

        mock_run.side_effect = Exception("network error")
        _print_cert_status("data-mcp.boston.gov", "staging")


# ---------------------------------------------------------------------------
# deploy — full flow (mocked)
# ---------------------------------------------------------------------------


def _make_tf_output(api_gw: str = "https://api.example.com/mcp") -> str:
    return json.dumps(
        {
            "api_gateway_url": {"value": api_gw},
            "lambda_url": {"value": "https://lambda.example.com"},
            "cloudwatch_log_group": {"value": "/aws/lambda/test-mcp"},
        }
    )


class TestDeployFullFlow:
    @patch("cli.commands.deploy.require_tty")
    @patch("cli.commands.deploy._run_validate_checks", return_value=True)
    @patch("cli.commands.deploy.get_project_root")
    @patch("cli.commands.deploy.get_terraform_dir")
    @patch("cli.commands.deploy.ensure_config_exists")
    @patch("cli.commands.deploy.ensure_terraform_init")
    @patch("cli.commands.deploy.load_config")
    @patch("cli.commands.deploy.load_tfvars")
    @patch("cli.commands.deploy._package_lambda")
    @patch("cli.commands.deploy.shutil.copy2")
    @patch("cli.commands.deploy.select_workspace")
    @patch("cli.commands.deploy.run_cmd_stream_capture")
    @patch("cli.commands.deploy.run_cmd_stream")
    @patch("cli.commands.deploy.subprocess.run")
    @patch("cli.commands.deploy.questionary")
    def test_successful_deploy_no_domain(
        self,
        mock_q,
        mock_subproc,
        mock_stream,
        mock_stream_capture,
        mock_select,
        mock_copy,
        mock_package,
        mock_load_tfvars,
        mock_load_config,
        mock_init,
        mock_config_exists,
        mock_tf_dir,
        mock_root,
        mock_validate,
        mock_tty,
        tmp_path,
    ):
        from cli.commands.deploy import deploy

        mock_root.return_value = tmp_path
        mock_tf_dir.return_value = tmp_path

        # Create the tfvars file
        (tmp_path / "staging.tfvars").write_text(
            'lambda_name = "test"\ncustom_domain = ""\n'
        )

        mock_load_config.return_value = {"plugins": {"ckan": {"enabled": True}}}
        mock_load_tfvars.return_value = {"custom_domain": ""}

        zip_mock = MagicMock()
        zip_mock.name = "lambda-deployment.zip"
        mock_package.return_value = zip_mock

        # Terraform plan succeeds with changes
        mock_stream_capture.return_value = (
            0,
            "Plan: 2 to add, 1 to change, 0 to destroy.",
        )

        # User confirms deployment
        mock_q.confirm.return_value.ask.return_value = True

        # Terraform apply succeeds
        mock_stream.return_value = 0

        # terraform output -json
        mock_subproc.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=_make_tf_output(), stderr=""
        )

        deploy(env="staging")

    @patch("cli.commands.deploy.require_tty")
    @patch("cli.commands.deploy._run_validate_checks", return_value=True)
    @patch("cli.commands.deploy.get_project_root")
    @patch("cli.commands.deploy.get_terraform_dir")
    @patch("cli.commands.deploy.ensure_config_exists")
    @patch("cli.commands.deploy.ensure_terraform_init")
    @patch("cli.commands.deploy.load_config")
    @patch("cli.commands.deploy.load_tfvars")
    @patch("cli.commands.deploy._package_lambda")
    @patch("cli.commands.deploy.shutil.copy2")
    @patch("cli.commands.deploy.select_workspace")
    @patch("cli.commands.deploy.run_cmd_stream_capture")
    @patch("cli.commands.deploy.questionary")
    def test_deploy_cancelled_by_user(
        self,
        mock_q,
        mock_stream_capture,
        mock_select,
        mock_copy,
        mock_package,
        mock_load_tfvars,
        mock_load_config,
        mock_init,
        mock_config_exists,
        mock_tf_dir,
        mock_root,
        mock_validate,
        mock_tty,
        tmp_path,
    ):
        from cli.commands.deploy import deploy

        mock_root.return_value = tmp_path
        mock_tf_dir.return_value = tmp_path
        (tmp_path / "staging.tfvars").write_text('lambda_name = "test"\n')

        mock_load_config.return_value = {"plugins": {"ckan": {"enabled": True}}}
        mock_load_tfvars.return_value = {"custom_domain": ""}

        zip_mock = MagicMock()
        zip_mock.name = "lambda-deployment.zip"
        mock_package.return_value = zip_mock

        mock_stream_capture.return_value = (
            0,
            "Plan: 1 to add, 0 to change, 0 to destroy.",
        )

        # User declines
        mock_q.confirm.return_value.ask.return_value = False

        with pytest.raises((SystemExit, click.exceptions.Exit)):
            deploy(env="staging")

    @patch("cli.commands.deploy.require_tty")
    @patch("cli.commands.deploy._run_validate_checks", return_value=False)
    def test_deploy_exits_on_validation_failure(self, mock_validate, mock_tty):
        from cli.commands.deploy import deploy

        with pytest.raises((SystemExit, click.exceptions.Exit)):
            deploy(env="staging")

    @patch("cli.commands.deploy.require_tty")
    @patch("cli.commands.deploy._run_validate_checks", return_value=True)
    @patch("cli.commands.deploy.get_project_root")
    @patch("cli.commands.deploy.get_terraform_dir")
    @patch("cli.commands.deploy.ensure_config_exists")
    @patch("cli.commands.deploy.ensure_terraform_init")
    @patch("cli.commands.deploy.load_config")
    @patch("cli.commands.deploy._package_lambda")
    @patch("cli.commands.deploy.shutil.copy2")
    @patch("cli.commands.deploy.select_workspace")
    @patch("cli.commands.deploy.run_cmd_stream_capture")
    def test_deploy_exits_when_tfvars_missing(
        self,
        mock_stream_capture,
        mock_select,
        mock_copy,
        mock_package,
        mock_load_config,
        mock_init,
        mock_config_exists,
        mock_tf_dir,
        mock_root,
        mock_validate,
        mock_tty,
        tmp_path,
    ):
        from cli.commands.deploy import deploy

        mock_root.return_value = tmp_path
        mock_tf_dir.return_value = tmp_path
        # No .tfvars file created

        mock_load_config.return_value = {"plugins": {"ckan": {"enabled": True}}}

        zip_mock = MagicMock()
        zip_mock.name = "lambda-deployment.zip"
        mock_package.return_value = zip_mock

        with pytest.raises((SystemExit, click.exceptions.Exit)):
            deploy(env="staging")

    @patch("cli.commands.deploy.require_tty")
    @patch("cli.commands.deploy._run_validate_checks", return_value=True)
    @patch("cli.commands.deploy.get_project_root")
    @patch("cli.commands.deploy.get_terraform_dir")
    @patch("cli.commands.deploy.ensure_config_exists")
    @patch("cli.commands.deploy.ensure_terraform_init")
    @patch("cli.commands.deploy.load_config")
    @patch("cli.commands.deploy.load_tfvars")
    @patch("cli.commands.deploy._package_lambda")
    @patch("cli.commands.deploy.shutil.copy2")
    @patch("cli.commands.deploy.select_workspace")
    @patch("cli.commands.deploy.run_cmd_stream_capture")
    def test_deploy_exits_on_plan_failure(
        self,
        mock_stream_capture,
        mock_select,
        mock_copy,
        mock_package,
        mock_load_tfvars,
        mock_load_config,
        mock_init,
        mock_config_exists,
        mock_tf_dir,
        mock_root,
        mock_validate,
        mock_tty,
        tmp_path,
    ):
        from cli.commands.deploy import deploy

        mock_root.return_value = tmp_path
        mock_tf_dir.return_value = tmp_path
        (tmp_path / "staging.tfvars").write_text('lambda_name = "test"\n')

        mock_load_config.return_value = {"plugins": {"ckan": {"enabled": True}}}
        mock_load_tfvars.return_value = {"custom_domain": ""}

        zip_mock = MagicMock()
        zip_mock.name = "lambda-deployment.zip"
        mock_package.return_value = zip_mock

        # Plan fails
        mock_stream_capture.return_value = (1, "Error: something went wrong")

        with pytest.raises((SystemExit, click.exceptions.Exit)):
            deploy(env="staging")

    @patch("cli.commands.deploy.require_tty")
    @patch("cli.commands.deploy._run_validate_checks", return_value=True)
    @patch("cli.commands.deploy.get_project_root")
    @patch("cli.commands.deploy.get_terraform_dir")
    @patch("cli.commands.deploy.ensure_config_exists")
    @patch("cli.commands.deploy.ensure_terraform_init")
    @patch("cli.commands.deploy.load_config")
    @patch("cli.commands.deploy.load_tfvars")
    @patch("cli.commands.deploy._package_lambda")
    @patch("cli.commands.deploy.shutil.copy2")
    @patch("cli.commands.deploy.select_workspace")
    @patch("cli.commands.deploy.run_cmd_stream_capture")
    @patch("cli.commands.deploy.run_cmd_stream")
    @patch("cli.commands.deploy.subprocess.run")
    @patch("cli.commands.deploy.questionary")
    def test_deploy_exits_on_apply_failure(
        self,
        mock_q,
        mock_subproc,
        mock_stream,
        mock_stream_capture,
        mock_select,
        mock_copy,
        mock_package,
        mock_load_tfvars,
        mock_load_config,
        mock_init,
        mock_config_exists,
        mock_tf_dir,
        mock_root,
        mock_validate,
        mock_tty,
        tmp_path,
    ):
        from cli.commands.deploy import deploy

        mock_root.return_value = tmp_path
        mock_tf_dir.return_value = tmp_path
        (tmp_path / "staging.tfvars").write_text('lambda_name = "test"\n')

        mock_load_config.return_value = {"plugins": {"ckan": {"enabled": True}}}
        mock_load_tfvars.return_value = {"custom_domain": ""}

        zip_mock = MagicMock()
        zip_mock.name = "lambda-deployment.zip"
        mock_package.return_value = zip_mock

        mock_stream_capture.return_value = (
            0,
            "Plan: 1 to add, 0 to change, 0 to destroy.",
        )
        mock_q.confirm.return_value.ask.return_value = True
        mock_stream.return_value = 1  # apply fails

        with pytest.raises((SystemExit, click.exceptions.Exit)):
            deploy(env="staging")

    @patch("cli.commands.deploy.require_tty")
    @patch("cli.commands.deploy._run_validate_checks", return_value=True)
    @patch("cli.commands.deploy.get_project_root")
    @patch("cli.commands.deploy.get_terraform_dir")
    @patch("cli.commands.deploy.ensure_config_exists")
    @patch("cli.commands.deploy.ensure_terraform_init")
    @patch("cli.commands.deploy.load_config")
    @patch("cli.commands.deploy.load_tfvars")
    @patch("cli.commands.deploy._package_lambda")
    @patch("cli.commands.deploy.shutil.copy2")
    @patch("cli.commands.deploy.select_workspace")
    @patch("cli.commands.deploy.run_cmd_stream_capture")
    @patch("cli.commands.deploy.run_cmd_stream")
    @patch("cli.commands.deploy.subprocess.run")
    @patch("cli.commands.deploy.questionary")
    def test_deploy_with_custom_domain_shows_cert_status(
        self,
        mock_q,
        mock_subproc,
        mock_stream,
        mock_stream_capture,
        mock_select,
        mock_copy,
        mock_package,
        mock_load_tfvars,
        mock_load_config,
        mock_init,
        mock_config_exists,
        mock_tf_dir,
        mock_root,
        mock_validate,
        mock_tty,
        tmp_path,
    ):
        from cli.commands.deploy import deploy

        mock_root.return_value = tmp_path
        mock_tf_dir.return_value = tmp_path
        (tmp_path / "prod.tfvars").write_text(
            'lambda_name = "test"\ncustom_domain = "data-mcp.boston.gov"\n'
        )

        mock_load_config.return_value = {"plugins": {"ckan": {"enabled": True}}}
        mock_load_tfvars.return_value = {"custom_domain": "data-mcp.boston.gov"}

        zip_mock = MagicMock()
        zip_mock.name = "lambda-deployment.zip"
        mock_package.return_value = zip_mock

        mock_stream_capture.return_value = (
            0,
            "Plan: 1 to add, 0 to change, 0 to destroy.",
        )
        mock_q.confirm.return_value.ask.return_value = True
        mock_stream.return_value = 0

        tf_output = {
            "api_gateway_url": {"value": "https://api.example.com/mcp"},
            "lambda_url": {"value": "https://lambda.example.com"},
            "cloudwatch_log_group": {"value": "/aws/lambda/test-mcp"},
            "custom_domain_target": {
                "value": "d-abc.execute-api.us-east-1.amazonaws.com"
            },
            "acm_certificate_arn": {"value": "arn:aws:acm:us-east-1:123:cert/x"},
            "acm_validation_cname_name": {"value": "_abc.data-mcp.boston.gov"},
            "acm_validation_cname_value": {"value": "_xyz.acm.aws"},
        }
        cert_list = {
            "CertificateSummaryList": [
                {"DomainName": "data-mcp.boston.gov", "Status": "PENDING_VALIDATION"}
            ]
        }

        mock_subproc.side_effect = [
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(tf_output), stderr=""
            ),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(cert_list), stderr=""
            ),
        ]

        deploy(env="prod")

    @patch("cli.commands.deploy.require_tty")
    @patch("cli.commands.deploy._run_validate_checks", return_value=True)
    @patch("cli.commands.deploy.get_project_root")
    @patch("cli.commands.deploy.get_terraform_dir")
    @patch("cli.commands.deploy.ensure_config_exists")
    @patch("cli.commands.deploy.ensure_terraform_init")
    @patch("cli.commands.deploy.load_config")
    @patch("cli.commands.deploy.load_tfvars")
    @patch("cli.commands.deploy._package_lambda")
    @patch("cli.commands.deploy.shutil.copy2")
    @patch("cli.commands.deploy.select_workspace")
    @patch("cli.commands.deploy.run_cmd_stream_capture")
    @patch("cli.commands.deploy.run_cmd_stream")
    @patch("cli.commands.deploy.subprocess.run")
    @patch("cli.commands.deploy.questionary")
    def test_deploy_cleans_up_tfplan_after_cancel(
        self,
        mock_q,
        mock_subproc,
        mock_stream,
        mock_stream_capture,
        mock_select,
        mock_copy,
        mock_package,
        mock_load_tfvars,
        mock_load_config,
        mock_init,
        mock_config_exists,
        mock_tf_dir,
        mock_root,
        mock_validate,
        mock_tty,
        tmp_path,
    ):
        from cli.commands.deploy import deploy

        mock_root.return_value = tmp_path
        mock_tf_dir.return_value = tmp_path
        (tmp_path / "staging.tfvars").write_text('lambda_name = "test"\n')
        # Create tfplan file to verify it gets cleaned up
        tfplan = tmp_path / "tfplan"
        tfplan.write_text("plan data")

        mock_load_config.return_value = {"plugins": {"ckan": {"enabled": True}}}
        mock_load_tfvars.return_value = {"custom_domain": ""}

        zip_mock = MagicMock()
        zip_mock.name = "lambda-deployment.zip"
        mock_package.return_value = zip_mock

        mock_stream_capture.return_value = (
            0,
            "Plan: 1 to add, 0 to change, 0 to destroy.",
        )
        mock_q.confirm.return_value.ask.return_value = False

        with pytest.raises((SystemExit, click.exceptions.Exit)):
            deploy(env="staging")

        assert not tfplan.exists()

    @patch("cli.commands.deploy.require_tty")
    @patch("cli.commands.deploy._run_validate_checks", return_value=True)
    @patch("cli.commands.deploy.get_project_root")
    @patch("cli.commands.deploy.get_terraform_dir")
    @patch("cli.commands.deploy.ensure_config_exists")
    @patch("cli.commands.deploy.ensure_terraform_init")
    @patch("cli.commands.deploy.load_config")
    @patch("cli.commands.deploy.load_tfvars")
    @patch("cli.commands.deploy._package_lambda")
    @patch("cli.commands.deploy.shutil.copy2")
    @patch("cli.commands.deploy.select_workspace")
    @patch("cli.commands.deploy.run_cmd_stream_capture")
    @patch("cli.commands.deploy.run_cmd_stream")
    @patch("cli.commands.deploy.subprocess.run")
    @patch("cli.commands.deploy.questionary")
    def test_deploy_regional_domain_warning_when_no_d_prefix(
        self,
        mock_q,
        mock_subproc,
        mock_stream,
        mock_stream_capture,
        mock_select,
        mock_copy,
        mock_package,
        mock_load_tfvars,
        mock_load_config,
        mock_init,
        mock_config_exists,
        mock_tf_dir,
        mock_root,
        mock_validate,
        mock_tty,
        tmp_path,
    ):
        """Regional domain without 'd-' prefix triggers a warning in the output table."""
        from cli.commands.deploy import deploy

        mock_root.return_value = tmp_path
        mock_tf_dir.return_value = tmp_path
        (tmp_path / "prod.tfvars").write_text('lambda_name = "test"\n')

        mock_load_config.return_value = {"plugins": {"ckan": {"enabled": True}}}
        mock_load_tfvars.return_value = {"custom_domain": "data-mcp.boston.gov"}

        zip_mock = MagicMock()
        zip_mock.name = "lambda-deployment.zip"
        mock_package.return_value = zip_mock

        mock_stream_capture.return_value = (
            0,
            "Plan: 1 to add, 0 to change, 0 to destroy.",
        )
        mock_q.confirm.return_value.ask.return_value = True
        mock_stream.return_value = 0

        # regional domain does NOT start with 'd-' — triggers warning
        tf_output = {
            "api_gateway_url": {"value": "https://api.example.com/mcp"},
            "custom_domain_target": {"value": "execute-api.us-east-1.amazonaws.com"},
        }
        cert_list = {"CertificateSummaryList": []}

        mock_subproc.side_effect = [
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(tf_output), stderr=""
            ),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(cert_list), stderr=""
            ),
        ]

        deploy(env="prod")
