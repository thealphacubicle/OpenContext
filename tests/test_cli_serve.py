"""Tests for CLI serve command."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typer
import yaml

from cli.commands.serve import (
    _derive_server_name,
    _load_config,
    _run_server,
    serve,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def config_file(tmp_path: Path) -> Path:
    """Write a minimal valid config.yaml to tmp_path and return its path."""
    cfg = {
        "server_name": "Test MCP",
        "plugins": {
            "ckan": {
                "enabled": True,
                "base_url": "https://data.example.gov",
                "city_name": "Testville",
                "timeout": 30,
            }
        },
        "logging": {"level": "INFO", "format": "json"},
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.dump(cfg))
    return path


# ---------------------------------------------------------------------------
# _load_config
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_loads_valid_yaml(self, config_file: Path) -> None:
        cfg, resolved = _load_config(str(config_file))
        assert cfg["server_name"] == "Test MCP"
        assert resolved == config_file.resolve()

    def test_missing_file_raises_exit(self, tmp_path: Path) -> None:
        with pytest.raises(typer.Exit):
            _load_config(str(tmp_path / "nonexistent.yaml"))


# ---------------------------------------------------------------------------
# _derive_server_name
# ---------------------------------------------------------------------------


class TestDeriveServerName:
    def test_uses_city_name_from_enabled_plugin(self) -> None:
        config = {
            "plugins": {
                "ckan": {"enabled": True, "city_name": "New York"},
            }
        }
        assert _derive_server_name(config) == "new-york-opendata"

    def test_uses_organization_when_no_city_name(self) -> None:
        config = {
            "plugins": {
                "arcgis": {"enabled": True, "organization": "County GIS"},
            }
        }
        assert _derive_server_name(config) == "county-gis-opendata"

    def test_skips_disabled_plugins(self) -> None:
        config = {
            "plugins": {
                "ckan": {"enabled": False, "city_name": "Boston"},
            },
            "server_name": "Fallback Server",
        }
        result = _derive_server_name(config)
        assert result == "fallback-server"

    def test_falls_back_to_lambda_name(self) -> None:
        config = {"aws": {"lambda_name": "my-city-mcp"}}
        assert _derive_server_name(config) == "my-city"

    def test_falls_back_to_server_name(self) -> None:
        config = {"server_name": "Boston OpenData MCP"}
        assert _derive_server_name(config) == "boston-opendata-mcp"

    def test_default_fallback(self) -> None:
        assert _derive_server_name({}) == "opencontext-mcp"


# ---------------------------------------------------------------------------
# serve — default port (8000)
# ---------------------------------------------------------------------------


class TestServeDefaultPort:
    def test_default_port_is_8000(self, config_file: Path) -> None:
        """When --port is not given, 8000 is passed to _run_server."""
        captured: dict = {}

        async def _fake_run(config: dict, port: int) -> None:
            captured["port"] = port

        mock_run_server = AsyncMock(side_effect=_fake_run)

        with (
            patch("cli.commands.serve._load_config", return_value=({}, config_file)),
            patch("cli.commands.serve._run_server", mock_run_server),
        ):
            ctx = MagicMock()
            ctx.invoked_subcommand = None
            serve(ctx=ctx, port=8000, config=str(config_file))

        assert captured.get("port") == 8000


# ---------------------------------------------------------------------------
# serve — default config path
# ---------------------------------------------------------------------------


class TestServeDefaultConfigPath:
    def test_default_config_path_is_config_yaml(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When --config is empty and OPENCONTEXT_CONFIG not set, 'config.yaml' is used."""
        monkeypatch.delenv("OPENCONTEXT_CONFIG", raising=False)

        captured: dict = {}

        def _fake_load(path: str) -> tuple[dict, Path]:
            captured["path"] = path
            return {}, tmp_path / "config.yaml"

        with (
            patch("cli.commands.serve._load_config", side_effect=_fake_load),
            patch("cli.commands.serve._run_server", AsyncMock()),
        ):
            ctx = MagicMock()
            ctx.invoked_subcommand = None
            serve(ctx=ctx, port=8000, config="")

        assert captured["path"] == "config.yaml"


