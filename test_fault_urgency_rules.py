import unittest

from pydantic import ValidationError

from fault_urgency_rules import FaultUrgencyRule


class FaultUrgencyRuleTest(unittest.TestCase):
    def test_valid_routine_routes(self):
        for path in ("routine_service_visit", "remote_troubleshooting"):
            with self.subTest(path=path):
                rule = FaultUrgencyRule(urgency_tag="routine", fix_path=path)
                self.assertEqual(rule.fix_path, path)

    def test_rejects_made_up_tag(self):
        with self.assertRaises(ValidationError):
            FaultUrgencyRule(urgency_tag="whenever", fix_path="routine_service_visit")

    def test_rejects_made_up_path(self):
        with self.assertRaises(ValidationError):
            FaultUrgencyRule(urgency_tag="soon", fix_path="ignore")

    def test_urgent_requires_safety_route(self):
        with self.assertRaises(ValidationError):
            FaultUrgencyRule(urgency_tag="safety_urgent", fix_path="routine_service_visit")


if __name__ == "__main__":
    unittest.main()
