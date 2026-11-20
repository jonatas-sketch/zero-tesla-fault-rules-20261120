"""Prepare the technical data shown by the Streamlit exercise."""

import argparse
import csv
from datetime import datetime
from pathlib import Path

from minimize_reports import minimize
from service_schedule import indexed
from verify_results import read_csv


def write_rows(path, rows):
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def prepare_queue(original, schedule):
    source = indexed(original, "message_id")
    by_id = indexed(schedule, "message_id")
    if len(source) != 300 or source.keys() != by_id.keys():
        raise ValueError("Expected the same 300 IDs in the source and schedule")
    arrivals = sorted(original, key=lambda row: (datetime.fromisoformat(row["received_at"]), row["message_id"]))
    received_order = {row["message_id"]: rank for rank, row in enumerate(arrivals, start=1)}
    return [
        {
            "message_id": item["message_id"],
            "received_rank": received_order[item["message_id"]],
            "technical_summary": minimize(source[item["message_id"]])["message_text"],
            "urgency_tag": item["urgency_tag"],
            "fix_path": item["fix_path"],
            "booking_status": item["booking_status"],
            "slot_id": item["slot_id"],
            "slot_date": item["slot_date"],
            "slot_start_time": item["slot_start_time"],
            "needs_human_review": item["needs_human_review"],
        }
        for item in schedule
    ]


def prepare_availability(slots, schedule):
    used = {row["slot_id"] for row in schedule if row["slot_id"]}
    fields = ("slot_id", "slot_date", "slot_start_time", "slot_type", "duration_minutes", "status")
    return [{key: row[key] for key in fields} for row in slots
            if row["status"] == "open" and row["slot_id"] not in used]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("original", type=Path)
    parser.add_argument("schedule", type=Path)
    parser.add_argument("slots", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    original, schedule, slots = map(read_csv, (args.original, args.schedule, args.slots))
    write_rows(args.output_dir / "queue-messages.csv", prepare_queue(original, schedule))
    write_rows(args.output_dir / "queue-availability.csv", prepare_availability(slots, schedule))


if __name__ == "__main__":
    main()
