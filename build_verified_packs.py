"""Build stage 2 packs only for source segments reviewed against the exercise."""

import argparse
import csv
import json
import math
from pathlib import Path

from build_evidence_pack import build_pack, inspect_video


SUBSTITUTE_PROVENANCE_FIELDS = ("source_url", "source_license", "source_creator", "dataset_gap")


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def build_batch(reference, manifest, output, model):
    reference_rows = read_csv(reference)
    media_rows = read_csv(manifest)
    media = {row["clip_id"]: row for row in media_rows}
    ids = {row["clip_id"] for row in reference_rows}
    if len(ids) != len(reference_rows) or len(media) != len(media_rows) or ids != media.keys():
        raise ValueError("The manifest must cover each reviewer ID exactly once")
    report = []
    context_fields = ("content_category", "is_news_report", "reviewer_guideline_reference")
    for reference_row in reference_rows:
        clip_id = reference_row["clip_id"]
        row = media[clip_id]
        if row["status"] != "verified":
            report.append({"clip_id": clip_id, "status": "pending", "reason": row["review_note"]})
            continue

        try:
            if not row["source_id"] or not row["local_segment"] or not row["review_note"]:
                raise ValueError("A verified match needs provenance, a local segment, and a review note")
            source_match = row.get("source_match") or "original"
            if source_match not in {"original", "equivalent", "substitute"}:
                raise ValueError("Unknown source match kind")
            provenance = {}
            if source_match == "substitute":
                for field in SUBSTITUTE_PROVENANCE_FIELDS:
                    value = row.get(field, "").strip()
                    if not value:
                        raise ValueError(f"External substitute requires {field}")
                    provenance[field] = value
                if not provenance["source_url"].startswith("https://"):
                    raise ValueError("External substitute requires an HTTPS source reference")
            checked_fields = (*context_fields, "reviewer_decision") if source_match == "original" else context_fields
            for field in checked_fields:
                if row[field].strip().casefold() != reference_row[field].strip().casefold():
                    raise ValueError(f"Source differs from the reference on {field}")
            offsets = float(row["source_start_seconds"]), float(row["source_end_seconds"])
            if not all(map(math.isfinite, offsets)) or not 0 <= offsets[0] < offsets[1]:
                raise ValueError("Source offsets are invalid")
            video = (manifest.parent / row["local_segment"]).resolve()
            length, _ = inspect_video(video)
            reference_duration = float(reference_row["duration_seconds"])
            if abs(offsets[1] - offsets[0] - length) > 0.1:
                raise ValueError("Trimmed segment does not match the recorded source interval")
            if source_match == "original" and abs(length - reference_duration) > 0.1:
                raise ValueError("Original segment does not match the reference duration")
            range_fields = ("reviewer_harm_start_seconds", "reviewer_harm_end_seconds")
            recorded = [row[field].strip() for field in range_fields]
            if source_match != "original":
                if any(recorded):
                    start, end = map(float, recorded)
                    if not all(map(math.isfinite, (start, end))) or not 0 <= start < end <= length:
                        raise ValueError("Observed evidence range is outside the equivalent clip")
            else:
                expected = [reference_row[field].strip() for field in range_fields]
                if [float(x) if x else None for x in recorded] != [float(x) if x else None for x in expected]:
                    raise ValueError("Verified evidence offsets differ from the original reference")
            pack = build_pack(video, output, clip_id, "reviewer_source", model)
            report.append({
                "clip_id": clip_id,
                "status": "built",
                "pack": pack.name,
                "source_id": row["source_id"],
                "source_match": source_match,
                "source_duration_seconds": length,
                "source_interval_seconds": list(offsets),
                **provenance,
            })
        except Exception as error:
            report.append({"clip_id": clip_id, "status": "failed", "reason": str(error)})

    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "build-report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="base")
    args = parser.parse_args()
    rows = build_batch(args.reference, args.manifest, args.output, args.model)
    counts = {status: sum(row["status"] == status for row in rows) for status in ("built", "pending", "failed")}
    print(json.dumps(counts))
    return int(counts["built"] != len(rows))


if __name__ == "__main__":
    raise SystemExit(main())
