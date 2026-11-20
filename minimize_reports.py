"""Project the course CSV to fixed technical phrases before external inference."""

import argparse
import csv
import re
from pathlib import Path

from fault_urgency_rules import SAFETY_ALERT_CODES


COMFORT_CODES = {"HVAC_w003", "UI_a004", "WIP_w001", "CP_a004"}
TECHNICAL_CUES = {
    "Soft or sinking brake pedal.": r"(?:soft|spongy|squishy)\b.{0,35}\bpedal|\bpedal\b.{0,45}\b(?:soft|spongy|squishy|sink|sank|floor|travel|lower|press twice)",
    "Reduced brake response or longer stopping distance.": r"(?:tak(?:es?|ing)|took|need(?:s|ed)?|takes a bit)\b.{0,35}\b(?:longer|more distance|more room)\b.{0,45}\b(?:stop|brak)|\b(?:longer to stop|stopping distance|brakes? (?:barely|almost|aren.t|don.t))\b",
    "Uncommanded pull during braking or slowing.": r"\b(?:pull\w*|drift\w*|veer\w*)\b.{0,65}\b(?:brak\w*|slow\w*|stop\w*)|\b(?:brak\w*|slow\w*|stop\w*)\b.{0,65}\b(?:pull\w*|drift\w*|veer\w*)",
    "Grinding or a marked vibration specifically when braking.": r"\b(?:grind\w*|vibrat\w*|grabb?\w*)\b.{0,55}\b(?:brak\w*|slow\w*|stop\w*)|\b(?:brak\w*|slow\w*|stop\w*)\b.{0,55}\b(?:grind\w*|vibrat\w*|grabb?\w*)",
    "Steering became heavy, stiff, stuck, or intermittent.": r"\b(?:steer\w*|wheel)\b.{0,55}\b(?:heavy|stiff|stuck|locked|tight|hard to turn|jerk\w*|cut\w* out)|\b(?:heavy|stiff|stuck|locked)\b.{0,25}\b(?:steer\w*|wheel)",
    "Loss of steering assist or difficulty controlling direction.": r"\b(?:lost|loss|no|without)\b.{0,28}\b(?:assist|steering|control)|\b(?:hard|difficult|couldn.t|can.t)\b.{0,25}\b(?:steer|turn the wheel|keep.{0,12}straight)|\b(?:steering|steer|wheel)\b.{0,35}\b(?:unresponsive|play|dead zone)",
    "Braking or steering mentioned, with limited detail.": r"\b(?:brak\w*|steering|brake pedal)\b",
    "ABS or stability control mentioned.": r"\b(?:abs|stability control|traction control|brake warning)\b",
    "Unexpected driving or suspension noise.": r"\b(?:clunk\w*|suspension|over bumps|grind\w*|rattl\w*)\b",
    "Charging, range, or charge port.": r"\b(?:charg\w*|range|charge port)\b",
    "Wipers, cabin heating, fan, seat, trim, or other comfort feature.": r"\b(?:wiper\w*|hvac|heater|climate|cabin|fan|seat|trim|rattl\w*|door handle)\b",
    "Screen, account, app, or phone key.": r"\b(?:screen|touchscreen|phone key|bluetooth|app|account|profile|unlock\w*|infotainment)\b",
    "The report cuts off mid-thought.": r"(?:\.\.\.|…|—|\[cut off\])\s*$",
}
PATTERNS = {cue: re.compile(pattern, re.IGNORECASE | re.DOTALL) for cue, pattern in TECHNICAL_CUES.items()}


def minimize(row):
    report = row["message_subject"] + "\n" + row["message_text"]
    cues = [cue for cue, pattern in PATTERNS.items() if pattern.search(report)]
    code = row["vehicle_alert_code"]
    return {
        "message_id": row["message_id"],
        "vehicle_alert_code": code if code in SAFETY_ALERT_CODES or code in COMFORT_CODES else "NONE",
        "message_subject": "Vehicle fault exercise",
        "message_text": " ".join(cues) or "No recognizable technical cue. Flag for manual review.",
        "hand_checked": row["hand_checked"],
        "hand_checked_safety_fault": row["hand_checked_safety_fault"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("result", type=Path)
    args = parser.parse_args()
    if args.source.resolve() == args.result.resolve():
        parser.error("Input and minimized output must have different paths")
    with args.source.open(encoding="utf-8-sig", newline="") as source:
        rows = [minimize(row) for row in csv.DictReader(source)]
    if not rows:
        parser.error("No input rows")
    with args.result.open("w", encoding="utf-8", newline="") as result:
        writer = csv.DictWriter(result, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
