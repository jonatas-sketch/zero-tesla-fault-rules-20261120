"""Compare verified video decisions to the course reviewer baseline."""

import argparse
from collections import Counter
import json
import math
from pathlib import Path

from build_verified_packs import SUBSTITUTE_PROVENANCE_FIELDS, read_csv
from classify_upload import classify, load_key


ACTIONS = {"allow", "restrict", "remove"}
REVIEW_REQUIRED = {"restrict", "remove"}
LEGACY_BUCKET = {
    (True, True): "tp",
    (True, False): "fp",
    (False, True): "fn",
    (False, False): "tn",
}


def score_benchmark(reference, packs, key, model, trace=None):
    rows = read_csv(reference)
    ids = {row["clip_id"] for row in rows}
    if len(rows) != 12 or len(ids) != 12:
        raise ValueError("This exercise requires twelve different reviewer IDs")

    records = json.loads((packs / "build-report.json").read_text())
    built = {record["clip_id"]: record for record in records}
    if len(records) != len(built) or built.keys() != ids:
        raise ValueError("The build report must cover the twelve reviewer IDs once")

    legacy = Counter(dict.fromkeys(LEGACY_BUCKET.values(), 0))
    report = []
    for reference_row in rows:
        clip_id = reference_row["clip_id"]
        expected = reference_row["reviewer_decision"]
        news = reference_row["is_news_report"].casefold()
        flag = reference_row["current_filter_flag"]
        if expected not in ACTIONS or news not in {"true", "false"} or flag not in {"flagged_harmful", "not_flagged"}:
            raise ValueError(f"Unrecognized reference fields for {clip_id}")
        intervention = expected in REVIEW_REQUIRED
        flagged = flag == "flagged_harmful"
        legacy[LEGACY_BUCKET[flagged, intervention]] += 1

        record = built[clip_id]
        result = {
            "clip_id": clip_id,
            "decision": None,
            "status": record["status"],
            "reference_action": expected,
            "is_news": news == "true",
        }
        if record["status"] == "built":
            path = packs / clip_id / "pack.json"
            evidence = json.loads(path.read_text())
            reference_duration = float(reference_row["duration_seconds"])
            source_match = record.get("source_match", "original")
            source_duration = record.get("source_duration_seconds", reference_duration)
            expected_duration = reference_duration if source_match == "original" else source_duration
            if (
                not record.get("source_id") or record.get("pack") != clip_id
                or evidence["clip_id"] != clip_id or evidence["source_kind"] != "reviewer_source"
                or source_match not in {"original", "equivalent", "substitute"}
                or not math.isclose(float(evidence["duration_seconds"]), expected_duration, abs_tol=0.1)
            ):
                raise ValueError(f"Pack provenance or duration differs for {clip_id}")
            if source_match == "substitute" and (
                any(not record.get(field) for field in SUBSTITUTE_PROVENANCE_FIELDS)
                or not record["source_url"].startswith("https://")
            ):
                raise ValueError(f"External source provenance is incomplete for {clip_id}")
            prediction = classify(path, key, model, trace=trace)
            result["status"] = prediction["status"]
            for field in ("reason", "trace_id", "trace_error"):
                if field in prediction:
                    result[field] = prediction[field]
            if prediction["status"] == "validated_recommendation":
                result["decision"] = prediction["finding"]["action"]
                result["rule_id"] = prediction["finding"]["rule_id"]
            elif prediction.get("finding"):
                result["review_context"] = prediction["finding"]["context_summary"]
            result["source_id"] = record["source_id"]
            result["source_match"] = source_match
            result["source_duration_seconds"] = source_duration
            result["reference_duration_seconds"] = reference_duration
            for field in ("source_interval_seconds", *SUBSTITUTE_PROVENANCE_FIELDS):
                if field in record:
                    result[field] = record[field]
        report.append(result)

    evaluated = [row for row in report if row["decision"] in ACTIONS]
    matches = sum(row["decision"] == row["reference_action"] for row in evaluated)
    evaluated_news = [row for row in evaluated if row["is_news"]]
    news_removals = sum(row["decision"] == "remove" for row in evaluated_news)
    traces_submitted = sum("trace_id" in row for row in report)
    return {
        "required": len(rows),
        "verified_packs": sum(record["status"] == "built" for record in records),
        "equivalent_packs": sum(row.get("source_match") == "equivalent" for row in report),
        "substitute_packs": sum(row.get("source_match") == "substitute" for row in report),
        "decisions_scored": len(evaluated),
        "matches": matches,
        "agreement": matches / len(evaluated) if evaluated else None,
        "news_rows_scored": len(evaluated_news),
        "news_removals": news_removals if evaluated_news else None,
        "langsmith_traces_submitted": traces_submitted,
        "decision_gates_met": len(evaluated) == len(rows) and matches >= 11 and news_removals == 0,
        "legacy_binary_confusion": dict(legacy),
        "clips": report,
    }


def main():
    from trace_langsmith import load_tracer

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("packs", type=Path)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--langsmith-env-file", type=Path)
    parser.add_argument("--model", default="gemini-3.1-flash-lite")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    trace = load_tracer(args.langsmith_env_file or args.env_file)
    report = score_benchmark(args.reference, args.packs, load_key(args.env_file), args.model, trace=trace)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(f"{report['decisions_scored']}/{report['required']} benchmark decisions evaluated")
    return int(not report["decision_gates_met"] or report["langsmith_traces_submitted"] != report["required"])


if __name__ == "__main__":
    raise SystemExit(main())
