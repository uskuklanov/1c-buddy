"""Transport-independent catalog of the public MCP tools.

Single source of names, descriptions, JSON schemas, defaults, enums, length
limits and aliases. Both the HTTP transport (tools/list) and the stdio
transport (list_tools) render this same result, so their schemas cannot drift.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from ..config import Settings
from .exceptions import ToolNotFoundError
from .validation import assert_schema_supported


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: Dict[str, Any]
    aliases: Tuple[str, ...] = field(default=())


def build_tool_definitions(settings: Settings) -> List[ToolDefinition]:
    min_len = getattr(settings, "MCP_TOOL_INPUT_MIN_LENGTH", 0)
    max_len = getattr(settings, "MCP_TOOL_INPUT_MAX_LENGTH", 200000)

    default_ssl = (settings.DEFAULT_SSL_VERSION or "").strip()
    default_config = (settings.DEFAULT_1C_CONFIGURATION or "").strip()

    ssl_desc = "Версия Библиотеки Стандартных Подсистем (БСП)."
    if default_ssl:
        ssl_desc += f" По умолчанию: {default_ssl}."

    config_desc = "Конфигурация 1С (например: Бухгалтерия предприятия, ERP, Управление торговлей)."
    if default_config:
        config_desc += f" По умолчанию: {default_config}."

    project_context_schema = {
        "ssl_version": {
            "type": "string",
            "description": ssl_desc,
            "default": default_ssl,
        },
        "configuration": {
            "type": "string",
            "description": config_desc,
            "default": default_config,
        },
    }

    definitions = [
        ToolDefinition(
            name="ask_1c_ai",
            description=(
                "Задать общий вопрос по платформе 1С:Предприятие и получить ответ, "
                "объяснение или практическую рекомендацию. Используй для общих вопросов "
                "по функциональности платформы, подходам к разработке и типовым сценариям, "
                "когда не нужен отдельный специализированный поиск по документации или ИТС."
            ),
            input_schema={
                "type": "object",
                "title": "Ask 1C expert",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Вопрос или задача на русском языке. Старайся формулировать конкретно.",
                        "minLength": min_len,
                        "maxLength": max_len,
                    },
                    "programming_language": {
                        "type": "string",
                        "description": "Язык, если вопрос связан с кодом или синтаксисом.",
                        "enum": ["", "BSL", "SQL", "JSON", "HTTP"],
                        "default": "",
                        "maxLength": max_len,
                    },
                    **project_context_schema,
                },
                "required": ["question"],
            },
        ),
        ToolDefinition(
            name="explain_1c_syntax",
            description=(
                "Объяснить конкретный элемент синтаксиса, объект или тип платформы 1С "
                "с примерами использования. Используй, когда нужно понять, как работает "
                "конкретный метод, объект, коллекция или конструкция языка."
            ),
            input_schema={
                "type": "object",
                "title": "Explain 1C syntax",
                "properties": {
                    "syntax_element": {
                        "type": "string",
                        "description": "Название элемента, который нужно объяснить, например HTTPЗапрос, ТаблицаЗначений или Запрос.",
                        "minLength": min_len,
                        "maxLength": max_len,
                    },
                    "context": {
                        "type": "string",
                        "description": "Дополнительный контекст использования, если он важен для ответа.",
                        "default": "",
                        "minLength": 0,
                        "maxLength": max_len,
                    },
                    **project_context_schema,
                },
                "required": ["syntax_element"],
            },
        ),
        ToolDefinition(
            name="check_1c_code",
            description=(
                "Проверить присланный BSL/1C код. Используй check_type='syntax' для "
                "быстрой синтаксической проверки конкретного фрагмента и check_type='review' "
                "для code review, поиска ошибок и замечаний по качеству кода. "
                "Проверка syntax выполняется без глобального контекста, поэтому возможны "
                "ложные срабатывания по необъявленным переменным и методам."
            ),
            input_schema={
                "type": "object",
                "title": "Check 1C code",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Проверяемый фрагмент кода 1С.",
                        "minLength": min_len,
                        "maxLength": max_len,
                    },
                    "check_type": {
                        "type": "string",
                        "description": "syntax — синтаксическая проверка; review — code review. Значения logic/performance сохранены для обратной совместимости и обрабатываются как review.",
                        "enum": ["syntax", "review", "logic", "performance"],
                        "default": "syntax",
                    },
                    "extended": {
                        "type": "boolean",
                        "description": "Только для syntax: включить обогащение стандартами 1С.",
                        "default": False,
                    },
                },
                "required": ["code"],
            },
        ),
        ToolDefinition(
            name="modify_1c_code",
            description=(
                "Изменить код 1С по явному заданию пользователя: исправить ошибку, "
                "сделать рефакторинг или добавить функциональность. В instruction "
                "опиши, какие изменения нужны и что ожидается на выходе. Если есть "
                "исходный код, передай его в параметре code."
            ),
            input_schema={
                "type": "object",
                "title": "Modify 1C code",
                "properties": {
                    "instruction": {
                        "type": "string",
                        "description": "Четкое описание задачи на русском языке: что нужно изменить и какой результат ожидается.",
                        "minLength": min_len,
                        "maxLength": max_len,
                    },
                    "code": {
                        "type": "string",
                        "description": "Исходный код 1С, который нужно изменить.",
                        "default": "",
                        "minLength": 0,
                        "maxLength": max_len,
                    },
                },
                "required": ["instruction"],
            },
        ),
        ToolDefinition(
            name="search_1c_documentation",
            description=(
                "Поиск по документации платформы 1С:Предприятие. Используй, когда вопрос "
                "касается функциональности самой платформы: объектов, методов, свойств, "
                "синтаксиса и параметров, а также перед написанием кода, если нужна точная "
                "документация по элементу платформы. Не выдумывай синтаксис и поведение, "
                "если их можно сначала найти в документации. Для общих запросов формируй "
                "query так, чтобы он искал обзорную информацию: 'Общая информация о ...', "
                "'Список всех ...', 'Все ...'. Если пользователь указал версию платформы, "
                "обязательно передай её."
            ),
            input_schema={
                "type": "object",
                "title": "Search 1C documentation",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Поисковый запрос для embedding-поиска. Для общих тем лучше писать 'Общая информация о ...' или 'Список всех ...'.",
                        "minLength": min_len,
                        "maxLength": max_len,
                    },
                    "version": {
                        "type": "string",
                        "description": "Версия документации платформы в формате v8.x.x или v8.x.x.x.",
                        "default": "v8.5.1",
                        "maxLength": max_len,
                    },
                },
                "required": ["query"],
            },
            aliases=("Search_1C_Documentation",),
        ),
        ToolDefinition(
            name="search_its",
            description=(
                "Поиск по базе знаний ИТС. Используй для стандартов и правил разработки "
                "на 1С, методических материалов, практических примеров, вопросов по "
                "конкретным конфигурациям и продуктам 1С, а также по EDT и Конфигуратору. "
                "Для фактологических вопросов по экосистеме 1С предпочитай именно этот "
                "инструмент, а не ответ по памяти. Если найденной информации недостаточно, "
                "переформулируй query или затем используй fetch_its для чтения конкретного документа."
            ),
            input_schema={
                "type": "object",
                "title": "Search ITS",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Поисковый запрос для embedding-поиска по ИТС.",
                        "minLength": min_len,
                        "maxLength": max_len,
                    },
                    **project_context_schema,
                },
                "required": ["query"],
            },
            aliases=("Search_ITS",),
        ),
        ToolDefinition(
            name="fetch_its",
            description=(
                "Получить содержимое документа, каталога или базы ИТС по id. Обычно "
                "используется после search_its, когда уже найден нужный документ, либо "
                "для исследования структуры ИТС с id='root'. Поддерживаются как специальные "
                "id вроде root, superior, v8std, так и идентификаторы документов и каталогов "
                "вида its-...-hdoc или its-...-hdir, возможно с 1-2 якорями через '/'. "
                "Обычно id документа выглядит как 'its-{database_id}-{doc_or_dir_id}-(hdoc|hdir|...)'."
            ),
            input_schema={
                "type": "object",
                "title": "Fetch ITS",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "Идентификатор документа, каталога или базы ИТС: root, superior, v8std или строка вида its-...-hdoc/hdir.",
                        "default": "root",
                        "minLength": 1,
                        "maxLength": max_len,
                    },
                },
                # id was declared required while the handler defaulted it to
                # "root". Strict validation would have rejected fetch_its {},
                # which works today, so the schema is relaxed to match reality.
                "required": [],
            },
            aliases=("Fetch_ITS",),
        ),
        ToolDefinition(
            name="diff_1c_documentation_versions",
            description=(
                "Сравнить документацию платформы 1С между двумя версиями. Используй, "
                "когда спрашивают об изменениях между версиями платформы. version_a "
                "должна быть более ранней, version_b — более поздней. Параметр query "
                "задаёт предметную область сравнения. Если разница пустая, но вернулся "
                "список изменённых файлов, значит query нужно переформулировать."
            ),
            input_schema={
                "type": "object",
                "title": "Diff 1C documentation versions",
                "properties": {
                    "version_a": {
                        "type": "string",
                        "description": "Более ранняя версия в формате v8.3.27 или v8.3.27.189.",
                        "minLength": 2,
                        "maxLength": max_len,
                    },
                    "version_b": {
                        "type": "string",
                        "description": "Более поздняя версия в формате v8.3.27 или v8.3.27.189.",
                        "minLength": 2,
                        "maxLength": max_len,
                    },
                    "query": {
                        "type": "string",
                        "description": "Необязательная предметная область сравнения, например 'HTTP соединение'.",
                        "default": "",
                        "maxLength": max_len,
                    },
                },
                "required": ["version_a", "version_b"],
            },
            aliases=("Diff_1C_Documentation_Versions",),
        ),
    ]

    for definition in definitions:
        assert_schema_supported(definition.input_schema, tool_name=definition.name)

    return definitions


def resolve_tool_name(name: str, settings: Settings) -> str:
    """Map a legacy alias to its canonical name; raise if neither is known.

    Aliases are accepted on call but never published in tools/list.
    """
    for definition in build_tool_definitions(settings):
        if name == definition.name or name in definition.aliases:
            return definition.name
    raise ToolNotFoundError(name)
