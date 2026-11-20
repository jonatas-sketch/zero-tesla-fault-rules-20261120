import io
import json
import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from classify_batch import FREE_MODEL, classify
from minimize_reports import minimize


class ExternalClassificationTest(unittest.TestCase):
    def test_request_excludes_raw_fields_and_resumes_after_temporary_limit(self):
        raw = {
            "message_id": "private-row-id",
            "customer_name": "Example Customer",
            "vin_last6": "ABC123",
            "vehicle_alert_code": "BRK_a001",
            "message_subject": "Note from Example Customer",
            "message_text": "Example Customer, VIN ABC123: the brake pedal sank toward the floor.",
            "hand_checked": "TRUE",
            "hand_checked_safety_fault": "TRUE",
        }
        reduced = minimize(raw)
        self.assertIn("Soft or sinking brake pedal.", reduced["message_text"])
        decision = {"fix_path": "routine_service_visit", "needs_human_review": False}
        good_response = io.BytesIO(json.dumps({
            "choices": [{"message": {"content": json.dumps(decision)}}],
            "model": FREE_MODEL,
        }).encode())
        quota_error = HTTPError("https://openrouter.ai/api/v1/chat/completions", 429, "", {"Retry-After": "1"}, None)
        snapshots = []
        with (
            patch.dict(os.environ, {"OPENROUTER_API_KEY": "mock-secret"}),
            patch("classify_batch.urlopen", side_effect=[quota_error, good_response]) as request,
            patch("classify_batch.sleep") as wait,
        ):
            result = classify([reduced], "openrouter", FREE_MODEL, 1, checkpoint=lambda saved: snapshots.append(list(saved)))

        self.assertEqual(request.call_count, 2)
        wait.assert_called_once_with(4)
        for call in request.call_args_list:
            payload = json.loads(call.args[0].data)
            content = json.loads(payload["messages"][1]["content"])
            self.assertEqual(set(content), {"index", "alert_code", "subject", "description"})
            self.assertNotIn("Example Customer", content["description"])
            self.assertNotIn("ABC123", content["description"])
            self.assertNotIn("private-row-id", json.dumps(content))
        self.assertEqual(result[0]["urgency_tag"], "safety_urgent")
        self.assertEqual(result[0]["model_used"], FREE_MODEL)
        self.assertEqual(snapshots, [result])
        with patch("classify_batch.urlopen") as request:
            self.assertEqual(classify([reduced], "openrouter", FREE_MODEL, 1, existing=result), result)
            request.assert_not_called()
