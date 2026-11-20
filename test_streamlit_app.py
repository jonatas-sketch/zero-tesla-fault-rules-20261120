import unittest

from streamlit.testing.v1 import AppTest


class MorningQueueTest(unittest.TestCase):
    def test_brake_case_is_inserted_ahead_of_soon_and_can_be_removed(self):
        app = AppTest.from_file("streamlit_app.py").run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.dataframe[0].value), 300)
        app.button(key="load_example").click().run()
        next(button for button in app.button if button.label == "Classify and preview slot").click().run()
        self.assertFalse(app.exception)
        table = app.dataframe[0].value
        case = table.iloc[105]
        self.assertEqual(len(table), 301)
        self.assertEqual(case["Message ID"], "MSG-10309")
        self.assertEqual(case["Urgency"], "Safety urgent")
        self.assertEqual(case["Fix path"], "Priority safety inspection")
        self.assertEqual(case["Status"], "Preview · Safety escalation")
        self.assertIn("SLOT-0291", case["Service slot"])
        self.assertEqual(table.iloc[106]["Urgency"], "Soon")
        next(button for button in app.button if button.label == "Remove test row").click().run()
        self.assertEqual(len(app.dataframe[0].value), 300)
