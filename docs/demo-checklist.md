# University of Makati — ELEC3 Cloud Computing (Track B Final Exam)
## Section IV-DCSAD | Group 3 (`dcsad-g03`)
### Case 4: School Clinic Visit Queue — Live Demo Checklist & 6-Minute Defense Script

- **Presentation Schedule:** Monday, Nov 23, 2026 at **7:27 PM – 7:38 PM PHT**
- **Format:** 6-Minute Live AWS Demonstration + 4-Minute Panel Defense Q&A
- **Target AWS Region:** `ap-southeast-1` (Singapore)

---

## Part 1: Pre-Demo AWS Console Verification Order (15 Minutes Before)

Before 7:20 PM PHT, open these 5 browser tabs in your presentation window:

1. **Tab 1 — DynamoDB Console:**
   - Table: `umak-elec3-dcsad-g03-clinic-queue`
   - View: "Explore Table Items". Verify partition key `PK` and sort key `SK`.
2. **Tab 2 — Lambda Console:**
   - Function: `umak-elec3-dcsad-g03-clinic-handler`
   - Configuration > Environment Variables: Verify `DEMO_MODE = "true"`, `NURSE_API_KEY = "dcsad-g03-nurse-secret-2026"`.
3. **Tab 3 — S3 Static Website (Student Phone View):**
   - URL: `http://umak-elec3-dcsad-g03-clinic-web.s3-website-ap-southeast-1.amazonaws.com` (opened in mobile simulation mode or on phone).
4. **Tab 4 — S3 Guidance Counselor Page:**
   - URL: `http://umak-elec3-dcsad-g03-clinic-web.s3-website-ap-southeast-1.amazonaws.com/counselor.html`.
5. **Tab 5 — EC2 Nurse Admin Web App:**
   - URL: `http://<EC2-PUBLIC-IP>/login`.
   - Verify instance is in `Running` state and Gunicorn is active on port 80.

---

## Part 2: Exact 6-Minute Demonstration Flow (7:27 PM – 7:33 PM)

| Time | Presenter Action | Speaking Script & Key Technical Highlights |
| :---: | :--- | :--- |
| **0:00 – 1:00**<br>(Minute 1) | **Architecture Overview**<br>Show AWS Console & Architecture Diagram. | *"Good evening, professors and panel. We are Group 3 from Section IV-DCSAD presenting Case 4: School Clinic Visit Queue.<br><br>Our goal is to eliminate crowding at the UMak clinic door while strictly safeguarding student health privacy. Our serverless architecture uses Amazon S3 for student and counselor static frontends, Amazon API Gateway HTTP API v2 routing to an AWS Lambda function in Python 3.13, a single DynamoDB table with atomic counters, and an Amazon EC2 t3.micro hosting the Nurse Admin portal inside our public subnet."* |
| **1:00 – 2:30**<br>(Minute 2) | **Student Queue Join & Operating Hours Override**<br>Switch to Student Mobile Page (`index.html`). | *"Notice that the current time is 7:28 PM PHT. Under regular school rules, our Lambda function enforces operating hours from 7:00 AM to 5:00 PM. But because our defense is tonight after hours, our Lambda environment variable `DEMO_MODE='true'` permits demo submissions while showing the active demo badge.<br><br>Now watch as I enter 'Headache and mild fever' and click Join. Instantly, DynamoDB executes an atomic `UpdateItem` with `ADD last_number :inc` and assigns ticket **Q-001**.<br><br>If I refresh the mobile browser, my ticket is preserved via date-keyed `localStorage`, so students never lose their place in line."* |
| **2:30 – 4:00**<br>(Minute 3–4) | **Nurse Admin Sign-In, Call Next & Private Health Note**<br>Switch to EC2 Nurse Portal (`http://<EC2-IP>/login`). | *"Now we switch to the School Nurse laptop. The nurse accesses our EC2 instance on port 80 and signs in with the clinic PIN.<br><br>Notice the queue displays student **Q-001** waiting. When the nurse clicks **Call Next Student**, our server-side Flask proxy injects the secret `x-nurse-key` header to API Gateway. The counter updates `current_serving` to 1.<br><br>Instantly, on the student's phone, their status flips to 'NOW CALLING! Proceed inside the clinic'.<br><br>The nurse examines the student and writes a private health note: 'Administered 500mg paracetamol, BP 115/75, rest 20 mins', then clicks 'Save Note & Complete Visit (DONE)'."* |
| **4:00 – 5:00**<br>(Minute 5) | **Counselor Portal & Strict Privacy Proof**<br>Switch to `counselor.html` and Open DevTools Network tab. | *"Next, we demonstrate our Guidance Counselor portal on S3. The counselor tracks student wellness capacity and visit trends.<br><br>Notice what the counselor sees: **Today's Visits: 1**, with daily history and volume charts.<br><br>Now look at the DevTools Network tab inspecting `GET /stats/daily`. In the raw JSON response payload, **there are ZERO student reasons and ZERO visit notes**. The projection expression in DynamoDB guarantees that sensitive health notes NEVER leave the database for unauthorized viewers."* |
| **5:00 – 6:00**<br>(Minute 6) | **Live DynamoDB Single-Table Inspection & Wrap-up**<br>Switch to Tab 1 (DynamoDB Items). | *"Finally, in our DynamoDB table `umak-elec3-dcsad-g03-clinic-queue`, we see our single-table design in action: `DATE#2026-11-23` with sort keys `COUNTER` and `QUEUE#0001`. Notice that the atomic counter holds `last_number: 1`, `current_serving: 1`, and `total_visits: 1`.<br><br>We are within our 6 minutes and ready for your questions. Thank you!"* |

