"""Minimal FastAPI app for `1c-buddy-mcp http`: MCP over HTTP and nothing else.

app.main cannot be reused — it imports the chat router and the OpenAI-compatible
routes unconditionally and mounts StaticFiles, which is exactly the payload this
distribution exists to leave out. So this is a separate composition root, not a
copy: the MCP logic itself comes from app.mcp.http_transport's router, unchanged.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.mcp.constants import MCP_SERVER_NAME
from app.mcp.http_transport import router as mcp_router, shutdown_mcp_state

logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s v%s (MCP-only, HTTP)", MCP_SERVER_NAME, __version__)
    yield
    # The router creates the upstream client lazily on app.state, so it owns the
    # disposal too.
    await shutdown_mcp_state(app)


app = FastAPI(
    title=MCP_SERVER_NAME,
    version=__version__,
    description="MCP over HTTP for code.1c.ai",
    lifespan=lifespan,
    # No chat, no /v1, no interactive docs: /mcp and /health are the whole surface.
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# POST /mcp and GET /mcp — the same router the full package mounts.
app.include_router(mcp_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": __version__}
