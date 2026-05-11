"""Tests for CLI validate command."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import patch

import yaml


# ---------------------------------------------------------------------------
# _parse_tfvars_file
# ---------------------------------------------------------------------------


class TestParseTfvarsFile:
    def test_parses_string_values(self, tmp_path):
        from cli.commands.validate import _parse_tfvars_file

        f = tmp_path / "staging.tfvars"
        f.write_text('lambda_name = "boston-mcp"\ncustom_domain = "data.boston.gov"\n')
        result = _parse_tfvars_file(f)
        assert result["lambda_name"] == "boston-mcp"
        assert result["custom_domain"] == "data.boston.gov"

    def test_parses_numeric_values(self, tmp_path):
        from cli.commands.validate import _parse_tfvars_file

        f = tmp_path / "staging.tfvars"
        f.write_text("memory_size = 512\n")
        result = _parse_tfvars_file(f)
        assert result["memory_size"] == "512"

    def test_skips_comments_and_blank_lines(self, tmp_path):
        from cli.commands.validate import _parse_tfvars_file

        f = tmp_path / "staging.tfvars"
        f.write_text('# This is a comment\n\nlambda_name = "mcp"\n')
        result = _parse_tfvars_file(f)
        assert list(result.keys()) == ["lambda_name"]

    def test_returns_empty_dict_for_empty_file(self, tmp_path):
        from cli.commands.validate import _parse_tfvars_file

        f = tmp_path / "staging.tfvars"
        f.write_text("")
        assert _parse_tfvars_file(f) == {}

    def test_ignores_lines_without_quotes_or_numbers(self, tmp_path):
        from cli.commands.validate import _parse_tfvars_file

        f = tmp_path / "staging.tfvars"
        f.write_text("tags = { env = staging }\n")
        result = _parse_tfvars_file(f)
        assert result == {}


# ---------------------------------------------------------------------------
# run_checks — config.yaml missing
# ---------------------------------------------------------------------------


class TestRunChecksConfigMissing:
    @patch("cli.commands.validate.get_project_root")
    @patch("cli.commands.validate.get_terraform_dir")
    def test_config_missing_fails_check(self, mock_tf_dir, mock_root, tmp_path):
        from cli.commands.validate import run_checks

        mock_root.return_value = tmp_path
        mock_tf_dir.return_value = tmp_path / "terraform" / "aws"

        with patch("cli.commands.validate.subprocess.run") as mock_run:
            # terraform --version
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="Terraform v1.7.0\n", stderr=""
            )
            passed = run_checks("staging")

        assert passed is False


# ---------------------------------------------------------------------------
# run_checks — all happy-path checks pass
# ---------------------------------------------------------------------------


class TestRunChecksHappyPath:
    @patch("cli.commands.validate.get_project_root")
    @patch("cli.commands.validate.get_terraform_dir")
    def test_all_checks_pass(self, mock_tf_dir, mock_root, tmp_path):
        from cli.commands.validate import run_checks

        # Create config.yaml with one enabled plugin
        config = {
            "plugins": {
                "ckan": {"enabled": True, "base_url": "https://data.boston.gov"}
            }
        }
        (tmp_path / "config.yaml").write_text(yaml.dump(config))

        # Create terraform dir and tfvars
        tf_dir = tmp_path / "terraform" / "aws"
        tf_dir.mkdir(parents=True)
        (tf_dir / "staging.tfvars").write_text('lambda_name = "boston-mcp"\n')
        (tf_dir / ".terraform").mkdir()

        mock_root.return_value = tmp_path
        mock_tf_dir.return_value = tf_dir

        aws_identity = json.dumps(
            {
                "Account": "123456789012",
                "Arn": "arn:aws:iam::123:user/test",
                "UserId": "AIDA...",
            }
        )
        iam_sim = json.dumps(
            {
                "EvaluationResults": [
                    {
                        "EvalActionName": "lambda:CreateFunction",
                        "EvalDecision": "allowed",
                    },
                    {
                        "EvalActionName": "lambda:UpdateFunctionCode",
                        "EvalDecision": "allowed",
                    },
                    {"EvalActionName": "apigateway:POST", "EvalDecision": "allowed"},
                    {"EvalActionName": "iam:CreateRole", "EvalDecision": "allowed"},
                ]
            }
        )

        def fake_run(args, **kwargs):
            cmd = args[0] if args else ""
            if cmd == "terraform" and "--version" in args:
                return subprocess.CompletedProcess(args, 0, "Terraform v1.7.0\n", "")
            if cmd == "terraform" and "validate" in args:
                return subprocess.CompletedProcess(args, 0, "{}", "")
            if cmd == "aws" and "get-caller-identity" in args:
                return subprocess.CompletedProcess(args, 0, aws_identity, "")
            if cmd == "aws" and "simulate-principal-policy" in args:
                return subprocess.CompletedProcess(args, 0, iam_sim, "")
            return subprocess.CompletedProcess(args, 0, "", "")

        with patch("cli.commands.validate.subprocess.run", side_effect=fake_run):
            passed = run_checks("staging")

        assert passed is True


# ---------------------------------------------------------------------------
# run_checks — multiple plugins enabled fails
# ---------------------------------------------------------------------------


class TestRunChecksMultiplePlugins:
    @patch("cli.commands.validate.get_project_root")
    @patch("cli.commands.validate.get_terraform_dir")
    def test_multiple_plugins_fails(self, mock_tf_dir, mock_root, tmp_path):
        from cli.commands.validate import run_checks

        config = {
            "plugins": {
                "ckan": {"enabled": True, "base_url": "https://data.boston.gov"},
                "socrata": {
                    "enabled": True,
                    "base_url": "https://data.cityofchicago.org",
                },
            }
        }
        (tmp_path / "config.yaml").write_text(yaml.dump(config))

        tf_dir = tmp_path / "terraform" / "aws"
        tf_dir.mkdir(parents=True)
        (tf_dir / "staging.tfvars").write_text('lambda_name = "mcp"\n')

        mock_root.return_value = tmp_path
        mock_tf_dir.return_value = tf_dir

        with patch("cli.commands.validate.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                [], 0, "Terraform v1.7.0\n", ""
            )
            passed = run_checks("staging")

        assert passed is False


# ---------------------------------------------------------------------------
# run_checks — plugin missing required fields fails
# ---------------------------------------------------------------------------


class TestRunChecksPluginMissingFields:
    @patch("cli.commands.validate.get_project_root")
    @patch("cli.commands.validate.get_terraform_dir")
    def test_plugin_missing_base_url_fails(self, mock_tf_dir, mock_root, tmp_path):
        from cli.commands.validate import run_checks

        config = {"plugins": {"ckan": {"enabled": True}}}  # no base_url
        (tmp_path / "config.yaml").write_text(yaml.dump(config))

        tf_dir = tmp_path / "terraform" / "aws"
        tf_dir.mkdir(parents=True)
        (tf_dir / "staging.tfvars").write_text('lambda_name = "mcp"\n')

        mock_root.return_value = tmp_path
        mock_tf_dir.return_value = tf_dir

        with patch("cli.commands.validate.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                [], 0, "Terraform v1.7.0\n", ""
            )
            passed = run_checks("staging")

        assert passed is False


# ---------------------------------------------------------------------------
# run_checks — terraform not installed
# ---------------------------------------------------------------------------


class TestRunChecksNoTerraform:
    @patch("cli.commands.validate.get_project_root")
    @patch("cli.commands.validate.get_terraform_dir")
    def test_terraform_not_found_fails(self, mock_tf_dir, mock_root, tmp_path):
        from cli.commands.validate import run_checks

        config = {
            "plugins": {
                "ckan": {"enabled": True, "base_url": "https://data.boston.gov"}
            }
        }
        (tmp_path / "config.yaml").write_text(yaml.dump(config))

        tf_dir = tmp_path / "terraform" / "aws"
        tf_dir.mkdir(parents=True)
        (tf_dir / "staging.tfvars").write_text('lambda_name = "mcp"\n')

        mock_root.return_value = tmp_path
        mock_tf_dir.return_value = tf_dir

        def fake_run(args, **kwargs):
            if args[0] == "terraform":
                raise FileNotFoundError
            if args[0] == "aws" and "get-caller-identity" in args:
                return subprocess.CompletedProcess(
                    args,
                    0,
                    '{"Account":"123","Arn":"arn:aws:iam::123:user/u","UserId":"U"}',
                    "",
                )
            return subprocess.CompletedProcess(args, 0, "", "")

        with patch("cli.commands.validate.subprocess.run", side_effect=fake_run):
            passed = run_checks("staging")

        assert passed is False


# ---------------------------------------------------------------------------
# run_checks — AWS credentials invalid
# ---------------------------------------------------------------------------


class TestRunChecksNoAws:
    @patch("cli.commands.validate.get_project_root")
    @patch("cli.commands.validate.get_terraform_dir")
    def test_aws_credentials_invalid_fails(self, mock_tf_dir, mock_root, tmp_path):
        from cli.commands.validate import run_checks

        config = {
            "plugins": {
                "ckan": {"enabled": True, "base_url": "https://data.boston.gov"}
            }
        }
        (tmp_path / "config.yaml").write_text(yaml.dump(config))

        tf_dir = tmp_path / "terraform" / "aws"
        tf_dir.mkdir(parents=True)
        (tf_dir / "staging.tfvars").write_text('lambda_name = "mcp"\n')
        (tf_dir / ".terraform").mkdir()

        mock_root.return_value = tmp_path
        mock_tf_dir.return_value = tf_dir

        def fake_run(args, **kwargs):
            if args[0] == "terraform" and "--version" in args:
                return subprocess.CompletedProcess(args, 0, "Terraform v1.7.0\n", "")
            if args[0] == "terraform" and "validate" in args:
                return subprocess.CompletedProcess(args, 0, "{}", "")
            if args[0] == "aws" and "get-caller-identity" in args:
                return subprocess.CompletedProcess(args, 1, "", "An error occurred")
            return subprocess.CompletedProcess(args, 0, "", "")

        with patch("cli.commands.validate.subprocess.run", side_effect=fake_run):
            passed = run_checks("staging")

        assert passed is False


# ---------------------------------------------------------------------------
# run_checks — custom domain triggers ACM cert check
# ---------------------------------------------------------------------------


class TestRunChecksCustomDomain:
    @patch("cli.commands.validate.get_project_root")
    @patch("cli.commands.validate.get_terraform_dir")
    def test_acm_cert_check_runs_when_custom_domain_set(
        self, mock_tf_dir, mock_root, tmp_path
    ):
        from cli.commands.validate import run_checks

        config = {
            "plugins": {
                "ckan": {"enabled": True, "base_url": "https://data.boston.gov"}
            }
        }
        (tmp_path / "config.yaml").write_text(yaml.dump(config))

        tf_dir = tmp_path / "terraform" / "aws"
        tf_dir.mkdir(parents=True)
        (tf_dir / "staging.tfvars").write_text(
            'lambda_name = "mcp"\ncustom_domain = "data.boston.gov"\n'
        )
        (tf_dir / ".terraform").mkdir()

        mock_root.return_value = tmp_path
        mock_tf_dir.return_value = tf_dir

        acm_response = json.dumps(
            {
                "CertificateSummaryList": [
                    {"DomainName": "data.boston.gov", "Status": "ISSUED"}
                ]
            }
        )
        identity = json.dumps(
            {"Account": "123", "Arn": "arn:aws:iam::123:user/u", "UserId": "U"}
        )
        iam_sim = json.dumps(
            {
                "EvaluationResults": [
                    {"EvalActionName": a, "EvalDecision": "allowed"}
                    for a in [
                        "lambda:CreateFunction",
                        "lambda:UpdateFunctionCode",
                        "apigateway:POST",
                        "iam:CreateRole",
                        "acm:RequestCertificate",
                    ]
                ]
            }
        )

        def fake_run(args, **kwargs):
            if args[0] == "terraform" and "--version" in args:
                return subprocess.CompletedProcess(args, 0, "Terraform v1.7.0\n", "")
            if args[0] == "terraform" and "validate" in args:
                return subprocess.CompletedProcess(args, 0, "{}", "")
            if args[0] == "aws" and "get-caller-identity" in args:
                return subprocess.CompletedProcess(args, 0, identity, "")
            if args[0] == "aws" and "simulate-principal-policy" in args:
                return subprocess.CompletedProcess(args, 0, iam_sim, "")
            if args[0] == "aws" and "list-certificates" in args:
                return subprocess.CompletedProcess(args, 0, acm_response, "")
            return subprocess.CompletedProcess(args, 0, "", "")

        acm_calls = []
        original_fake = fake_run

        def tracking_run(args, **kwargs):
            if "list-certificates" in args:
                acm_calls.append(args)
            return original_fake(args, **kwargs)

        with patch("cli.commands.validate.subprocess.run", side_effect=tracking_run):
            run_checks("staging")

        assert len(acm_calls) >= 1
