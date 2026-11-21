"""
University of Makati — ELEC3 Cloud Computing (Track B Final Exam)
Section IV-DCSAD | Group 3 (dcsad-g03)
Case 4: School Clinic Visit Queue

School Nurse Admin Backend — Amazon EC2 (t3.micro)
Flask Application running on port 80 with Gunicorn
Authenticates Nurse via PIN session and injects x-nurse-key server-side.
"""

import os
import sys
import requests
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file

app = Flask(__name__)

# Secret key for server-side Flask session signing
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "umak-elec3-dcsad-g03-nurse-secret-2026")

# Environment configurations
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000").rstrip("/")
NURSE_API_KEY = os.environ.get("NURSE_API_KEY", "dcsad-g03-nurse-secret-2026").strip()
NURSE_PIN = os.environ.get("NURSE_PIN", "umak2026").strip()

# Path to shared frontend styles
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_CSS_PATH = os.path.join(BASE_DIR, "..", "frontend", "styles.css")


def is_authenticated():
    """Verify if the current user session is an authenticated nurse."""
    return session.get("nurse_logged_in") is True


@app.route("/styles.css")
def serve_styles():
    """Serve shared monochrome design stylesheet."""
    if os.path.exists(SHARED_CSS_PATH):
        return send_file(SHARED_CSS_PATH, mimetype="text/css")
    # Fallback inline minimal CSS if running isolated
    return "body { font-family: sans-serif; background: #fafafa; }", 200, {"Content-Type": "text/css"}


@app.route("/login", methods=["GET", "POST"])
def login():
    """Nurse PIN authentication endpoint."""
    error = None
    if request.method == "POST":
        submitted_pin = request.form.get("pin", "").strip()
        if submitted_pin == NURSE_PIN:
            session["nurse_logged_in"] = True
            return redirect(url_for("nurse_dashboard"))
        else:
            error = "Invalid Clinic Access PIN. Please try again."

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    """Clear session and redirect to login."""
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def nurse_dashboard():
    """Main Nurse Dashboard view. Requires active session."""
    if not is_authenticated():
        return redirect(url_for("login"))
    return render_template("nurse.html")


def safe_json(resp):
    """Safely decode JSON from upstream API Gateway, falling back to raw text on error."""
    try:
        return resp.json()
    except (ValueError, requests.exceptions.JSONDecodeError):
        return {"error": resp.text or f"Upstream HTTP {resp.status_code}"}


# ==============================================================================
# SECURE SERVER-SIDE PROXY ROUTES
# The Nurse's browser calls these endpoints. Flask validates the session cookie
# and injects the secret 'x-nurse-key' header server-side when talking to
# API Gateway. The secret key is NEVER exposed to the browser.
# ==============================================================================

@app.route("/api/queue", methods=["GET"])
def proxy_get_queue():
    if not is_authenticated():
        return jsonify({"error": "Unauthorized: nurse session required"}), 401

    date_param = request.args.get("date", "")
    target_url = f"{API_BASE_URL}/nurse/queue"
    params = {"date": date_param} if date_param else {}

    try:
        resp = requests.get(
            target_url,
            params=params,
            headers={"x-nurse-key": NURSE_API_KEY},
            timeout=8
        )
        return jsonify(safe_json(resp)), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": f"Failed to connect to API Gateway: {str(e)}"}), 502


@app.route("/api/call-next", methods=["POST"])
def proxy_call_next():
    if not is_authenticated():
        return jsonify({"error": "Unauthorized: nurse session required"}), 401

    payload = request.get_json(silent=True) or {}
    target_url = f"{API_BASE_URL}/nurse/call-next"

    try:
        resp = requests.post(
            target_url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "x-nurse-key": NURSE_API_KEY
            },
            timeout=8
        )
        return jsonify(safe_json(resp)), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": f"Failed to connect to API Gateway: {str(e)}"}), 502


@app.route("/api/note", methods=["POST"])
def proxy_save_note():
    if not is_authenticated():
        return jsonify({"error": "Unauthorized: nurse session required"}), 401

    payload = request.get_json(silent=True) or {}
    target_url = f"{API_BASE_URL}/nurse/note"

    try:
        resp = requests.post(
            target_url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "x-nurse-key": NURSE_API_KEY
            },
            timeout=8
        )
        return jsonify(safe_json(resp)), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": f"Failed to connect to API Gateway: {str(e)}"}), 502


@app.route("/api/status", methods=["GET"])
def proxy_get_status():
    if not is_authenticated():
        return jsonify({"error": "Unauthorized: nurse session required"}), 401

    target_url = f"{API_BASE_URL}/queue/status"
    try:
        resp = requests.get(target_url, timeout=8)
        return jsonify(safe_json(resp)), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": f"Failed to connect to API Gateway: {str(e)}"}), 502


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting School Nurse Admin Backend on port {port}...")
    print(f"API Target: {API_BASE_URL}")
    app.run(host="0.0.0.0", port=port, debug=False)
