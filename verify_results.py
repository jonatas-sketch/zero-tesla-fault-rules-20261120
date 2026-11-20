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
SAFETY_RECHECK = re.compile(
    r"(?P<pulling_while_stopping>\b(?:car|vehicle) (?:tugs?|pulls?) (?:gently )?(?:to the )?(?:left|right)\b"
    r".{0,35}\b(?:when i (?:come to a )?stop|while braking)\b"
    r"|\bwhen i (?:come to a )?stop\b.{0,35}\bthe car (?:tugs?|pulls?)\b)"
    r"|(?P<pedal_noise>\bpress the (?:brake )?pedal\b.{0,45}\b(?:grinding feel|scraping)\b)"
    r"|(?P<wheel_wobble>\bsteering wheel (?:starts? to )?(?:shimmy|wobbl\w*)\b)"
    r"|(?P<steering_control>\bsteering(?: wheel)? feels (?:heav(?:y|ier)|loose)\b)"
    r"|(?P<persistent_correction>\b(?:pulls?|tugs?)\b.{0,45}\b(?:straight.? )?flat road\b"
    r".{0,80}\b(?:have|need) to keep correcting\b)"
    r"|(?P<pedal_travel>\bbrake pedal (?:goes|travels)\b.{0,40}\blong before it bites\b)",
    re.IGNORECASE,
)


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
        if not prediction.model_used or not prediction.model_used.endswith(":free"):
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


def recheck_safety_notes(source, results):
    """Apply the same safety rule to concrete details lost by the projection."""
    reviewed = []
    overrides = 0
    for raw, row in zip(source, results, strict=True):
        if row["urgency_tag"] != "safety_urgent" and SAFETY_RECHECK.search(raw["message_text"]):
            row = {**row, "urgency_tag": "safety_urgent", "fix_path": "priority_safety_inspection", "needs_human_review": "True"}
            overrides += 1
        reviewed.append(row)
    return reviewed, overrides


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="Course input, used locally")
    parser.add_argument("results", type=Path, help="Completed OpenRouter classifications")
    parser.add_argument("output", type=Path, help="Tag-only artifact for the exercise review")
    args = parser.parse_args()
    if args.output.resolve() in {args.source.resolve(), args.results.resolve()}:
        parser.error("Output must use a separate path")
    source, results = read_csv(args.source), read_csv(args.results)
    model_metrics = verify(source, results)
    results, overrides = recheck_safety_notes(source, results)
    metrics = {
        "model_run": model_metrics,
        "local_safety_overrides": overrides,
        "exported_queue": verify(source, results),
    }
    destination = args.output.with_suffix(args.output.suffix + ".tmp")
    with destination.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=OUTPUT_FIELDS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(results)
    destination.replace(args.output)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
