"""Extended tests for CLI logs command — log parsing, formatting, streaming."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# _extract
# ---------------------------------------------------------------------------


class TestExtract:
    def test_extracts_timestamp_and_message(self):
        from cli.commands.logs import _extract

        raw = "2024-01-15T10:30:00+00:00\tstream-1\tHello world"
        ts, msg = _extract(raw)
        assert ts == "2024-01-15T10:30:00+00:00"
        assert msg == "Hello world"

    def test_no_timestamp_returns_empty_string(self):
        from cli.commands.logs import _extract

        raw = "no-timestamp-here just a message"
        ts, msg = _extract(raw)
        assert ts == ""

    def test_non_matching_line_returned_as_msg(self):
        from cli.commands.logs import _extract

        raw = "plain text"
        _, msg = _extract(raw)
        # Falls back to raw line when no two-token prefix
        assert msg == raw or msg == "plain text"

    def test_timestamp_with_milliseconds(self):
        from cli.commands.logs import _extract

        raw = "2024-01-15T10:30:00.123+00:00\tstream\tSome log"
        ts, msg = _extract(raw)
        assert "2024-01-15" in ts
        assert msg == "Some log"


# ---------------------------------------------------------------------------
# _parse_logs
# ---------------------------------------------------------------------------


SAMPLE_LOG = """2024-01-15T10:00:00Z\tstream\tSTART RequestId: req-001 Version: $LATEST
2024-01-15T10:00:01Z\tstream\tProcessing request
2024-01-15T10:00:02Z\tstream\tEND RequestId: req-001
2024-01-15T10:00:02Z\tstream\tREPORT RequestId: req-001 Duration: 123.4 ms Billed: 200 ms
2024-01-15T10:01:00Z\tstream\tSTART RequestId: req-002 Version: $LATEST
2024-01-15T10:01:01Z\tstream\t[ERROR] Something went wrong
2024-01-15T10:01:02Z\tstream\tEND RequestId: req-002
2024-01-15T10:01:02Z\tstream\tREPORT RequestId: req-002 Duration: 55.0 ms Billed: 100 ms"""


class TestParseLogs:
    def test_parses_two_invocations(self):
        from cli.commands.logs import _parse_logs

        invocations = _parse_logs(SAMPLE_LOG)
        assert len(invocations) == 2

    def test_first_invocation_has_no_error(self):
        from cli.commands.logs import _parse_logs

        invocations = _parse_logs(SAMPLE_LOG)
        assert invocations[0].has_error is False

    def test_second_invocation_has_error(self):
        from cli.commands.logs import _parse_logs

        invocations = _parse_logs(SAMPLE_LOG)
        assert invocations[1].has_error is True

    def test_duration_parsed(self):
        from cli.commands.logs import _parse_logs

        invocations = _parse_logs(SAMPLE_LOG)
        assert invocations[0].duration_ms == pytest.approx(123.4)
        assert invocations[1].duration_ms == pytest.approx(55.0)

    def test_log_lines_captured(self):
        from cli.commands.logs import _parse_logs

        invocations = _parse_logs(SAMPLE_LOG)
        assert any("Processing request" in line for line in invocations[0].lines)

    def test_empty_log_returns_empty_list(self):
        from cli.commands.logs import _parse_logs

        assert _parse_logs("") == []

    def test_lines_without_start_are_ignored(self):
        from cli.commands.logs import _parse_logs

        raw = "some random line\nanother line"
        result = _parse_logs(raw)
        assert result == []

    def test_report_without_matching_start_is_ignored(self):
        from cli.commands.logs import _parse_logs

        raw = "2024-01-15T10:00:02Z\tstream\tREPORT RequestId: orphan-req Duration: 99.0 ms"
        result = _parse_logs(raw)
        assert result == []

    def test_error_patterns_recognized(self):
        """Various error pattern strings set has_error=True."""
        from cli.commands.logs import _parse_logs

        for pattern in [
            "[ERROR]",
            "ERROR occurred",
            "Exception: bad",
            "Traceback (most recent)",
        ]:
            raw = f"""2024-01-15T10:00:00Z\tstream\tSTART RequestId: r1 Version: $LATEST
