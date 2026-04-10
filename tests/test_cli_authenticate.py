"""Tests for CLI authenticate command."""

import subprocess
from unittest.mock import patch

import click
import pytest


# ---------------------------------------------------------------------------
# Helper: build a mock CompletedProcess
# ---------------------------------------------------------------------------


def _ok(stdout="", stderr=""):
    return subprocess.CompletedProcess(
        args=[], returncode=0, stdout=stdout, stderr=stderr
    )


def _fail(stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr=stderr)


# ---------------------------------------------------------------------------
# _is_available
# ---------------------------------------------------------------------------


class TestIsAvailable:
    @patch("cli.commands.authenticate.subprocess.run")
    def test_returns_result_on_success(self, mock_run):
        mock_run.return_value = _ok("aws-cli/2.0.0")
        from cli.commands.authenticate import _is_available

        result = _is_available(["aws", "--version"])
        assert result is not None
        assert result.stdout == "aws-cli/2.0.0"

    @patch("cli.commands.authenticate.subprocess.run")
    def test_returns_none_on_failure(self, mock_run):
        mock_run.return_value = _fail()
        from cli.commands.authenticate import _is_available

        assert _is_available(["aws", "--version"]) is None

    @patch("cli.commands.authenticate.subprocess.run", side_effect=FileNotFoundError)
    def test_returns_none_when_not_found(self, mock_run):
        from cli.commands.authenticate import _is_available

        assert _is_available(["aws", "--version"]) is None


# ---------------------------------------------------------------------------
# _auto_install
# ---------------------------------------------------------------------------


class TestAutoInstall:
    @patch("cli.commands.authenticate.subprocess.run")
    def test_returns_true_on_success(self, mock_run):
        mock_run.return_value = _ok()
        from cli.commands.authenticate import _auto_install

        assert _auto_install("uv", ["pip", "install", "uv"], "uv") is True

    @patch("cli.commands.authenticate.subprocess.run")
    def test_returns_false_on_failure(self, mock_run):
        mock_run.return_value = _fail()
        from cli.commands.authenticate import _auto_install

        assert _auto_install("uv", ["pip", "install", "uv"], "uv") is False

    @patch("cli.commands.authenticate.subprocess.run", side_effect=FileNotFoundError)
    def test_returns_false_when_installer_missing(self, mock_run):
        from cli.commands.authenticate import _auto_install

        assert _auto_install("uv", ["nonexistent", "install", "uv"], "uv") is False


# ---------------------------------------------------------------------------
# _find_pip
# ---------------------------------------------------------------------------


class TestFindPip:
    @patch("cli.commands.authenticate.shutil.which")
    def test_finds_pip3(self, mock_which):
        mock_which.side_effect = lambda cmd: "/usr/bin/pip3" if cmd == "pip3" else None
        from cli.commands.authenticate import _find_pip

        assert _find_pip() == ["pip3"]

    @patch("cli.commands.authenticate.shutil.which")
    def test_finds_pip_fallback(self, mock_which):
        mock_which.side_effect = lambda cmd: "/usr/bin/pip" if cmd == "pip" else None
        from cli.commands.authenticate import _find_pip

        assert _find_pip() == ["pip"]

    @patch("cli.commands.authenticate.shutil.which", return_value=None)
    def test_returns_none_when_no_pip(self, mock_which):
        from cli.commands.authenticate import _find_pip

        assert _find_pip() is None


# ---------------------------------------------------------------------------
# authenticate — all checks pass
# ---------------------------------------------------------------------------


