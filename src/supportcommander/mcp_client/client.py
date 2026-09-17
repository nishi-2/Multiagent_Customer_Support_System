from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import dotenv_values
from fastmcp import Client
from fastmcp.client.transports import (
    StdioTransport,
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[3]
)


SERVER_PATH = (
    PROJECT_ROOT
    / "src"
    / "supportcommander"
    / "mcp_server"
    / "server.py"
)


def build_server_environment() -> dict[str, str]:
    """
    Build the environment passed to the
    FastMCP STDIO subprocess.

    Values already present in the running
    process override .env values.

    This matters because:
      local -> MONGO_HOST=localhost
      Docker -> MONGO_HOST=mongo
    """

    dotenv_values_map = dotenv_values(
        PROJECT_ROOT / ".env"
    )

    merged = {
        key: value
        for key, value
        in dotenv_values_map.items()
        if value is not None
    }

    merged.update(
        os.environ
    )

    merged[
        "PYTHONPATH"
    ] = str(
        PROJECT_ROOT / "src"
    )

    return {
        str(key): str(value)
        for key, value
        in merged.items()
    }


def create_mcp_client() -> Client:

    transport = StdioTransport(
        command=sys.executable,
        args=[
            str(SERVER_PATH),
        ],
        env=(
            build_server_environment()
        ),
        cwd=str(
            PROJECT_ROOT
        ),
    )

    return Client(transport)


# Module-level shared client — initialized once at app startup via startup_mcp().
_shared_client: Client | None = None


async def startup_mcp() -> None:
    global _shared_client
    _shared_client = create_mcp_client()
    await _shared_client.__aenter__()


async def shutdown_mcp() -> None:
    global _shared_client
    if _shared_client is not None:
        try:
            await _shared_client.__aexit__(None, None, None)
        except Exception:
            pass
        _shared_client = None


def get_shared_client() -> Client:
    if _shared_client is None:
        raise RuntimeError(
            "MCP client is not initialized. "
            "Ensure startup_mcp() ran during app lifespan."
        )
    return _shared_client
