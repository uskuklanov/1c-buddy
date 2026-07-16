from __future__ import annotations

import time
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

from .. import __version__
from .constants import MCP_SERVER_NAME
from .models import (
    JsonRpcRequest,
    JsonRpcResponse,
    JsonRpcError,
    InitializeParams,
    InitializeResult,
    ToolsCallParams,
    ToolsListResult,
)
from .session import McpSessionStore, validate_origin
from .handlers import McpHandlers, ToolNotFoundError
from .upstream_tools_client import McpUpstreamToolsClient
from ..onec_models import ApiError

router = APIRouter()


def _get_session_store(request: Request) -> McpSessionStore:
    store: Optional[McpSessionStore] = getattr(request.app.state, "mcp_session_store", None)
    if store is None:
        # TTL for MCP sessions: 1 hour default
        store = McpSessionStore(ttl_seconds=3600)
        request.app.state.mcp_session_store = store
    return store


def _get_mcp_upstream_client(request: Request) -> McpUpstreamToolsClient:
    client: Optional[McpUpstreamToolsClient] = getattr(
        request.app.state, "mcp_upstream_client", None
    )
    if client is None:
        client = McpUpstreamToolsClient()
        request.app.state.mcp_upstream_client = client
    return client


async def shutdown_mcp_state(app) -> None:
    """Release what this router lazily put on app.state.

    The router owns the creation of these objects, so it owns their disposal
    too. Both app shells — app.main and the minimal one in the MCP-only wheel —
    call this instead of each carrying its own copy of the state keys.
    """
    client: Optional[McpUpstreamToolsClient] = getattr(app.state, "mcp_upstream_client", None)
    if client is not None:
        try:
            await client.close()
            logger.info("MCP upstream client closed successfully")
        except Exception as e:
            logger.error(f"Error closing MCP upstream client: {e}")


def _jsonrpc_error(id_value: Any, code: int, message: str, data: Any = None, http_status: int = 200) -> JSONResponse:
    body = JsonRpcResponse(
        jsonrpc="2.0",
        id=id_value,
        error=JsonRpcError(code=code, message=message, data=data),
    ).model_dump(exclude_none=True)
    return JSONResponse(status_code=http_status, content=body)


def _bad_request(message: str, data: Any = None) -> JSONResponse:
    # Transport error (invalid HTTP usage) → 400 without JSON-RPC id
    body = JsonRpcResponse(
        jsonrpc="2.0",
        id=None,
        error=JsonRpcError(code=-32600, message=message, data=data),
    ).model_dump(exclude_none=True)
    return JSONResponse(status_code=400, content=body)


def _api_error_data(err: ApiError) -> Dict[str, Any]:
    data: Dict[str, Any] = dict(err.data or {})
    if err.status_code is not None and "upstream_status" not in data:
        data["upstream_status"] = err.status_code
    if "detail" not in data:
        data["detail"] = str(err)
    return data


