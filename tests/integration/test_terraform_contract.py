"""Hermetic integration: Terraform module declares CLI-required outputs and variables."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TF_AWS = REPO_ROOT / "terraform" / "aws"
TF_GCP = REPO_ROOT / "terraform" / "gcp"


def _output_names(terraform_dir: Path) -> set[str]:
    text = (terraform_dir / "outputs.tf").read_text(encoding="utf-8")
    return set(re.findall(r'output\s+"([^"]+)"', text))


def _variable_names(terraform_dir: Path) -> set[str]:
    text = (terraform_dir / "variables.tf").read_text(encoding="utf-8")
    return set(re.findall(r'variable\s+"([^"]+)"', text))


def test_aws_outputs_include_api_gateway_url_and_lambda_name() -> None:
    output_names = _output_names(TF_AWS)
    assert "api_gateway_url" in output_names
    assert "lambda_function_name" in output_names


def test_aws_variables_include_cli_deploy_inputs() -> None:
    var_names = _variable_names(TF_AWS)
    for required in (
        "config_file",
        "stage_name",
        "lambda_memory",
        "lambda_timeout",
        "aws_region",
    ):
        assert required in var_names


def test_gcp_outputs_include_mcp_endpoint_and_function_identifiers() -> None:
    output_names = _output_names(TF_GCP)
    for required in (
        "mcp_endpoint_url",
        "function_uri",
        "function_name",
        "source_bucket",
    ):
        assert required in output_names


def test_gcp_variables_include_cli_deploy_inputs() -> None:
    var_names = _variable_names(TF_GCP)
    for required in (
        "config_file",
        "stage_name",
        "project_id",
        "gcp_region",
        "function_memory_mb",
        "function_timeout_sec",
        "min_instance_count",
        "max_instance_count",
    ):
        assert required in var_names
