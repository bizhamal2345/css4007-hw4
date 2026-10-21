import ast
import math
import operator


MAX_CHARS = 200
MAX_NODES = 100
MAX_DEPTH = 20
MAX_NUMBER = 1e15

BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}

UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


class ToolError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def error_result(code, message):
    return {
        "ok": False,
        "error": {"code": code, "message": message}
    }


def check_number(value):
    if type(value) not in (int, float):
        raise ToolError(
            "UNSAFE_EXPRESSION",
            "Only real numeric literals are allowed."
        )

    if not math.isfinite(value) or abs(value) > MAX_NUMBER:
        raise ToolError(
            "NUMBER_OUT_OF_RANGE",
            "Numbers must be finite and have absolute value at most 1e15."
        )

    return float(value)


def validate_tree(tree):
    allowed = (
        ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant,
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.UAdd, ast.USub
    )

    stack = [(tree, 1)]
    count = 0

    while stack:
        node, depth = stack.pop()
        count += 1

        if count > MAX_NODES or depth > MAX_DEPTH:
            raise ToolError(
                "EXPRESSION_TOO_COMPLEX",
                "Expression exceeds the node or depth limit."
            )

        if not isinstance(node, allowed):
            raise ToolError(
                "UNSAFE_EXPRESSION",
                "Only numbers, parentheses, +, -, * and / are allowed."
            )

        if isinstance(node, ast.Constant):
            check_number(node.value)

        for child in ast.iter_child_nodes(node):
            stack.append((child, depth + 1))


def evaluate_node(node):
    if isinstance(node, ast.Expression):
        return evaluate_node(node.body)

    if isinstance(node, ast.Constant):
        return check_number(node.value)

    if isinstance(node, ast.UnaryOp):
        value = evaluate_node(node.operand)
        return check_number(UNARY_OPERATORS[type(node.op)](value))

    if isinstance(node, ast.BinOp):
        left = evaluate_node(node.left)
        right = evaluate_node(node.right)

        if isinstance(node.op, ast.Div) and right == 0:
            raise ToolError("DIVISION_BY_ZERO", "Cannot divide by zero.")

        return check_number(
            BINARY_OPERATORS[type(node.op)](left, right)
        )

    raise ToolError("UNSAFE_EXPRESSION", "Unsupported expression.")


def calculate(expression):
    try:
        if not isinstance(expression, str):
            raise ToolError(
                "INVALID_ARGUMENTS",
                "expression must be a string."
            )

        if not expression.strip() or len(expression) > MAX_CHARS:
            raise ToolError(
                "INVALID_ARGUMENTS",
                "Expression must contain 1 to 200 characters."
            )

        try:
            tree = ast.parse(expression.strip(), mode="eval")
        except SyntaxError:
            raise ToolError(
                "INVALID_EXPRESSION",
                "The expression has invalid syntax."
            )

        # Сначала проверяется всё дерево, затем выполняется арифметика.
        validate_tree(tree)
        return {"ok": True, "result": evaluate_node(tree)}

    except ToolError as exc:
        return error_result(exc.code, exc.message)

    except OverflowError:
        return error_result(
            "NUMBER_OUT_OF_RANGE", "The number is too large."
        )

    except RecursionError:
        return error_result(
            "EXPRESSION_TOO_COMPLEX", "The expression is too deeply nested."
        )

    except Exception:
        return error_result(
            "INTERNAL_ERROR", "The calculation could not be completed."
        )


import json
import re
import difflib
from pathlib import Path


CORPUS_PATH = Path(__file__).resolve().parent / "data" / "corpus.jsonl"
NUMBER_PATTERN = r"([0-9][0-9,]*(?:\.[0-9]+)?)"

