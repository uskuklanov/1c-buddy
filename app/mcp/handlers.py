from __future__ import annotations

import logging
from typing import Optional

from .. import __version__
from .constants import MCP_SERVER_NAME
from .exceptions import ToolInputError, ToolNotFoundError
from .models import (
    InitializeParams,
    InitializeResult,
    ServerInfo,
    ToolsListResult,
    ToolDesc,
    ToolsCallParams,
    ToolsCallResult,
    ToolsCallTextContent,
)
from .service import McpToolService
from .session import McpSessionStore
from .tool_catalog import build_tool_definitions
from .upstream_tools_client import McpUpstreamToolsClient

logger = logging.getLogger(__name__)

__all__ = ["McpHandlers", "ToolNotFoundError"]


class McpHandlers:
    """HTTP presentation layer for MCP: JSON-RPC shapes and the session footer.

    All tool logic lives in McpToolService, which the stdio transport shares.
    """

    def __init__(self, mcp_client: McpUpstreamToolsClient, store: McpSessionStore):
        self.client = mcp_client
        self.store = store
        self.service = McpToolService(mcp_client)

    async def initialize(self, params: InitializeParams, protocol_version: str) -> InitializeResult:
        return InitializeResult(
            protocolVersion=protocol_version,
            serverInfo=ServerInfo(name=MCP_SERVER_NAME, version=__version__),
            capabilities={"tools": {}},
        )

    async def tools_list(self) -> ToolsListResult:
        definitions = build_tool_definitions(self.client.settings)
        return ToolsListResult(
            tools=[
                ToolDesc(
                    name=definition.name,
                    description=definition.description,
                    inputSchema=definition.input_schema,
                )
                for definition in definitions
            ]
        )

    async def tools_call(self, params: ToolsCallParams, session_id: Optional[str]) -> ToolsCallResult:
        try:
            result = await self.service.execute(params.name, params.arguments or {})
        except ToolInputError as e:
            # Input errors have always been an ordinary result carrying "Ошибка: ...",
            # not a JSON-RPC error. ToolNotFoundError and ApiError still propagate.
            return ToolsCallResult(content=[ToolsCallTextContent(text=e.message)])

        header = f"{result.title}:\n\n" if result.title else ""
        text = (
            f"{header}{result.text}"
            f"\n\nСессия: {session_id or '-'}"
            f"\nРазговор: {result.conversation_id}"
        )
        return ToolsCallResult(content=[ToolsCallTextContent(text=text)])
