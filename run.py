import hashlib
import json
from pathlib import Path

import strategies
from evaluation import score_answer


PROJECT = Path(__file__).resolve().parent
OUTPUTS = PROJECT / "outputs"
STRATEGIES = ("S1", "S2", "S3")

COMPLETED_STATUSES = {
    "answered",
    "unanswered_invalid_final",
    "unanswered_incomplete_response",
    "unanswered_empty_response",
    "unanswered_round_limit",
}

FINGERPRINT_FILES = [
    "tools.py",
    "tool_runtime.py",
    "strategies.py",
    "evaluation.py",
    "run.py",
    "tool_definitions.json",
    "data/corpus.jsonl",
    "data/questions.json",
]


def load_questions():
    data = json.loads(
        (PROJECT / "data/questions.json").read_text(encoding="utf-8")
    )
    questions = data["questions"] if isinstance(data, dict) else data

    if len(questions) != 20:
        raise ValueError("Expected exactly 20 questions.")

    ids = [question["id"] for question in questions]
    if len(set(ids)) != len(ids):
        raise ValueError("Question IDs must be unique.")

    return questions


def check_manifest():
    """Prevent mixing results produced with different code or settings."""
    hashes = {
        name: hashlib.sha256((PROJECT / name).read_bytes()).hexdigest()
        for name in FINGERPRINT_FILES
    }

    manifest = {
        "file_sha256": hashes,
        "settings": strategies.REQUEST_SETTINGS,
        "max_rounds": strategies.MAX_ROUNDS,
        "s2_samples": 5,
        "strategy_order": list(STRATEGIES),
    }

    path = OUTPUTS / "experiment_manifest.json"
    if path.exists():
        previous = json.loads(path.read_text(encoding="utf-8"))
        if previous != manifest:
            raise RuntimeError(
                "Code, data or settings changed after the experiment "
                "started. Existing results cannot be mixed with new ones."
            )
    else:
        strategies.save_log(path, manifest)

    return manifest


def summarise(run_number, questions):
    directory = OUTPUTS / f"run_{run_number}"
    records = []

    for question in questions:
        for strategy in STRATEGIES:
            path = directory / f"{strategy}_{question['id']}.json"
            if not path.exists():
                continue

            log = json.loads(path.read_text(encoding="utf-8"))
            completed = log["status"] in COMPLETED_STATUSES
            score = (
                score_answer(log.get("answer"), question)
                if completed else None
            )

            records.append({
                "question_id": question["id"],
                "strategy": strategy,
                "status": log["status"],
                "completed": completed,
                "score": score,
                "answer": log.get("answer"),
                "input_tokens": log["input_tokens"],
                "output_tokens": log["output_tokens"],
                "api_calls": log["api_calls"],
                "api_attempts": log["api_attempts"],
                "calls_without_usage": log["calls_without_usage"],
                "tool_calls": log["tool_calls"],
                "total_seconds": log["total_seconds"],
                "log_path": path.relative_to(PROJECT).as_posix(),
            })

    summary = {
        "run": run_number,
        "expected_results": len(questions) * len(STRATEGIES),
        "completed_results": sum(r["completed"] for r in records),
        "records": records,
    }

    strategies.save_log(directory / "summary.json", summary)
    return summary


def run_experiment(run_number):
    if type(run_number) is not int or run_number not in (1, 2):
        raise ValueError("run_number must be 1 or 2.")

    questions = load_questions()
    check_manifest()

    directory = OUTPUTS / f"run_{run_number}"
    directory.mkdir(parents=True, exist_ok=True)

    for question in questions:
        for strategy in STRATEGIES:
            path = directory / f"{strategy}_{question['id']}.json"

            if path.exists():
                existing = json.loads(path.read_text(encoding="utf-8"))

                if (
                    existing.get("question_id") != question["id"]
                    or existing.get("question") != question["question"]
                    or existing.get("strategy") != strategy
                    or existing.get("settings")
                    != strategies.REQUEST_SETTINGS
                ):
                    raise RuntimeError(f"Inconsistent log: {path}")

                if existing["status"] in COMPLETED_STATUSES:
                    print(
                        f"SKIP: run {run_number}, "
                        f"{strategy}, {question['id']}",
                        flush=True,
                    )
                    continue

                print(
                    f"STOP: unfinished or failed log: {path}\n"
                    "Preserved for diagnosis; no automatic retry.",
                    flush=True,
                )
                return summarise(run_number, questions)

            arguments = {
                "question": question["question"],
                "question_id": question["id"],
                "log_path": path,
            }

            if strategy == "S1":
                result = strategies.run_s1(**arguments)
            elif strategy == "S2":
                result = strategies.run_s2(
                    **arguments,
                    decimals=question["decimals"],
                )
            else:
                result = strategies.run_s3(**arguments)

            summary = summarise(run_number, questions)
            print(
                f"Saved: {summary['completed_results']}/"
                f"{summary['expected_results']}",
                flush=True,
            )

            if result["status"] not in COMPLETED_STATUSES:
                print(
                    "Experiment stopped. Send the error output "
                    "before retrying.",
                    flush=True,
                )
                return summary

    summary = summarise(run_number, questions)
    print(
        f"\nRUN {run_number} COMPLETE: "
        f"{summary['completed_results']}/"
        f"{summary['expected_results']} results"
    )

    for strategy in STRATEGIES:
        records = [
            record for record in summary["records"]
            if record["strategy"] == strategy and record["completed"]
        ]
        correct = sum(r["score"]["correct"] for r in records)
        unanswered = sum(r["score"]["unanswered"] for r in records)
        print(
            f"{strategy}: correct {correct}/20; unanswered {unanswered}"
        )

    return summary