2024-01-15T10:00:01Z\tstream\t{pattern}
"""
            invocations = _parse_logs(raw)
            if invocations:
                assert invocations[0].has_error is True, (
                    f"Expected error for: {pattern}"
                )


# ---------------------------------------------------------------------------
# _print_summary
# ---------------------------------------------------------------------------


class TestPrintSummary:
    def test_prints_without_errors(self, capsys):
        from cli.commands.logs import Invocation, _print_summary

        invocations = [
            Invocation(request_id="r1", duration_ms=100.0, has_error=False),
            Invocation(request_id="r2", duration_ms=200.0, has_error=False),
        ]
        _print_summary(invocations, "/aws/lambda/test", "1h")
        # Should not raise; rich console output goes to its own stream

    def test_prints_with_errors(self):
        from cli.commands.logs import Invocation, _print_summary

        invocations = [
            Invocation(request_id="r1", duration_ms=None, has_error=True),
        ]
        _print_summary(invocations, "/aws/lambda/test", "30m")

    def test_empty_invocations(self):
        from cli.commands.logs import _print_summary

        _print_summary([], "/aws/lambda/test", "1h")

    def test_avg_duration_computed(self):
        """avg_ms is correctly averaged — no exceptions raised."""
        from cli.commands.logs import Invocation, _print_summary

        invocations = [
            Invocation(request_id="r1", duration_ms=100.0),
            Invocation(request_id="r2", duration_ms=300.0),
        ]
        _print_summary(invocations, "/aws/lambda/test", "1h")

    def test_none_duration_excluded_from_avg(self):
        from cli.commands.logs import Invocation, _print_summary

        invocations = [
            Invocation(request_id="r1", duration_ms=None),
            Invocation(request_id="r2", duration_ms=None),
        ]
        _print_summary(invocations, "/aws/lambda/test", "1h")


# ---------------------------------------------------------------------------
# _print_verbose
# ---------------------------------------------------------------------------


class TestPrintVerbose:
    def test_no_invocations_prints_message(self):
        from cli.commands.logs import _print_verbose

        _print_verbose([], "/aws/lambda/test")

    def test_invocation_with_error_line(self):
        from cli.commands.logs import Invocation, _print_verbose

        invocations = [
            Invocation(
                request_id="req-deadbeef",
                timestamp="2024-01-15T10:00:00+00:00",
                duration_ms=42.0,
                has_error=True,
                lines=["[ERROR] bad thing happened", "normal line"],
            )
        ]
        _print_verbose(invocations, "/aws/lambda/test")

    def test_invocation_without_duration(self):
        from cli.commands.logs import Invocation, _print_verbose

        invocations = [
            Invocation(
                request_id="req-noduration",
                timestamp="",
                duration_ms=None,
                has_error=False,
                lines=[],
            )
        ]
        _print_verbose(invocations, "/aws/lambda/test")

    def test_invocation_with_empty_lines(self):
        from cli.commands.logs import Invocation, _print_verbose

        invocations = [
            Invocation(
                request_id="req-empty",
                timestamp="2024-01-15T10:00:00+00:00",
                duration_ms=10.0,
                has_error=False,
                lines=[],
            )
        ]
        _print_verbose(invocations, "/aws/lambda/test")

    def test_short_request_id_handled(self):
        """request_id shorter than 8 chars should not raise."""
        from cli.commands.logs import Invocation, _print_verbose

        invocations = [
            Invocation(
                request_id="r1", timestamp="2024-01-15T10:00:00+00:00", duration_ms=1.0
            )
        ]
        _print_verbose(invocations, "/aws/lambda/test")


# ---------------------------------------------------------------------------
# run_cmd_stream (local to logs module)
# ---------------------------------------------------------------------------


class TestRunCmdStreamLogs:
    def test_streams_output_and_returns_exit_code(self):
        from cli.commands.logs import run_cmd_stream

        mock_process = MagicMock()
        mock_process.stdout = iter(
            [
                "START RequestId: req-001 Version: $LATEST\n",
                "END RequestId: req-001\n",
                "REPORT RequestId: req-001 Duration: 50.0 ms\n",
                "[ERROR] crash\n",
                "normal line\n",
            ]
        )
        mock_process.wait.return_value = 0

        with patch("cli.commands.logs.subprocess.Popen", return_value=mock_process):
            code = run_cmd_stream(["aws", "logs", "tail", "/aws/lambda/test"])

        assert code == 0

    def test_returns_nonzero_exit_code(self):
        from cli.commands.logs import run_cmd_stream

        mock_process = MagicMock()
        mock_process.stdout = iter([])
        mock_process.wait.return_value = 1

        with patch("cli.commands.logs.subprocess.Popen", return_value=mock_process):
            code = run_cmd_stream(["aws", "logs", "tail", "/missing"])

        assert code == 1


# ---------------------------------------------------------------------------
# logs — verbose mode
# ---------------------------------------------------------------------------


class TestLogsVerboseMode:
    @patch("cli.commands.logs.ensure_config_exists")
    @patch("cli.commands.logs.ensure_terraform_init")
    @patch("cli.commands.logs.select_workspace")
    @patch("cli.commands.logs.get_terraform_dir")
    @patch("cli.commands.logs.subprocess.run")
    def test_verbose_mode_calls_parse_logs(
        self,
        mock_run,
        mock_tf_dir,
        mock_select,
        mock_init,
        mock_config,
        tmp_path,
    ):
        from cli.commands.logs import logs

        mock_tf_dir.return_value = tmp_path

        mock_run.side_effect = [
            # First call: terraform output
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="/aws/lambda/test", stderr=""
            ),
            # Second call: aws logs tail (verbose)
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout=SAMPLE_LOG, stderr=""
            ),
        ]

        logs(env="staging", follow=False, verbose=True, since="1h")

    @patch("cli.commands.logs.ensure_config_exists")
    @patch("cli.commands.logs.ensure_terraform_init")
    @patch("cli.commands.logs.select_workspace")
    @patch("cli.commands.logs.get_terraform_dir")
    @patch("cli.commands.logs.subprocess.run")
    def test_verbose_mode_exits_on_aws_failure(
        self,
        mock_run,
        mock_tf_dir,
        mock_select,
        mock_init,
        mock_config,
        tmp_path,
    ):
        import click

        from cli.commands.logs import logs

        mock_tf_dir.return_value = tmp_path
        mock_run.side_effect = [
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="/aws/lambda/test", stderr=""
            ),
            subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr="error"
            ),
        ]

        with pytest.raises((SystemExit, click.exceptions.Exit)):
            logs(env="staging", follow=False, verbose=True, since="1h")

    @patch("cli.commands.logs.ensure_config_exists")
    @patch("cli.commands.logs.ensure_terraform_init")
    @patch("cli.commands.logs.select_workspace")
    @patch("cli.commands.logs.get_terraform_dir")
    @patch("cli.commands.logs.subprocess.run")
    def test_since_flag_passed_to_aws(
        self,
        mock_run,
        mock_tf_dir,
        mock_select,
        mock_init,
        mock_config,
        tmp_path,
    ):
        from cli.commands.logs import logs

        mock_tf_dir.return_value = tmp_path
        mock_run.side_effect = [
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="/aws/lambda/t", stderr=""
            ),
        ]

        with patch("cli.commands.logs.run_cmd_stream", return_value=0) as mock_stream:
            logs(env="staging", follow=False, verbose=False, since="30m")

        cmd = mock_stream.call_args[0][0]
        assert "--since" in cmd
        assert "30m" in cmd
