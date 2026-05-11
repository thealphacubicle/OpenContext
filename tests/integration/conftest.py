"""Fixtures for hermetic integration tests."""

from __future__ import annotations

import json
from typing import Any, Dict, Generator

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def integration_fake_config_dict() -> Dict[str, Any]:
    """Minimal valid config with only the fake integration plugin enabled."""
    return {
        "server_name": "Integration Test MCP",
        "organization": "Test Org",
        "plugins": {
            "integration_test_fake": {"enabled": True},
            "ckan": {"enabled": False},
            "arcgis": {"enabled": False},
            "socrata": {"enabled": False},
        },
        "aws": {"region": "us-east-1"},
        "logging": {"level": "WARNING", "format": "json"},
    }


@pytest.fixture
def opencontext_config_env(
    integration_fake_config_dict: Dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENCONTEXT_CONFIG", json.dumps(integration_fake_config_dict))


@pytest.fixture
def reset_http_handler_globals() -> Generator[None, None, None]:
    """Clear UniversalHTTPHandler module singletons between tests."""
    import server.http_handler as hh

    hh._config = None
    hh._plugin_manager = None
    hh._mcp_server = None
    yield
    hh._config = None
    hh._plugin_manager = None
    hh._mcp_server = None


@pytest.fixture
def reset_lambda_adapter_handler() -> Generator[None, None, None]:
    """Reset Lambda adapter handler singleton."""
    import server.adapters.aws_lambda as lam

    lam._handler = None
    yield
    lam._handler = None
