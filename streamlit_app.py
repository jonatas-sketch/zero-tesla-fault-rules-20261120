"""Morning fault queue for the Zero Tesla practice project."""

from pathlib import Path

import pandas as pd
import streamlit as st

from queue_preview import preview_report
from service_schedule import RANK
from verify_results import read_csv


ROOT = Path(__file__).resolve().parent
URGENCY = {"safety_urgent": "Safety urgent", "soon": "Soon", "routine": "Routine"}
ROUTES = {
    "priority_safety_inspection": "Priority safety inspection",
    "book_service_soon": "Book service soon",
    "routine_service_visit": "Routine service visit",
    "remote_troubleshooting": "Remote troubleshooting",
}
STATUS = {
    "safety_same_day": "Same-day safety",
    "safety_overflow_escalated": "Safety escalation",
    "booked": "Reserved",
    "awaiting_remote_capacity": "Awaiting remote capacity",
    "awaiting_compatible_capacity": "Awaiting compatible capacity",
}
EXERCISE_EXAMPLE = ("MSG-10309. We had a lovely weekend trip. On the way back the brake pedal went further down "
                    "before the car slowed, and there was faint grinding at a full stop. No rush whenever a slot opens.")


def load_data():
    messages = read_csv(ROOT / "queue-messages.csv")
    for row in messages:
        row["received_rank"] = int(row["received_rank"])
    return messages, read_csv(ROOT / "queue-availability.csv")


def slot_text(row):
    return f'{row["slot_date"]} · {row["slot_start_time"]} · {row["slot_id"]}' if row["slot_id"] else "Pending"


def display_row(row):
    return {
        "Message ID": row["message_id"],
        "Urgency": URGENCY[row["urgency_tag"]],
        "Fix path": ROUTES[row["fix_path"]],
        "Service slot": slot_text(row),
        "Status": ("Preview · " if row.get("is_preview") else "") + STATUS[row["booking_status"]],
        "Safety evidence": row["safety_evidence"],
        "Technical summary": row["technical_summary"],
        "Human review": str(row["needs_human_review"]).casefold() == "true",
    }


def show_preview(messages, availability):
    st.subheader("Check a new message")
    result_area = st.container()
    if st.button("Load brake-warning example", key="load_example"):
        st.session_state["source_message"] = EXERCISE_EXAMPLE
    with st.form("preview_form"):
        text = st.text_area("Paste a fault message", height=160, max_chars=2500, key="source_message")
        submitted = st.form_submit_button("Classify and preview slot", type="primary", width="stretch")
    if submitted:
        if text.strip():
            first_day = min(row["slot_date"] for row in messages if row["slot_date"])
            preview = preview_report(text.strip(), availability, {row["message_id"] for row in messages}, first_day)
            st.session_state["message_preview"] = {**preview, "is_preview": True}
        else:
            st.warning("Paste a message to see its urgency and slot.")
    preview = st.session_state.get("message_preview")
    if preview:
        with result_area.container(border=True):
            level = URGENCY[preview["urgency_tag"]]
            if preview["urgency_tag"] == "safety_urgent":
                st.error(f'{preview["message_id"]} · {level}')
            else:
                st.info(f'{preview["message_id"]} · {level}')
            st.caption(preview["safety_evidence"] or preview["technical_summary"])
            st.write(ROUTES[preview["fix_path"]])
            st.write(slot_text(preview))
            st.caption(STATUS[preview["booking_status"]] + " · Test only")
        if st.button("Remove test row"):
            st.session_state.pop("message_preview", None)
            st.rerun()
    return preview


def main():
    st.set_page_config(page_title="Morning fault queue", layout="wide")
    st.title("Morning fault queue")
    st.caption("16–21 November 2026 · Overnight service review")
    messages, availability = load_data()
    metrics = st.columns(4)
    metrics[0].metric("Overnight reports", len(messages))
    metrics[1].metric("Safety urgent", sum(row["urgency_tag"] == "safety_urgent" for row in messages))
    metrics[2].metric("Reserved slots", sum(bool(row["slot_id"]) for row in messages))
    metrics[3].metric("Awaiting capacity", sum(not row["slot_id"] for row in messages))
    escalated = sum(row["booking_status"] == "safety_overflow_escalated" for row in messages)
    st.warning(f"{escalated} safety reports need immediate escalation because Monday's bays are full.")

    left, right = st.columns([2.4, 1], gap="large")
    with right:
        preview = show_preview(messages, availability)
    with left:
        st.subheader("Service queue")
        st.caption("Urgency first. Oldest report first within each urgency.")
        controls = st.columns([1, 1.5])
        level = controls[0].selectbox("Urgency", ["All", *URGENCY.values()])
        search = controls[1].text_input("Find a message", placeholder="Exercise ID or symptom").casefold().strip()
        rows = [*messages, preview] if preview else messages
        rows = sorted(rows, key=lambda row: (RANK[row["urgency_tag"]], row["received_rank"], row["message_id"]))
        visible = [display_row(row) for row in rows if (level == "All" or URGENCY[row["urgency_tag"]] == level)
                   and (not search or search in (row["message_id"] + " " + row["technical_summary"]).casefold())]
        if visible:
            st.dataframe(pd.DataFrame(visible), height=min(540, 40 + 35 * len(visible)), hide_index=True, width="stretch",
                         column_config={"Safety evidence": st.column_config.TextColumn(width="medium"),
                                        "Technical summary": st.column_config.TextColumn(width="large"),
                                        "Human review": st.column_config.CheckboxColumn()})
            st.caption(f"{len(visible)} {'message' if len(visible) == 1 else 'messages'} shown")
        else:
            st.info("No messages match these filters.")


if __name__ == "__main__":
    main()
