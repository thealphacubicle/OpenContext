"""Tests for CLI test command (MCP endpoint smoke tests)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# _summarize
# ---------------------------------------------------------------------------


class TestSummarize:
    def test_string_truncated_to_80(self):
        from cli.commands.test import _summarize

        long_str = "x" * 200
        result = _summarize(long_str)
        assert result == "x" * 80

    def test_short_string_unchanged(self):
        from cli.commands.test import _summarize

        assert _summarize("hello") == "hello"

    def test_dict_with_error_returns_message(self):
        from cli.commands.test import _summarize

        body = {"error": {"message": "Method not found", "code": -32601}}
        result = _summarize(body)
        assert "error" in result
        assert "Method not found" in result

    def test_dict_with_string_error(self):
        from cli.commands.test import _summarize

        body = {"error": "something went wrong"}
        result = _summarize(body)
        assert "error" in result

    def test_dict_with_result_keys(self):
        from cli.commands.test import _summarize

        body = {"result": {"tools": [], "protocolVersion": "2024-11-05"}}
        result = _summarize(body)
        assert "result keys" in result

    def test_dict_with_string_result(self):
        from cli.commands.test import _summarize

        body = {"result": "pong"}
        result = _summarize(body)
        assert "pong" in result

    def test_non_dict_non_str_converted(self):
        from cli.commands.test import _summarize

        result = _summarize(42)
        assert result == "42"

    def test_empty_dict(self):
        from cli.commands.test import _summarize

        result = _summarize({})
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _post_mcp — success
# ---------------------------------------------------------------------------


class TestPostMcp:
    def test_returns_true_on_2xx(self):
        from cli.commands.test import _post_mcp

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "pong"}

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response

        ok, elapsed_ms, body = _post_mcp(
            mock_client,
            "https://api.example.com",
            {"jsonrpc": "2.0", "id": 1, "method": "ping"},
        )

        assert ok is True
        assert elapsed_ms >= 0
        assert body == {"result": "pong"}

    def test_returns_false_on_5xx(self):
        from cli.commands.test import _post_mcp

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {}

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response

        ok, elapsed_ms, body = _post_mcp(
            mock_client, "https://api.example.com", {"method": "ping"}
        )

        assert ok is False

    def test_returns_true_on_4xx(self):
        """4xx is not a server error — method may just be unknown."""
        from cli.commands.test import _post_mcp

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": {"message": "bad request"}}

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response

        ok, _, _ = _post_mcp(mock_client, "https://api.example.com", {"method": "ping"})

        assert ok is True

    def test_timeout_returns_false(self):
        import httpx

        from cli.commands.test import _post_mcp

        mock_client = MagicMock()
        mock_client.post.side_effect = httpx.TimeoutException("timed out")

        ok, elapsed_ms, body = _post_mcp(
            mock_client, "https://api.example.com", {"method": "ping"}
        )

        assert ok is False
        assert body == "Timeout"

    def test_generic_exception_returns_false(self):
        from cli.commands.test import _post_mcp

        mock_client = MagicMock()
        mock_client.post.side_effect = Exception("connection refused")

        ok, _, body = _post_mcp(
            mock_client, "https://api.example.com", {"method": "ping"}
        )

        assert ok is False
        assert "connection refused" in body

    def test_non_json_response_falls_back_to_text(self):
        from cli.commands.test import _post_mcp

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("not JSON")
        mock_response.text = "OK"

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response

        ok, _, body = _post_mcp(mock_client, "https://api.example.com", {})

        assert ok is True
        assert body == "OK"


# ---------------------------------------------------------------------------
# _run_tests
# ---------------------------------------------------------------------------


class TestRunTests:
    def _make_response(self, status_code: int, body: dict):
        mock_response = MagicMock()
        mock_response.status_code = status_code
        mock_response.json.return_value = body
        return mock_response

    def test_all_pass_when_tools_available(self):
        from cli.commands.test import _run_tests

        tools_body = {"result": {"tools": [{"name": "search_datasets"}]}}
        ping_body = {"result": "pong"}
        init_body = {"result": {"protocolVersion": "2024-11-05", "capabilities": {}}}
        tool_call_body = {"result": {"content": []}}

        responses = [
            self._make_response(200, ping_body),
            self._make_response(200, init_body),
            self._make_response(200, tools_body),
            self._make_response(200, tool_call_body),
        ]

        mock_client = MagicMock()
        mock_client.post.side_effect = responses
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("cli.commands.test.httpx.Client", return_value=mock_client):
            passed, total = _run_tests("https://api.example.com")

        assert total == 4
        assert passed == 4

    def test_no_tools_returned_fails_tool_call(self):
        from cli.commands.test import _run_tests

        ping_body = {"result": "pong"}
        init_body = {"result": {"protocolVersion": "2024-11-05"}}
        tools_body = {"result": {"tools": []}}  # empty list

        responses = [
            self._make_response(200, ping_body),
            self._make_response(200, init_body),
            self._make_response(200, tools_body),
        ]

        mock_client = MagicMock()
        mock_client.post.side_effect = responses
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("cli.commands.test.httpx.Client", return_value=mock_client):
            passed, total = _run_tests("https://api.example.com")

        # The 4th test "Call first tool" should fail with "No tools returned"
        assert total == 4
        assert passed < total

    def test_server_error_on_ping_fails(self):
        from cli.commands.test import _run_tests

        responses = [
            self._make_response(500, {}),  # ping fails
            self._make_response(200, {"result": {}}),  # init
            self._make_response(200, {"result": {"tools": []}}),  # list
        ]

        mock_client = MagicMock()
        mock_client.post.side_effect = responses
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("cli.commands.test.httpx.Client", return_value=mock_client):
            passed, total = _run_tests("https://api.example.com")

        assert passed < total


# ---------------------------------------------------------------------------
# test command — explicit --url flag
# ---------------------------------------------------------------------------


class TestTestCommandWithUrl:
    @patch("cli.commands.test._run_tests", return_value=(4, 4))
    def test_uses_provided_url(self, mock_run):
        from cli.commands.test import test

        ctx = MagicMock()
        ctx.invoked_subcommand = None

        test(ctx=ctx, env="staging", url="https://custom.example.com/")

        mock_run.assert_called_once_with(
            "https://custom.example.com"
        )  # trailing slash stripped

    @patch("cli.commands.test._run_tests", return_value=(3, 4))
    def test_exits_1_when_tests_fail(self, mock_run):
        import click

        from cli.commands.test import test

        ctx = MagicMock()
        ctx.invoked_subcommand = None

        with pytest.raises(click.exceptions.Exit) as exc_info:
            test(ctx=ctx, env="staging", url="https://custom.example.com")

        assert exc_info.value.exit_code == 1


# ---------------------------------------------------------------------------
# test command — fetches URL from terraform when no --url
# ---------------------------------------------------------------------------


class TestTestCommandNoUrl:
    @patch("cli.commands.test._get_api_url", return_value="https://api.example.com")
    @patch("cli.commands.test._get_custom_domain_url", return_value=None)
    @patch("cli.commands.test._run_tests", return_value=(4, 4))
    def test_fetches_from_terraform(self, mock_run, mock_custom, mock_api):
        from cli.commands.test import test

        ctx = MagicMock()
        ctx.invoked_subcommand = None

        test(ctx=ctx, env="staging", url=None)

        mock_api.assert_called_once_with("staging")
        mock_run.assert_called_once_with("https://api.example.com")

    @patch("cli.commands.test._get_api_url", return_value=None)
    def test_exits_when_no_api_url(self, mock_api):
        import click

        from cli.commands.test import test

        ctx = MagicMock()
        ctx.invoked_subcommand = None

        with pytest.raises(click.exceptions.Exit):
            test(ctx=ctx, env="staging", url=None)

    @patch("cli.commands.test._get_api_url", return_value="https://api.example.com")
    @patch(
        "cli.commands.test._get_custom_domain_url",
        return_value="https://data.boston.gov",
    )
    @patch("cli.commands.test._run_tests", return_value=(4, 4))
    def test_also_tests_custom_domain(self, mock_run, mock_custom, mock_api):
        from cli.commands.test import test

        ctx = MagicMock()
        ctx.invoked_subcommand = None

        test(ctx=ctx, env="staging", url=None)

        assert mock_run.call_count == 2
        urls_tested = [call[0][0] for call in mock_run.call_args_list]
        assert "https://api.example.com" in urls_tested
        assert "https://data.boston.gov" in urls_tested