FIELD_PATTERNS = {
    "population_2025": [
        rf"2025 census (?:recorded|counted)\s+{NUMBER_PATTERN}",
        rf"{NUMBER_PATTERN}\s+in 2025"
    ],
    "population_2020": [
        rf"2020 census had recorded\s+{NUMBER_PATTERN}",
        rf"{NUMBER_PATTERN}\s+at the 2020 census",
        rf"{NUMBER_PATTERN}\s+in 2020"
    ],
    "area_km2": [rf"{NUMBER_PATTERN}\s+square kilometres"],
    "budget_million_tenge": [rf"{NUMBER_PATTERN}\s+million tenge"],
    "schools": [rf"{NUMBER_PATTERN}\s+schools"],
    "pupils": [rf"{NUMBER_PATTERN}\s+pupils"],
    "road_km": [rf"{NUMBER_PATTERN}\s+km"],
    "founded": [rf"founded in\s+{NUMBER_PATTERN}"]
}

FIELD_UNITS = {
    "population_2025": "residents",
    "population_2020": "residents",
    "area_km2": "km2",
    "budget_million_tenge": "million tenge",
    "water_m3": "m3",
    "schools": "schools",
    "pupils": "pupils",
    "road_km": "km",
    "founded": "year",
    "water_tariff_2025": "tenge/m3"
}

INTEGER_FIELDS = {
    "population_2025", "population_2020",
    "schools", "pupils", "founded"
}


def read_corpus():
    try:
        with CORPUS_PATH.open(encoding="utf-8") as file:
            docs = [json.loads(line) for line in file if line.strip()]
    except (OSError, ValueError):
        raise ToolError("DATA_ERROR", "Cannot read the corpus.")

    if not docs:
        raise ToolError("DATA_ERROR", "The corpus is empty.")

    for doc in docs:
        if not isinstance(doc, dict):
            raise ToolError("DATA_ERROR", "Invalid document structure.")

        if any(
            not isinstance(doc.get(key), str)
            for key in ("id", "title", "text")
        ):
            raise ToolError("DATA_ERROR", "Invalid document fields.")

    ids = [doc["id"] for doc in docs]
    if len(ids) != len(set(ids)):
        raise ToolError("DATA_ERROR", "Duplicate document IDs.")

    return docs


def extract_number(text, patterns):
    for pattern in patterns:
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        if not matches:
            continue

        try:
            values = {
                float(value.replace(",", ""))
                for value in matches
            }
        except (ValueError, OverflowError):
            raise ToolError("INVALID_NUMBER", "Cannot parse the number.")

        if len(values) != 1:
            raise ToolError("INVALID_NUMBER", "Conflicting numeric values.")

        value = values.pop()
        if not math.isfinite(value) or value < 0:
            raise ToolError("INVALID_NUMBER", "Invalid numeric value.")

        return value

    raise ToolError("MISSING_FACT", "The requested fact was not found.")


