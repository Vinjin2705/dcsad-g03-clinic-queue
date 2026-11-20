"""
University of Makati — ELEC3 Cloud Computing (Track B Final Exam)
Section IV-DCSAD | Group 3 (dcsad-g03)
Case 4: School Clinic Visit Queue

Comprehensive Automated Test Suite
Verifies:
1. Sequential atomic queue numbering (Q-001, Q-002, etc.)
2. Operating hours blocking (outside 7am-5pm Mon-Fri) & DEMO_MODE bypass
3. Unauthorized access blocking on /nurse/* (missing/invalid x-nurse-key)
4. Nurse workflow (call next, save private note, mark done)
5. Strict Health Data Privacy (zero visit notes or reasons in student/counselor responses)
6. Concurrency safety (atomic increments under simultaneous student requests)
7. Input validation (empty reason, reason > 200 chars)

Runs natively with: python test_app.py OR pytest test_app.py
"""

import sys
import os
import json
import unittest
from unittest.mock import patch
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor

# Add directories to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LAMBDA_DIR = os.path.join(BASE_DIR, "lambda")
if LAMBDA_DIR not in sys.path:
    sys.path.insert(0, LAMBDA_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import lambda_function
from local_server import InMemoryDynamoDBTable

PHT = timezone(timedelta(hours=8))
NURSE_KEY = "dcsad-g03-nurse-secret-2026"


def invoke_api(method, path, body=None, headers=None, query_params=None):
    """Helper to dispatch simulated API Gateway v2 event to lambda_handler."""
    h = headers.copy() if headers else {}
    if body and "Content-Type" not in h:
        h["Content-Type"] = "application/json"

    event = {
        "version": "2.0",
        "routeKey": f"{method} {path}",
        "rawPath": path,
        "rawQueryString": "",
        "headers": h,
        "queryStringParameters": query_params,
        "requestContext": {
            "http": {
                "method": method,
                "path": path,
                "protocol": "HTTP/1.1",
            }
        },
        "body": json.dumps(body) if isinstance(body, dict) else body,
        "isBase64Encoded": False,
    }
    resp = lambda_function.lambda_handler(event, {})
    resp["json"] = json.loads(resp.get("body", "{}")) if resp.get("body") else {}
    return resp


class TestSchoolClinicQueue(unittest.TestCase):

    def setUp(self):
        # Create fresh in-memory table before each test
        self.mock_table = InMemoryDynamoDBTable()
        lambda_function.set_table(self.mock_table)
        os.environ["NURSE_API_KEY"] = NURSE_KEY
        os.environ["DEMO_MODE"] = "true"

    def test_01_sequential_atomic_queue_numbering(self):
        """Verify sequential numbering Q-001, Q-002, Q-003 for the day."""
        res1 = invoke_api("POST", "/queue", body={"reason": "Headache"})
        self.assertEqual(res1["statusCode"], 201)
        self.assertEqual(res1["json"]["queue_no"], 1)
        self.assertEqual(res1["json"]["display_no"], "Q-001")
        self.assertEqual(res1["json"]["status"], "WAITING")

        res2 = invoke_api("POST", "/queue", body={"reason": "Fever"})
        self.assertEqual(res2["statusCode"], 201)
        self.assertEqual(res2["json"]["queue_no"], 2)
        self.assertEqual(res2["json"]["display_no"], "Q-002")

        res3 = invoke_api("POST", "/queue", body={"reason": "Minor Cut"})
        self.assertEqual(res3["statusCode"], 201)
        self.assertEqual(res3["json"]["queue_no"], 3)
        self.assertEqual(res3["json"]["display_no"], "Q-003")

    def test_02_clinic_hours_blocking_and_demo_mode_override(self):
        """
        Verify clinic hours enforcement (Mon-Fri 7:00 AM - 5:00 PM PHT)
        and DEMO_MODE bypass for live presentation after hours.
        """
        # Simulate Monday at 7:27 PM PHT (19:27) — after clinic hours
        mon_evening = datetime(2026, 11, 23, 19, 27, 0, tzinfo=PHT)

        with patch("lambda_function.get_pht_now", return_value=mon_evening):
            # Case A: DEMO_MODE="false" -> MUST BE BLOCKED (403)
            os.environ["DEMO_MODE"] = "false"
            blocked_res = invoke_api("POST", "/queue", body={"reason": "Asthma attack"})
            self.assertEqual(blocked_res["statusCode"], 403)
            self.assertIn("Clinic is closed", blocked_res["json"]["error"])
            self.assertFalse(blocked_res["json"]["clinic_open"])
            self.assertFalse(blocked_res["json"]["demo_mode"])

            # Case B: DEMO_MODE="true" -> MUST BE ALLOWED (201)
            os.environ["DEMO_MODE"] = "true"
            allowed_res = invoke_api("POST", "/queue", body={"reason": "Live Demo Presentation"})
            self.assertEqual(allowed_res["statusCode"], 201)
            self.assertFalse(allowed_res["json"]["clinic_open"])
            self.assertTrue(allowed_res["json"]["demo_mode"])
            self.assertEqual(allowed_res["json"]["display_no"], "Q-001")

        # Case C: Regular school hours (Monday 10:00 AM PHT) -> Always allowed
        mon_morning = datetime(2026, 11, 23, 10, 0, 0, tzinfo=PHT)
        with patch("lambda_function.get_pht_now", return_value=mon_morning):
            os.environ["DEMO_MODE"] = "false"
            normal_res = invoke_api("POST", "/queue", body={"reason": "Morning checkup"})
            self.assertEqual(normal_res["statusCode"], 201)
            self.assertTrue(normal_res["json"]["clinic_open"])

    def test_03_unauthorized_nurse_access_blocked(self):
        """Verify protected /nurse/* routes strictly require valid x-nurse-key."""
        # 1. Missing header
        res1 = invoke_api("GET", "/nurse/queue")
        self.assertEqual(res1["statusCode"], 401)
        self.assertIn("Unauthorized", res1["json"]["error"])

        # 2. Invalid header
        res2 = invoke_api("GET", "/nurse/queue", headers={"x-nurse-key": "wrong-secret"})
        self.assertEqual(res2["statusCode"], 401)

        # 3. Unauthorized call-next
        res3 = invoke_api("POST", "/nurse/call-next")
        self.assertEqual(res3["statusCode"], 401)

        # 4. Unauthorized note save
        res4 = invoke_api("POST", "/nurse/note", body={"queue_no": 1, "visit_note": "test"})
        self.assertEqual(res4["statusCode"], 401)

    def test_04_nurse_workflow_call_next_and_private_note(self):
        """Verify full Nurse workflow: queue viewing, calling next student, and saving private note."""
        # Students join queue
        invoke_api("POST", "/queue", body={"reason": "High fever 39C"})
        invoke_api("POST", "/queue", body={"reason": "Sprained ankle"})

        # Nurse gets queue
        q_res = invoke_api("GET", "/nurse/queue", headers={"x-nurse-key": NURSE_KEY})
        self.assertEqual(q_res["statusCode"], 200)
        self.assertEqual(len(q_res["json"]["queue"]), 2)
        self.assertEqual(q_res["json"]["queue"][0]["display_no"], "Q-001")

        # Nurse calls next student
        call_res = invoke_api("POST", "/nurse/call-next", headers={"x-nurse-key": NURSE_KEY})
        self.assertEqual(call_res["statusCode"], 200)
        self.assertIsNotNone(call_res["json"]["called"])
        self.assertEqual(call_res["json"]["called"]["display_no"], "Q-001")
        self.assertEqual(call_res["json"]["current_serving"], 1)

        # Check queue status reflects serving student 1
        stat_res = invoke_api("GET", "/queue/status")
        self.assertEqual(stat_res["json"]["current_serving"], 1)
        self.assertEqual(stat_res["json"]["current_serving_display"], "Q-001")

        # Nurse saves note and marks student DONE
        note_body = {
            "date": q_res["json"]["date"],
            "queue_no": 1,
            "visit_note": "Administered paracetamol 500mg, advised 20 min rest.",
            "mark_done": True,
        }
        note_res = invoke_api("POST", "/nurse/note", headers={"x-nurse-key": NURSE_KEY}, body=note_body)
        self.assertEqual(note_res["statusCode"], 200)
        self.assertEqual(note_res["json"]["item"]["status"], "DONE")
        self.assertIn("paracetamol", note_res["json"]["item"]["visit_note"])

        # Call next student again -> should get Q-002
        call_res2 = invoke_api("POST", "/nurse/call-next", headers={"x-nurse-key": NURSE_KEY})
        self.assertEqual(call_res2["statusCode"], 200)
        self.assertEqual(call_res2["json"]["called"]["display_no"], "Q-002")

        # Call next again -> queue empty
        call_res3 = invoke_api("POST", "/nurse/call-next", headers={"x-nurse-key": NURSE_KEY})
        self.assertEqual(call_res3["statusCode"], 200)
        self.assertIsNone(call_res3["json"]["called"])
        self.assertIn("No waiting students", call_res3["json"]["message"])

    def test_05_strict_privacy_isolation(self):
        """
        CRITICAL PRIVACY TEST:
        Ensure GET /queue/status and GET /stats/daily NEVER return visit_note or reason.
        """
        # Student joins with private medical reason
        invoke_api("POST", "/queue", body={"reason": "Severe panic attack and migraine"})

        # Nurse calls and saves private medical diagnosis note
        invoke_api("POST", "/nurse/call-next", headers={"x-nurse-key": NURSE_KEY})
        invoke_api(
            "POST",
            "/nurse/note",
            headers={"x-nurse-key": NURSE_KEY},
            body={
                "queue_no": 1,
                "visit_note": "Confidential diagnosis: elevated heart rate 110bpm. Calming exercises applied.",
                "mark_done": True,
            },
        )

        # 1. Student Queue Status Check
        status_res = invoke_api("GET", "/queue/status")
        self.assertEqual(status_res["statusCode"], 200)
        raw_status_body = status_res.get("body", "")

        # Strict Assertions: Zero visit notes or reasons in response
        self.assertNotIn("visit_note", raw_status_body)
        self.assertNotIn("panic attack", raw_status_body)
        self.assertNotIn("Confidential diagnosis", raw_status_body)
        self.assertNotIn("reason", status_res["json"])
        self.assertNotIn("visit_note", status_res["json"])

        # 2. Guidance Counselor Daily Stats Check
        stats_res = invoke_api("GET", "/stats/daily")
        self.assertEqual(stats_res["statusCode"], 200)
        raw_stats_body = stats_res.get("body", "")

        self.assertNotIn("visit_note", raw_stats_body)
        self.assertNotIn("panic attack", raw_stats_body)
        self.assertNotIn("Confidential diagnosis", raw_stats_body)
        for day in stats_res["json"].get("days", []):
            self.assertIn("date", day)
            self.assertIn("total_visits", day)
            self.assertNotIn("visit_note", day)
            self.assertNotIn("reason", day)

    def test_06_concurrency_safety(self):
        """Simulate concurrent student join requests to verify atomic sequential numbering without collisions."""
        num_students = 12

        def student_join(i):
            return invoke_api("POST", "/queue", body={"reason": f"Concurrent Student {i}"})

        with ThreadPoolExecutor(max_workers=6) as executor:
            results = list(executor.map(student_join, range(num_students)))

        queue_numbers = []
        for r in results:
            self.assertEqual(r["statusCode"], 201)
            queue_numbers.append(r["json"]["queue_no"])

        # Assert all numbers are unique and strictly 1 through num_students
        self.assertEqual(len(queue_numbers), num_students)
        self.assertEqual(len(set(queue_numbers)), num_students)
        self.assertEqual(sorted(queue_numbers), list(range(1, num_students + 1)))

    def test_07_validation(self):
        """Verify input validation for POST /queue."""
        # Empty reason
        r1 = invoke_api("POST", "/queue", body={"reason": ""})
        self.assertEqual(r1["statusCode"], 400)

        # Whitespace only
        r2 = invoke_api("POST", "/queue", body={"reason": "   "})
        self.assertEqual(r2["statusCode"], 400)

        # Reason exceeding 200 characters
        r3 = invoke_api("POST", "/queue", body={"reason": "a" * 201})
        self.assertEqual(r3["statusCode"], 400)


if __name__ == "__main__":
    unittest.main(verbosity=2)