---

## Part 3: 4-Minute Defense Q&A Preparation (7:33 PM – 7:37 PM)

### Question 1: "How do you guarantee that two students clicking 'Join Queue' at the exact same millisecond don't get the same ticket number?"
**Answer:**
> "We avoid race conditions by using DynamoDB's native atomic counter operation (`UpdateItem` with expression `ADD last_number :inc, total_visits :inc` and `ReturnValues='ALL_NEW'`). DynamoDB handles atomic serial execution on the partition key without requiring distributed locking or external transaction managers. Even under 100 simultaneous requests, every student receives a guaranteed unique, monotonically increasing sequential number."

### Question 2: "Where is the `x-nurse-key` stored and why can't a curious student inspect it in browser DevTools?"
**Answer:**
> "The `x-nurse-key` is an environment variable stored only on AWS Lambda and the EC2 Flask server. The student frontend hosted on S3 has no knowledge of it. When the nurse uses the web portal, requests go to the EC2 Flask backend authenticated by a secure HTTP-only session cookie. The EC2 Flask server injects the `x-nurse-key` header server-side during the outbound call to API Gateway. It is never exposed in client JavaScript or network payloads."

### Question 3: "If `DEMO_MODE` is disabled, what happens when a student tries to join at 5:01 PM?"
**Answer:**
> "The Lambda function checks current time in Asia/Manila (PHT, UTC+8). If the current time is outside Mon–Fri 07:00–17:00 and `DEMO_MODE='false'`, Lambda immediately terminates execution and returns HTTP 403 Forbidden with `{ 'error': 'Clinic is closed. Hours: 7:00 AM – 5:00 PM on school days.' }` without touching DynamoDB or incrementing the counter."

### Question 4: "Why did you use a single DynamoDB table instead of multiple tables for counters and visits?"
**Answer:**
> "A single-table design (`PK: DATE#YYYY-MM-DD`, `SK: COUNTER` or `QUEUE#xxxx`) allows us to fetch all relevant records for a given school day in a single efficient `Query` operation. It also fits within the strict Free Tier and minimizes AWS resource provisioning overhead in our class lab account."

### Question 5: "Why does your Lambda IAM policy include `dynamodb:Scan` for the Guidance Counselor view?"
**Answer:**
> "For the Guidance Counselor portal, `handle_get_daily_stats()` runs a `table.scan()` with a `FilterExpression` on `SK = 'COUNTER'` and a `ProjectionExpression` on `date, total_visits`. This strictly isolates health data: student reasons and nurse visit notes never leave DynamoDB. At our expected school clinic traffic of 120 visits/day (one counter item per school day, ~200 items/year), a Filtered Scan consumes less than 1 Read Capacity Unit (RCU) and completes in under 10 milliseconds. At 10× university-wide scale over decades, we would add a Global Secondary Index (GSI) with Partition Key `SK` so counselors can perform an indexed `Query` instead of a `Scan`."
