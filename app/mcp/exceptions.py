"""Error contract of the transport-independent MCP layer.

Lives apart from service.py to keep the import graph acyclic: tool_catalog and
validation raise these, and service imports both of them.

Not to be confused with app/errors.py, which builds FastAPI JSONResponse.
"""

from __future__ import annotations


class ToolNotFoundError(Exception):
    """Requested tool name is neither a canonical name nor a known alias."""

    def __init__(self, tool_name: str):
        self.tool_name = tool_name
        super().__init__(tool_name)


class ToolInputError(Exception):
    """Arguments do not satisfy the declared input schema.

    `message` is user-facing text, already localized, safe to return verbatim
    to an MCP client over either transport.
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)