# ---------------------------------------------------------------------------
# serve — --port flag
# ---------------------------------------------------------------------------


class TestServePortFlag:
    def test_custom_port_passed_to_run_server(self, config_file: Path) -> None:
        captured: dict = {}

        async def _fake_run(config: dict, port: int) -> None:
            captured["port"] = port

        mock_run_server = AsyncMock(side_effect=_fake_run)

        with (
            patch("cli.commands.serve._load_config", return_value=({}, config_file)),
            patch("cli.commands.serve._run_server", mock_run_server),
        ):
            ctx = MagicMock()
            ctx.invoked_subcommand = None
            serve(ctx=ctx, port=9090, config=str(config_file))

        assert captured.get("port") == 9090


# ---------------------------------------------------------------------------
# serve — --config flag
# ---------------------------------------------------------------------------


class TestServeConfigFlag:
    def test_explicit_config_path_is_used(self, config_file: Path) -> None:
        captured: dict = {}

        def _fake_load(path: str) -> tuple[dict, Path]:
            captured["path"] = path
            return {}, config_file

        with (
            patch("cli.commands.serve._load_config", side_effect=_fake_load),
            patch("cli.commands.serve._run_server", AsyncMock()),
        ):
            ctx = MagicMock()
            ctx.invoked_subcommand = None
            serve(ctx=ctx, port=8000, config=str(config_file))

        assert captured["path"] == str(config_file)


# ---------------------------------------------------------------------------
# serve — OPENCONTEXT_CONFIG env var
# ---------------------------------------------------------------------------


