# University of Makati — ELEC3 Cloud Computing (Track B Final Exam)
## Section IV-DCSAD | Group 3 (`dcsad-g03`)
### Case 4: School Clinic Visit Queue — Architecture Diagram

This document contains both the **Mermaid.js Diagram Code** (for live markdown viewing and documentation) and instructions for the **draw.io Diagram XML** saved at `docs/architecture-diagram.drawio` for inclusion in your `DCSAD-B-03.pdf`.

---

## 1. Mermaid Architecture Diagram

```mermaid
flowchart TD
  %% Styling Definitions (UMak Deep Navy #000B3C & UMak Gold #F5CE3A Theme)
  classDef client fill:#071A5A,stroke:#F5CE3A,stroke-width:2px,color:#FFFFFF;
  classDef vpc fill:#020B2C,stroke:#2563EB,stroke-width:2px,color:#60A5FA;
  classDef publicSubnet fill:#071A5A,stroke:#10B981,stroke-width:1.5px,color:#34D399;
  classDef privateSubnet fill:#071330,stroke:#64748B,stroke-dasharray: 4 4,stroke-width:1.5px,color:#94A3B8;
  classDef ec2 fill:#00104A,stroke:#F5CE3A,stroke-width:2px,color:#FFFFFF;
  classDef serverless fill:#001A5E,stroke:#38BDF8,stroke-width:2px,color:#FFFFFF;
  classDef apigw fill:#001A5E,stroke:#34D399,stroke-width:2px,color:#FFFFFF;
  classDef lambda fill:#001A5E,stroke:#F59E0B,stroke-width:2px,color:#FFFFFF;
  classDef db fill:#001A5E,stroke:#818CF8,stroke-width:2px,color:#FFFFFF;

  subgraph CLIENTS["Actors & Clients Layer"]
    STUDENT["Senior High Student<br/>Mobile Smartphone Browser"]:::client
    NURSE["School Nurse<br/>Clinic Admin Laptop"]:::client
    COUNSELOR["Guidance Counselor<br/>Office Workstation"]:::client
  end

  subgraph VPC["AWS VPC: Section IV-DCSAD 10.0.0.0/16 (ap-southeast-1 Singapore)"]
    subgraph PUBLIC_SN["Group 3 Public Subnet (Routing: 0.0.0.0/0 -> IGW)"]
      EC2["Amazon EC2: t3.micro<br/>Amazon Linux 2023 | Flask on Port 80<br/>SG: dcsad-g03-nurse-sg<br/>Security Guard: Injects secret x-nurse-key"]:::ec2
    end
    subgraph PRIVATE_SN["Group 3 Private Subnet"]
      ISOLATED["Lab Private Subnet<br/>Zero Internet-Facing Resources"]:::privateSubnet
    end
  end

  subgraph AWS_SERVERLESS["AWS Managed Serverless Layer (ap-southeast-1)"]
    S3["Amazon S3 Static Website<br/>umak-elec3-dcsad-g03-clinic-web<br/>index.html, counselor.html, styles.css<br/>(Guard: Zero health notes stored)"]:::serverless
    APIGW["Amazon API Gateway HTTP API v2<br/>umak-elec3-dcsad-g03-api<br/>Public: /queue, /queue/status, /stats/daily<br/>Protected: /nurse/* (requires x-nurse-key)"]:::apigw
    LAMBDA["AWS Lambda Function: Python 3.13<br/>umak-elec3-dcsad-g03-clinic-handler<br/>Role: umak-elec3-dcsad-g03-lambda-role<br/>Clinic Hours 7am-5pm PHT + Atomic Counters"]:::lambda
    DDB[("Amazon DynamoDB Single-Table<br/>umak-elec3-dcsad-g03-clinic-queue<br/>PK: DATE#YYYY-MM-DD<br/>SK: COUNTER | QUEUE#xxxx<br/>Confidential visit_note strictly isolated")]:::db
  end

  %% Client Interactions
  STUDENT -->|"1. Load Web App (HTTPS)"| S3
  STUDENT -->|"2. POST /queue & GET /queue/status"| APIGW
  COUNSELOR -->|"1. Load counselor.html"| S3
  COUNSELOR -->|"2. GET /stats/daily (Daily counts only)"| APIGW

  NURSE -->|"HTTP Port 80 (PIN Login & Station)"| EC2
  EC2 -->|"HTTPS Port 443 + Injected x-nurse-key"| APIGW

  %% Backend Invocations
  APIGW -->|"Payload Format v2.0 Proxy Integration"| LAMBDA
  LAMBDA -->|"Atomic UpdateItem & Filtered Projections"| DDB
```

---

## 2. draw.io Diagram File Location

The raw draw.io XML is saved in your repository at:
`docs/architecture-diagram.drawio`

### How to Open & Export in draw.io (diagrams.net):
1. Go to **[https://app.diagrams.net/](https://app.diagrams.net/)**.
2. Click **File** &rarr; **Open From** &rarr; **Device** and select `docs/architecture-diagram.drawio`.
   *(Or click **Arrange** &rarr; **Insert** &rarr; **Advanced** &rarr; **From Text...** and paste the raw XML).*
3. The diagram will render in full UMak Navy & Gold theme with VPC subnets, security boundaries, and data flows.
4. Click **File** &rarr; **Export as** &rarr; **PNG** (or **PDF**) at 300 DPI to paste directly into your **`DCSAD-B-03.pdf`** submission template!
