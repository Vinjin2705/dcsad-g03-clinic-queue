"""
University of Makati — ELEC3 Cloud Computing (Track B Final Exam)
Section IV-DCSAD | Group 3 (dcsad-g03)
Case 4: School Clinic Visit Queue

AWS Lambda Handler: umak-elec3-dcsad-g03-clinic-handler
Runtime: Python 3.13 (AWS Lambda Native - Zero external pip dependencies)
"""

import json
import os
import base64
from datetime import datetime, timezone, timedelta
from decimal import Decimal

# PHT is UTC+8 (Asia/Manila)
PHT = timezone(timedelta(hours=8))

# Standard CORS headers for HTTP API Gateway v2.0
CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type, x-nurse-key",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
}

# Module-level table reference for dependency injection (used by local_server.py & tests)
_table_instance = None


def set_table(table):
    """Dependency injection helper for tests and local development server."""
    global _table_instance
    _table_instance = table


def get_table():
    """Retrieve DynamoDB Table instance (real boto3 on AWS Lambda or injected mock locally)."""
    global _table_instance
    if _table_instance is not None:
        return _table_instance

    import boto3
    table_name = os.environ.get("TABLE_NAME", "umak-elec3-dcsad-g03-clinic-queue")
    region_name = os.environ.get("AWS_REGION", "ap-southeast-1")
    dynamodb = boto3.resource("dynamodb", region_name=region_name)
    _table_instance = dynamodb.Table(table_name)
    return _table_instance


def get_pht_now():
    """Return current timestamp in Asia/Manila (PHT, UTC+8)."""
    return datetime.now(PHT)


def is_clinic_open_pht(dt=None):
    """
    Check if the clinic is currently open:
    Mon-Fri, 07:00 to 17:00 PHT (Asia/Manila).
    """
    if dt is None:
        dt = get_pht_now()
    # Monday is 0, Sunday is 6
    if dt.weekday() >= 5:
        return False
    # 7:00 AM to 5:00 PM (17:00)
    return 7 <= dt.hour < 17


def is_demo_mode_enabled():
    """
    Check DEMO_MODE environment variable.
    When 'true', allows queue creation outside operating hours for Monday 7:27 PM live defense.
    """
    val = os.environ.get("DEMO_MODE", "true").strip().lower()
    return val in ("true", "1", "yes")


