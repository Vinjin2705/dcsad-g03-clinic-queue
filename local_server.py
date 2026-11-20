"""
University of Makati — ELEC3 Cloud Computing (Track B Final Exam)
Section IV-DCSAD | Group 3 (dcsad-g03)
Case 4: School Clinic Visit Queue

Local Development Server & Mock DynamoDB Harness
Runs on Python stdlib (zero external dependencies).
Serves S3 static frontend at http://localhost:8000/
Directly routes API calls to lambda/lambda_function.py via in-memory DynamoDB mock.
"""

import sys
import os
import json
import threading
import mimetypes
from urllib.parse import urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

# Add lambda directory to sys.path so lambda_function can be imported cleanly
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LAMBDA_DIR = os.path.join(BASE_DIR, "lambda")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

if LAMBDA_DIR not in sys.path:
    sys.path.insert(0, LAMBDA_DIR)

import lambda_function


class InMemoryDynamoDBTable:
    """
    Thread-safe, high-fidelity in-memory mock of DynamoDB single-table.
    Simulates Atomic Counter updates (ADD), Conditionals, Queries, and Scans.
    """

    def __init__(self, table_name="umak-elec3-dcsad-g03-clinic-queue"):
        self.table_name = table_name
        self._lock = threading.Lock()
        # Storage dictionary keyed by (PK, SK) tuple
        self._items = {}

    def put_item(self, Item):
        with self._lock:
            key = (Item["PK"], Item["SK"])
            self._items[key] = dict(Item)
            return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    def get_item(self, Key):
        with self._lock:
            key = (Key["PK"], Key["SK"])
            item = self._items.get(key)
            if item:
                return {"Item": dict(item), "ResponseMetadata": {"HTTPStatusCode": 200}}
            return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    def update_item(
        self,
        Key,
        UpdateExpression="",
        ExpressionAttributeNames=None,
        ExpressionAttributeValues=None,
        ReturnValues="NONE",
    ):
        with self._lock:
            key = (Key["PK"], Key["SK"])
            item = self._items.get(key)
            if item is None:
                item = {"PK": Key["PK"], "SK": Key["SK"]}
                self._items[key] = item

            attr_names = ExpressionAttributeNames or {}
            attr_values = ExpressionAttributeValues or {}

            # Parse and execute UpdateExpression
            # Handles: SET ... ADD ...
            tokens = UpdateExpression.split()
            current_mode = None
            i = 0

            # Helper to resolve field name
            def resolve_name(name):
                return attr_names.get(name, name)

            # Helper to resolve value
            def resolve_val(val_placeholder):
                return attr_values.get(val_placeholder, val_placeholder)

            while i < len(tokens):
                token = tokens[i]
                if token.upper() in ("SET", "ADD"):
                    current_mode = token.upper()
                    i += 1
                    continue

                if current_mode == "SET":
                    # Clause: field = if_not_exists(field, :val) OR field = :val
                    # Collect tokens until next keyword or end
                    clause_tokens = []
                    while i < len(tokens) and tokens[i].upper() not in ("ADD", "REMOVE", "DELETE"):
                        clause_tokens.append(tokens[i])
                        i += 1

                    clause_str = " ".join(clause_tokens)
                    # Split assignments respecting parentheses (e.g. if_not_exists(a, b))
                    assignments = []
                    curr_part = []
                    paren_depth = 0
                    for ch in clause_str:
                        if ch == "(":
                            paren_depth += 1
                            curr_part.append(ch)
                        elif ch == ")":
                            paren_depth = max(0, paren_depth - 1)
                            curr_part.append(ch)
                        elif ch == "," and paren_depth == 0:
                            assignments.append("".join(curr_part).strip())
                            curr_part = []
                        else:
                            curr_part.append(ch)
                    if curr_part:
                        assignments.append("".join(curr_part).strip())

                    for assign in assignments:
                        if "=" in assign:
                            field_part, val_part = [p.strip() for p in assign.split("=", 1)]
                            target_field = resolve_name(field_part)

                            if "if_not_exists(" in val_part:
                                # Example: if_not_exists(#d, :d)
                                inside = val_part.split("if_not_exists(", 1)[1].rstrip(")")
                                args = [a.strip() for a in inside.split(",")]
                                fallback_val = resolve_val(args[1]) if len(args) > 1 else None
                                if target_field not in item:
                                    item[target_field] = fallback_val
                            else:
                                item[target_field] = resolve_val(val_part)

                elif current_mode == "ADD":
                    # Clause: last_number :inc, total_visits :inc
                    clause_tokens = []
                    while i < len(tokens) and tokens[i].upper() not in ("SET", "REMOVE", "DELETE"):
                        clause_tokens.append(tokens[i])
                        i += 1

                    clause_str = " ".join(clause_tokens)
                    add_clauses = [a.strip() for a in clause_str.split(",") if a.strip()]

                    for add_item in add_clauses:
                        parts = add_item.split()
                        if len(parts) >= 2:
                            field = resolve_name(parts[0])
                            inc_val = resolve_val(parts[1])
                            item[field] = int(item.get(field, 0)) + int(inc_val)

            response = {"ResponseMetadata": {"HTTPStatusCode": 200}}
            if ReturnValues in ("ALL_NEW", "UPDATED_NEW"):
                response["Attributes"] = dict(item)
            return response

    def query(self, KeyConditionExpression=None, **kwargs):
        with self._lock:
            # KeyConditionExpression can be a Key object from boto3 or dict or string
            matched = []
            pk_target = None

            if isinstance(KeyConditionExpression, dict):
                pk_target = KeyConditionExpression.get("PK")
            elif hasattr(KeyConditionExpression, "get_expression"):
                # boto3 Key condition object
                expr_dict = KeyConditionExpression.get_expression()
                values = expr_dict.get("values", [])
                if values:
                    pk_target = values[0]
            elif KeyConditionExpression is not None:
                str_expr = str(KeyConditionExpression)
                # Try finding value in ExpressionAttributeValues
                val_dict = kwargs.get("ExpressionAttributeValues", {})
                for v in val_dict.values():
                    if str(v).startswith("DATE#"):
                        pk_target = v
                        break

            for (pk, sk), item in self._items.items():
                if pk_target is None or pk == pk_target:
                    matched.append(dict(item))

            return {"Items": matched, "ResponseMetadata": {"HTTPStatusCode": 200}}

    def scan(self, FilterExpression=None, ProjectionExpression=None, ExpressionAttributeNames=None, **kwargs):
        with self._lock:
            matched = []
            attr_names = ExpressionAttributeNames or {}

            for item in self._items.values():
                # Filter by SK == 'COUNTER' if specified
                is_counter = item.get("SK") == "COUNTER"
                if FilterExpression is not None:
                    str_filter = str(FilterExpression)
                    if "COUNTER" in str_filter and not is_counter:
                        continue
                matched.append(dict(item))

            # Apply projection if requested
            if ProjectionExpression:
                projected = []
                proj_fields = [attr_names.get(p.strip(), p.strip()) for p in ProjectionExpression.split(",")]
                for item in matched:
                    proj_item = {k: item[k] for k in proj_fields if k in item}
                    projected.append(proj_item)
                return {"Items": projected, "ResponseMetadata": {"HTTPStatusCode": 200}}

            return {"Items": matched, "ResponseMetadata": {"HTTPStatusCode": 200}}


