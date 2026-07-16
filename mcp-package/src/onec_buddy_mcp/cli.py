"""Console script `1c-buddy-mcp` of the MCP-only distribution.

Same environment, token and error handling as the full product — all of it comes
from app.cli_support, which both wheels ship. What differs is what this CLI owns:
stdio is the default mode (not http), the http mode serves the minimal MCP app
instead of app.main, and the missing-extra hints name this distribution.

app.cli is deliberately not reused: its http path probes tiktoken and launches
app.main:app, neither of which exists here.

Nothing transport-specific is imported at module level — get_settings() is
lru_cached, so --env-file and LOG_LEVEL must be applied before anything reads
Settings.
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from app.cli_support import (
    EXIT_OK,
    LOG_LEVELS,
    CliError,
    apply_log_level,
    check_coinstalled,
    load_env_file,
    port_type,
    require_token,
    run_guarded,
    run_stdio_transport,
)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 6002

PROG = "1c-buddy-mcp"

HTTP_EXTRA_HINT = (
    "HTTP MCP-режим требует дополнительных пакетов:\n" 'pip install "1c-buddy-mcp[http]"'
)
# The MCP SDK is a base dependency here, so this should be unreachable — but a
# broken install must still say which package is missing rather than crash.
STDIO_EXTRA_HINT = (
    "stdio-режим требует MCP SDK:\n" 'pip install --force-reinstall "1c-buddy-mcp"'
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="MCP-сервер для code.1c.ai: stdio по умолчанию, HTTP MCP через extra [http].",
    )
    parser.add_argument(
        "--env-file",
        metavar="PATH",
        help="Загрузить переменные окружения из файла. Существующее окружение приоритетнее.",
    )
    parser.add_argument("--log-level", choices=LOG_LEVELS)
    # Without a subcommand we run stdio, but the http options must still resolve.
    parser.set_defaults(host=DEFAULT_HOST, port=DEFAULT_PORT, reload=False)

    subparsers = parser.add_subparsers(dest="mode")

    # SUPPRESS on the shared options: argparse would otherwise overwrite the
    # value parsed before the subcommand with the subparser's own None default,
    # so `1c-buddy-mcp --env-file .env http` would silently lose the file.
    stdio = subparsers.add_parser("stdio", help="MCP через stdin/stdout, без HTTP-порта")
    stdio.add_argument("--log-level", choices=LOG_LEVELS, default=argparse.SUPPRESS)
    stdio.add_argument("--env-file", metavar="PATH", default=argparse.SUPPRESS)

    http = subparsers.add_parser("http", help="MCP через HTTP: /mcp и /health")
    http.add_argument("--host", default=DEFAULT_HOST)
    http.add_argument("--port", type=port_type, default=DEFAULT_PORT)
    http.add_argument("--reload", action="store_true")
    http.add_argument("--log-level", choices=LOG_LEVELS, default=argparse.SUPPRESS)
    http.add_argument("--env-file", metavar="PATH", default=argparse.SUPPRESS)

    return parser


def _run_stdio(args: argparse.Namespace) -> int:
    level = apply_log_level(args.log_level, "WARNING")
    # run_stdio_transport keeps stdout clean and rejects a blank token before the
    # MCP handshake; both are part of its contract, not this caller's job.
    return run_stdio_transport(level, STDIO_EXTRA_HINT)


def _run_http(args: argparse.Namespace) -> int:
    level = apply_log_level(args.log_level, "INFO")
    try:
        import fastapi  # noqa: F401
        import uvicorn
    except ImportError:
        raise CliError(HTTP_EXTRA_HINT)

    require_token()

    uvicorn.run(
        "onec_buddy_mcp.http_app:app",
        host=args.host,
        port=args.port,
        log_level=level.lower(),
        reload=args.reload,
    )
    return EXIT_OK


def _dispatch(argv: Optional[Sequence[str]]) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)

    if getattr(args, "env_file", None):
        load_env_file(args.env_file)

    # `1c-buddy-mcp` is owned by both distributions, so which code this command
    # runs depends on install order. In a mixed environment its behaviour is
    # undefined — refuse rather than guess.
    status = check_coinstalled()
    if status.detected:
        raise CliError(status.message)

    if args.mode == "http":
        return _run_http(args)
    return _run_stdio(args)


def _run(argv: Optional[Sequence[str]]) -> int:
    return run_guarded(lambda: _dispatch(argv), PROG)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Console script `1c-buddy-mcp`. No subcommand means stdio."""
    return _run(argv)


if __name__ == "__main__":
    sys.exit(main())
