"""Book the simulated overnight faults against the supplied service inventory."""

import argparse
import csv
import hashlib
import json
import os
from collections import Counter
from datetime import date, datetime, time
from pathlib import Path
from time import monotonic, sleep
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field, ValidationError

from classify_batch import FREE_MODEL, checked_metrics
from fault_urgency_rules import FixPath, FaultUrgencyRule, UrgencyTag
from minimize_reports import minimize
from verify_results import SAFETY_RECHECK, read_csv


TOOL_NAME = "book_service_slot"
RANK = {UrgencyTag.SAFETY_URGENT: 0, UrgencyTag.SOON: 1, UrgencyTag.ROUTINE: 2}
BAY = "service_center_bay"
PHYSICAL = {BAY, "mobile_service_visit"}
REMOTE = {"remote_ota_or_diagnostic", "support_callback"}
SAFETY_EVIDENCE = {
    "pulling_while_stopping": "The vehicle pulls to one side while stopping.",
    "pedal_noise": "Grinding or scraping occurs when the brake pedal is pressed.",
    "wheel_wobble": "The steering wheel shimmies or wobbles while driving.",
    "steering_control": "The steering feels unusually heavy or loose.",
    "persistent_correction": "Repeated steering correction is needed on a flat road.",
    "pedal_travel": "The brake pedal travels further before the brakes engage.",
}


class Slot(BaseModel):
    slot_id: str
    slot_date: date
    slot_start_time: time
    duration_minutes: int = Field(gt=0)
    slot_type: str
    status: str


class BookingCall(FaultUrgencyRule):
    request_number: int = Field(gt=0)


def indexed(rows, key):
    by_id = {row[key]: row for row in rows}
    if len(by_id) != len(rows):
        raise ValueError(f"Duplicate {key} values")
    return by_id


def prepare_records(original_rows, tagged_rows):
    original = indexed(original_rows, "message_id")
    tagged = indexed(tagged_rows, "message_id")
    if len(original) != 300 or original.keys() != tagged.keys():
        raise ValueError("Expected identical sets of 300 original and tagged records")
    for row in tagged_rows:
        FaultUrgencyRule(urgency_tag=row["urgency_tag"], fix_path=row["fix_path"])
    ordered = sorted(tagged_rows, key=lambda row: (
        RANK[row["urgency_tag"]],
        datetime.fromisoformat(original[row["message_id"]]["received_at"]),
        row["message_id"],
    ))
    calls = [BookingCall(request_number=n, urgency_tag=row["urgency_tag"], fix_path=row["fix_path"])
             for n, row in enumerate(ordered, start=1)]
    return ordered, calls


class BookingTool:
    def __init__(self, records, slots):
        if not slots or len({slot.slot_id for slot in slots}) != len(slots):
            raise ValueError("Missing inventory or duplicate slot IDs")
        self.records = records
        self.slots = sorted((slot for slot in slots if slot.status == "open"),
                            key=lambda slot: (slot.slot_date, slot.slot_start_time, slot.slot_id))
        if not self.slots:
            raise ValueError("Inventory has no open slots")
        self.first_day = self.slots[0].slot_date
        self.reserved = {}

    def book_service_slot(self, call):
        if not 1 <= call.request_number <= len(self.records):
            raise ValueError("Unknown booking request")
        record = self.records[call.request_number - 1]
        if (call.urgency_tag, call.fix_path) != (record["urgency_tag"], record["fix_path"]):
            raise ValueError("Tool arguments disagree with the tagged record")
        if call.request_number in self.reserved:
            return self.reserved[call.request_number]
        if call.request_number != len(self.reserved) + 1:
            raise ValueError("Bookings must follow the ordered queue")

        is_safety = call.urgency_tag == UrgencyTag.SAFETY_URGENT
        is_remote = call.fix_path == FixPath.REMOTE_TROUBLESHOOTING
        eligible = {BAY} if is_safety else (REMOTE if is_remote else PHYSICAL)
        slot = next((item for item in self.slots if item.slot_type in eligible), None)
        if slot:
            self.slots.remove(slot)
            if is_safety:
                state = "safety_same_day" if slot.slot_date == self.first_day else "safety_overflow_escalated"
            else:
                state = "booked"
        else:
            state = "awaiting_remote_capacity" if is_remote else "awaiting_compatible_capacity"
        result = {
            "message_id": record["message_id"],
            "urgency_tag": call.urgency_tag.value,
            "fix_path": call.fix_path.value,
            "slot_id": slot.slot_id if slot else "",
            "slot_date": slot.slot_date.isoformat() if slot else "",
            "slot_start_time": slot.slot_start_time.strftime("%H:%M") if slot else "",
            "duration_minutes": slot.duration_minutes if slot else "",
            "slot_type": slot.slot_type if slot else "",
            "booking_status": state,
            "needs_human_review": record["needs_human_review"].casefold() == "true"
            or is_safety or slot is None,
        }
        self.reserved[call.request_number] = result
        return result


