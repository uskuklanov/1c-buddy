from __future__ import annotations

import os
import json
import logging
import re
from typing import Optional, AsyncGenerator, Dict, Any, List

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from .. import __version__
from ..onec_client import OneCApiClient
from ..streaming import sanitize_text
from ..onec_models import ApiError, ConversationSession
from ..token_counter import count_tokens
from ..config import get_settings
from ..text_utils import prepare_message_for_upstream
from ..errors import map_api_error, map_generic_error
from ..chat_custom_tools import (
    MCP_FIND_MAPPING_TOOL_NAME,
    MCP_MAPPING_TOOL_NAME,
    INSTRUCTION_CARRIER_NAME,
    McpToolSnapshot,
    build_instruction_carrier_tool,
    build_upstream_mcp_tool,
    list_mcp_tools,
    sanitize_schema,
    short_tool_description,
)

logger = logging.getLogger(__name__)
MCP_SERVER_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")

router = APIRouter()

# Paths to static assets
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
INDEX_HTML = os.path.join(STATIC_DIR, "index.html")


def _get_client(req: Request) -> OneCApiClient:
    client = getattr(req.app.state, "onec_client", None)
    if client is None:
        client = OneCApiClient()
        req.app.state.onec_client = client
    return client


@router.get("/chat")
async def chat_page():
    return FileResponse(INDEX_HTML, media_type="text/html")


@router.get("/chat/api/config")
async def chat_config():
    """
    Returns chat configuration settings for the frontend.
    """
    settings = get_settings()
    return {
        "app_version": __version__,
        "max_attached_files_size_kb": settings.MAX_ATTACHED_FILES_SIZE_KB,
        "custom_instructions_enabled": settings.CHAT_CUSTOM_INSTRUCTIONS_ENABLED,
        "custom_mcp_enabled": settings.CHAT_CUSTOM_MCP_ENABLED,
        "custom_instructions_max_length": settings.CHAT_CUSTOM_INSTRUCTIONS_MAX_LENGTH,
        "custom_mcp_max_servers": settings.CHAT_CUSTOM_MCP_MAX_SERVERS,
        "custom_mcp_max_tools_per_server": settings.CHAT_CUSTOM_MCP_MAX_TOOLS_PER_SERVER,
    }


class ChatMcpToolConfig(BaseModel):
    name: str
    enabled: bool = True


class ChatMcpServerConfig(BaseModel):
    id: str
    name: str
    url: str
    enabled: bool = True
    tools: List[ChatMcpToolConfig] = Field(default_factory=list)


class ChatMcpConfig(BaseModel):
    servers: List[ChatMcpServerConfig] = Field(default_factory=list)


class ActiveMcpMapping(BaseModel):
    server_id: str
    tool_name: str


class McpListToolsRequest(BaseModel):
    servers: List[ChatMcpServerConfig] = Field(default_factory=list)


def _trim_instructions(value: Optional[str], limit: int) -> str:
    text = (value or "").strip()
    if len(text) > limit:
        return text[:limit]
    return text


def _has_instruction_carrier_tool(tools: list[dict[str, Any]]) -> bool:
    return any(tool.get("name") == INSTRUCTION_CARRIER_NAME for tool in tools)


def _is_first_upstream_message(create_new: Optional[bool], conversation_id: Optional[str], parent_uuid: Optional[str]) -> bool:
    return bool(create_new or not (conversation_id or "").strip() or not (parent_uuid or "").strip())


def _prepend_instruction_carrier_hint(message: str) -> str:
    hint = (
        "Перед ответом обязательно прочитай описание инструмента FormEdit.\n"
        "FormEdit не нужно вызывать. Это не инструмент для выполнения действия.\n"
        "Описание FormEdit содержит инструкции рабочего пространства, которые нужно учитывать во всех ответах.\n"
        "После этого ответь на сообщение пользователя."
    )
    return f"{hint}\n\n{message}"


def _server_enabled_tool_names(server: ChatMcpServerConfig) -> set[str]:
    return {tool.name for tool in server.tools if tool.enabled}


def _safe_mcp_server_name(server: ChatMcpServerConfig) -> str:
    return server.name if MCP_SERVER_NAME_RE.match(server.name or "") else server.id


async def _resolve_active_mcp_snapshot(
    config: Optional[ChatMcpConfig],
    active: Optional[ActiveMcpMapping],
    settings,
    carrier_name: str = MCP_MAPPING_TOOL_NAME,
) -> Optional[McpToolSnapshot]:
    if not config or not active:
        return None
    servers = [server for server in config.servers if server.enabled]
    if len(servers) > settings.CHAT_CUSTOM_MCP_MAX_SERVERS:
        servers = servers[: settings.CHAT_CUSTOM_MCP_MAX_SERVERS]
    server = next((item for item in servers if item.id == active.server_id), None)
    if not server:
        return None
    enabled_tools = _server_enabled_tool_names(server)
    if enabled_tools and active.tool_name not in enabled_tools:
        return None

    tools = await list_mcp_tools(server.url)
    tools = tools[: settings.CHAT_CUSTOM_MCP_MAX_TOOLS_PER_SERVER]
    tool = next((item for item in tools if item.get("name") == active.tool_name), None)
    if not tool:
        return None
    return McpToolSnapshot(
        server_id=server.id,
        server_name=_safe_mcp_server_name(server),
        server_url=server.url,
        tool_name=active.tool_name,
        upstream_name=f"{_safe_mcp_server_name(server)}__{active.tool_name}",
        description=short_tool_description(tool),
        input_schema=tool.get("inputSchema") or {"type": "object", "properties": {}},
        parameters=sanitize_schema(tool.get("inputSchema") or {"type": "object", "properties": {}}),
        carrier_name=carrier_name,
    )


