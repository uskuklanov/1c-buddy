"""Entry point for both transports: `1c-buddy http` and `1c-buddy stdio`.

Nothing transport-specific — and nothing that reads Settings — may be imported
at module level. get_settings() is lru_cached and app.main builds Settings plus
configures stdout logging while being imported, so --env-file and LOG_LEVEL must
be applied first. Hence the local imports inside the run functions.

Everything transport-neutral lives in app.cli_support, which the MCP-only wheel
also ships. This module keeps only what belongs to the full product: its parser,
the HTTP mode that launches app.main, and the two console scripts.
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from .cli_support import (
    EXIT_ERROR,
    EXIT_OK,
    EXIT_USAGE,
    LOG_LEVELS,
    CliError,
    apply_log_level,
    check_coinstalled,
    find_validation_error,
    load_env_file,
    port_type,
    require_token,
    run_guarded,
    run_stdio_transport,
)

# The pre-split private names, kept as aliases: they are what callers already
# know, and re-exporting them costs nothing.
_CliError = CliError
_port = port_type
_load_env_file = load_env_file
_apply_log_level = apply_log_level
_require_token = require_token
_find_validation_error = find_validation_error

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 6002

PROG = "1c-buddy"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Gateway для code.1c.ai: HTTP (чат, MCP, OpenAI API) или MCP через stdio.",
    )
    parser.add_argument(
        "--env-file",
        metavar="PATH",
        help="Загрузить переменные окружения из файла. Существующее окружение приоритетнее.",
    )
    parser.add_argument("--log-level", choices=LOG_LEVELS)
    # Without a subcommand we run http, so its options need values here too.
    parser.set_defaults(host=DEFAULT_HOST, port=DEFAULT_PORT, reload=False)

    subparsers = parser.add_subparsers(dest="mode")

    # SUPPRESS on the shared options: argparse would otherwise overwrite the
    # value parsed before the subcommand with the subparser's own None default,
    # so `1c-buddy --env-file .env http` would silently lose the file.
    http = subparsers.add_parser(
        "http", help="HTTP-сервис: /chat, /mcp, /health, опционально /v1"
    )
    http.add_argument("--host", default=DEFAULT_HOST)
    http.add_argument("--port", type=port_type, default=DEFAULT_PORT)
    http.add_argument("--reload", action="store_true")
    http.add_argument("--log-level", choices=LOG_LEVELS, default=argparse.SUPPRESS)
    http.add_argument("--env-file", metavar="PATH", default=argparse.SUPPRESS)

    stdio = subparsers.add_parser("stdio", help="MCP через stdin/stdout, без HTTP-порта")
    stdio.add_argument("--log-level", choices=LOG_LEVELS, default=argparse.SUPPRESS)
    stdio.add_argument("--env-file", metavar="PATH", default=argparse.SUPPRESS)

    return parser


def _run_http(args: argparse.Namespace) -> int:
    level = apply_log_level(args.log_level, "INFO")
    try:
        # Probing uvicorn alone is not enough: the MCP SDK from the stdio extra
        # depends on uvicorn, so it is present in a stdio-only install while
        # FastAPI is not. Without this, the missing FastAPI would only surface
        # inside uvicorn.run() as a generic crash with exit code 1.
        import fastapi  # noqa: F401
        import tiktoken  # noqa: F401
        import uvicorn
    except ImportError:
        raise CliError('HTTP-режим требует дополнительных пакетов: pip install "1c-buddy[http]"')

    require_token()

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        log_level=level.lower(),
        reload=args.reload,
    )
    return EXIT_OK


def _run_stdio(args: argparse.Namespace) -> int:
    level = apply_log_level(args.log_level, "WARNING")
    return run_stdio_transport(
        level,
        'stdio-режим требует дополнительных пакетов: pip install "1c-buddy[stdio]"',
    )


def _check_coinstall(contested: bool) -> None:
    """Which console script we were invoked as decides the severity — not which
    transport it picked.

    `1c-buddy-mcp` is owned by both distributions, so what it runs depends on
    install order: in a mixed environment its behaviour is undefined and it must
    refuse. `1c-buddy` is this distribution's alone, and with matching versions
    the shared app/* files are byte-identical, so it genuinely works — killing it
    would be the regression. A mixed-version tree is another matter: that is not
    a supported combination of internal modules.
    """
    status = check_coinstalled()
    if not status.detected:
        return
    if contested or not status.same_version:
        raise CliError(status.message)
    print(status.message, file=sys.stderr)


def _dispatch(argv: Optional[Sequence[str]], *, contested: bool) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)

    if getattr(args, "env_file", None):
        load_env_file(args.env_file)

    _check_coinstall(contested)

    if args.mode == "stdio":
        return _run_stdio(args)
    return _run_http(args)


def _run(argv: Optional[Sequence[str]], *, contested: bool = False) -> int:
    return run_guarded(lambda: _dispatch(argv, contested=contested), PROG)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Console script `1c-buddy`. No subcommand means http."""
    return _run(argv)


def stdio_main(argv: Optional[Sequence[str]] = None) -> int:
    """Console script `1c-buddy-mcp`: straight to stdio."""
    if argv is None:
        argv = sys.argv[1:]
    return _run(["stdio", *argv], contested=True)


if __name__ == "__main__":
    sys.exit(main())
