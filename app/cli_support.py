"""CLI primitives shared by both distributions.

`1c-buddy` (full product) and `1c-buddy-mcp` (the MCP-only wheel built from
mcp-package/) must behave identically around the environment file, the token and
error reporting, but they own different parsers, defaults and transports. This
module is the border between them: everything transport-neutral lives here, so
the MCP-only wrapper never has to reach into app.cli's privates — and app/cli.py,
which knows about tiktoken and app.main, stays out of the minimal wheel.

Nothing that reads Settings may be imported at module level. get_settings() is
lru_cached and app.main builds Settings plus configures stdout logging while
being imported, so --env-file and LOG_LEVEL must be applied first. Hence the
local imports inside the functions.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Callable, NamedTuple, Optional

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2

LOG_LEVELS = ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]

DIST_FULL = "1c-buddy"
DIST_MCP = "1c-buddy-mcp"


class CliError(Exception):
    """Message for stderr plus the exit code to leave with."""

    def __init__(self, message: str, code: int = EXIT_USAGE):
        self.message = message
        self.code = code
        super().__init__(message)


def port_type(value: str) -> int:
    try:
        port = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"порт должен быть числом: {value!r}")
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError(f"порт должен быть в диапазоне 1..65535: {port}")
    return port


def load_env_file(path: str) -> None:
    """Populate os.environ from PATH without overriding what is already set."""
    if not os.path.isfile(path):
        raise CliError(f"Файл окружения не найден: {path}")
    from dotenv import load_dotenv

    # Never log the contents: they hold the token and possibly proxy credentials.
    load_dotenv(path, override=False, encoding="utf-8")


def apply_log_level(cli_level: Optional[str], default: str) -> str:
    """CLI wins over the process environment, which wins over the default."""
    level = (cli_level or os.environ.get("LOG_LEVEL") or default).upper()
    os.environ["LOG_LEVEL"] = level
    return level


def require_token() -> None:
    """A blank token is a configuration error, not a server that starts and 401s.

    Settings only requires the variable to exist, so ONEC_AI_TOKEN="" would sail
    through and the process would sit there talking to 1C.ai with no credentials.
    """
    from .config import get_settings

    settings = get_settings()
    if not (settings.ONEC_AI_TOKEN or "").strip():
        raise CliError("Ошибка конфигурации: ONEC_AI_TOKEN не задан")


def run_stdio_transport(level: str, missing_extra_message: str) -> int:
    """Launch the MCP stdio server. The order of the steps is the contract."""
    import logging

    # stdout is the MCP frame stream: logs must never touch it.
    logging.basicConfig(
        level=getattr(logging, level, logging.WARNING),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
    )

    try:
        import anyio

        from .mcp.stdio_server import run_stdio
    except ImportError:
        raise CliError(missing_extra_message)

    # Fail before the MCP handshake rather than on the first tool call.
    require_token()

    anyio.run(run_stdio)
    return EXIT_OK


def find_validation_error(exc: BaseException):
    """Settings are built inside the stdio lifespan, so anyio wraps the failure
    in an ExceptionGroup. Unwrap it, or a missing token reports as a generic
    crash instead of a configuration error."""
    from pydantic import ValidationError

    if isinstance(exc, ValidationError):
        return exc
    for nested in getattr(exc, "exceptions", ()):
        found = find_validation_error(nested)
        if found is not None:
            return found
    return None


def run_guarded(dispatch: Callable[[], int], prog: str) -> int:
    """Turn every failure into a message on stderr and an exit code.

    Never prints a traceback or the exception text: both can carry the token.
    """
    try:
        return dispatch()
    except CliError as e:
        print(e.message, file=sys.stderr)
        return e.code
    except KeyboardInterrupt:
        return EXIT_OK
    except BaseException as e:  # config errors land here: no traceback, no secrets
        if isinstance(e, SystemExit):
            raise
        validation_error = find_validation_error(e)
        if validation_error is not None:
            missing = [
                ".".join(str(part) for part in err["loc"])
                for err in validation_error.errors()
                if err["type"] == "missing"
            ]
            detail = (
                f"не заданы обязательные переменные окружения: {', '.join(missing)}"
                if missing
                else "проверьте переменные окружения"
            )
            print(f"Ошибка конфигурации: {detail}", file=sys.stderr)
            return EXIT_USAGE
        print(f"Не удалось запустить {prog}: {type(e).__name__}", file=sys.stderr)
        return EXIT_ERROR


class CoinstallStatus(NamedTuple):
    detected: bool
    same_version: bool
    message: str


# The distribution is installed but its version could not be read. Distinct from
# None (not installed): an unreadable version proves nothing about compatibility,
# so it must not silently pass as a clean environment.
UNKNOWN_VERSION = "неизвестна"


def _dist_version(name: str) -> Optional[str]:
    """None if not installed, UNKNOWN_VERSION if installed but unreadable."""
    from importlib.metadata import PackageNotFoundError, distribution

    try:
        dist = distribution(name)
    except PackageNotFoundError:
        return None
    except Exception:
        # Metadata exists in some form but cannot be parsed. Erring towards
        # "installed" is the safe direction: the alternative is to declare a
        # coinstalled environment clean.
        return UNKNOWN_VERSION

    try:
        return dist.version or UNKNOWN_VERSION
    except Exception:
        return UNKNOWN_VERSION


def check_coinstalled() -> CoinstallStatus:
    """Both distributions in one environment.

    They ship the same app/* modules and the same `1c-buddy-mcp` console script,
    so pip lets the second install overwrite the first's files and a later
    `pip uninstall` of either one guts the other. This is a diagnostic, not a
    guard: it cannot prevent that uninstall, and a `1c-buddy` released before
    this module existed will not run it at all.
    """
    full = _dist_version(DIST_FULL)
    mcp = _dist_version(DIST_MCP)
    if full is None or mcp is None:
        return CoinstallStatus(False, False, "")

    known = full != UNKNOWN_VERSION and mcp != UNKNOWN_VERSION
    same = known and _normalize_version(full) == _normalize_version(mcp)
    message = (
        f"В окружении установлены оба пакета: {DIST_FULL} {full} и {DIST_MCP} {mcp}.\n"
        f"Они делят модули app/ и команду {DIST_MCP}; окружение неконсистентно.\n"
        "Восстановление (простой pip uninstall одного пакета удалит общие файлы\n"
        "и сломает второй):\n"
        f"  pip uninstall -y {DIST_FULL} {DIST_MCP}\n"
        "  pip install <нужный пакет>"
    )
    return CoinstallStatus(True, same, message)


def _normalize_version(raw: str) -> str:
    try:
        from packaging.version import InvalidVersion, Version
    except ImportError:
        return raw.strip()
    try:
        return str(Version(raw))
    except InvalidVersion:
        return raw.strip()
