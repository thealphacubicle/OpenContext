"""Tests for the CLI security command."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_dep(name: str, version: str, vulns: list[dict]) -> dict:
    return {"name": name, "version": version, "vulns": vulns}


def _make_vuln(
    vuln_id: str = "PYSEC-2024-1",
    fix_versions: list[str] | None = None,
    aliases: list[str] | None = None,
    description: str = "A test vulnerability.",
) -> dict:
    return {
        "id": vuln_id,
        "fix_versions": fix_versions or [],
        "aliases": aliases or [],
        "description": description,
    }


# ---------------------------------------------------------------------------
# _infer_severity
# ---------------------------------------------------------------------------


class TestInferSeverity:
    def test_cve_in_vuln_id_returns_high(self):
        from cli.commands.security import _infer_severity

        assert _infer_severity("CVE-2024-1234", []) == "HIGH"

    def test_cve_in_aliases_returns_high(self):
        from cli.commands.security import _infer_severity

        assert _infer_severity("PYSEC-2024-1", ["CVE-2024-9999"]) == "HIGH"

    def test_ghsa_only_returns_medium(self):
        from cli.commands.security import _infer_severity

        assert (
            _infer_severity("GHSA-xxxx-yyyy-zzzz", ["GHSA-xxxx-yyyy-zzzz"]) == "MEDIUM"
        )

    def test_no_cve_no_ghsa_returns_medium(self):
        from cli.commands.security import _infer_severity

        assert _infer_severity("PYSEC-2024-1", []) == "MEDIUM"


# ---------------------------------------------------------------------------
# _flatten_vulns
# ---------------------------------------------------------------------------


class TestFlattenVulns:
    def test_single_dep_single_vuln(self):
        from cli.commands.security import _flatten_vulns

        deps = [_make_dep("requests", "2.28.0", [_make_vuln(aliases=["CVE-2024-1"])])]
        findings = _flatten_vulns(deps)

        assert len(findings) == 1
        assert findings[0]["package"] == "requests"
        assert findings[0]["installed_version"] == "2.28.0"
        assert findings[0]["cve_ids"] == ["CVE-2024-1"]
        assert findings[0]["severity"] == "HIGH"

    def test_multiple_vulns_per_dep(self):
        from cli.commands.security import _flatten_vulns

        deps = [
            _make_dep(
                "httpx",
                "0.26.0",
                [
                    _make_vuln(vuln_id="CVE-2024-1"),
                    _make_vuln(vuln_id="PYSEC-2024-99"),
                ],
            )
        ]
        findings = _flatten_vulns(deps)
        assert len(findings) == 2

    def test_dep_with_no_vulns_excluded(self):
        from cli.commands.security import _flatten_vulns

        deps = [_make_dep("pyyaml", "6.0", [])]
        findings = _flatten_vulns(deps)
        assert findings == []

    def test_skipped_dep_excluded(self):
        from cli.commands.security import _flatten_vulns

        # Skipped deps have no "vulns" key, only "skip_reason"
        deps = [{"name": "some-pkg", "skip_reason": "Could not resolve version"}]
        findings = _flatten_vulns(deps)
        assert findings == []

    def test_fix_versions_populated(self):
        from cli.commands.security import _flatten_vulns

        deps = [_make_dep("aiohttp", "3.9.0", [_make_vuln(fix_versions=["3.9.5"])])]
        findings = _flatten_vulns(deps)
        assert findings[0]["fix_versions"] == ["3.9.5"]

    def test_empty_dependency_list(self):
        from cli.commands.security import _flatten_vulns

        assert _flatten_vulns([]) == []


# ---------------------------------------------------------------------------
# _run_pip_audit
# ---------------------------------------------------------------------------


class TestRunPipAudit:
    def test_returns_dependencies_on_success(self, tmp_path):
        from cli.commands.security import _run_pip_audit

        payload = json.dumps(
            {
                "dependencies": [
                    _make_dep("requests", "2.28.0", [_make_vuln()]),
                ],
                "fixes": [],
            }
        )

        with patch("cli.commands.security.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], 0, payload, "")
            result = _run_pip_audit(tmp_path)

        assert len(result) == 1
        assert result[0]["name"] == "requests"

    def test_returns_empty_list_when_no_vulns(self, tmp_path):
        from cli.commands.security import _run_pip_audit

        payload = json.dumps({"dependencies": [], "fixes": []})

        with patch("cli.commands.security.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], 0, payload, "")
            result = _run_pip_audit(tmp_path)

        assert result == []

    def test_pip_audit_exit_1_still_parsed(self, tmp_path):
        """pip-audit exits 1 when vulns found; output is still valid JSON."""
        from cli.commands.security import _run_pip_audit

        payload = json.dumps(
            {
                "dependencies": [_make_dep("httpx", "0.24.0", [_make_vuln()])],
                "fixes": [],
            }
        )

        with patch("cli.commands.security.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], 1, payload, "")
            result = _run_pip_audit(tmp_path)

        assert len(result) == 1

    def test_raises_file_not_found_when_not_installed(self, tmp_path):
        from cli.commands.security import _run_pip_audit

        with patch(
            "cli.commands.security.subprocess.run", side_effect=FileNotFoundError
        ):
            with pytest.raises(FileNotFoundError):
                _run_pip_audit(tmp_path)

    def test_raises_timeout_expired(self, tmp_path):
        from cli.commands.security import _run_pip_audit

        with patch(
            "cli.commands.security.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="pip-audit", timeout=120),
        ):
            with pytest.raises(subprocess.TimeoutExpired):
                _run_pip_audit(tmp_path)

    def test_raises_json_decode_error_on_bad_output(self, tmp_path):
        from cli.commands.security import _run_pip_audit

        with patch("cli.commands.security.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                [], 0, "not valid json", ""
            )
            with pytest.raises(RuntimeError):
                _run_pip_audit(tmp_path)

    def test_raises_runtime_error_on_tool_error_with_no_output(self, tmp_path):
        from cli.commands.security import _run_pip_audit

        with patch("cli.commands.security.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                [], 2, "", "Something broke"
            )
            with pytest.raises(RuntimeError, match="Something broke"):
                _run_pip_audit(tmp_path)

    def test_uses_requirements_txt_when_present(self, tmp_path):
        from cli.commands.security import _run_pip_audit

        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests>=2.28\n")

        payload = json.dumps({"dependencies": [], "fixes": []})

        with patch("cli.commands.security.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], 0, payload, "")
            result = _run_pip_audit(tmp_path)

        assert result == []


# ---------------------------------------------------------------------------
# _print_report — smoke tests (just confirm no crash)
# ---------------------------------------------------------------------------


class TestPrintReport:
    def test_no_findings_prints_all_clear(self, capsys):
        from cli.commands.security import _print_report

        # Should not raise
        _print_report([])

    def test_with_findings_renders_table(self):
        from cli.commands.security import _print_report

        findings = [
            {
                "package": "requests",
                "installed_version": "2.28.0",
                "vuln_id": "CVE-2024-1234",
                "cve_ids": ["CVE-2024-1234"],
                "fix_versions": ["2.32.0"],
                "description": "A serious vulnerability in requests.",
                "severity": "HIGH",
            }
        ]
        # Should not raise
        _print_report(findings)

    def test_medium_severity_finding(self):
        from cli.commands.security import _print_report

        findings = [
            {
                "package": "pyyaml",
                "installed_version": "6.0",
                "vuln_id": "PYSEC-2024-1",
                "cve_ids": [],
                "fix_versions": [],
                "description": "A medium severity issue.",
                "severity": "MEDIUM",
            }
        ]
        _print_report(findings)

    def test_long_description_truncated(self):
        from cli.commands.security import _print_report

        long_desc = "x" * 200
        findings = [
            {
                "package": "httpx",
                "installed_version": "0.24.0",
                "vuln_id": "CVE-2024-99",
                "cve_ids": ["CVE-2024-99"],
                "fix_versions": ["0.27.0"],
                "description": long_desc,
                "severity": "HIGH",
            }
        ]
        # Should not raise; description is truncated internally
        _print_report(findings)


# ---------------------------------------------------------------------------
# _export_report
# ---------------------------------------------------------------------------


class TestExportReport:
    def test_creates_file_with_timestamp_name(self, tmp_path):
        from cli.commands.security import _export_report

        findings = [
            {
                "package": "requests",
                "installed_version": "2.28.0",
                "vuln_id": "CVE-2024-1",
                "cve_ids": ["CVE-2024-1"],
                "fix_versions": ["2.32.0"],
                "description": "Test.",
                "severity": "HIGH",
            }
        ]
        output_path = _export_report(findings, tmp_path)

        assert output_path.exists()
        assert output_path.suffix == ".txt"
        assert "security-report-" in output_path.name

    def test_exported_file_contains_package_name(self, tmp_path):
        from cli.commands.security import _export_report

        findings = [
            {
                "package": "aiohttp",
                "installed_version": "3.9.0",
                "vuln_id": "CVE-2024-5",
                "cve_ids": ["CVE-2024-5"],
                "fix_versions": ["3.9.5"],
                "description": "An aiohttp issue.",
                "severity": "HIGH",
            }
        ]
        output_path = _export_report(findings, tmp_path)
        content = output_path.read_text()
        assert "aiohttp" in content

    def test_export_with_no_findings(self, tmp_path):
        from cli.commands.security import _export_report

        output_path = _export_report([], tmp_path)
        assert output_path.exists()
        content = output_path.read_text()
        assert "No vulnerabilities found" in content

    def test_export_summary_line_includes_count(self, tmp_path):
        from cli.commands.security import _export_report

        findings = [
            {
                "package": "requests",
                "installed_version": "2.28.0",
                "vuln_id": "CVE-2024-1",
                "cve_ids": ["CVE-2024-1"],
                "fix_versions": [],
                "description": "",
                "severity": "HIGH",
            },
            {
                "package": "pyyaml",
                "installed_version": "6.0",
                "vuln_id": "PYSEC-2024-2",
                "cve_ids": [],
                "fix_versions": [],
                "description": "",
                "severity": "MEDIUM",
            },
        ]
        output_path = _export_report(findings, tmp_path)
        content = output_path.read_text()
        assert "2 vulnerabilities found" in content


# ---------------------------------------------------------------------------
# security command — integration-style
# ---------------------------------------------------------------------------


class TestSecurityCommand:
    @patch("cli.commands.security.get_project_root")
    @patch("cli.commands.security._run_pip_audit", return_value=[])
    def test_all_clear_exits_zero(self, mock_audit, mock_root, tmp_path):
        from cli.commands.security import security

        mock_root.return_value = tmp_path
        ctx = MagicMock()
        ctx.invoked_subcommand = None

        # No findings means no Exit(1) raised
        security(ctx=ctx, export=False)

    @patch("cli.commands.security.get_project_root")
    @patch("cli.commands.security._run_pip_audit")
    def test_exits_one_when_vulns_found(self, mock_audit, mock_root, tmp_path):
        import click

        from cli.commands.security import security

        mock_root.return_value = tmp_path
        mock_audit.return_value = [
            _make_dep("requests", "2.28.0", [_make_vuln(aliases=["CVE-2024-1"])])
        ]
        ctx = MagicMock()
        ctx.invoked_subcommand = None

        with pytest.raises(click.exceptions.Exit) as exc_info:
            security(ctx=ctx, export=False)

        assert exc_info.value.exit_code == 1

    @patch("cli.commands.security.get_project_root")
    @patch(
        "cli.commands.security._run_pip_audit",
        side_effect=FileNotFoundError,
    )
    def test_exits_one_when_pip_audit_not_installed(
        self, mock_audit, mock_root, tmp_path
    ):
        import click

        from cli.commands.security import security

        mock_root.return_value = tmp_path
        ctx = MagicMock()
        ctx.invoked_subcommand = None

        with pytest.raises(click.exceptions.Exit) as exc_info:
            security(ctx=ctx, export=False)

        assert exc_info.value.exit_code == 1

    @patch("cli.commands.security.get_project_root")
    @patch(
        "cli.commands.security._run_pip_audit",
        side_effect=subprocess.TimeoutExpired(cmd="pip-audit", timeout=120),
    )
    def test_exits_one_on_timeout(self, mock_audit, mock_root, tmp_path):
        import click

        from cli.commands.security import security

        mock_root.return_value = tmp_path
        ctx = MagicMock()
        ctx.invoked_subcommand = None

        with pytest.raises(click.exceptions.Exit) as exc_info:
            security(ctx=ctx, export=False)

        assert exc_info.value.exit_code == 1

    @patch("cli.commands.security.get_project_root")
    @patch(
        "cli.commands.security._run_pip_audit",
        side_effect=RuntimeError("pip-audit error"),
    )
    def test_exits_one_on_runtime_error(self, mock_audit, mock_root, tmp_path):
        import click

        from cli.commands.security import security

        mock_root.return_value = tmp_path
        ctx = MagicMock()
        ctx.invoked_subcommand = None

        with pytest.raises(click.exceptions.Exit) as exc_info:
            security(ctx=ctx, export=False)

        assert exc_info.value.exit_code == 1

    @patch("cli.commands.security.get_project_root")
    @patch("cli.commands.security._run_pip_audit", return_value=[])
    def test_export_creates_report_file(self, mock_audit, mock_root, tmp_path):
        from cli.commands.security import security

        mock_root.return_value = tmp_path
        ctx = MagicMock()
        ctx.invoked_subcommand = None

        security(ctx=ctx, export=True)

        report_files = list(tmp_path.glob("security-report-*.txt"))
        assert len(report_files) == 1

    @patch("cli.commands.security.get_project_root")
    @patch("cli.commands.security._run_pip_audit")
    def test_export_flag_writes_file_with_findings(
        self, mock_audit, mock_root, tmp_path
    ):
        import click

        from cli.commands.security import security

        mock_root.return_value = tmp_path
        mock_audit.return_value = [
            _make_dep("requests", "2.28.0", [_make_vuln(aliases=["CVE-2024-1"])])
        ]
        ctx = MagicMock()
        ctx.invoked_subcommand = None

        with pytest.raises(click.exceptions.Exit):
            security(ctx=ctx, export=True)

        report_files = list(tmp_path.glob("security-report-*.txt"))
        assert len(report_files) == 1
        content = report_files[0].read_text()
        assert "requests" in content

    def test_skips_when_subcommand_invoked(self):
        from cli.commands.security import security

        ctx = MagicMock()
        ctx.invoked_subcommand = "some-subcommand"

        # Should return immediately without doing any work
        result = security(ctx=ctx, export=False)
        assert result is None


# ---------------------------------------------------------------------------
# CLI registration smoke test
# ---------------------------------------------------------------------------


class TestSecurityRegisteredInMain:
    def test_security_app_importable_from_main(self):
        from cli.main import app

        command_names = [c.name for c in app.registered_groups]
        assert "security" in command_names
