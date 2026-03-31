"""Tests for CLI domain and status commands."""

import json
import subprocess
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# domain — _get_cert_for_domain
# ---------------------------------------------------------------------------


class TestGetCertForDomain:
    @patch("cli.commands.domain.subprocess.run")
    def test_finds_matching_cert(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {
                    "CertificateSummaryList": [
                        {"DomainName": "other.gov", "Status": "ISSUED"},
                        {
                            "DomainName": "data-mcp.boston.gov",
                            "Status": "PENDING_VALIDATION",
                            "CertificateArn": "arn:aws:acm:us-east-1:123:cert/abc",
                        },
                    ]
                }
            ),
            stderr="",
        )

        from cli.commands.domain import _get_cert_for_domain

        cert = _get_cert_for_domain("data-mcp.boston.gov")
        assert cert is not None
        assert cert["Status"] == "PENDING_VALIDATION"

    @patch("cli.commands.domain.subprocess.run")
    def test_returns_none_when_not_found(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({"CertificateSummaryList": []}),
            stderr="",
        )

        from cli.commands.domain import _get_cert_for_domain

        assert _get_cert_for_domain("missing.gov") is None

    @patch("cli.commands.domain.subprocess.run")
    def test_returns_none_on_aws_failure(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="error"
        )

        from cli.commands.domain import _get_cert_for_domain

        assert _get_cert_for_domain("any.gov") is None


# ---------------------------------------------------------------------------
# domain — _get_apigw_domain
# ---------------------------------------------------------------------------


class TestGetApigwDomain:
    @patch("cli.commands.domain.subprocess.run")
    def test_returns_domain_info(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {
                    "domainName": "data-mcp.boston.gov",
                    "regionalDomainName": "d-abc123.execute-api.us-east-1.amazonaws.com",
                }
            ),
            stderr="",
        )

        from cli.commands.domain import _get_apigw_domain

        result = _get_apigw_domain("data-mcp.boston.gov")
        assert result is not None
        assert result["regionalDomainName"].startswith("d-")

    @patch("cli.commands.domain.subprocess.run")
    def test_returns_none_on_not_found(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="NotFoundException"
        )

        from cli.commands.domain import _get_apigw_domain

        assert _get_apigw_domain("missing.gov") is None


# ---------------------------------------------------------------------------
# domain — requires custom_domain in tfvars
# ---------------------------------------------------------------------------


class TestDomainRequiresDomain:
    @patch("cli.commands.domain.ensure_config_exists")
    @patch("cli.commands.domain.ensure_terraform_init")
    @patch("cli.commands.domain.load_tfvars", return_value={"custom_domain": ""})
    def test_exits_when_no_domain_configured(self, mock_tfvars, mock_init, mock_config):
        from cli.commands.domain import domain

        with pytest.raises(SystemExit):
            domain(env="staging")

    @patch("cli.commands.domain.ensure_config_exists")
    @patch("cli.commands.domain.ensure_terraform_init")
    @patch("cli.commands.domain.load_tfvars", return_value={"lambda_name": "func"})
    def test_exits_when_domain_key_missing(self, mock_tfvars, mock_init, mock_config):
        from cli.commands.domain import domain

        with pytest.raises(SystemExit):
            domain(env="staging")


# ---------------------------------------------------------------------------
# domain — email template
# ---------------------------------------------------------------------------


class TestEmailTemplate:
    def test_template_has_placeholders(self):
        from cli.commands.domain import EMAIL_TEMPLATE

        assert "{domain}" in EMAIL_TEMPLATE
        assert "{regional_domain}" in EMAIL_TEMPLATE
        assert "{validation_name}" in EMAIL_TEMPLATE
        assert "{validation_value}" in EMAIL_TEMPLATE

    def test_template_formats_correctly(self):
        from cli.commands.domain import EMAIL_TEMPLATE

        result = EMAIL_TEMPLATE.format(
            domain="data-mcp.boston.gov",
            regional_domain="d-abc.execute-api.us-east-1.amazonaws.com",
            validation_name="_abc.data-mcp.boston.gov",
            validation_value="_xyz.acm-validations.aws",
        )
        assert "data-mcp.boston.gov" in result
        assert "d-abc.execute-api" in result
        assert "_abc.data-mcp" in result


# ---------------------------------------------------------------------------
# status — workspace name shown correctly
# ---------------------------------------------------------------------------


class TestStatusWorkspace:
    @patch("cli.commands.status.ensure_config_exists")
    @patch("cli.commands.status.ensure_terraform_init")
    @patch(
        "cli.commands.status.load_tfvars",
        return_value={"lambda_name": "test-mcp", "custom_domain": ""},
    )
    @patch("cli.commands.status.select_workspace")
    @patch("cli.commands.status.workspace_name", return_value="boston-staging")
    @patch("cli.commands.status.subprocess.run")
    def test_status_gathers_terraform_outputs(
        self,
        mock_run,
        mock_ws,
        mock_select,
        mock_tfvars,
        mock_init,
        mock_config,
        tmp_path,
    ):
        from cli.commands.status import status

        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {
                    "api_gateway_url": {"value": "https://api.example.com/mcp"},
                    "lambda_url": {"value": "https://lambda.example.com"},
                    "cloudwatch_log_group": {"value": "/aws/lambda/test-mcp"},
                }
            ),
            stderr="",
        )

        with patch("cli.commands.status.get_terraform_dir", return_value=tmp_path):
            status(env="staging")

        mock_select.assert_called_once()
