# University of Makati — ELEC3 Cloud Computing (Track B Final Exam)
## Section IV-DCSAD | Group 3 (`dcsad-g03`)
### Case 4: School Clinic Visit Queue

A secure, serverless school clinic queuing system designed to eliminate congestion at the campus health center while strictly safeguarding student medical privacy. Built for **120 students/day** (~25,000 requests/month) on **AWS Asia Pacific (Singapore) `ap-southeast-1`**.

---

## 1. System Architecture & Flow

```text
[ Student Phone ]                   [ Guidance Counselor ]             [ School Nurse Laptop ]
 (S3: index.html)                    (S3: counselor.html)                 (EC2: t3.micro)
        │                                     │                                  │
        │ HTTP (CORS)                         │ HTTP (CORS)                      │ Port 80
        ▼                                     ▼                                  ▼
 ┌─────────────────────────────────────────────────────┐                  ┌─────────────────────┐
 │ Amazon API Gateway: umak-elec3-dcsad-g03-api        │                  │ EC2 Flask Backend   │
 │ Routes: /queue, /queue/status, /stats/daily         │◄───(Port 443)────┤ Injects:            │
 │         /nurse/queue, /nurse/call-next, /nurse/note │  + x-nurse-key   │ x-nurse-key header  │
 └─────────────────────────┬───────────────────────────┘                  └─────────────────────┘
                           │ (Payload Format v2.0)
                           ▼
 ┌─────────────────────────────────────────────────────────────────────────────────────────────┐
 │ AWS Lambda Function: umak-elec3-dcsad-g03-clinic-handler (Python 3.13)                      │
 │ - Atomic queue numbering & operating hours validation (07:00–17:00 PHT / DEMO_MODE)         │
 │ - Strict privacy projections (zero health notes exposed to students or counselor)          │
 └─────────────────────────┬───────────────────────────────────────────────────────────────────┘
                           │ IAM Role: umak-elec3-dcsad-g03-lambda-role
                           ▼
 ┌─────────────────────────────────────────────────────────────────────────────────────────────┐
 │ Amazon DynamoDB: umak-elec3-dcsad-g03-clinic-queue (On-Demand Single-Table)                 │
 │ - PK: DATE#YYYY-MM-DD  |  SK: COUNTER     (last_number, current_serving, total_visits)      │
 │ - PK: DATE#YYYY-MM-DD  |  SK: QUEUE#0001  (queue_no, reason, status, private visit_note)    │
 └─────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Directory Layout

```text
dcsad-g03-clinic-queue/
├── frontend/                  # Deploy directly to S3: umak-elec3-dcsad-g03-clinic-web
│   ├── config.js              # Single place for API_BASE_URL (localhost for dev, API GW for deploy)
│   ├── styles.css             # Ultra-minimalist monochrome UI (shadcn/ui & Linear inspired)
│   ├── index.html             # Student mobile queue join & live ticket tracker
│   └── counselor.html         # Guidance counselor daily visit counts page (counts only, zero notes)
├── lambda/                    # Deploy to Lambda: umak-elec3-dcsad-g03-clinic-handler (Python 3.13)
│   └── lambda_function.py     # Single-file handler using ONLY Python stdlib + built-in boto3
├── ec2-nurse/                 # Amazon EC2 t3.micro Nurse Admin portal
│   ├── app.py                 # Lightweight Flask server (port 80) + server-side proxy injecting x-nurse-key
│   ├── templates/
│   │   ├── login.html         # Clean monochrome PIN login page
│   │   └── nurse.html         # Nurse queue dashboard: Call Next + private visit note editor
│   ├── requirements.txt       # Minimal dependencies: flask, requests, gunicorn
│   └── user-data.sh           # Amazon Linux 2023 bash script for EC2 Launch Template
├── local_server.py            # Local dev harness: in-memory DynamoDB mock + static frontend server
├── test_app.py                # Automated test suite (privacy, atomic concurrency, clinic hours)
├── docs/
│   ├── least-privilege-iam-policy.json  # Narrowed IAM policy for defense Q&A
│   ├── ec2-security-group.md            # Exact inbound/outbound SG rules + justification
│   └── demo-checklist.md                # Exact 6-minute Monday demo flow & AWS console build order
└── README.md                  # Complete local setup + AWS Console deployment guide
```

---

## 3. Local Development & Testing Guide

You can run and verify the entire system on your laptop without any AWS credentials or external pip installations for the core API!

### Step 1: Run Automated Verification Tests
```bash
# Run the complete test suite (all 7 tests)
python test_app.py
```
**Verification Coverage:**
- Sequential atomic queue numbering (`Q-001`, `Q-002`, `Q-003`)
- Operating hours blocking outside 7:00 AM–5:00 PM PHT when `DEMO_MODE="false"`
- Presentation bypass when `DEMO_MODE="true"` (for Monday 7:27 PM live defense)
- Unauthorized access blocking on `/nurse/*` routes without `x-nurse-key` (returns HTTP 401)
- Nurse workflow (Call Next, saving private notes, marking status `DONE`)
- Strict privacy assertions (`GET /queue/status` and `GET /stats/daily` contain zero notes/reasons)
- Concurrency safety (12+ simultaneous threads without queue number collisions)

---

### Step 2: Run Local Servers Side by Side

Open two terminal windows:

#### Terminal 1 — Local DynamoDB Mock & API / S3 Server
```bash
# Runs on Python standard library on port 8000
python local_server.py
```
- Student Mobile Page: `http://localhost:8000/index.html`
- Guidance Counselor Page: `http://localhost:8000/counselor.html`
- API Gateway Endpoint: `http://localhost:8000`

#### Terminal 2 — Nurse Admin Web App (Flask Backend)
```bash
cd ec2-nurse

# Create virtualenv and install minimal dependencies
python -m venv venv
venv\Scripts\activate       # On Windows (or 'source venv/bin/activate' on Linux/macOS)
pip install -r requirements.txt

# Run on port 5000 locally
python app.py
```
- Open Nurse Portal: `http://localhost:5000/login`
- Default Clinic PIN: `umak2026`

---

## 4. Single-Table DynamoDB Schema Specification

**Table Name:** `umak-elec3-dcsad-g03-clinic-queue`  
**Billing Mode:** On-Demand (`PAY_PER_REQUEST`)  
**Partition Key:** `PK` (String) | **Sort Key:** `SK` (String)

| Entity Type | PK | SK | Attributes | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Daily Counter** | `DATE#YYYY-MM-DD` | `COUNTER` | `date` (S)<br>`last_number` (N)<br>`current_serving` (N)<br>`total_visits` (N)<br>`updated_at` (S) | Tracks atomic ticket counter and currently called number for the day. |
| **Student Visit** | `DATE#YYYY-MM-DD` | `QUEUE#0001` | `date` (S)<br>`queue_no` (N)<br>`display_no` (S)<br>`reason` (S)<br>`status` (S: `WAITING`, `SERVING`, `DONE`)<br>`visit_note` (S: private health note)<br>`created_at` (S)<br>`updated_at` (S) | Individual student visit record. 4-digit zero-padded SK guarantees natural chronological sort order. |

---

## 5. API Gateway Route Catalog

Target HTTP API Gateway: `umak-elec3-dcsad-g03-api` (Payload Format v2.0)  
All responses include CORS headers: `Access-Control-Allow-Origin: *`.

| Method & Route | Access Level | Description | Key Request / Response Contract |
| :--- | :--- | :--- | :--- |
| `POST /queue` | Public (Student) | Join queue | **Body:** `{"reason": "Headache"}`<br>**Response (201):** `{"queue_no": 1, "display_no": "Q-001", "status": "WAITING", "clinic_open": true, "demo_mode": true}` |
| `GET /queue/status` | Public (Student) | View live queue position | **Response (200):** `{"current_serving": 1, "current_serving_display": "Q-001", "last_number": 5, "total_visits": 5}` *(Zero notes/reasons)* |
| `GET /stats/daily` | Public (Counselor) | View daily visit trends | **Response (200):** `{"days": [{"date": "2026-11-23", "total_visits": 18}], "total_all_time": 18}` *(Zero notes/reasons)* |
| `GET /nurse/queue` | Protected (`x-nurse-key`) | View full queue roster | **Query:** `?date=YYYY-MM-DD`<br>**Response (200):** `{"date": "...", "counter": {...}, "queue": [...]}` |
| `POST /nurse/call-next` | Protected (`x-nurse-key`) | Call next waiting student | **Response (200):** `{"called": {"display_no": "Q-001", "reason": "..."}, "current_serving": 1}` |
| `POST /nurse/note` | Protected (`x-nurse-key`) | Save private note / mark DONE | **Body:** `{"queue_no": 1, "visit_note": "Gave paracetamol", "mark_done": true}`<br>**Response (200):** `{"item": {...}, "message": "..."}` |

---

## 6. Step-by-Step AWS Console Deployment Guide (`dcsad-g03`)

Target Region: **`ap-southeast-1` (Asia Pacific — Singapore)**.

### Step 1: Create the DynamoDB Table
1. Open the **Amazon DynamoDB Console** in `ap-southeast-1`.
2. Click **Create table**:
   - **Table name:** `umak-elec3-dcsad-g03-clinic-queue`
   - **Partition key:** `PK` (String)
   - **Sort key:** `SK` (String)
   - **Table class:** DynamoDB Standard
   - **Capacity mode:** **On-demand**
3. Add Mandatory Tag:
   - Key: `team` | Value: `dcsad-g03`
4. Click **Create table**.

---

### Step 2: Deploy the AWS Lambda Function
1. Open the **AWS Lambda Console** in `ap-southeast-1`.
2. Click **Create function**:
   - **Function name:** `umak-elec3-dcsad-g03-clinic-handler`
   - **Runtime:** **Python 3.13**
   - **Architecture:** `x86_64`
   - **Execution role:** Select **Use an existing role** -> Choose pre-created role `umak-elec3-dcsad-g03-lambda-role`.
3. Under **Code source**:
   - Replace the default code with the full contents of `lambda/lambda_function.py`.
   - Click **Deploy**.
4. Under **Configuration > Environment variables**, click **Edit** and add:
   - `TABLE_NAME` = `umak-elec3-dcsad-g03-clinic-queue`
   - `NURSE_API_KEY` = `dcsad-g03-nurse-secret-2026`
   - `DEMO_MODE` = `true`
5. Under **Configuration > General configuration**, set:
   - **Timeout:** `10 seconds` (to comfortably accommodate DynamoDB calls).
   - **Memory:** `128 MB`.
6. Add Mandatory Tag:
   - Key: `team` | Value: `dcsad-g03`

---

### Step 3: Configure Routes on Existing API Gateway
*DO NOT create a new API Gateway. Attach routes to our existing group gateway.*

1. Open **Amazon API Gateway Console** -> Find existing HTTP API: `umak-elec3-dcsad-g03-api`.
2. Under **Integrations**, click **Create integration**:
   - **Integration type:** Lambda function
   - **Lambda function:** `umak-elec3-dcsad-g03-clinic-handler`
   - **Payload format version:** `2.0`
3. Under **Routes**, create the following routes and attach the Lambda integration to each:
   - `POST /queue`
   - `GET /queue/status`
   - `GET /stats/daily`
   - `GET /nurse/queue`
   - `POST /nurse/call-next`
   - `POST /nurse/note`
4. Under **CORS**:
   - **Access-Control-Allow-Origin:** `*`
   - **Access-Control-Allow-Headers:** `Content-Type, x-nurse-key`
   - **Access-Control-Allow-Methods:** `GET, POST, OPTIONS`
5. Note your **Invoke URL**: `https://<api-id>.execute-api.ap-southeast-1.amazonaws.com`.

---

### Step 4: Deploy Static Web Frontend to Amazon S3
1. Open the **Amazon S3 Console**.
2. Click **Create bucket**:
   - **Bucket name:** `umak-elec3-dcsad-g03-clinic-web`
   - **Region:** `ap-southeast-1`
   - **Object Ownership:** ACLs disabled (recommended)
   - **Block Public Access:** Uncheck "Block all public access" (acknowledge warning).
3. Under **Properties > Static website hosting**:
   - Enable static website hosting.
   - **Index document:** `index.html`.
4. Under **Permissions > Bucket Policy**, paste:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Sid": "PublicReadGetObject",
         "Effect": "Allow",
         "Principal": "*",
         "Action": "s3:GetObject",
         "Resource": "arn:aws:s3:::umak-elec3-dcsad-g03-clinic-web/*"
       }
     ]
   }
   ```
5. Update `frontend/config.js` with your API Gateway invoke URL:
   ```javascript
   const CONFIG = {
     API_BASE_URL: "https://<your-api-id>.execute-api.ap-southeast-1.amazonaws.com",
     POLL_INTERVAL_MS: 4000,
   };
   ```
6. Upload the 4 frontend files to the root of the S3 bucket:
   - `index.html`
   - `counselor.html`
   - `styles.css`
   - `config.js`
7. Test the student portal at:
   `http://umak-elec3-dcsad-g03-clinic-web.s3-website-ap-southeast-1.amazonaws.com`

---

### Step 5: Launch the EC2 Nurse Admin Instance
1. Open **Amazon EC2 Console** in `ap-southeast-1`.
2. Under **Security Groups**, create `umak-elec3-dcsad-g03-nurse-sg`:
   - **VPC:** Section `IV-DCSAD` VPC.
   - **Inbound Rules:**
     - HTTP (Port 80) from `0.0.0.0/0`
     - SSH (Port 22) from your IP
   - **Outbound Rules:**
     - HTTPS (Port 443) to `0.0.0.0/0`
     - HTTP (Port 80) to `0.0.0.0/0`
   - **Tag:** `team` = `dcsad-g03`
3. Under **Instances > Launch instances**:
   - **Name:** `umak-elec3-dcsad-g03-nurse-station`
   - **AMI:** Amazon Linux 2023 AMI (`x86_64`)
   - **Instance type:** `t3.micro` (1 vCPU, 1 GiB RAM)
   - **Key pair:** Your group key pair (tagged `team = dcsad-g03`)
   - **Network settings:**
     - **VPC:** Section `IV-DCSAD` VPC
     - **Subnet:** `dcsad-g03` **Public Subnet** *(private subnet remains empty)*
     - **Auto-assign public IP:** **Enable**
     - **Security group:** Select `umak-elec3-dcsad-g03-nurse-sg`
   - **Storage:** `8 GiB` `gp3` (within 20 GiB lab limit)
   - **Advanced details:**
     - **IAM instance profile:** Select pre-created `umak-elec3-dcsad-g03-ec2-role`
     - **User Data:** Paste the full contents of `ec2-nurse/user-data.sh` *(update `REPO_URL` and `API_BASE_URL` with your values)*.
   - **Tags:**
     - Tag instance: `team` = `dcsad-g03`
4. Click **Launch instance**.
5. Once running (after ~2 minutes for package installation), open your browser to:
   `http://<EC2-PUBLIC-IP>/login`
   - PIN: `umak2026`

---

## 7. Strict AWS Lab Account Rule Compliance Checklist

- [x] **No IAM Role Creation:** Uses pre-created `umak-elec3-dcsad-g03-lambda-role` and `umak-elec3-dcsad-g03-ec2-role`.
- [x] **Mandatory Resource Tagging:** Tag `team = dcsad-g03` applied across DynamoDB, Security Group, EC2 Instance, and Launch Template.
- [x] **No VPC / Subnet Modifications:** Deploys solely inside the pre-existing `IV-DCSAD` Section VPC and `dcsad-g03` public subnet.
- [x] **No NAT Gateway or Elastic IP:** Avoids prohibited resources; EC2 uses auto-assigned dynamic public IP in public subnet.
- [x] **Lightweight Architecture:** Zero Node/Docker build steps; runs on Python 3.13 Lambda native and 1 GiB RAM `t3.micro` with 8 GiB `gp3`.
- [x] **Health Privacy Isolated:** Sensitive medical visit notes are stored only in DynamoDB and accessible strictly via the authenticated EC2 server-side proxy.

---

## 8. Group Members & Contributions

**University of Makati — College of Computer Science**  
**Section:** IV-DCSAD  
**Group:** 3 (`dcsad-g03`)  
**Track:** Track B Final Exam — Case 4: School Clinic Visit Queue