@router.post("/mcp")
async def mcp_endpoint(request: Request, response: Response):
    # Origin validation for DNS rebinding mitigation
    if not validate_origin(request):
        return JSONResponse(status_code=403, content={"error": "Forbidden origin"})

    # Parse JSON body
    try:
        payload: Dict[str, Any] = await request.json()
        logger.debug(f"MCP request payload: {payload}")
        if not isinstance(payload, dict):
            logger.debug(f"Payload is not dict: {type(payload)}, value: {payload}")
            return _bad_request("Request body must be a single JSON-RPC object (dict).")
    except Exception as e:
        logger.debug(f"Failed to parse JSON body: {e}")
        return _bad_request("Invalid JSON.")

    # Distinguish message types
    is_request = "method" in payload
    has_id = "id" in payload and payload.get("id") is not None
    is_notification = is_request and not has_id
    is_response_from_client = ("result" in payload or "error" in payload) and not is_request

    # Per spec: accept client notifications/responses with 202 and no body
    if is_response_from_client or (is_notification and payload.get("method") != "initialize"):
        return Response(status_code=202)

    # Handle JSON-RPC request
    if is_request:
        # Try to parse as JsonRpcRequest
        try:
            req = JsonRpcRequest(**payload)
        except Exception:
            return _bad_request("Invalid JSON-RPC request object.")

        method = req.method
        req_id = req.id  # may be None for notification (but we handled non-initialize notification above)

        # Initialize handshake (no session required)
        if method == "initialize":
            # Create session - no version negotiation
            store = _get_session_store(request)
            sess = store.create(protocol_version="")

            # Build result
            try:
                params = InitializeParams(**(req.params or {}))
            except Exception:
                return _jsonrpc_error(req_id, -32602, "Invalid params for initialize")

            handlers = McpHandlers(_get_mcp_upstream_client(request), store)
            # Use protocol version from params or default
            result: InitializeResult = await handlers.initialize(params, params.protocolVersion or "")

            # Transport headers
            response.headers["MCP-Session-Id"] = sess.session_id
            logger.debug(f"Returning session ID: {sess.session_id} in MCP-Session-Id header")

            json_response = JSONResponse(
                status_code=200,
                content=JsonRpcResponse(jsonrpc="2.0", id=req_id, result=result.model_dump()).model_dump(exclude_none=True),
            )
            json_response.headers["MCP-Session-Id"] = sess.session_id
            return json_response

        # Everything else requires a valid session
        session_id = request.headers.get("mcp-session-id")
        if not session_id:
            logger.debug(f"Missing session ID for method {method}, headers: {dict(request.headers)}")
            return _bad_request("Missing Mcp-Session-Id header.")

        store = _get_session_store(request)
        sess = store.get(session_id)
        if not sess:
            # Per spec: 404 for unknown/expired session
            return JSONResponse(status_code=404, content={"error": "Unknown or expired session"})

        # Dispatch methods
        handlers = McpHandlers(_get_mcp_upstream_client(request), store)

        if method == "initialized":
            if req_id is None:
                # Notification acknowledged
                return Response(status_code=202)
            # Per JSON-RPC, requests with id must get a response
            return JSONResponse(
                status_code=200,
                content=JsonRpcResponse(
                    jsonrpc="2.0",
                    id=req_id,
                    error=JsonRpcError(code=-32600, message="'initialized' must be sent as a notification"),
                ).model_dump(exclude_none=True),
            )

        if method == "tools/list":
            try:
                result: ToolsListResult = await handlers.tools_list()
                return JSONResponse(
                    status_code=200,
                    content=JsonRpcResponse(jsonrpc="2.0", id=req_id, result=result.model_dump()).model_dump(exclude_none=True),
                )
            except ApiError as e:
                return _jsonrpc_error(req_id, -32603, "Internal error", _api_error_data(e))
            except Exception as e:
                return _jsonrpc_error(req_id, -32603, "Internal error", {"detail": str(e)})

        if method == "tools/call":
            try:
                params = ToolsCallParams(**(req.params or {}))
            except Exception:
                return _jsonrpc_error(req_id, -32602, "Invalid params for tools/call")

            try:
                result = await handlers.tools_call(params, session_id)
                return JSONResponse(
                    status_code=200,
                    content=JsonRpcResponse(jsonrpc="2.0", id=req_id, result=result.model_dump()).model_dump(exclude_none=True),
                )
            except ToolNotFoundError:
                return _jsonrpc_error(req_id, -32601, "Tool not found", {"name": params.name})
            except ApiError as e:
                return _jsonrpc_error(req_id, -32603, "Internal error", _api_error_data(e))
            except Exception as e:
                return _jsonrpc_error(req_id, -32603, "Internal error", {"detail": str(e)})

        # Unknown method
        return _jsonrpc_error(req_id, -32601, f"Method not found: {method}")

    # Not a request/notification/response we understand
    return _bad_request("Unsupported JSON-RPC message type.")
@router.get("/mcp")
async def mcp_get(request: Request):
    # Return server info for discovery
    if not validate_origin(request):
        return JSONResponse(status_code=403, content={"error": "Forbidden origin"})

    # Return endpoint info
    return JSONResponse(status_code=200, content={
        "name": MCP_SERVER_NAME,
        "version": __version__,
        "endpoint": "/mcp"
    })
