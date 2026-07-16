"""Single arbiter of the declared tool input schemas.

The stdio transport runs the MCP SDK with validate_input=False, so this module
is the only thing standing between a client and the upstream call on either
transport. Both transports therefore see identical errors, in Russian.

Only a flat slice of JSON Schema is understood. assert_schema_supported() fails
fast on anything outside it, so a future tool cannot publish a schema richer
than what is actually enforced.
"""

from __future__ import annotations

from typing import Any, Mapping

from .exceptions import ToolInputError

# Supported dialect, split by level: a keyword must not be silently accepted at
# the wrong one.
ROOT_KEYS = frozenset({"type", "title", "properties", "required"})
PROPERTY_KEYS = frozenset(
    {"type", "description", "default", "enum", "minLength", "maxLength"}
)
PROPERTY_TYPES = frozenset({"string", "boolean"})

_MISSING = object()

# Verbatim public messages for empty required fields. These predate the strict
# validator and are part of the tool contract, so they are kept byte for byte.
_EMPTY_REQUIRED_MESSAGES: dict[tuple[str, str], str] = {
    ("ask_1c_ai", "question"): "Ошибка: Вопрос не может быть пустым",
    ("explain_1c_syntax", "syntax_element"): "Ошибка: Элемент синтаксиса не может быть пустым",
    ("check_1c_code", "code"): "Ошибка: Код для проверки не может быть пустым",
    ("modify_1c_code", "instruction"): "Ошибка: instruction не может быть пустым",
    ("search_1c_documentation", "query"): "Ошибка: query не может быть пустым",
    ("search_its", "query"): "Ошибка: query не может быть пустым",
    ("diff_1c_documentation_versions", "version_a"): "Ошибка: version_a и version_b обязательны",
    ("diff_1c_documentation_versions", "version_b"): "Ошибка: version_a и version_b обязательны",
}


class UnsupportedSchemaError(Exception):
    """A tool schema uses a keyword or type outside the supported dialect."""


def _empty_required_message(tool_name: str, field: str) -> str:
    return _EMPTY_REQUIRED_MESSAGES.get(
        (tool_name, field), f"Ошибка: {field} не может быть пустым"
    )


def _type_message(field: str, spec: Mapping[str, Any]) -> str:
    if spec.get("type") == "boolean":
        return f"Ошибка: {field} должно быть логическим значением (true или false)"
    return f"Ошибка: {field} должно быть строкой"


def assert_schema_supported(input_schema: Mapping[str, Any], *, tool_name: str) -> None:
    """Fail fast if the schema exceeds what validate_arguments() can enforce.

    Takes a raw mapping rather than a ToolDefinition: tool_catalog imports this
    module, so importing its type back would close a cycle.
    """
    unknown_root = set(input_schema) - ROOT_KEYS
    if unknown_root:
        raise UnsupportedSchemaError(
            f"{tool_name}: unsupported root keywords: {sorted(unknown_root)}"
        )
    if input_schema.get("type") != "object":
        raise UnsupportedSchemaError(f"{tool_name}: root type must be 'object'")

    properties = input_schema.get("properties")
    if not isinstance(properties, dict):
        raise UnsupportedSchemaError(f"{tool_name}: 'properties' must be an object")

    for field, spec in properties.items():
        if not isinstance(spec, dict):
            raise UnsupportedSchemaError(f"{tool_name}.{field}: property must be an object")
        unknown = set(spec) - PROPERTY_KEYS
        if unknown:
            raise UnsupportedSchemaError(
                f"{tool_name}.{field}: unsupported keywords: {sorted(unknown)}"
            )
        if spec.get("type") not in PROPERTY_TYPES:
            raise UnsupportedSchemaError(
                f"{tool_name}.{field}: unsupported type {spec.get('type')!r}"
            )

    required = input_schema.get("required", [])
    if not isinstance(required, list):
        raise UnsupportedSchemaError(f"{tool_name}: 'required' must be a list")
    missing = [field for field in required if field not in properties]
    if missing:
        raise UnsupportedSchemaError(
            f"{tool_name}: required names not declared as properties: {missing}"
        )


def _default_for(spec: Mapping[str, Any]) -> Any:
    if "default" in spec:
        return spec["default"]
    return "" if spec.get("type") == "string" else False


def validate_arguments(
    input_schema: Mapping[str, Any],
    arguments: Mapping[str, Any],
    *,
    tool_name: str,
) -> dict[str, Any]:
    """Normalize arguments against the schema, applying defaults.

    Strings are stripped; an empty optional string falls back to its schema
    default (this is what turns version="" into "v8.5.1" and id="" into "root").
    Undeclared arguments are ignored, as they always have been.
    """
    properties: Mapping[str, Any] = input_schema.get("properties", {})
    required = set(input_schema.get("required", []))
    normalized: dict[str, Any] = {}

    for field, spec in properties.items():
        raw = arguments.get(field, _MISSING)

        if raw is _MISSING:
            if field in required:
                raise ToolInputError(_empty_required_message(tool_name, field))
            normalized[field] = _default_for(spec)
            continue

        if raw is None:
            # A required null has always answered with the "empty" message, and
            # that text is part of the public contract. An optional null is a
            # plain type violation: no schema declares a nullable type, and the
            # SDK's own jsonschema would reject it too.
            if field in required:
                raise ToolInputError(_empty_required_message(tool_name, field))
            raise ToolInputError(_type_message(field, spec))

        if spec.get("type") == "boolean":
            if not isinstance(raw, bool):
                raise ToolInputError(_type_message(field, spec))
            normalized[field] = raw
            continue

        if not isinstance(raw, str):
            raise ToolInputError(_type_message(field, spec))

        value = raw.strip()
        if not value:
            if field in required:
                raise ToolInputError(_empty_required_message(tool_name, field))
            value = _default_for(spec)

        if "enum" in spec and value not in spec["enum"]:
            allowed = ", ".join(f"'{item}'" for item in spec["enum"])
            raise ToolInputError(f"Ошибка: {field} должно быть одним из: {allowed}")

        if value:
            min_length = spec.get("minLength")
            if min_length is not None and len(value) < min_length:
                raise ToolInputError(
                    f"Ошибка: {field} короче минимальной длины {min_length}"
                )
            max_length = spec.get("maxLength")
            if max_length is not None and len(value) > max_length:
                raise ToolInputError(
                    f"Ошибка: {field} длиннее максимальной длины {max_length}"
                )

        normalized[field] = value

    return normalized