class OpenRouterBookingCalls:
    def __init__(self, key):
        self.key = key
        self.next_request = 0.0

    def request(self, calls):
        payload = {
            "model": FREE_MODEL,
            "temperature": 0,
            "max_tokens": 1500,
            "reasoning": {"enabled": False},
            "provider": {"max_price": {"prompt": 0, "completion": 0}},
            "parallel_tool_calls": True,
            "tool_choice": "required",
            "tools": [{"type": "function", "function": {
                "name": TOOL_NAME,
                "description": "Book one record in the local service exercise.",
                "parameters": BookingCall.model_json_schema(),
            }}],
            "messages": [
                {"role": "system", "content": "Call book_service_slot once for every record. Copy all three fields exactly in separate tool calls. Use parallel tool calls and no prose."},
                {"role": "user", "content": json.dumps([call.model_dump(mode="json") for call in calls])},
            ],
        }
        request = Request("https://openrouter.ai/api/v1/chat/completions", json.dumps(payload).encode(),
                          headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"})
        for delay in (5, 15, 0):
            sleep(max(0.0, self.next_request - monotonic()))
            self.next_request = monotonic() + 3.5
            try:
                with urlopen(request, timeout=45) as response:
                    return json.load(response)
            except HTTPError as error:
                if error.code not in {429, 500, 502, 503, 504} or delay == 0:
                    raise RuntimeError(f"OpenRouter HTTP {error.code}") from None
                retry_after = error.headers.get("Retry-After", "")
                if retry_after.isdecimal() and int(retry_after) > 60:
                    raise RuntimeError(f"OpenRouter asks to wait {retry_after} seconds") from None
                sleep(max(delay, int(retry_after) if retry_after.isdecimal() else 0))

    def get_receipts(self, calls):
        result = self.request(calls)
        if result.get("model") != FREE_MODEL or not result.get("id"):
            raise RuntimeError("Missing the expected free-model receipt")
        try:
            tool_calls = result["choices"][0]["message"]["tool_calls"]
            expected = {call.request_number: call for call in calls}
            receipts = {}
            seen_call_ids = set()
            for event in tool_calls:
                function = event["function"]
                call = BookingCall.model_validate_json(function["arguments"])
                if function["name"] != TOOL_NAME or call != expected.get(call.request_number):
                    raise ValueError("Tool arguments differ from the request")
                event_id = event["id"]
                if not event_id or call.request_number in receipts or event_id in seen_call_ids:
                    raise ValueError("Duplicate or missing tool call ID")
                receipts[call.request_number] = {
                    "arguments": call.model_dump(mode="json"),
                    "tool_call_id": event_id,
                    "completion_id": result["id"],
                }
                seen_call_ids.add(event_id)
            if receipts.keys() != expected.keys():
                raise ValueError("Model did not return one tool call per record")
            return receipts
        except (IndexError, KeyError, TypeError, ValidationError, ValueError):
            if len(calls) == 1:
                raise RuntimeError("OpenRouter did not return a valid booking call") from None
            midpoint = len(calls) // 2
            return self.get_receipts(calls[:midpoint]) | self.get_receipts(calls[midpoint:])


def write_safety_report(path, original, baseline, tagged, schedule):
    initial_tags = indexed(baseline, "message_id")
    final_tags = indexed(tagged, "message_id")
    initial = checked_metrics(original, [initial_tags[row["message_id"]] for row in original])
    final = checked_metrics(original, [final_tags[row["message_id"]] for row in original])
    counts = Counter(row["booking_status"] for row in schedule)
    overflow = Counter(row["slot_date"] for row in schedule if row["booking_status"] == "safety_overflow_escalated")
    lines = [
        "# Morning fault queue safety report", "",
        f"The comparison joins {final['checked']} hand-checked rows by exercise message ID.",
        f"The initial OpenRouter and alert-code pass detected {initial['detected']} of {initial['checked_positives']} reviewed positives, with {initial['missed']} false negatives.",
        f"After local evidence review, the submitted tags cover {final['detected']} of {final['checked_positives']} reviewed positives and have {final['missed']} residual false negatives.",
        "The reviewed subset contains only positives. These counts measure batch coverage and cannot establish precision, specificity, or general accuracy.", "",
        "## Initial model misses", "",
        "| Exercise ID | Initial | Expected | Technical context |", "|---|---|---|---|",
    ]
    for row in original:
        prediction = initial_tags[row["message_id"]]["urgency_tag"]
        if row["hand_checked"] == "TRUE" and row["hand_checked_safety_fault"] == "TRUE" and prediction != "safety_urgent":
            observed = SAFETY_RECHECK.search(row["message_text"])
            reason = SAFETY_EVIDENCE.get(observed.lastgroup) if observed else None
            lines.append(f"| {row['message_id']} | {prediction} | safety_urgent | {reason or minimize(row)['message_text']} |")
    lines.extend(["", "## Booking results", ""])
    lines.extend(f"- {state.replace('_', ' ')} — {count}" for state, count in counts.items())
    lines.extend(f"- Safety overflow on {day} — {count}" for day, count in sorted(overflow.items()))
    lines.extend(["", "Safety overflow cases get immediate advisor escalation. The later bay remains reserved for priority inspection.",
                  "Cases awaiting remote capacity have no slot ID. An advisor reviews them before booking any alternative.",
                  "This exercise uses the supplied unique slot IDs. Technician and facility coverage would need separate validation in a live schedule.", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--tags", type=Path, required=True)
    parser.add_argument("--slots", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--checkpoints", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        parser.error("Set OPENROUTER_API_KEY to use the free booking model")
    original, tags = read_csv(args.original), read_csv(args.tags)
    records, calls = prepare_records(original, tags)
    slots = [Slot.model_validate(row) for row in read_csv(args.slots)]
    booking_tool = BookingTool(records, slots)
    inputs = {"model": FREE_MODEL, **{name: hashlib.sha256(getattr(args, name).read_bytes()).hexdigest()
                                    for name in ("original", "tags", "slots")}}
    receipts = {}
    if args.checkpoints.exists():
        checkpoint = json.loads(args.checkpoints.read_text())
        if checkpoint["inputs"] != inputs:
            parser.error("Tool receipts do not match the supplied inputs")
        receipts = {int(number): receipt for number, receipt in checkpoint["receipts"].items()}
    endpoint = OpenRouterBookingCalls(key)
    missing = [call for call in calls if call.request_number not in receipts]
    for start in range(0, len(missing), 8):
        receipts.update(endpoint.get_receipts(missing[start:start + 8]))
        temp = args.checkpoints.with_suffix(".tmp")
        temp.write_text(json.dumps({"inputs": inputs, "receipts": receipts}))
        temp.replace(args.checkpoints)
        print(f"Validated booking tool requests: {len(receipts)}/{len(calls)}", flush=True)
    if set(receipts) != {call.request_number for call in calls}:
        raise ValueError("Missing or unexpected booking tool requests")
    schedule = [booking_tool.book_service_slot(BookingCall.model_validate(receipts[call.request_number]["arguments"]))
                for call in calls]
    write_safety_report(args.report, original, read_csv(args.baseline), tags, schedule)
    temp_output = args.output.with_suffix(".tmp")
    with temp_output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(schedule[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(schedule)
    temp_output.replace(args.output)
    print(json.dumps(dict(Counter(row["booking_status"] for row in schedule))))


if __name__ == "__main__":
    main()
