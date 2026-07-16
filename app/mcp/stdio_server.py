"""MCP stdio transport built on the official low-level Server.

The only module that imports the MCP SDK. stdout belongs to the SDK: never
print() here, and never import app.main, whose logging goes to stdout.

Tool schemas and execution come from the shared layer, so stdio and the HTTP
/mcp endpoint cannot drift apart.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict

import mcp.types as types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

from .. import __version__
from ..config import Settings, get_settings
from ..onec_models import ApiError
from .constants import MCP_SERVER_NAME
from .exceptions import ToolInputError, ToolNotFoundError
from .service import McpToolService
from .tool_catalog import build_tool_definitions
from .upstream_tools_client import McpUpstreamToolsClient

logger = logging.getLogger(__name__)


@dataclass
class StdioContext:
    settings: Settings
    client: McpUpstreamToolsClient
    service: McpToolService


def _error_result(text: str) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=text)],
        isError=True,
    )


def _describe_api_error(error: ApiError) -> str:
    """User-facing text for an upstream failure.

    Never leaks the token, proxy credentials, the upstream response body or a
    traceback: only the class of failure.
    """
    status = error.status_code
    if status in (401, 403):
        return (
            "Ошибка: 1C.ai отклонил запрос (нет доступа). "
            "Проверьте ONEC_AI_TOKEN и права доступа."
        )
    if status == 429:
        return "Ошибка: превышен лимит запросов к 1C.ai. Повторите попытку позже."
    if status is not None and status >= 500:
        return "Ошибка: сервис 1C.ai временно недоступен. Повторите попытку позже."
    if status is None:
        return "Ошибка: сетевая ошибка при обращении к 1C.ai."
    return "Ошибка: 1C.ai вернул ошибку при обработке запроса."


def build_server(server_name: str = MCP_SERVER_NAME) -> Server:
    @asynccontextmanager
    async def lifespan(_server: Server) -> AsyncIterator[StdioContext]:
        settings = get_settings()
        client = McpUpstreamToolsClient(settings)
        try:
            yield StdioContext(
                settings=settings,
                client=client,
                service=McpToolService(client),
            )
        finally:
            await client.close()

    server: Server = Server(server_name, version=__version__, lifespan=lifespan)

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        context: StdioContext = server.request_context.lifespan_context
        return [
            types.Tool(
                name=definition.name,
                description=definition.description,
                inputSchema=definition.input_schema,
            )
            for definition in build_tool_definitions(context.settings)
        ]

    # validate_input=False on purpose: validation.py is the single arbiter, so
    # both transports return the same Russian messages instead of the SDK's
    # English jsonschema text.
    @server.call_tool(validate_input=False)
    async def call_tool(name: str, arguments: Dict[str, Any]) -> types.CallToolResult:
        context: StdioContext = server.request_context.lifespan_context
        try:
            result = await context.service.execute(name, arguments or {})
        except ToolInputError as e:
            return _error_result(e.message)
        except ToolNotFoundError as e:
            return _error_result(f"Инструмент не найден: {e.tool_name}")
        except ApiError as e:
            logger.warning("Upstream error for tool %s: status=%s", name, e.status_code)
            return _error_result(_describe_api_error(e))
        except Exception:
            logger.exception("Unexpected error while running tool %s", name)
            return _error_result("Непредвиденная ошибка при обращении к 1C.ai")

        return types.CallToolResult(
            content=[types.TextContent(type="text", text=result.text)],
            isError=False,
        )

    return server


async def run_stdio() -> None:
    server = build_server()
    options = InitializationOptions(
        server_name=MCP_SERVER_NAME,
        server_version=__version__,
        capabilities=server.get_capabilities(
            notification_options=NotificationOptions(),
            experimental_capabilities={},
        ),
    )
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options)
