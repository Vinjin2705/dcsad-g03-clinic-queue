# University of Makati — ELEC3 Cloud Computing (Track B Final Exam)
## Section IV-DCSAD | Group 3 (`dcsad-g03`)
### Case 4: School Clinic Visit Queue — EC2 Security Group Specification & Defense Rationale

---

## 1. Security Group Configuration

- **Security Group Name:** `umak-elec3-dcsad-g03-nurse-sg`
- **VPC:** Section `IV-DCSAD` Section VPC
- **Mandatory Tag (Strict AWS IAM Rule):**
  - **Key:** `team`
  - **Value:** `dcsad-g03`

---

## 2. Rule Specifications

### Inbound Rules (Ingress)

| Type | Protocol | Port Range | Source | Justification & Architectural Rationale |
| :--- | :---: | :---: | :---: | :--- |
| **HTTP** | TCP | `80` | `0.0.0.0/0` (or VPC CIDR) | Allows school nurses and evaluators to access the Nurse Admin Web App portal (`login.html` and `nurse.html`) hosted on Gunicorn. |
| **SSH** | TCP | `22` | Group Admin IP / Lab CIDR | Administrative maintenance, troubleshooting, and inspection of `/var/log/user-data.log`. In production, this is restricted to the clinic administration subnet or bastion host. |

> [!NOTE]
> **Why port 80 instead of 443 on EC2?**
> In this lab environment, no custom domain or ACM certificate is provisioned for the EC2 instance. HTTPS is terminated at Amazon API Gateway (`https://<api-id>.execute-api.ap-southeast-1.amazonaws.com`) for all backend API communication. The nurse web frontend communicates locally with Flask on port 80, which then initiates secure outbound TLS 1.3 (port 443) calls to API Gateway.

### Outbound Rules (Egress)

| Type | Protocol | Port Range | Destination | Justification & Architectural Rationale |
| :--- | :---: | :---: | :---: | :--- |
| **HTTPS** | TCP | `443` | `0.0.0.0/0` | **Mandatory:** Enables the EC2 Flask backend proxy to invoke the AWS API Gateway endpoint (`umak-elec3-dcsad-g03-api`), clone the GitHub repository during User Data boot, and reach AWS STS/IAM if needed. |
| **HTTP** | TCP | `80` | `0.0.0.0/0` | **Mandatory:** Allows Amazon Linux 2023 `dnf` package manager to reach repository mirrors to install Python 3, pip, and Git during initial launch. |

---

## 3. Defense Panel Q&A Guide (Anticipated Questions)

### Q1: Why is the EC2 instance located in the public subnet instead of the private subnet?
**Answer:**
> "Our class lab account forbids creating a NAT Gateway or Elastic IP. If we launched the EC2 instance into the private subnet, it would have no route to the internet to reach Amazon Linux package mirrors or clone our GitHub repository during Launch Template boot, nor could the nurse access the web UI without a Load Balancer. Therefore, per lab rules, our `dcsad-g03` public subnet hosts the `t3.micro` instance with a dynamic Public IP, while our `dcsad-g03` private subnet remains completely empty."

### Q2: How do you handle the changing Public IP of the EC2 instance?
**Answer:**
> "Because the class lab account automatically stops EC2 instances after 24 hours (and we stop it after working to conserve credits), the public IP changes on every boot. We designed our architecture with zero dependency on the EC2 IP:
> 1. Neither S3 frontend (`index.html`, `counselor.html`) nor Lambda ever call EC2.
> 2. All client traffic from S3 goes straight to Amazon API Gateway.
> 3. The nurse simply visits the new Public IP shown in the AWS EC2 Console upon starting the instance.
> 4. The Launch Template User Data script pulls the app from GitHub automatically on every start, guaranteeing zero manual reconfiguration."

### Q3: Why does the Nurse portal use a server-side proxy instead of calling API Gateway directly from the browser?
**Answer:**
> "This is a cornerstone of our Health Data Privacy design. To access `/nurse/*` routes, API Gateway requires the `x-nurse-key` header. If the browser made this request directly, the secret key would be visible in browser DevTools Network tabs. By having the EC2 Flask server validate the nurse's session cookie and inject the `x-nurse-key` header server-side, the secret key is never transmitted to or exposed in any client browser."
