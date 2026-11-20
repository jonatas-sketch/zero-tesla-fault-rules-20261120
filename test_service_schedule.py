import unittest

from service_schedule import BookingCall, BookingTool, Slot


class BookingToolTest(unittest.TestCase):
    def setUp(self):
        requests = [
            ("safety_urgent", "priority_safety_inspection"),
            ("safety_urgent", "priority_safety_inspection"),
            ("routine", "remote_troubleshooting"),
            ("routine", "remote_troubleshooting"),
        ]
        self.calls = [BookingCall(request_number=i, urgency_tag=urgency, fix_path=route)
                      for i, (urgency, route) in enumerate(requests, start=1)]
        records = [dict(call.model_dump(mode="json"), message_id=f"MSG-{i}", needs_human_review="False")
                   for i, call in enumerate(self.calls, start=1)]
        self.tool = BookingTool(records, [
            self.slot("first", "2026-11-16", "service_center_bay"),
            self.slot("next", "2026-11-17", "service_center_bay"),
            self.slot("support", "2026-11-16", "support_callback"),
            self.slot("spare", "2026-11-18", "service_center_bay"),
        ])

    @staticmethod
    def slot(id, date, type):
        return Slot(slot_id=id, slot_date=date, slot_start_time="09:00", duration_minutes=60,
                    slot_type=type, status="open")

    def test_safety_overflow_and_remote_capacity_are_explicit(self):
        results = [self.tool.book_service_slot(call) for call in self.calls]
        self.assertEqual([r["slot_id"] for r in results], ["first", "next", "support", ""])
        self.assertEqual([r["booking_status"] for r in results],
                         ["safety_same_day", "safety_overflow_escalated", "booked", "awaiting_remote_capacity"])
        self.assertTrue(results[-1]["needs_human_review"])
        self.assertEqual(self.tool.book_service_slot(self.calls[0]), results[0])
        self.assertEqual([slot.slot_id for slot in self.tool.slots], ["spare"])

    def test_out_of_order_and_mismatched_arguments_fail_before_booking(self):
        with self.assertRaises(ValueError):
            self.tool.book_service_slot(self.calls[1])
        wrong = BookingCall(request_number=1, urgency_tag="routine", fix_path="remote_troubleshooting")
        with self.assertRaises(ValueError):
            self.tool.book_service_slot(wrong)
        self.assertEqual(len(self.tool.slots), 4)