def decimal_to_python(obj):
    """Convert DynamoDB Decimal instances to standard Python int or float."""
    if isinstance(obj, list):
        return [decimal_to_python(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: decimal_to_python(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    return obj


def build_response(status_code, body_dict):
    """Format HTTP API v2 response with CORS headers and JSON body."""
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(decimal_to_python(body_dict), default=str),
    }


def verify_nurse_key(headers):
    """
    Verify the x-nurse-key header against the configured secret.
    Injected server-side by EC2 Flask backend so it is never exposed in client JS.
    """
    expected_key = os.environ.get("NURSE_API_KEY", "dcsad-g03-nurse-secret-2026").strip()
    if not headers:
        return False
    for k, v in headers.items():
        if k.lower() == "x-nurse-key":
            return str(v).strip() == expected_key
    return False


def parse_request_body(event):
    """Parse JSON body from API Gateway v2 event safely."""
    body = event.get("body")
    if not body:
        return {}
    if event.get("isBase64Encoded", False):
        try:
            body = base64.b64decode(body).decode("utf-8")
        except Exception:
            return {}
    if isinstance(body, dict):
        return body
    try:
        return json.loads(body)
    except Exception:
        return {}


def handle_options():
    """Handle CORS preflight requests."""
    return {
        "statusCode": 204,
        "headers": CORS_HEADERS,
        "body": "",
    }


def handle_post_queue(event):
    """
    Public — Student joins queue.
    Atomically increments daily counter and creates student record.
    """
    body = parse_request_body(event)
    reason = str(body.get("reason", "")).strip()

    if not reason:
        return build_response(400, {"error": "Reason is required and cannot be empty."})
    if len(reason) > 200:
        return build_response(400, {"error": "Reason must be 200 characters or fewer."})

    now = get_pht_now()
    clinic_open = is_clinic_open_pht(now)
    demo_mode = is_demo_mode_enabled()

    # Clinic hours enforcement: Mon-Fri 07:00-17:00 PHT (bypassed if DEMO_MODE="true")
    if not clinic_open and not demo_mode:
        return build_response(
            403,
            {
                "error": "Clinic is closed. Hours: 7:00 AM – 5:00 PM on school days.",
                "clinic_open": False,
                "demo_mode": False,
                "clinic_hours": "7:00 AM – 5:00 PM (Mon–Fri, PHT)",
            },
        )

    today_str = now.strftime("%Y-%m-%d")
    pk = f"DATE#{today_str}"
    now_iso = now.isoformat()
    table = get_table()

    # Atomic increment on daily COUNTER
    update_res = table.update_item(
        Key={"PK": pk, "SK": "COUNTER"},
        UpdateExpression="SET #d = if_not_exists(#d, :d), current_serving = if_not_exists(current_serving, :zero), updated_at = :now ADD last_number :inc, total_visits :inc",
        ExpressionAttributeNames={"#d": "date"},
        ExpressionAttributeValues={
            ":d": today_str,
            ":zero": 0,
            ":now": now_iso,
            ":inc": 1,
        },
        ReturnValues="ALL_NEW",
    )

    attrs = decimal_to_python(update_res.get("Attributes", {}))
    queue_no = int(attrs.get("last_number") or 1)
    current_serving = int(attrs.get("current_serving") or 0)
    display_no = f"Q-{queue_no:03d}"
    sk = f"QUEUE#{queue_no:04d}"

    visit_item = {
        "PK": pk,
        "SK": sk,
        "date": today_str,
        "queue_no": queue_no,
        "display_no": display_no,
        "reason": reason,
        "status": "WAITING",
        "visit_note": "",
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    table.put_item(Item=visit_item)

    return build_response(
        201,
        {
            "date": today_str,
            "queue_no": queue_no,
            "display_no": display_no,
            "current_serving": current_serving,
            "status": "WAITING",
            "clinic_open": clinic_open,
            "demo_mode": demo_mode,
        },
    )


def handle_get_queue_status():
    """
    Public — Student queue tracker.
    Returns ONLY counter information (current serving, total waiting/issued).
    Strict Privacy: Zero visit reasons or nurse notes returned.
    """
    now = get_pht_now()
    today_str = now.strftime("%Y-%m-%d")
    pk = f"DATE#{today_str}"
    table = get_table()

    res = table.get_item(Key={"PK": pk, "SK": "COUNTER"})
    counter_item = decimal_to_python(res.get("Item", {}))

    current_serving = int(counter_item.get("current_serving", 0))
    last_number = int(counter_item.get("last_number", 0))
    total_visits = int(counter_item.get("total_visits", 0))
    current_serving_display = f"Q-{current_serving:03d}" if current_serving > 0 else "None"

    return build_response(
        200,
        {
            "date": today_str,
            "current_serving": current_serving,
            "current_serving_display": current_serving_display,
            "last_number": last_number,
            "total_visits": total_visits,
            "clinic_open": is_clinic_open_pht(now),
            "demo_mode": is_demo_mode_enabled(),
            "clinic_hours": "7:00 AM – 5:00 PM (Mon–Fri, PHT)",
        },
    )


def handle_get_daily_stats():
    """
    Public — Guidance Counselor Daily Summary.
    Scans for COUNTER items across all dates.
    Strict Privacy: Uses ProjectionExpression on date and total_visits only.
    Zero visit notes or reasons are retrieved or exposed.
    """
    table = get_table()

    try:
        from boto3.dynamodb.conditions import Attr
        scan_kwargs = {
            "FilterExpression": Attr("SK").eq("COUNTER"),
            "ProjectionExpression": "#d, total_visits",
            "ExpressionAttributeNames": {"#d": "date"},
        }
        res = table.scan(**scan_kwargs)
        items = res.get("Items", [])
    except Exception:
        # Fallback for custom mocks or plain scan
        res = table.scan()
        all_items = res.get("Items", [])
        items = [
            {"date": i.get("date"), "total_visits": i.get("total_visits", 0)}
            for i in all_items
            if i.get("SK") == "COUNTER"
        ]

    days = []
    for item in items:
        item_py = decimal_to_python(item)
        d_val = item_py.get("date")
        if d_val:
            days.append({
                "date": str(d_val),
                "total_visits": int(item_py.get("total_visits", 0)),
            })

    # Sort descending by date (newest first)
    days.sort(key=lambda x: x["date"], reverse=True)
    total_all_time = sum(d["total_visits"] for d in days)

    return build_response(
        200,
        {
            "days": days,
            "total_all_time": total_all_time,
        },
    )


def handle_nurse_get_queue(event):
    """
    Protected — Nurse accesses full queue for today or specified date.
    Requires valid x-nurse-key header.
    """
    headers = event.get("headers") or {}
    if not verify_nurse_key(headers):
        return build_response(401, {"error": "Unauthorized: invalid or missing x-nurse-key header"})

    params = event.get("queryStringParameters") or {}
    target_date = params.get("date") or get_pht_now().strftime("%Y-%m-%d")
    pk = f"DATE#{target_date}"
    table = get_table()

    try:
        from boto3.dynamodb.conditions import Key
        res = table.query(KeyConditionExpression=Key("PK").eq(pk))
        items = decimal_to_python(res.get("Items", []))
    except Exception:
        # Fallback for local mock
        res = table.query(KeyConditionExpression={"PK": pk})
        items = decimal_to_python(res.get("Items", []))

    counter = {"last_number": 0, "current_serving": 0, "total_visits": 0}
    queue_records = []

    for item in items:
        sk = str(item.get("SK", ""))
        if sk == "COUNTER":
            counter["last_number"] = int(item.get("last_number", 0))
            counter["current_serving"] = int(item.get("current_serving", 0))
            counter["total_visits"] = int(item.get("total_visits", 0))
        elif sk.startswith("QUEUE#"):
            queue_records.append({
                "queue_no": int(item.get("queue_no", 0)),
                "display_no": item.get("display_no", f"Q-{int(item.get('queue_no', 0)):03d}"),
                "reason": item.get("reason", ""),
                "status": item.get("status", "WAITING"),
                "visit_note": item.get("visit_note", ""),
                "created_at": item.get("created_at", ""),
                "updated_at": item.get("updated_at", ""),
            })

    # Sort queue records by queue number ascending
    queue_records.sort(key=lambda x: x["queue_no"])

    return build_response(
        200,
        {
            "date": target_date,
            "counter": counter,
            "queue": queue_records,
        },
    )


def handle_nurse_call_next(event):
    """
    Protected — Nurse advances queue to next WAITING student.
    Requires valid x-nurse-key header.
    """
    headers = event.get("headers") or {}
    if not verify_nurse_key(headers):
        return build_response(401, {"error": "Unauthorized: invalid or missing x-nurse-key header"})

    body = parse_request_body(event)
    now = get_pht_now()
    target_date = body.get("date") or now.strftime("%Y-%m-%d")
    pk = f"DATE#{target_date}"
    now_iso = now.isoformat()
    table = get_table()

    # Query all records for the date
    try:
        from boto3.dynamodb.conditions import Key
        res = table.query(KeyConditionExpression=Key("PK").eq(pk))
        items = decimal_to_python(res.get("Items", []))
    except Exception:
        res = table.query(KeyConditionExpression={"PK": pk})
        items = decimal_to_python(res.get("Items", []))

    waiting_students = [
        item for item in items
        if str(item.get("SK", "")).startswith("QUEUE#") and item.get("status") == "WAITING"
    ]

    if not waiting_students:
        return build_response(
            200,
            {
                "called": None,
                "current_serving": 0,
                "message": "No waiting students in queue.",
            },
        )

    # Sort to find the lowest numbered waiting student
    waiting_students.sort(key=lambda x: int(x.get("queue_no", 0)))
    next_student = waiting_students[0]
    next_queue_no = int(next_student["queue_no"])
    next_sk = next_student["SK"]

    # Update student status to SERVING
    student_res = table.update_item(
        Key={"PK": pk, "SK": next_sk},
        UpdateExpression="SET #s = :serving, updated_at = :now",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":serving": "SERVING", ":now": now_iso},
        ReturnValues="ALL_NEW",
    )
    updated_student = decimal_to_python(student_res.get("Attributes", next_student))

    # Update COUNTER.current_serving
    table.update_item(
        Key={"PK": pk, "SK": "COUNTER"},
        UpdateExpression="SET current_serving = :cs, updated_at = :now",
        ExpressionAttributeValues={":cs": next_queue_no, ":now": now_iso},
        ReturnValues="UPDATED_NEW",
    )

    return build_response(
        200,
        {
            "called": updated_student,
            "current_serving": next_queue_no,
            "message": f"Now calling {updated_student.get('display_no', f'Q-{next_queue_no:03d}')}.",
        },
    )


def handle_nurse_save_note(event):
    """
    Protected — Nurse writes/updates private visit note and optionally marks DONE.
    Requires valid x-nurse-key header.
    """
    headers = event.get("headers") or {}
    if not verify_nurse_key(headers):
        return build_response(401, {"error": "Unauthorized: invalid or missing x-nurse-key header"})

    body = parse_request_body(event)
    now = get_pht_now()
    target_date = body.get("date") or now.strftime("%Y-%m-%d")
    queue_no = body.get("queue_no")
    visit_note = str(body.get("visit_note", "")).strip()
    mark_done = bool(body.get("mark_done", False))

    if queue_no is None:
        return build_response(400, {"error": "queue_no is required."})

    try:
        queue_no = int(queue_no)
    except ValueError:
        return build_response(400, {"error": "queue_no must be an integer."})

    pk = f"DATE#{target_date}"
    sk = f"QUEUE#{queue_no:04d}"
    now_iso = now.isoformat()
    table = get_table()

    if mark_done:
        res = table.update_item(
            Key={"PK": pk, "SK": sk},
            UpdateExpression="SET visit_note = :vn, #s = :done, updated_at = :now",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":vn": visit_note,
                ":done": "DONE",
                ":now": now_iso,
            },
            ReturnValues="ALL_NEW",
        )
    else:
        res = table.update_item(
            Key={"PK": pk, "SK": sk},
            UpdateExpression="SET visit_note = :vn, updated_at = :now",
            ExpressionAttributeValues={
                ":vn": visit_note,
                ":now": now_iso,
            },
            ReturnValues="ALL_NEW",
        )

    updated_item = decimal_to_python(res.get("Attributes", {}))
    return build_response(
        200,
        {
            "item": updated_item,
            "message": "Visit note saved successfully.",
        },
    )


def lambda_handler(event, context):
    """
    AWS Lambda entry point for API Gateway HTTP API (Payload Format v2.0).
    Routes requests according to path and HTTP method.
    """
    # Normalize path and method
    raw_path = event.get("rawPath") or event.get("path") or "/"
    if raw_path.startswith("/$default"):
        raw_path = raw_path[len("/$default"):]
    raw_path = raw_path.rstrip("/")
    if not raw_path:
        raw_path = "/"

    http_context = event.get("requestContext", {}).get("http", {})
    http_method = (http_context.get("method") or event.get("httpMethod") or "GET").upper()

    # Preflight CORS
    if http_method == "OPTIONS":
        return handle_options()

    # Route matching
    if raw_path == "/queue" and http_method == "POST":
        return handle_post_queue(event)

    elif raw_path == "/queue/status" and http_method == "GET":
        return handle_get_queue_status()

    elif raw_path == "/stats/daily" and http_method == "GET":
        return handle_get_daily_stats()

    elif raw_path == "/nurse/queue" and http_method == "GET":
        return handle_nurse_get_queue(event)

    elif raw_path == "/nurse/call-next" and http_method == "POST":
        return handle_nurse_call_next(event)

    elif raw_path == "/nurse/note" and http_method == "POST":
        return handle_nurse_save_note(event)

    return build_response(404, {"error": f"Route not found: {http_method} {raw_path}"})
