"""Hermetic integration: CLI MCP probe against local aiohttp server."""

from __future__ import annotations

import asyncio

import pytest

from cli.commands.test import _run_tests

from tests.integration.local_server import start_local_mcp_server


@pytest.mark.asyncio
async def test_run_tests_protocol_against_local_server(
    integration_fake_config_dict: dict,
) -> None:
    base_url, shutdown = await start_local_mcp_server(integration_fake_config_dict)
    try:
        # _run_tests uses sync httpx; run it in a thread so the aiohttp loop stays responsive.
        passed, total = await asyncio.to_thread(_run_tests, base_url)
    finally:
        await shutdown()

    assert total == 4
    assert passed == 4
