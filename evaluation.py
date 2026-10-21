from collections import Counter
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext


def rounded_number(value, decimals):
    """Round a finite number using the declared scoring rule."""
    if type(decimals) is not int or not 0 <= decimals <= 10:
        raise ValueError("decimals must be an integer from 0 to 10.")

    if isinstance(value, bool):
        raise ValueError("Boolean values are not numbers here.")

    text = str(value).strip()
    if not text or len(text) > 200:
        raise ValueError("Invalid numeric value.")

    try:
        number = Decimal(text)
        if not number.is_finite():
            raise ValueError("Number must be finite.")

        if abs(number.as_tuple().exponent) > 100:
            raise ValueError("Numeric exponent is too large.")

        with localcontext() as context:
            context.prec = 400
            quantum = Decimal(1).scaleb(-decimals)
            return number.quantize(quantum, rounding=ROUND_HALF_UP)

    except InvalidOperation as exc:
        raise ValueError("Invalid numeric value.") from exc


def normalise_answer(answer, decimals):
    """Return a valid voting pair or None."""
    if not isinstance(answer, dict):
        return None

    name = answer.get("name")
    if not isinstance(name, str) or not name.strip():
        return None

    try:
        number = rounded_number(answer.get("number"), decimals)
    except (ValueError, TypeError):
        return None

    return name.strip(), number


def score_answer(answer, reference):
    """Reference contains answer, value and decimals from questions.json."""
    decimals = reference["decimals"]
    expected_name = reference["answer"].strip()
    expected_number = rounded_number(reference["value"], decimals)

    pair = normalise_answer(answer, decimals)
    if pair is None:
        return {
            "correct": False,
            "unanswered": True,
            "reason": "missing_or_invalid_answer",
        }

    name, number = pair

    with localcontext() as context:
        context.prec = 400
        tolerance = Decimal(1).scaleb(-decimals)
        difference = abs(number - expected_number)

    name_matches = name == expected_name
    number_matches = difference <= tolerance

    return {
        "correct": name_matches and number_matches,
        "unanswered": False,
        "name_matches": name_matches,
        "number_matches": number_matches,
        "rounded_prediction": format(number, "f"),
        "rounded_reference": format(expected_number, "f"),
        "absolute_difference": format(difference, "f"),
        "tolerance": format(tolerance, "f"),
    }


def majority_vote(answers, decimals):
    """Vote by rounded pairs; ties go to the earliest observed pair."""
    pairs = []

    for answer in answers:
        pair = normalise_answer(answer, decimals)
        if pair is not None:
            pairs.append(pair)

    if not pairs:
        return {
            "answer": None,
            "valid_votes": 0,
            "winning_votes": 0,
            "tied": False,
            "counts": [],
        }

    counts = Counter(pairs)
    highest_count = max(counts.values())

    # Counter preserves the order in which distinct pairs first appear.
    leaders = [
        pair for pair, count in counts.items()
        if count == highest_count
    ]
    winner = leaders[0]

    return {
        "answer": {
            "name": winner[0],
            "number": format(winner[1], "f"),
        },
        "valid_votes": len(pairs),
        "winning_votes": highest_count,
        "tied": len(leaders) > 1,
        "counts": [
            {
                "name": name,
                "number": format(number, "f"),
                "votes": count,
            }
            for (name, number), count in counts.items()
        ],
    }