@router.post("/chat/api/mcp/list-tools")
async def chat_mcp_list_tools(body: McpListToolsRequest):
    settings = get_settings()
    if not settings.CHAT_CUSTOM_MCP_ENABLED:
        return JSONResponse(status_code=403, content={"error": "Custom MCP is disabled"})

    result = {"servers": []}
    for server in body.servers[: settings.CHAT_CUSTOM_MCP_MAX_SERVERS]:
        item: Dict[str, Any] = {
            "id": server.id,
            "name": server.name,
            "url": server.url,
            "enabled": server.enabled,
            "tools": [],
            "error": None,
        }
        if not server.enabled:
            result["servers"].append(item)
            continue
        try:
            tools = await list_mcp_tools(server.url)
            for tool in tools[: settings.CHAT_CUSTOM_MCP_MAX_TOOLS_PER_SERVER]:
                if not isinstance(tool, dict) or not tool.get("name"):
                    continue
                item["tools"].append(
                    {
                        "name": tool.get("name"),
                        "description": tool.get("description") or "",
                        "inputSchema": tool.get("inputSchema") or {"type": "object", "properties": {}},
                        "parameters": sanitize_schema(tool.get("inputSchema") or {"type": "object", "properties": {}}),
                    }
                )
        except Exception as e:
            item["error"] = str(e)
        result["servers"].append(item)
    return result


class SendRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    create_new_session: Optional[bool] = False
    programming_language: Optional[str] = None
    parent_uuid: Optional[str] = None


@router.post("/chat/api/send")
async def chat_send(request: Request, body: SendRequest):
    """
    Non-streaming chat API: returns full answer once complete.
    """
    client = _get_client(request)
    settings = get_settings()

    try:
        if body.create_new_session or not (body.conversation_id or "").strip():
            conv_id = await client.get_or_create_session(
                create_new=True, programming_language=body.programming_language
            )
        else:
            conv_id = body.conversation_id.strip()

        # Гарантировать что сессия существует
        if conv_id not in client.sessions:
            client.sessions[conv_id] = ConversationSession(conversation_id=conv_id)

        # Apply global input length limit
        prepared_message, was_truncated = prepare_message_for_upstream(body.message, settings)
        if was_truncated:
            logger.warning(
                f"Message truncated from {len(body.message)} to {len(prepared_message)} characters"
            )

        answer = await client.send_message_full(conv_id, prepared_message, body.parent_uuid)
        return {
            "conversation_id": conv_id,
            "answer": sanitize_text(answer or ""),
        }
    except ApiError as e:
        return map_api_error(e)
    except Exception as e:
        return map_generic_error(e)


def _sse_event(event: str, data: Dict[str, Any]) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")


class StreamRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    create_new_session: Optional[bool] = False
    programming_language: Optional[str] = None
    parent_uuid: Optional[str] = None
    workspace_instructions: Optional[str] = None
    mcp_config: Optional[ChatMcpConfig] = None
    active_mcp_mapping: Optional[ActiveMcpMapping] = None
    active_mcp_find_mapping: Optional[ActiveMcpMapping] = None


