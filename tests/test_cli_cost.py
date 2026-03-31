"""Tests for CLI cost command."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

import click
import pytest


# ---------------------------------------------------------------------------
# _cloudwatch_metric
# ---------------------------------------------------------------------------


class TestCloudwatchMetric:
    def test_returns_datapoint_value(self):
        from cli.commands.cost import _cloudwatch_metric

        payload = json.dumps(
            {"Datapoints": [{"Sum": 42000.0, "Timestamp": "2024-01-01T00:00:00Z"}]}
        )

        with patch("cli.commands.cost.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], 0, payload, "")
            result = _cloudwatch_metric(
                namespace="AWS/Lambda",
                metric_name="Invocations",
                dimensions=[{"Name": "FunctionName", "Value": "boston-mcp"}],
                start_time="2024-01-01T00:00:00Z",
                end_time="2024-01-31T00:00:00Z",
                period=2592000,
                statistic="Sum",
            )

        assert result == 42000.0

    def test_returns_zero_when_no_datapoints(self):
        from cli.commands.cost import _cloudwatch_metric

        payload = json.dumps({"Datapoints": []})

        with patch("cli.commands.cost.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], 0, payload, "")
            result = _cloudwatch_metric(
                namespace="AWS/Lambda",
                metric_name="Invocations",
                dimensions=[{"Name": "FunctionName", "Value": "mcp"}],
                start_time="2024-01-01T00:00:00Z",
                end_time="2024-01-31T00:00:00Z",
                period=2592000,
                statistic="Sum",
            )

        assert result == 0.0

    def test_returns_none_when_aws_fails(self):
        from cli.commands.cost import _cloudwatch_metric

        with patch("cli.commands.cost.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], 1, "", "Error")
            result = _cloudwatch_metric(
                namespace="AWS/Lambda",
                metric_name="Invocations",
                dimensions=[],
                start_time="2024-01-01T00:00:00Z",
                end_time="2024-01-31T00:00:00Z",
                period=2592000,
                statistic="Sum",
            )

        assert result is None

    def test_returns_none_when_aws_not_found(self):
        from cli.commands.cost import _cloudwatch_metric

        with patch("cli.commands.cost.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError
            result = _cloudwatch_metric(
                namespace="AWS/Lambda",
                metric_name="Invocations",
                dimensions=[],
                start_time="2024-01-01T00:00:00Z",
                end_time="2024-01-31T00:00:00Z",
                period=2592000,
                statistic="Sum",
            )

        assert result is None

    def test_returns_none_on_timeout(self):
        from cli.commands.cost import _cloudwatch_metric

        with patch("cli.commands.cost.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="aws", timeout=30)
            result = _cloudwatch_metric(
                namespace="AWS/Lambda",
                metric_name="Invocations",
                dimensions=[],
                start_time="2024-01-01T00:00:00Z",
                end_time="2024-01-31T00:00:00Z",
                period=2592000,
                statistic="Sum",
            )

        assert result is None

    def test_returns_none_on_invalid_json(self):
        from cli.commands.cost import _cloudwatch_metric

        with patch("cli.commands.cost.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], 0, "not-json", "")
            result = _cloudwatch_metric(
                namespace="AWS/Lambda",
                metric_name="Invocations",
                dimensions=[],
                start_time="2024-01-01T00:00:00Z",
                end_time="2024-01-31T00:00:00Z",
                period=2592000,
                statistic="Sum",
            )

        assert result is None

    def test_builds_dimension_args(self):
        """Verify dimensions are passed correctly as Name=...,Value=... to the CLI."""
        from cli.commands.cost import _cloudwatch_metric

        payload = json.dumps({"Datapoints": [{"Sum": 1.0}]})

        with patch("cli.commands.cost.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], 0, payload, "")
            _cloudwatch_metric(
                namespace="AWS/Lambda",
                metric_name="Invocations",
                dimensions=[
                    {"Name": "FunctionName", "Value": "my-func"},
                ],
                start_time="2024-01-01T00:00:00Z",
                end_time="2024-01-31T00:00:00Z",
                period=86400,
                statistic="Sum",
            )

        call_args = mock_run.call_args[0][0]
        assert "Name=FunctionName,Value=my-func" in call_args


# ---------------------------------------------------------------------------
# cost calculation constants
# ---------------------------------------------------------------------------


class TestCostConstants:
    def test_lambda_price_constants(self):
        from cli.commands.cost import (
            APIGW_PRICE_PER_1M_REQUESTS,
            LAMBDA_DEFAULT_MEMORY_MB,
            LAMBDA_PRICE_PER_1M_REQUESTS,
            LAMBDA_PRICE_PER_GB_SECOND,
        )

        assert LAMBDA_PRICE_PER_1M_REQUESTS == pytest.approx(0.20)
        assert LAMBDA_PRICE_PER_GB_SECOND > 0
        assert LAMBDA_DEFAULT_MEMORY_MB == 512
        assert APIGW_PRICE_PER_1M_REQUESTS == pytest.approx(3.50)


# ---------------------------------------------------------------------------
# cost command — exits when lambda_name missing
# ---------------------------------------------------------------------------


class TestCostCommandNoLambdaName:
    @patch("cli.commands.cost.get_terraform_dir")
    @patch("cli.commands.cost.load_tfvars", return_value={})  # no lambda_name
    def test_exits_when_lambda_name_missing(self, mock_tfvars, mock_tf_dir, tmp_path):
        from cli.commands.cost import cost

        mock_tf_dir.return_value = tmp_path

        ctx = MagicMock()
        ctx.invoked_subcommand = None

        with pytest.raises(click.exceptions.Exit):
            cost(ctx=ctx, env="staging", days=30)


# ---------------------------------------------------------------------------
# cost command — exits when tfvars not found
# ---------------------------------------------------------------------------


class TestCostCommandNoTfvars:
    @patch("cli.commands.cost.get_terraform_dir")
    @patch("cli.commands.cost.load_tfvars", side_effect=SystemExit(1))
    def test_exits_when_tfvars_missing(self, mock_tfvars, mock_tf_dir, tmp_path):
        from cli.commands.cost import cost

        mock_tf_dir.return_value = tmp_path

        ctx = MagicMock()
        ctx.invoked_subcommand = None

        with pytest.raises(click.exceptions.Exit):
            cost(ctx=ctx, env="staging", days=30)


# ---------------------------------------------------------------------------
# cost command — happy path with all metrics available
# ---------------------------------------------------------------------------


class TestCostCommandHappyPath:
    @patch("cli.commands.cost.get_terraform_dir")
    @patch(
        "cli.commands.cost.load_tfvars",
        return_value={"lambda_name": "boston-mcp"},
    )
    @patch("cli.commands.cost.select_workspace")
    @patch("cli.commands.cost._get_api_name", return_value="boston-mcp-api")
    @patch("cli.commands.cost._cloudwatch_metric")
    def test_renders_table_without_error(
        self,
        mock_metric,
        mock_api_name,
        mock_select,
        mock_tfvars,
        mock_tf_dir,
        tmp_path,
    ):
        from cli.commands.cost import cost

        mock_tf_dir.return_value = tmp_path
        # First call: invocations, second: avg duration, third: apigw requests
        mock_metric.side_effect = [10000.0, 250.0, 8000.0]

        ctx = MagicMock()
        ctx.invoked_subcommand = None

        # Should complete without raising
        cost(ctx=ctx, env="staging", days=30)

        assert mock_metric.call_count == 3


# ---------------------------------------------------------------------------
# cost command — all metrics return None (graceful degradation)
# ---------------------------------------------------------------------------


class TestCostCommandNullMetrics:
    @patch("cli.commands.cost.get_terraform_dir")
    @patch(
        "cli.commands.cost.load_tfvars",
        return_value={"lambda_name": "boston-mcp"},
    )
    @patch("cli.commands.cost.select_workspace")
    @patch("cli.commands.cost._get_api_name", return_value=None)
    @patch("cli.commands.cost._cloudwatch_metric", return_value=None)
    def test_renders_table_with_null_metrics(
        self,
        mock_metric,
        mock_api_name,
        mock_select,
        mock_tfvars,
        mock_tf_dir,
        tmp_path,
    ):
        from cli.commands.cost import cost

        mock_tf_dir.return_value = tmp_path

        ctx = MagicMock()
        ctx.invoked_subcommand = None

        # Should not crash even with no metrics
        cost(ctx=ctx, env="staging", days=30)


# ---------------------------------------------------------------------------
# cost command — projected monthly cost shown when days != 30
# ---------------------------------------------------------------------------


class TestCostCommandProjectedMonthly:
    @patch("cli.commands.cost.get_terraform_dir")
    @patch(
        "cli.commands.cost.load_tfvars",
        return_value={"lambda_name": "boston-mcp"},
    )
    @patch("cli.commands.cost.select_workspace")
    @patch("cli.commands.cost._get_api_name", return_value=None)
    @patch("cli.commands.cost._cloudwatch_metric", return_value=5000.0)
    def test_projected_cost_shown_for_non_30_day_window(
        self,
        mock_metric,
        mock_api_name,
        mock_select,
        mock_tfvars,
        mock_tf_dir,
        tmp_path,
    ):
        from cli.commands.cost import cost

        mock_tf_dir.return_value = tmp_path

        ctx = MagicMock()
        ctx.invoked_subcommand = None

        # With days=7, a projected monthly row should appear
        cost(ctx=ctx, env="staging", days=7)


# ---------------------------------------------------------------------------
# _get_api_name
# ---------------------------------------------------------------------------


class TestGetApiName:
    def test_extracts_api_name_from_url(self, tmp_path):
        from cli.commands.cost import _get_api_name

        api_url = "https://abc123def.execute-api.us-east-1.amazonaws.com/staging"
        api_info = json.dumps({"id": "abc123def", "name": "boston-mcp-api"})

        def fake_run(args, **kwargs):
            if "output" in args and "-raw" in args:
                return subprocess.CompletedProcess(args, 0, api_url, "")
            if "get-rest-api" in args:
                return subprocess.CompletedProcess(args, 0, api_info, "")
            return subprocess.CompletedProcess(args, 0, "", "")

        with patch("cli.commands.cost.subprocess.run", side_effect=fake_run):
            result = _get_api_name(tmp_path, "staging")

        assert result == "boston-mcp-api"

    def test_returns_none_when_terraform_output_fails(self, tmp_path):
        from cli.commands.cost import _get_api_name

        with patch("cli.commands.cost.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], 1, "", "error")
            result = _get_api_name(tmp_path, "staging")

        assert result is None

    def test_returns_none_on_exception(self, tmp_path):
        from cli.commands.cost import _get_api_name

        with patch("cli.commands.cost.subprocess.run", side_effect=Exception("boom")):
            result = _get_api_name(tmp_path, "staging")

        assert result is None
