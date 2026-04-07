"""Shared pytest fixtures and sys.modules stubs for the OpenContext test suite.

boto3 and botocore are listed as project dependencies in pyproject.toml and will
be present in any standard install (``uv sync --all-extras``).  The lightweight
stubs below act as a fallback for minimal/partial installs that omit the AWS SDK
— they allow import-time resolution of CLI modules that reference boto3 at the
top level so the rest of the test suite can still run.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock


def _make_boto3_stub() -> types.ModuleType:
    """Return a minimal boto3 stub sufficient for import-time resolution."""
    boto3_mod = types.ModuleType("boto3")

    # boto3.client() returns a MagicMock by default — tests that care about
    # specific S3 responses should patch cli.commands.configure._ensure_state_bucket
    # or boto3.client directly in their own setUp / patch context.
    boto3_mod.client = MagicMock(return_value=MagicMock())
    return boto3_mod


def _make_botocore_stub() -> types.ModuleType:
    """Return a minimal botocore stub that satisfies `import botocore.exceptions`."""
    botocore_mod = types.ModuleType("botocore")

    exceptions_mod = types.ModuleType("botocore.exceptions")

    class ClientError(Exception):
        def __init__(self, error_response: dict, operation_name: str) -> None:
            self.response = error_response
            super().__init__(str(error_response))

    exceptions_mod.ClientError = ClientError  # type: ignore[attr-defined]
    botocore_mod.exceptions = exceptions_mod  # type: ignore[attr-defined]

    return botocore_mod, exceptions_mod


# Install stubs only when the real packages are absent so that environments
# that have boto3 installed (e.g. CI with full deps) continue to use the real
# library.
if "boto3" not in sys.modules:
    sys.modules["boto3"] = _make_boto3_stub()

if "botocore" not in sys.modules:
    botocore_stub, botocore_exceptions_stub = _make_botocore_stub()
    sys.modules["botocore"] = botocore_stub
    sys.modules["botocore.exceptions"] = botocore_exceptions_stub