class TestAuthenticateAllPass:
    @patch("cli.commands.authenticate.shutil.which", return_value="/usr/bin/uv")
    @patch("cli.commands.authenticate._is_available")
    def test_all_pass_exits_zero(self, mock_avail, mock_which):
        def side_effect(cmd, timeout=10):
            if cmd == ["uv", "--version"]:
                return _ok("uv 0.9.0")
            if cmd == ["aws", "--version"]:
                return _ok("aws-cli/2.0.0 Python/3.11")
            if cmd == ["aws", "sts", "get-caller-identity"]:
                return _ok('{"Account": "123456789012"}')
            if cmd == ["terraform", "--version"]:
                return _ok("Terraform v1.5.0")
            return None

        mock_avail.side_effect = side_effect

        from cli.commands.authenticate import authenticate

        with patch("cli.commands.authenticate.sys") as mock_sys:
            mock_sys.version_info = (3, 11, 5, "final", 0)
            authenticate()


# ---------------------------------------------------------------------------
# authenticate — a check fails
# ---------------------------------------------------------------------------


class TestAuthenticateWithFailures:
    @patch("cli.commands.authenticate.shutil.which", return_value=None)
    @patch("cli.commands.authenticate._is_available", return_value=None)
    @patch("cli.commands.authenticate._find_pip", return_value=None)
    def test_all_fail_exits_nonzero(self, mock_pip, mock_avail, mock_which):
        from cli.commands.authenticate import authenticate

        with patch("cli.commands.authenticate.sys") as mock_sys:
            mock_sys.version_info = (3, 9, 0, "final", 0)
            with pytest.raises((SystemExit, click.exceptions.Exit)):
                authenticate()

    @patch("cli.commands.authenticate.shutil.which", return_value="/usr/bin/uv")
    @patch("cli.commands.authenticate._is_available")
    def test_only_credentials_fail(self, mock_avail, mock_which):
        """All tools installed but AWS credentials invalid → exit 1."""

        def side_effect(cmd, timeout=10):
            if cmd == ["uv", "--version"]:
                return _ok("uv 0.9.0")
            if cmd == ["aws", "--version"]:
                return _ok("aws-cli/2.0.0")
            if cmd == ["aws", "sts", "get-caller-identity"]:
                return None
            if cmd == ["terraform", "--version"]:
                return _ok("Terraform v1.5.0")
            return None

        mock_avail.side_effect = side_effect

        from cli.commands.authenticate import authenticate

        with patch("cli.commands.authenticate.sys") as mock_sys:
            mock_sys.version_info = (3, 11, 5, "final", 0)
            with pytest.raises((SystemExit, click.exceptions.Exit)):
                authenticate()


# ---------------------------------------------------------------------------
# authenticate — auto-install flow
# ---------------------------------------------------------------------------


class TestAuthenticateAutoInstall:
    @patch("cli.commands.authenticate.shutil.which")
    @patch("cli.commands.authenticate._is_available")
    @patch("cli.commands.authenticate._auto_install")
    @patch("cli.commands.authenticate._find_pip", return_value=["pip3"])
    def test_uv_auto_installed(self, mock_pip, mock_auto, mock_avail, mock_which):
        """uv missing initially → auto-installed → rechecked → pass."""
        call_count = {"uv_check": 0}

        def avail_side_effect(cmd, timeout=10):
            if cmd == ["uv", "--version"]:
                call_count["uv_check"] += 1
                if call_count["uv_check"] == 1:
                    return None  # First check: missing
                return _ok("uv 0.9.0")  # After install: present
            if cmd == ["aws", "--version"]:
                return _ok("aws-cli/2.0.0")
            if cmd == ["aws", "sts", "get-caller-identity"]:
                return _ok('{"Account": "123"}')
            if cmd == ["terraform", "--version"]:
                return _ok("Terraform v1.5.0")
            return None

        mock_avail.side_effect = avail_side_effect
        mock_auto.return_value = True
        mock_which.return_value = "/usr/bin/uv"

        from cli.commands.authenticate import authenticate

        with patch("cli.commands.authenticate.sys") as mock_sys:
            mock_sys.version_info = (3, 11, 5, "final", 0)
            authenticate()

        mock_auto.assert_called_once()