class TestServeEnvVar:
    def test_env_var_used_when_config_flag_absent(
        self, config_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENCONTEXT_CONFIG", str(config_file))

        captured: dict = {}

        def _fake_load(path: str) -> tuple[dict, Path]:
            captured["path"] = path
            return {}, config_file

        with (
            patch("cli.commands.serve._load_config", side_effect=_fake_load),
            patch("cli.commands.serve._run_server", AsyncMock()),
        ):
            ctx = MagicMock()
            ctx.invoked_subcommand = None
            serve(ctx=ctx, port=8000, config="")

        assert captured["path"] == str(config_file)

    def test_explicit_config_flag_overrides_env_var(
        self, config_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        other = tmp_path / "other.yaml"
        other.write_text(yaml.dump({"server_name": "other"}))
        monkeypatch.setenv("OPENCONTEXT_CONFIG", str(config_file))

        captured: dict = {}

        def _fake_load(path: str) -> tuple[dict, Path]:
            captured["path"] = path
            return {}, other

        with (
            patch("cli.commands.serve._load_config", side_effect=_fake_load),
            patch("cli.commands.serve._run_server", AsyncMock()),
        ):
            ctx = MagicMock()
            ctx.invoked_subcommand = None
            serve(ctx=ctx, port=8000, config=str(other))

        assert captured["path"] == str(other)


# ---------------------------------------------------------------------------
# _run_server — startup initialises PluginManager and MCPServer
# ---------------------------------------------------------------------------


def _make_aiohttp_mocks():
    """Return a dict of mocks needed to stub out aiohttp in _run_server."""
    mock_app = MagicMock()
    mock_app.router.add_post = MagicMock()

    mock_runner = AsyncMock()
    mock_site = AsyncMock()

    mock_event_instance = MagicMock()
    mock_event_instance.wait = AsyncMock(side_effect=KeyboardInterrupt)

    return {
        "app": mock_app,
        "runner": mock_runner,
        "site": mock_site,
        "event_instance": mock_event_instance,
    }


class TestRunServerStartup:
    def _make_plugin_manager(self) -> MagicMock:
        pm = MagicMock()
        pm.load_plugins = AsyncMock()
        pm.shutdown = AsyncMock()
        pm.plugins = {"ckan": MagicMock()}
        pm.get_all_tools.return_value = [MagicMock(), MagicMock()]
        return pm

    def test_plugin_manager_load_plugins_called(self, config_file: Path) -> None:
        config = yaml.safe_load(config_file.read_text())
        pm = self._make_plugin_manager()
        mocks = _make_aiohttp_mocks()

        with (
            patch("cli.commands.serve.configure_json_logging"),
            patch(
                "cli.commands.serve.get_logging_config", return_value={"level": "INFO"}
            ),
            patch("cli.commands.serve.PluginManager", return_value=pm),
            patch("cli.commands.serve.MCPServer"),
            patch("cli.commands.serve.web.Application", return_value=mocks["app"]),
            patch("cli.commands.serve.web.AppRunner", return_value=mocks["runner"]),
            patch("cli.commands.serve.web.TCPSite", return_value=mocks["site"]),
            patch(
                "cli.commands.serve.asyncio.Event", return_value=mocks["event_instance"]
            ),
        ):
            asyncio.run(_run_server(config, port=8000))

        pm.load_plugins.assert_awaited_once()

    def test_mcp_server_initialised_with_plugin_manager(
        self, config_file: Path
    ) -> None:
        config = yaml.safe_load(config_file.read_text())
        pm = self._make_plugin_manager()
        mocks = _make_aiohttp_mocks()

        with (
            patch("cli.commands.serve.configure_json_logging"),
            patch(
                "cli.commands.serve.get_logging_config", return_value={"level": "INFO"}
            ),
            patch("cli.commands.serve.PluginManager", return_value=pm),
            patch("cli.commands.serve.MCPServer") as mock_mcp_cls,
            patch("cli.commands.serve.web.Application", return_value=mocks["app"]),
            patch("cli.commands.serve.web.AppRunner", return_value=mocks["runner"]),
            patch("cli.commands.serve.web.TCPSite", return_value=mocks["site"]),
            patch(
                "cli.commands.serve.asyncio.Event", return_value=mocks["event_instance"]
            ),
        ):
            asyncio.run(_run_server(config, port=8000))

        mock_mcp_cls.assert_called_once_with(pm)


# ---------------------------------------------------------------------------
# _run_server — graceful shutdown calls plugin_manager.shutdown()
# ---------------------------------------------------------------------------


class TestRunServerShutdown:
    def test_shutdown_called_on_keyboard_interrupt(self, config_file: Path) -> None:
        config = yaml.safe_load(config_file.read_text())
        pm = MagicMock()
        pm.load_plugins = AsyncMock()
        pm.shutdown = AsyncMock()
        pm.plugins = {}
        pm.get_all_tools.return_value = []
        mocks = _make_aiohttp_mocks()

        with (
            patch("cli.commands.serve.configure_json_logging"),
            patch(
                "cli.commands.serve.get_logging_config", return_value={"level": "INFO"}
            ),
            patch("cli.commands.serve.PluginManager", return_value=pm),
            patch("cli.commands.serve.MCPServer"),
            patch("cli.commands.serve.web.Application", return_value=mocks["app"]),
            patch("cli.commands.serve.web.AppRunner", return_value=mocks["runner"]),
            patch("cli.commands.serve.web.TCPSite", return_value=mocks["site"]),
            patch(
                "cli.commands.serve.asyncio.Event", return_value=mocks["event_instance"]
            ),
        ):
            asyncio.run(_run_server(config, port=8000))

        pm.shutdown.assert_awaited_once()


# ---------------------------------------------------------------------------
# serve — config file not found produces clear error
# ---------------------------------------------------------------------------


class TestServeConfigNotFound:
    def test_missing_config_exits_with_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OPENCONTEXT_CONFIG", raising=False)

        with pytest.raises(typer.Exit):
            ctx = MagicMock()
            ctx.invoked_subcommand = None
            serve(ctx=ctx, port=8000, config=str(tmp_path / "missing.yaml"))


# ---------------------------------------------------------------------------
# Registration in cli/main.py
# ---------------------------------------------------------------------------


class TestServeRegistered:
    def test_serve_typer_registered_in_app(self) -> None:
        """serve_app must be mounted under the 'serve' name in the main app."""
        from cli.main import app

        group_names = [g.name or "" for g in app.registered_groups]
        assert "serve" in group_names, (
            f"'serve' not found in registered groups: {group_names}"
        )
