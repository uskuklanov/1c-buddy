"""Transport-independent execution of the public MCP tools.

Knows nothing about FastAPI, the MCP SDK or HTTP sessions: it validates
arguments, talks to 1C.ai and returns a cleaned result. Each transport renders
that result its own way — HTTP appends the session/conversation footer, stdio
returns the text alone.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional

from ..config import Settings
from ..streaming import sanitize_text
from ..text_utils import prepare_message_for_upstream
from .exceptions import ToolInputError, ToolNotFoundError
from .tool_catalog import ToolDefinition, build_tool_definitions
from .upstream_tools_client import McpUpstreamToolsClient
from .validation import validate_arguments

logger = logging.getLogger(__name__)

__all__ = [
    "McpToolService",
    "ToolExecutionResult",
    "ToolInputError",
    "ToolNotFoundError",
]


@dataclass(frozen=True)
class ToolExecutionResult:
    text: str
    title: Optional[str]
    conversation_id: str
    canonical_tool_name: str


class McpToolService:
    """Runs one public MCP tool call against 1C.ai."""

    def __init__(self, client: McpUpstreamToolsClient):
        self.client = client
        self._executors: Dict[str, Callable[[Dict[str, Any]], Awaitable[ToolExecutionResult]]] = {
            "ask_1c_ai": self._run_ask,
            "explain_1c_syntax": self._run_explain,
            "check_1c_code": self._run_check,
            "modify_1c_code": self._run_modify,
            "search_1c_documentation": self._run_search_documentation,
            "search_its": self._run_search_its,
            "fetch_its": self._run_fetch_its,
            "diff_1c_documentation_versions": self._run_diff,
        }

    @property
    def settings(self) -> Settings:
        return self.client.settings

    @property
    def executor_names(self) -> frozenset:
        """Canonical names this service can run. Must equal the catalog's."""
        return frozenset(self._executors)

    async def execute(self, tool_name: str, arguments: Dict[str, Any]) -> ToolExecutionResult:
        settings = self.settings
        definition = self._find_definition(tool_name, settings)
        args = validate_arguments(
            definition.input_schema, arguments or {}, tool_name=definition.name
        )
        return await self._executors[definition.name](args)

    @staticmethod
    def _find_definition(tool_name: str, settings: Settings) -> ToolDefinition:
        for definition in build_tool_definitions(settings):
            if tool_name == definition.name or tool_name in definition.aliases:
                return definition
        raise ToolNotFoundError(tool_name)

    # ---- upstream helpers ----

    async def _new_conversation(self, *, programming_language: Optional[str] = None) -> str:
        """Every public tool call gets its own isolated 1C.ai conversation."""
        return await self.client.create_conversation(programming_language=programming_language)

    def _use_direct_mode(self) -> bool:
        return (self.settings.MCP_TOOL_CALL_MODE or "standard").strip().lower() == "direct"

    def _default_ssl_version(self) -> str:
        return (self.settings.DEFAULT_SSL_VERSION or "").strip()

    def _default_1c_config(self) -> str:
        return (self.settings.DEFAULT_1C_CONFIGURATION or "").strip()

    def _project_context(self, args: Dict[str, Any]) -> tuple[str, str]:
        """Explicit argument wins over the environment default."""
        ssl_version = (args.get("ssl_version") or "").strip() or self._default_ssl_version()
        config = (args.get("configuration") or "").strip() or self._default_1c_config()
        return config, ssl_version

    @staticmethod
    def _build_context_prefix(config: str, ssl_version: str) -> str:
        parts = []
        if config:
            parts.append(config)
        if ssl_version:
            parts.append(f"БСП {ssl_version}")
        return " ".join(parts)

    @staticmethod
    def _build_context_hint(config: str, ssl_version: str) -> str:
        parts = []
        if config:
            parts.append(f"конфигурация {config}")
        if ssl_version:
            parts.append(f"версия БСП {ssl_version}")
        if not parts:
            return ""
        return "Контекст проекта: " + ", ".join(parts) + "."

    # ---- result extraction ----

    def _extract_tool_text(
        self, result: Dict[str, Any], *, include_tool_details: bool = False
    ) -> str:
        full_text = (result.get("full_text") or "").strip()
        followups = [
            item.get("text", "").strip()
            for item in result.get("tool_followups", [])
            if item.get("text")
        ]
        final_text = (result.get("final_text") or "").strip()
        tool_results = result.get("tool_results") or []

        blocks: List[str] = []
        for item in tool_results:
            md = (item.get("response_markdown") or "").strip()
            if md and md != "✓ Инструмент выполнен":
                blocks.append(md)
            details = item.get("response_details") or []
            if include_tool_details and details:
                blocks.extend(str(detail) for detail in details if detail)

        if full_text:
            blocks.append(full_text)
        elif followups:
            blocks.append(followups[-1])
        elif final_text:
            blocks.append(final_text)
        return "\n".join(part for part in blocks if part).strip()

    @staticmethod
    def _extract_task_text(result: Dict[str, Any]) -> str:
        full_text = (result.get("full_text") or "").strip()
        if full_text:
            return full_text
        final_text = (result.get("final_text") or "").strip()
        if final_text:
            return final_text
        followups = [
            item.get("text", "").strip()
            for item in result.get("tool_followups", [])
            if item.get("text")
        ]
        return followups[-1] if followups else ""

    # _extract_standard_text is identical to _extract_task_text today; keeping
    # both names would only suggest a difference that does not exist.
    _extract_standard_text = _extract_task_text

    # ---- prompt builders ----

    @staticmethod
    def _build_check_review_prompt(code: str) -> str:
        return (
            "Проведи code review этого кода 1С. Найди ошибки, нарушения стандартов, "
            "риски и предложи исправленный вариант.\n\n"
            "Код:\n```bsl\n"
            f"{code}\n"
            "```"
        )

    @staticmethod
    def _build_modify_prompt(instruction: str, code: str) -> str:
        base = (
            "Измени этот код 1С по заданию пользователя. Верни итоговый измененный код "
            "и кратко перечисли, что именно было изменено.\n\n"
            f"Задание:\n{instruction.strip()}"
        )
        validation_tail = (
            "\n\n"
            "ОБЯЗАТЕЛЬНО выполни синтаксическую проверку измененного кода с помощью "
            "инструмента mcp__syntax-checker__validate перед отправкой результата."
        )
        if code.strip():
            return (
                f"{base}\n\n"
                "Код:\n```bsl\n"
                f"{code}\n"
                "```"
                f"{validation_tail}"
            )
        return f"{base}{validation_tail}"

    @staticmethod
    def _build_check_syntax_prompt(code: str, extended: bool) -> str:
        suffix = (
            " Используй расширенную проверку со стандартами 1С."
            if extended
            else ""
        )
        return (
            "Проверь этот код 1С на синтаксические ошибки перед отправкой пользователю."
            f"{suffix}\n\n"
            "Код:\n```bsl\n"
            f"{code}\n"
            "```"
        )

    @staticmethod
    def _build_search_documentation_prompt(query: str, version: str) -> str:
        return (
            "Найди информацию в документации платформы 1С:Предприятие. "
            f"Используй документацию версии {version}. "
            "Верни краткий, но информативный ответ по найденным данным.\n\n"
            f"Запрос: {query}"
        )

    @staticmethod
    def _build_search_its_prompt(query: str, context_hint: str = "") -> str:
        hint_line = f"{context_hint}\n" if context_hint else ""
        return (
            "Выполни поиск в базе знаний ИТС по этому запросу. "
            "Верни фактический результат и обязательно сохрани ссылки на источники.\n"
            f"{hint_line}"
            f"\nЗапрос: {query}"
        )

    @staticmethod
    def _build_fetch_its_prompt(item_id: str) -> str:
        return (
            "Получить содержимое документа, каталога или базы ИТС по идентификатору.\n\n"
            f"id: {item_id}"
        )

    @staticmethod
    def _build_diff_prompt(version_a: str, version_b: str, query: str) -> str:
        scope = f"\nПредметная область: {query}" if query else ""
        return (
            "Сравни документацию платформы 1С между двумя версиями и верни различия.\n\n"
            f"Более ранняя версия: {version_a}\n"
            f"Более поздняя версия: {version_b}"
            f"{scope}"
        )

    # ---- executors ----

    async def _run_ask(self, args: Dict[str, Any]) -> ToolExecutionResult:
        question = args["question"]
        programming_language = args.get("programming_language") or None
        config, ssl_version = self._project_context(args)

        hint = self._build_context_hint(config, ssl_version)
        if hint:
            question += f"\n\n{hint}"
        prepared_question, _ = prepare_message_for_upstream(question, self.settings)

        conv_id = await self._new_conversation(programming_language=programming_language)
        if self._use_direct_mode():
            result = await self.client.call_task(
                conv_id,
                instruction=prepared_question,
                skill="custom",
            )
            clean = sanitize_text(self._extract_task_text(result))
        else:
            result = await self.client.call_prompt(conv_id, instruction=prepared_question)
            clean = sanitize_text(self._extract_standard_text(result))
        return ToolExecutionResult(
            text=clean,
            title="Ответ от 1С.ai",
            conversation_id=conv_id,
            canonical_tool_name="ask_1c_ai",
        )

    async def _run_explain(self, args: Dict[str, Any]) -> ToolExecutionResult:
        syntax_element = args["syntax_element"]
        context = args.get("context") or ""
        config, ssl_version = self._project_context(args)

        question = f"Объясни синтаксис и использование: {syntax_element}"
        if context:
            question += f" в контексте: {context}"
        hint = self._build_context_hint(config, ssl_version)
        if hint:
            question += f"\n\n{hint}"
        prepared_question, _ = prepare_message_for_upstream(question, self.settings)

        conv_id = await self._new_conversation()
        if self._use_direct_mode():
            result = await self.client.call_task(
                conv_id,
                instruction=prepared_question,
                skill="explain",
            )
            clean = sanitize_text(self._extract_task_text(result))
        else:
            result = await self.client.call_prompt(conv_id, instruction=prepared_question)
            clean = sanitize_text(self._extract_standard_text(result))
        return ToolExecutionResult(
            text=clean,
            title=f"Объяснение синтаксиса '{syntax_element}'",
            conversation_id=conv_id,
            canonical_tool_name="explain_1c_syntax",
        )

    async def _run_check(self, args: Dict[str, Any]) -> ToolExecutionResult:
        code = args["code"]
        check_type = args.get("check_type") or "syntax"
        extended = bool(args.get("extended") or False)

        # logic/performance are kept as aliases of review for compatibility.
        normalized_check_type = {"logic": "review", "performance": "review"}.get(
            check_type, check_type
        )

        conv_id = await self._new_conversation()

        if self._use_direct_mode() and normalized_check_type == "syntax":
            result = await self.client.call_exact_tool(
                conv_id,
                tool_name="mcp__syntax-checker__validate",
                arguments={"code": code, "extended": extended},
                payload_ensure_ascii=False,
            )
            clean = sanitize_text(self._extract_tool_text(result, include_tool_details=True))
            title = "Проверка кода на синтаксис"
        elif self._use_direct_mode():
            result = await self.client.call_task(
                conv_id,
                instruction=self._build_check_review_prompt(code),
                skill="review",
            )
            clean = sanitize_text(self._extract_task_text(result))
            title = "Проверка кода review"
        else:
            prompt = (
                self._build_check_syntax_prompt(code, extended)
                if normalized_check_type == "syntax"
                else self._build_check_review_prompt(code)
            )
            result = await self.client.call_prompt(conv_id, instruction=prompt)
            clean = sanitize_text(self._extract_standard_text(result))
            title = (
                "Проверка кода на синтаксис"
                if normalized_check_type == "syntax"
                else "Проверка кода review"
            )

        return ToolExecutionResult(
            text=clean,
            title=title,
            conversation_id=conv_id,
            canonical_tool_name="check_1c_code",
        )

    async def _run_modify(self, args: Dict[str, Any]) -> ToolExecutionResult:
        instruction = args["instruction"]
        code = args.get("code") or ""

        conv_id = await self._new_conversation()
        prompt = self._build_modify_prompt(instruction, code)
        if self._use_direct_mode():
            result = await self.client.call_task(
                conv_id,
                instruction=prompt,
                skill="modify",
            )
            clean = sanitize_text(self._extract_task_text(result))
        else:
            result = await self.client.call_prompt(conv_id, instruction=prompt)
            clean = sanitize_text(self._extract_standard_text(result))
        return ToolExecutionResult(
            text=clean,
            title="Изменение кода",
            conversation_id=conv_id,
            canonical_tool_name="modify_1c_code",
        )

    async def _run_search_documentation(self, args: Dict[str, Any]) -> ToolExecutionResult:
        query = args["query"]
        version = args.get("version") or "v8.5.1"

        conv_id = await self._new_conversation()
        if self._use_direct_mode():
            result = await self.client.call_exact_tool(
                conv_id,
                tool_name="mcp__knowledge-hub__Search_Documentation",
                arguments={"query": query, "version": version},
            )
            clean = sanitize_text(self._extract_tool_text(result, include_tool_details=True))
        else:
            result = await self.client.call_prompt(
                conv_id,
                instruction=self._build_search_documentation_prompt(query, version),
            )
            clean = sanitize_text(self._extract_standard_text(result))
        return ToolExecutionResult(
            text=clean,
            title=None,
            conversation_id=conv_id,
            canonical_tool_name="search_1c_documentation",
        )

    async def _run_search_its(self, args: Dict[str, Any]) -> ToolExecutionResult:
        query = args["query"]
        config, ssl_version = self._project_context(args)

        conv_id = await self._new_conversation()
        if self._use_direct_mode():
            prefix = self._build_context_prefix(config, ssl_version)
            search_query = f"{prefix} {query}".strip() if prefix else query
            result = await self.client.call_exact_tool(
                conv_id,
                tool_name="mcp__knowledge-hub__Search_ITS",
                arguments={"query": search_query},
            )
            clean = sanitize_text(self._extract_tool_text(result, include_tool_details=True))
        else:
            hint = self._build_context_hint(config, ssl_version)
            result = await self.client.call_prompt(
                conv_id,
                instruction=self._build_search_its_prompt(query, hint),
            )
            clean = sanitize_text(self._extract_standard_text(result))
        return ToolExecutionResult(
            text=clean,
            title=None,
            conversation_id=conv_id,
            canonical_tool_name="search_its",
        )

    async def _run_fetch_its(self, args: Dict[str, Any]) -> ToolExecutionResult:
        item_id = args.get("id") or "root"

        conv_id = await self._new_conversation()
        if self._use_direct_mode():
            result = await self.client.call_exact_tool(
                conv_id,
                tool_name="mcp__knowledge-hub__Fetch_ITS",
                arguments={"id": item_id},
            )
            clean = sanitize_text(self._extract_tool_text(result, include_tool_details=True))
        else:
            result = await self.client.call_prompt(
                conv_id,
                instruction=self._build_fetch_its_prompt(item_id),
            )
            clean = sanitize_text(self._extract_standard_text(result))
        return ToolExecutionResult(
            text=clean,
            title=None,
            conversation_id=conv_id,
            canonical_tool_name="fetch_its",
        )

    async def _run_diff(self, args: Dict[str, Any]) -> ToolExecutionResult:
        version_a = args["version_a"]
        version_b = args["version_b"]
        query = args.get("query") or ""

        conv_id = await self._new_conversation()
        if self._use_direct_mode():
            direct_args: Dict[str, Any] = {"version_a": version_a, "version_b": version_b}
            if query:
                direct_args["query"] = query
            result = await self.client.call_exact_tool(
                conv_id,
                tool_name="mcp__knowledge-hub__Diff_Documentation_Versions",
                arguments=direct_args,
            )
            clean = sanitize_text(self._extract_tool_text(result, include_tool_details=True))
        else:
            result = await self.client.call_prompt(
                conv_id,
                instruction=self._build_diff_prompt(version_a, version_b, query),
            )
            clean = sanitize_text(self._extract_standard_text(result))
        return ToolExecutionResult(
            text=clean,
            title=None,
            conversation_id=conv_id,
            canonical_tool_name="diff_1c_documentation_versions",
        )
