#!/bin/bash
# ==============================================================================
# University of Makati — ELEC3 Cloud Computing (Track B Final Exam)
# Section IV-DCSAD | Group 3 (dcsad-g03)
# Case 4: School Clinic Visit Queue
#
# EC2 Launch Template User Data Script
# Target: Amazon Linux 2023 (t3.micro, gp3 8 GiB)
# Role: umak-elec3-dcsad-g03-ec2-role
# Security Group: team = dcsad-g03 (Inbound: Port 80 HTTP, Outbound: HTTPS/HTTP)
# ==============================================================================

set -e

# Redirect all script output to system log for debugging via AWS Console
exec > >(tee /var/log/user-data.log | logger -t user-data -s 2>/dev/console) 2>&1
echo "=== Starting UMak ELEC3 dcsad-g03 Nurse Station Setup ==="
date

# ------------------------------------------------------------------------------
# 1. Install prerequisites (fast boot - skip full OS update)
# ------------------------------------------------------------------------------
dnf install -y python3 python3-pip git

# ------------------------------------------------------------------------------
# 2. Clone Group 3 GitHub Repository
# Replace REPO_URL with Vinjin2705's public repository
# ------------------------------------------------------------------------------
APP_DIR="/opt/dcsad-g03-clinic-queue"
REPO_URL="https://github.com/Vinjin2705/dcsad-g03-clinic-queue.git"

if [ -d "$APP_DIR" ]; then
    echo "Directory $APP_DIR exists. Pulling latest code..."
    cd "$APP_DIR"
    git pull || true
else
    echo "Cloning repository from $REPO_URL..."
    git clone "$REPO_URL" "$APP_DIR" || {
        echo "Git clone failed. Creating fallback app directory..."
        mkdir -p "$APP_DIR/ec2-nurse"
    }
fi

cd "$APP_DIR/ec2-nurse"

# ------------------------------------------------------------------------------
# 3. Create Python virtual environment & install requirements
# ------------------------------------------------------------------------------
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# ------------------------------------------------------------------------------
# 4. Configure Application Environment (.env)
# Replace placeholder values with Group 3 AWS deployment configurations:
# ------------------------------------------------------------------------------
cat << 'EOF' > "$APP_DIR/ec2-nurse/.env"
# API Gateway HTTP API Endpoint (umak-elec3-dcsad-g03-api)
API_BASE_URL=https://your-api-gateway-id.execute-api.ap-southeast-1.amazonaws.com

# Nurse authentication secrets
NURSE_API_KEY=dcsad-g03-nurse-secret-2026
NURSE_PIN=umak2026

# Server configuration
FLASK_SECRET_KEY=umak-elec3-dcsad-g03-nurse-secret-2026
PORT=80
EOF

# ------------------------------------------------------------------------------
# 5. Create Systemd Service running Gunicorn on Port 80
# ------------------------------------------------------------------------------
cat << 'EOF' > /etc/systemd/system/dcsad-g03-nurse.service
[Unit]
Description=UMak ELEC3 Group 3 School Nurse Admin Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/dcsad-g03-clinic-queue/ec2-nurse
EnvironmentFile=/opt/dcsad-g03-clinic-queue/ec2-nurse/.env
ExecStart=/opt/dcsad-g03-clinic-queue/ec2-nurse/venv/bin/gunicorn \
    --workers 2 \
    --bind 0.0.0.0:80 \
    --timeout 30 \
    --access-logfile /var/log/nurse-access.log \
    --error-logfile /var/log/nurse-error.log \
    app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# ------------------------------------------------------------------------------
# 6. Enable and start the systemd service
# ------------------------------------------------------------------------------
systemctl daemon-reload
systemctl enable dcsad-g03-nurse.service
systemctl restart dcsad-g03-nurse.service

echo "=== UMak ELEC3 dcsad-g03 Nurse Station Setup Complete ==="
systemctl status dcsad-g03-nurse.service --no-pager
