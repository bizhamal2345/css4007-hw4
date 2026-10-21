import json
from pathlib import Path

from tools import lookup, calculate


DEFINITIONS_PATH = Path(__file__).resolve().parent / "tool_definitions.json"
TOOL_DEFINITIONS = json.loads(
    DEFINITIONS_PATH.read_text(encoding="utf-8")
)

FUNCTIONS = {
    "lookup": lookup,
    "calculate": calculate,
}

SCHEMAS = {
    definition["function"]["name"]:
        definition["function"]["parameters"]
    for definition in TOOL_DEFINITIONS
}

MAX_ARGUMENT_CHARS = 10_000


def error_result(code, message):
    return {
        "ok": False,
        "error": {"code": code, "message": message},
    }


def reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key.")
        result[key] = value
    return result


def reject_nonfinite_constant(value):
    raise ValueError("Non-finite JSON numbers are not allowed.")


def dispatch_tool(name, arguments):
    """Validate a model's tool request and execute an allowed function."""
    if not isinstance(name, str) or name not in FUNCTIONS:
        return error_result(
            "UNKNOWN_TOOL",
            "Allowed tools: lookup, calculate.",
        )

    if not isinstance(arguments, str):
        return error_result(
            "INVALID_ARGUMENTS",
            "Arguments must be a JSON string.",
        )

    if len(arguments) > MAX_ARGUMENT_CHARS:
        return error_result(
            "INVALID_ARGUMENTS",
            "Arguments are too long.",
        )

    try:
        parsed = json.loads(
            arguments,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_nonfinite_constant,
        )
    except (ValueError, RecursionError):
        return error_result(
            "INVALID_ARGUMENTS",
            "Arguments must contain valid JSON without duplicate keys "
            "or non-finite numbers.",
        )

    if not isinstance(parsed, dict):
        return error_result(
            "INVALID_ARGUMENTS",
            "Arguments must be a JSON object.",
        )

    schema = SCHEMAS[name]
    properties = schema["properties"]
    required = set(schema.get("required", []))

    missing = required - set(parsed)
    extra = set(parsed) - set(properties)

    if missing or extra:
        return error_result(
            "INVALID_ARGUMENTS",
            f"Missing fields: {sorted(missing)}; "
            f"extra fields: {sorted(extra)}.",
        )

    for field, value in parsed.items():
        rules = properties[field]

        # Both tools accept only string arguments.
        if not isinstance(value, str):
            return error_result(
                "INVALID_ARGUMENTS",
                f"{field} must be a string.",
            )

        if len(value) < rules.get("minLength", 0):
            return error_result(
                "INVALID_ARGUMENTS",
                f"{field} is too short.",
            )

        if "maxLength" in rules and len(value) > rules["maxLength"]:
            return error_result(
                "INVALID_ARGUMENTS",
                f"{field} is too long.",
            )

        if "enum" in rules and value not in rules["enum"]:
            return error_result(
                "INVALID_ARGUMENTS",
                f"{field} must be one of: {rules['enum']}.",
            )

    try:
        return FUNCTIONS[name](**parsed)
    except Exception:
        return error_result(
            "INTERNAL_ERROR",
            "The tool could not complete the request.",
        )
