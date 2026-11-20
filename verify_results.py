"""Verify the overnight batch and export only the exercise's tags."""

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

from classify_batch import Decision, checked_metrics
from fault_urgency_rules import SAFETY_ALERT_CODES


OUTPUT_FIELDS = ("message_id", "urgency_tag", "fix_path", "needs_human_review")


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def verify(source, results):
    identifiers = [row["message_id"] for row in source]
    if len(identifiers) != 300 or len(set(identifiers)) != 300:
        raise ValueError("Expected the 300 distinct IDs from the overnight exercise")
    if [row["message_id"] for row in results] != identifiers:
        raise ValueError("Results must preserve every message ID in input order")

    for index, (raw, row) in enumerate(zip(source, results, strict=True)):
        if not re.fullmatch(r"MSG-\d+", row["message_id"]):
            raise ValueError("Unexpected identifier format in the overnight exercise")
        prediction = Decision.model_validate({"index": index, **{key: row[key] for key in (*OUTPUT_FIELDS[1:], "model_used")}})
        if not prediction.model_used.endswith(":free"):
            raise ValueError("Expected an OpenRouter free model for every record")
        if raw["vehicle_alert_code"] in SAFETY_ALERT_CODES and prediction.urgency_tag != "safety_urgent":
            raise ValueError(f"Safety code downgraded on row {index + 1}")
        if prediction.urgency_tag == "safety_urgent" and not prediction.needs_human_review:
            raise ValueError(f"Safety case lacks a human-review flag on row {index + 1}")

    return {
        **checked_metrics(source, results),
        "urgency": dict(Counter(row["urgency_tag"] for row in results)),
        "human_review": sum(row["needs_human_review"].lower() == "true" for row in results),
        "models": dict(Counter(row["model_used"] for row in results)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="Course input, used locally")
    parser.add_argument("results", type=Path, help="Completed OpenRouter classifications")
    parser.add_argument("output", type=Path, help="Tag-only artifact for the exercise review")
    args = parser.parse_args()
    if args.output.resolve() in {args.source.resolve(), args.results.resolve()}:
        parser.error("Output must use a separate path")
    source, results = read_csv(args.source), read_csv(args.results)
    metrics = verify(source, results)
    destination = args.output.with_suffix(args.output.suffix + ".tmp")
    with destination.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    destination.replace(args.output)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
