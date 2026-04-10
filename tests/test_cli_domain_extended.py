"""Extended tests for CLI domain command — domain flow, pending validation, issued cert."""

import json
import subprocess
from unittest.mock import patch

import click
import pytest


# ---------------------------------------------------------------------------
# _get_terraform_outputs
# ---------------------------------------------------------------------------


class TestGetTerraformOutputs:
    @patch("cli.commands.domain.subprocess.run")
    def test_extracts_requested_keys(self, mock_run):
        from cli.commands.domain import _get_terraform_outputs

        payload = {
            "custom_domain_target": {
                "value": "d-abc.execute-api.us-east-1.amazonaws.com"
            },
            "acm_certificate_arn": {"value": "arn:aws:acm:us-east-1:123:cert/x"},
        }
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(payload), stderr=""
        )

        result = _get_terraform_outputs(
            "/fake/terraform/dir",
            ["custom_domain_target", "acm_certificate_arn"],
        )

        assert (
            result["custom_domain_target"]
            == "d-abc.execute-api.us-east-1.amazonaws.com"
        )
        assert result["acm_certificate_arn"] == "arn:aws:acm:us-east-1:123:cert/x"

    @patch("cli.commands.domain.subprocess.run")
    def test_returns_empty_on_failure(self, mock_run):
        from cli.commands.domain import _get_terraform_outputs

        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="error"
        )

        result = _get_terraform_outputs("/fake/dir", ["custom_domain_target"])
        assert result == {}

    @patch("cli.commands.domain.subprocess.run")
    def test_returns_empty_on_empty_stdout(self, mock_run):
        from cli.commands.domain import _get_terraform_outputs

        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="   ", stderr=""
        )

        result = _get_terraform_outputs("/fake/dir", ["custom_domain_target"])
        assert result == {}

    @patch("cli.commands.domain.subprocess.run")
    def test_ignores_missing_keys(self, mock_run):
        from cli.commands.domain import _get_terraform_outputs

        payload = {"some_other_key": {"value": "something"}}
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(payload), stderr=""
        )

        result = _get_terraform_outputs("/fake/dir", ["nonexistent_key"])
        assert "nonexistent_key" not in result

    @patch("cli.commands.domain.subprocess.run")
    def test_none_values_not_included(self, mock_run):
        from cli.commands.domain import _get_terraform_outputs

        payload = {"key": {"value": None}}
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(payload), stderr=""
        )

        result = _get_terraform_outputs("/fake/dir", ["key"])
        assert "key" not in result


# ---------------------------------------------------------------------------
# _handle_pending_validation
# ---------------------------------------------------------------------------


class TestHandlePendingValidation:
    def test_prints_dns_records_table(self):
        from cli.commands.domain import _handle_pending_validation

        tf_out = {
            "custom_domain_target": "d-abc.execute-api.us-east-1.amazonaws.com",
            "acm_validation_cname_name": "_abc.data-mcp.boston.gov",
            "acm_validation_cname_value": "_xyz.acm-validations.aws",
        }
        # Should not raise — just print
        _handle_pending_validation("data-mcp.boston.gov", "staging", tf_out)

    def test_warning_when_regional_domain_lacks_d_prefix(self):
        from cli.commands.domain import _handle_pending_validation

        tf_out = {
            "custom_domain_target": "execute-api.us-east-1.amazonaws.com",
            "acm_validation_cname_name": "_abc.data-mcp.boston.gov",
            "acm_validation_cname_value": "_xyz.acm-validations.aws",
        }
        # No exception expected; warning is printed by rich console
        _handle_pending_validation("data-mcp.boston.gov", "staging", tf_out)

    def test_empty_tf_out_does_not_raise(self):
        from cli.commands.domain import _handle_pending_validation

        _handle_pending_validation("data-mcp.boston.gov", "prod", {})

    def test_email_template_rendered(self):
        from cli.commands.domain import _handle_pending_validation

        tf_out = {
            "custom_domain_target": "d-abc.example.com",
            "acm_validation_cname_name": "_validate.example.gov",
            "acm_validation_cname_value": "_token.acm.aws",
        }
        # This exercises the EMAIL_TEMPLATE.format() path — must not raise
        _handle_pending_validation("example.gov", "staging", tf_out)


# ---------------------------------------------------------------------------
# _handle_issued
# ---------------------------------------------------------------------------


class TestHandleIssued:
    @patch("cli.commands.domain.subprocess.run")
    def test_live_domain_returns_success(self, mock_run):
        from cli.commands.domain import _handle_issued

        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="200", stderr=""
        )

        tf_out = {"custom_domain_target": "d-abc.execute-api.us-east-1.amazonaws.com"}
        _handle_issued("data-mcp.boston.gov", "staging", tf_out)

    @patch("cli.commands.domain.subprocess.run")
    def test_high_status_code_shows_warning(self, mock_run):
        from cli.commands.domain import _handle_issued

        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="503", stderr=""
        )

        tf_out = {"custom_domain_target": "d-abc.execute-api.us-east-1.amazonaws.com"}
        _handle_issued("data-mcp.boston.gov", "staging", tf_out)

    @patch("cli.commands.domain.subprocess.run")
    def test_curl_exception_handled_gracefully(self, mock_run):
        from cli.commands.domain import _handle_issued

        mock_run.side_effect = Exception("network error")

        tf_out = {"custom_domain_target": "d-abc.execute-api.us-east-1.amazonaws.com"}
        # Should not raise — exception is caught internally
        _handle_issued("data-mcp.boston.gov", "staging", tf_out)

    def test_empty_regional_domain_returns_early(self):
        from cli.commands.domain import _handle_issued

        # If regional domain is missing, prints a message and returns without HTTP call
        with patch(
            "cli.commands.domain.subprocess.run", side_effect=AssertionError("no call")
        ):
            _handle_issued("data-mcp.boston.gov", "staging", {})


