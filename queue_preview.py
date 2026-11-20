"""Local triage and slot preview for the Streamlit exercise."""

import re
from datetime import date

from fault_urgency_rules import FixPath, FaultUrgencyRule, SAFETY_ALERT_CODES, UrgencyTag
from minimize_reports import PATTERNS
from service_schedule import SAFETY_EVIDENCE, BookingCall, BookingTool, Slot
from verify_results import SAFETY_RECHECK


SAFETY_CODE = re.compile(r"\b(?:" + "|".join(re.escape(code) for code in SAFETY_ALERT_CODES) + r")\b", re.IGNORECASE)
CONCRETE_SAFETY = {
    "Soft or sinking brake pedal.",
    "Reduced brake response or longer stopping distance.",
    "Uncommanded pull during braking or slowing.",
    "Grinding or a marked vibration specifically when braking.",
    "Steering became heavy, stiff, stuck, or intermittent.",
    "Loss of steering assist or difficulty controlling direction.",
}
SOFTWARE = "Screen, account, app, or phone key."
COMFORT = "Wipers, cabin heating, fan, seat, trim, or other comfort feature."
CHARGING = "Charging, range, or charge port."
VAGUE_SAFETY = "Braking or steering mentioned, with limited detail."
TRUNCATED = "The report cuts off mid-thought."
ABS_CUE = "ABS or stability control mentioned."


def explain_safety(text, alert_code=""):
    code = next((code for code in SAFETY_ALERT_CODES if code.casefold() == alert_code.casefold()), "")
    inline_code = SAFETY_CODE.search(text)
    if code or inline_code:
        return "Listed safety alert " + (code or inline_code.group()) + "."
    local_detail = SAFETY_RECHECK.search(text)
    if local_detail:
        return SAFETY_EVIDENCE[local_detail.lastgroup]
    direct = [cue for cue, pattern in PATTERNS.items() if cue in CONCRETE_SAFETY and pattern.search(text)]
    if direct:
        return " ".join(direct)
    if PATTERNS[ABS_CUE].search(text):
        return "ABS or stability symptoms were reported."
    return "Safety tag assigned. Review the underlying report."


def label_message(text):
    cues = {cue for cue, pattern in PATTERNS.items() if pattern.search(text)}
    confident_safety = SAFETY_CODE.search(text) or SAFETY_RECHECK.search(text) or cues & CONCRETE_SAFETY
    if confident_safety:
        return FaultUrgencyRule(urgency_tag=UrgencyTag.SAFETY_URGENT,
                                fix_path=FixPath.PRIORITY_SAFETY_INSPECTION), True
    if not cues or TRUNCATED in cues or ABS_CUE in cues or (VAGUE_SAFETY in cues and COMFORT not in cues):
        return FaultUrgencyRule(urgency_tag=UrgencyTag.SOON, fix_path=FixPath.BOOK_SERVICE_SOON), True
    if CHARGING in cues:
        return FaultUrgencyRule(urgency_tag=UrgencyTag.SOON, fix_path=FixPath.BOOK_SERVICE_SOON), False
    route = FixPath.REMOTE_TROUBLESHOOTING if SOFTWARE in cues and COMFORT not in cues else FixPath.ROUTINE_SERVICE_VISIT
    return FaultUrgencyRule(urgency_tag=UrgencyTag.ROUTINE, fix_path=route), False


def preview_report(text, availability, base_ids, first_day):
    rule, review = label_message(text)
    candidate = re.search(r"\bMSG-\d+\b", text, re.IGNORECASE)
    example_id = candidate.group().upper() if candidate else "New message"
    record = {
        **rule.model_dump(mode="json"),
        "message_id": example_id if example_id not in base_ids else f"Preview of {example_id}",
        "needs_human_review": str(review),
    }
    booking_tool = BookingTool([record], [Slot.model_validate(row) for row in availability],
                               week_start=date.fromisoformat(first_day))
    booking = booking_tool.book_service_slot(BookingCall(request_number=1, **rule.model_dump()))
    summary = [cue for cue, pattern in PATTERNS.items() if pattern.search(text)]
    if not summary and SAFETY_CODE.search(text):
        summary.append("Listed safety alert.")
    return {
        **booking,
        "received_rank": len(base_ids) + 1,
        "technical_summary": " ".join(summary) or "No recognizable technical cue.",
        "safety_evidence": explain_safety(text) if rule.urgency_tag == UrgencyTag.SAFETY_URGENT else "",
    }