# Global mock table instance
mock_table = InMemoryDynamoDBTable()
lambda_function.set_table(mock_table)


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Multi-threaded HTTP Server for smooth concurrency handling."""
    daemon_threads = True


class LocalDevHandler(BaseHTTPRequestHandler):
    """
    Unified HTTP Request Handler:
    - Serves static frontend from frontend/ directory
    - Dispatches API requests directly to lambda_function.py
    """

    def log_message(self, format, *args):
        # Clean terminal logging
        sys.stderr.write(f"[{self.log_date_time_string()}] {self.address_string()} - {format % args}\n")

    def _serve_static_file(self, file_path):
        """Serve a static file with appropriate Content-Type and CORS headers."""
        if not os.path.exists(file_path) or os.path.isdir(file_path):
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"404 Not Found")
            return

        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = "application/octet-stream"

        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(f"500 Internal Error: {e}".encode())

    def _handle_api_request(self, method):
        """Translate HTTP request into API Gateway v2 event and invoke lambda_handler."""
        parsed_url = urlparse(self.path)
        raw_path = parsed_url.path
        query_params = {k: v[0] for k, v in parse_qs(parsed_url.query).items()}

        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length) if content_length > 0 else b""
        body_str = body_bytes.decode("utf-8", errors="ignore")

        # Build simulated API Gateway HTTP API v2 event
        event = {
            "version": "2.0",
            "routeKey": f"{method} {raw_path}",
            "rawPath": raw_path,
            "rawQueryString": parsed_url.query,
            "headers": dict(self.headers),
            "queryStringParameters": query_params if query_params else None,
            "requestContext": {
                "http": {
                    "method": method,
                    "path": raw_path,
                    "protocol": "HTTP/1.1",
                    "sourceIp": self.client_address[0],
                }
            },
            "body": body_str if body_str else None,
            "isBase64Encoded": False,
        }

        # Invoke Lambda Handler
        result = lambda_function.lambda_handler(event, {})

        status_code = result.get("statusCode", 200)
        headers = result.get("headers", {})
        body = result.get("body", "")

        self.send_response(status_code)
        for h_name, h_val in headers.items():
            self.send_header(h_name, str(h_val))
        self.end_headers()

        if isinstance(body, str):
            self.wfile.write(body.encode("utf-8"))
        elif isinstance(body, bytes):
            self.wfile.write(body)

    def do_OPTIONS(self):
        parsed_url = urlparse(self.path)
        raw_path = parsed_url.path
        # If API path, forward to lambda
        if raw_path.startswith(("/queue", "/stats", "/nurse")):
            self._handle_api_request("OPTIONS")
        else:
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, x-nurse-key")
            self.end_headers()

    def do_GET(self):
        parsed_url = urlparse(self.path)
        raw_path = parsed_url.path

        # Check if this is an API route
        if raw_path.startswith(("/queue", "/stats", "/nurse")):
            self._handle_api_request("GET")
            return

        # Serve static frontend files
        if raw_path in ("/", ""):
            file_path = os.path.join(FRONTEND_DIR, "index.html")
        else:
            rel_path = raw_path.lstrip("/")
            file_path = os.path.join(FRONTEND_DIR, rel_path)

        self._serve_static_file(file_path)

    def do_POST(self):
        self._handle_api_request("POST")


def run_local_server(port=8000):
    server_address = ("0.0.0.0", port)
    httpd = ThreadedHTTPServer(server_address, LocalDevHandler)
    print("=" * 70)
    print("UMak ELEC3 (Track B) — Case 4: School Clinic Visit Queue")
    print(f"Local Server running at: http://localhost:{port}/")
    print(f"- Student Portal:        http://localhost:{port}/index.html")
    print(f"- Counselor Portal:      http://localhost:{port}/counselor.html")
    print(f"- API Endpoint Base:     http://localhost:{port}")
    print(f"- DynamoDB Mock:         Active (In-Memory)")
    print("=" * 70)
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping local server...")
        httpd.server_close()


if __name__ == "__main__":
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    run_local_server(port)