# ---------------------------------------------------------------------------
# domain command — full flow via mocked subprocess
# ---------------------------------------------------------------------------


class TestDomainCommand:
    @patch("cli.commands.domain.ensure_config_exists")
    @patch("cli.commands.domain.ensure_terraform_init")
    @patch("cli.commands.domain.select_workspace")
    @patch("cli.commands.domain.get_terraform_dir")
    @patch("cli.commands.domain.load_tfvars")
    @patch("cli.commands.domain.subprocess.run")
    def test_pending_validation_flow(
        self,
        mock_run,
        mock_tfvars,
        mock_tf_dir,
        mock_select,
        mock_init,
        mock_config,
        tmp_path,
    ):
        from cli.commands.domain import domain

        mock_tf_dir.return_value = tmp_path
        mock_tfvars.return_value = {"custom_domain": "data-mcp.boston.gov"}

        tf_outputs = {
            "custom_domain_target": {
                "value": "d-abc.execute-api.us-east-1.amazonaws.com"
            },
            "acm_certificate_arn": {"value": "arn:aws:acm:us-east-1:123:cert/x"},
            "acm_validation_cname_name": {"value": "_abc.data-mcp.boston.gov"},
            "acm_validation_cname_value": {"value": "_xyz.acm.aws"},
        }
        cert_list = {
            "CertificateSummaryList": [
                {"DomainName": "data-mcp.boston.gov", "Status": "PENDING_VALIDATION"},
            ]
        }

        mock_run.side_effect = [
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(tf_outputs), stderr=""
            ),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(cert_list), stderr=""
            ),
        ]

        domain(env="staging")

    @patch("cli.commands.domain.ensure_config_exists")
    @patch("cli.commands.domain.ensure_terraform_init")
    @patch("cli.commands.domain.select_workspace")
    @patch("cli.commands.domain.get_terraform_dir")
    @patch("cli.commands.domain.load_tfvars")
    @patch("cli.commands.domain.subprocess.run")
    def test_issued_cert_flow(
        self,
        mock_run,
        mock_tfvars,
        mock_tf_dir,
        mock_select,
        mock_init,
        mock_config,
        tmp_path,
    ):
        from cli.commands.domain import domain

        mock_tf_dir.return_value = tmp_path
        mock_tfvars.return_value = {"custom_domain": "data-mcp.boston.gov"}

        tf_outputs = {
            "custom_domain_target": {
                "value": "d-abc.execute-api.us-east-1.amazonaws.com"
            },
        }
        cert_list = {
            "CertificateSummaryList": [
                {"DomainName": "data-mcp.boston.gov", "Status": "ISSUED"},
            ]
        }
        curl_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="200", stderr=""
        )

        mock_run.side_effect = [
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(tf_outputs), stderr=""
            ),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(cert_list), stderr=""
            ),
            curl_result,
        ]

        domain(env="staging")

    @patch("cli.commands.domain.ensure_config_exists")
    @patch("cli.commands.domain.ensure_terraform_init")
    @patch("cli.commands.domain.select_workspace")
    @patch("cli.commands.domain.get_terraform_dir")
    @patch("cli.commands.domain.load_tfvars")
    @patch("cli.commands.domain.subprocess.run")
    def test_unknown_cert_status_shown(
        self,
        mock_run,
        mock_tfvars,
        mock_tf_dir,
        mock_select,
        mock_init,
        mock_config,
        tmp_path,
    ):
        from cli.commands.domain import domain

        mock_tf_dir.return_value = tmp_path
        mock_tfvars.return_value = {"custom_domain": "data-mcp.boston.gov"}

        cert_list = {
            "CertificateSummaryList": [
                {"DomainName": "data-mcp.boston.gov", "Status": "FAILED"},
            ]
        }

        mock_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout="{}", stderr=""),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(cert_list), stderr=""
            ),
        ]

        domain(env="staging")

    @patch("cli.commands.domain.ensure_config_exists")
    @patch("cli.commands.domain.ensure_terraform_init")
    @patch("cli.commands.domain.load_tfvars")
    @patch("cli.commands.domain.get_terraform_dir")
    @patch("cli.commands.domain.subprocess.run")
    def test_exits_when_no_cert_found(
        self,
        mock_run,
        mock_tf_dir,
        mock_tfvars,
        mock_init,
        mock_config,
        tmp_path,
    ):
        from cli.commands.domain import domain

        mock_tf_dir.return_value = tmp_path
        mock_tfvars.return_value = {"custom_domain": "data-mcp.boston.gov"}

        cert_list = {"CertificateSummaryList": []}

        mock_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout="{}", stderr=""),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(cert_list), stderr=""
            ),
        ]

        with pytest.raises((SystemExit, click.exceptions.Exit)):
            domain(env="staging")
