"""Hermetic integration: Terraform module declares CLI-required outputs and variables."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TF_AWS = REPO_ROOT / "terraform" / "aws"


def test_outputs_include_api_gateway_url_and_lambda_name() -> None:
    text = (TF_AWS / "outputs.tf").read_text(encoding="utf-8")
    output_names = set(re.findall(r'output\s+"([^"]+)"', text))
    assert "api_gateway_url" in output_names
    assert "lambda_function_name" in output_names


def test_variables_include_cli_deploy_inputs() -> None:
    text = (TF_AWS / "variables.tf").read_text(encoding="utf-8")
    var_names = set(re.findall(r'variable\s+"([^"]+)"', text))
    for required in (
        "config_file",
        "stage_name",
        "lambda_memory",
        "lambda_timeout",
        "aws_region",
    ):
        assert required in var_names