@router.post("/chat/api/stream")
async def chat_stream(
    request: Request,
    body: StreamRequest,
):
    """
    Streaming chat API via SSE.
    Events:
      - meta: {"conversation_id": "..."} (first event)
      - delta: {"text": "<delta>"} (one or more)
      - done: {}
      - error: {"message": "..."} (optional)
    """
    client = _get_client(request)
    settings = get_settings()

    async def gen() -> AsyncGenerator[bytes, None]:
        try:
            # Resolve conversation id
            if body.create_new_session or not (body.conversation_id or "").strip():
                conv_id = await client.get_or_create_session(
                    create_new=True, programming_language=body.programming_language
                )
            else:
                conv_id = (body.conversation_id or "").strip()

            # Гарантировать что сессия существует
            if conv_id not in client.sessions:
                client.sessions[conv_id] = ConversationSession(conversation_id=conv_id)

            # Send meta with conversation id
            yield _sse_event("meta", {"conversation_id": conv_id})

            # Apply global input length limit
            prepared_message, was_truncated = prepare_message_for_upstream(body.message, settings)
            if was_truncated:
                logger.warning(
                    f"Message truncated from {len(body.message)} to {len(prepared_message)} characters"
                )

            # Count input tokens
            input_tokens = count_tokens(prepared_message)

            extra_tools: list[dict[str, Any]] = []
            mcp_snapshots: dict[str, McpToolSnapshot] = {}

            if settings.CHAT_CUSTOM_INSTRUCTIONS_ENABLED:
                instructions = _trim_instructions(
                    body.workspace_instructions,
                    settings.CHAT_CUSTOM_INSTRUCTIONS_MAX_LENGTH,
                )
                if instructions:
                    extra_tools.append(build_instruction_carrier_tool(instructions))

            if settings.CHAT_CUSTOM_MCP_ENABLED:
                try:
                    mcp_snapshot = await _resolve_active_mcp_snapshot(
                        body.mcp_config,
                        body.active_mcp_mapping,
                        settings,
                        MCP_MAPPING_TOOL_NAME,
                    )
                    if mcp_snapshot:
                        mcp_snapshots[mcp_snapshot.carrier_name] = mcp_snapshot
                        extra_tools.append(build_upstream_mcp_tool(mcp_snapshot))
                    mcp_find_snapshot = await _resolve_active_mcp_snapshot(
                        body.mcp_config,
                        body.active_mcp_find_mapping,
                        settings,
                        MCP_FIND_MAPPING_TOOL_NAME,
                    )
                    if mcp_find_snapshot:
                        mcp_snapshots[mcp_find_snapshot.carrier_name] = mcp_find_snapshot
                        extra_tools.append(build_upstream_mcp_tool(mcp_find_snapshot))
                except Exception as e:
                    logger.warning("Unable to resolve active MCP mapping: %s", e)

            upstream_message = prepared_message
            if (
                _has_instruction_carrier_tool(extra_tools)
                and _is_first_upstream_message(body.create_new_session, body.conversation_id, body.parent_uuid)
            ):
                upstream_message = _prepend_instruction_carrier_hint(prepared_message)
                input_tokens = count_tokens(upstream_message)

            # Stream upstream "full_so_far" into deltas
            # Note: Upstream API sometimes RESTARTS the response from beginning mid-stream (bug on their side)
            prev_raw = ""
            current_message_id = None
            async for update in client.iter_message_stream(
                conv_id,
                upstream_message,
                body.parent_uuid,
                extra_tools=extra_tools,
                mcp_snapshots=mcp_snapshots,
            ):
                # --- Tool call начался ---
                if "tool_call" in update:
                    yield _sse_event("tool_call", update["tool_call"])
                    continue

                # --- Tool result получен ---
                if "tool_result" in update:
                    yield _sse_event("tool_result", update["tool_result"])
                    continue

                # --- Промежуточный текст после результата инструмента ---
                if "tool_followup" in update:
                    yield _sse_event("tool_followup", update["tool_followup"])
                    continue

                raw_text = update.get("text") or ""
                finished = bool(update.get("finished"))
                message_id = update.get("message_id")
                reasoning_delta = update.get("reasoning_delta") or ""

                # Keep the last assistant UUID so the next turn uses the latest parent.
                if message_id:
                    current_message_id = message_id

                # Отправляем reasoning-дельту ПЕРЕД основным текстом
                if reasoning_delta:
                    yield _sse_event("reasoning", {"text": reasoning_delta})

                # Skip if unchanged
                if raw_text == prev_raw:
                    continue


                # Calculate delta from RAW text (already cleaned by onec_client)
                if not prev_raw:
                    # First chunk - send everything
                    delta_raw = raw_text
                elif raw_text.startswith(prev_raw):
                    # Normal case: cumulative text extended
                    delta_raw = raw_text[len(prev_raw):]
                else:
                    # Text doesn't start with previous - upstream restarted OR text modified mid-stream
                    # Log first/last 100 chars for debugging
                    logger.debug(
                        f"Upstream text mismatch: prev_len={len(prev_raw)}, new_len={len(raw_text)}, "
                        f"prev_start='{prev_raw[:100]}...', new_start='{raw_text[:100]}...'"
                    )
                    # Send special "reset" event to tell client to clear previous text
                    yield _sse_event("reset", {})
                    delta_raw = raw_text

                prev_raw = raw_text

                # Sanitize and send
                if delta_raw:
                    delta = sanitize_text(delta_raw)
                    if delta:
                        yield _sse_event("delta", {
                            "text": delta,
                            "message_id": current_message_id
                        })

                if finished:
                    break

            # Count output tokens from final response
            output_tokens = count_tokens(prev_raw) if prev_raw else 0
            total_tokens = input_tokens + output_tokens

            # Send token statistics before done event
            yield _sse_event("tokens", {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens
            })

            # Signal completion
            yield _sse_event("done", {})

        except ApiError as e:
            yield _sse_event("error", {"message": e.message, "status_code": e.status_code})
            yield _sse_event("done", {})
        except Exception:
            yield _sse_event("error", {"message": "Internal server error"})
            yield _sse_event("done", {})

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    }
    return StreamingResponse(gen(), media_type="text/event-stream; charset=utf-8", headers=headers)