def lookup(district, field):
    try:
        if (
            not isinstance(district, str)
            or not district.strip()
            or len(district) > 80
            or not isinstance(field, str)
            or field not in FIELD_UNITS
        ):
            raise ToolError("INVALID_ARGUMENTS", "Invalid district or field.")

        district = district.strip()
        docs = read_corpus()
        by_id = {doc["id"]: doc for doc in docs}

        if district.casefold() == "region":
            if field != "water_tariff_2025":
                raise ToolError(
                    "INVALID_FIELD_FOR_DISTRICT",
                    "REGION supports only water_tariff_2025."
                )

            tariff = by_id.get("NR-15")
            if tariff is None:
                raise ToolError("MISSING_FACT", "Tariff document is missing.")

            value = extract_number(
                tariff["text"],
                [
                    rf"From 1 January 2025.*?tariff is\s+"
                    rf"{NUMBER_PATTERN}\s+tenge per cubic metre"
                ]
            )

            return {
                "ok": True,
                "district": "REGION",
                "field": field,
                "value": value,
                "unit": FIELD_UNITS[field],
                "period": "2025",
                "sources": [tariff["id"]]
            }

        if field == "water_tariff_2025":
            raise ToolError(
                "INVALID_FIELD_FOR_DISTRICT",
                "Use REGION for the regional water tariff."
            )

        profiles = []
        for doc in docs:
            match = re.match(
                r"^(.+?) district profile \((.+?)\)$",
                doc["title"],
                flags=re.IGNORECASE
            )
            if match:
                profiles.append((match.group(1), match.group(2), doc))

        names = sorted({name for name, _, _ in profiles})
        matching = [
            item for item in profiles
            if item[0].casefold() == district.casefold()
        ]

        if not matching:
            name_map = {name.casefold(): name for name in names}
            suggestions = difflib.get_close_matches(
                district.casefold(), list(name_map), n=3, cutoff=0.5
            )
            result = error_result(
                "UNKNOWN_DISTRICT", "Unknown district. Use an exact name."
            )
            result["error"]["suggestions"] = [
                name_map[name] for name in suggestions
            ]
            return result

        current = [
            item for item in matching
            if item[1] == "2025"
            and "ARCHIVED" not in (
                item[2]["title"] + " " + item[2]["text"]
            ).upper()
        ]

        if not current:
            raise ToolError(
                "NO_CURRENT_PROFILE", "No current 2025 profile is available."
            )

        if len(current) != 1:
            raise ToolError(
                "AMBIGUOUS_DISTRICT", "Multiple current profiles match."
            )

        canonical_name, _, profile = current[0]
        sources = [profile["id"]]

        if field == "water_m3":
            match = re.search(
                rf"(?:Households used|Household water use in 2025 came to)"
                rf"\s+{NUMBER_PATTERN}\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)",
                profile["text"],
                flags=re.IGNORECASE
            )

            if not match:
                raise ToolError("MISSING_FACT", "Water use was not found.")

            raw_value = float(match.group(1).replace(",", ""))
            unit = match.group(2).lower()

            if unit.startswith("megalitres"):
                tariff = by_id.get("NR-15")
                if tariff is None:
                    raise ToolError(
                        "MISSING_FACT", "Water conversion source is missing."
                    )

                factor = extract_number(
                    tariff["text"],
                    [rf"One megalitre is\s+{NUMBER_PATTERN}\s+cubic metres"]
                )
                value = raw_value * factor
                sources.append(tariff["id"])

            elif unit == "cubic metres":
                value = raw_value

            else:
                raise ToolError("UNKNOWN_UNIT", "Unsupported water unit.")

        else:
            value = extract_number(profile["text"], FIELD_PATTERNS[field])

        if field == "area_km2":
            notices = [
                doc for doc in docs
                if doc["title"].casefold()
                == f"Correction notice - {canonical_name}".casefold()
            ]

            if len(notices) > 1:
                raise ToolError(
                    "DATA_ERROR", "Multiple correction notices require review."
                )

            if notices:
                notice = notices[0]
                value = extract_number(
                    notice["text"],
                    [rf"correct area is\s+{NUMBER_PATTERN}\s+square kilometres"]
                )
                sources.append(notice["id"])

        if not math.isfinite(value) or value < 0:
            raise ToolError("INVALID_NUMBER", "Invalid fact value.")

        if field in INTEGER_FIELDS:
            if not value.is_integer():
                raise ToolError("INVALID_NUMBER", "An integer is required.")
            value = int(value)

        period = "2025"
        if field == "population_2020":
            period = "2020"
        elif field in {"schools", "pupils"}:
            period = "2025/26"
        elif field == "founded":
            period = "historical"

        return {
            "ok": True,
            "district": canonical_name,
            "field": field,
            "value": value,
            "unit": FIELD_UNITS[field],
            "period": period,
            "sources": sources
        }

    except ToolError as exc:
        return error_result(exc.code, exc.message)

    except (ValueError, OverflowError):
        return error_result("INVALID_NUMBER", "Cannot parse a numeric value.")

    except Exception:
        return error_result("INTERNAL_ERROR", "Lookup could not be completed.")
