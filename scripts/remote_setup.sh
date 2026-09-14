#!/usr/bin/env bash
set -e

echo "================================================================"
echo "  AWS EC2 ATTENDANCE SYSTEM PROVISIONING & DEPLOYMENT SCRIPT   "
echo "================================================================"

APP_DIR="/home/ubuntu/attendance-system"
TAR_FILE="/home/ubuntu/attendance_deploy.tar.gz"

# 1. Enable Swapfile (3GB) for compiling dlib & C++ extensions on 1GB RAM
if [ ! -f /swapfile ]; then
    echo "[1/8] Creating 3GB Swapfile to prevent OOM during dlib build..."
    sudo fallocate -l 3G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=3072
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    if ! grep -q '/swapfile' /etc/fstab; then
        echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    fi
    echo "[OK] Swap enabled: $(free -m | grep Swap)"
else
    echo "[1/8] Swapfile already exists. Ensuring swap is active..."
    sudo swapon -a || true
fi

# 2. Update APT & Install System Packages
echo "[2/8] Installing build tools, computer vision libraries & Nginx..."
sudo DEBIAN_FRONTEND=noninteractive apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    build-essential \
    cmake \
    pkg-config \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    libgtk-3-dev \
    libgl1 \
    libglib2.0-0 \
    python3-pip \
    python3-venv \
    python3-dev \
    nginx \
    curl \
    mysql-client

# 3. Unpack Codebase
echo "[3/8] Unpacking codebase to ${APP_DIR}..."
mkdir -p "${APP_DIR}"
tar -xzf "${TAR_FILE}" -C "${APP_DIR}"
sudo chown -R ubuntu:ubuntu "${APP_DIR}"

# 4. Create Python Virtualenv & Install Python Dependencies
echo "[4/8] Setting up Python virtual environment & installing wheels..."
mkdir -p /var/tmp
export TMPDIR=/var/tmp

if [ ! -d "${APP_DIR}/venv" ]; then
    python3 -m venv "${APP_DIR}/venv"
fi

"${APP_DIR}/venv/bin/pip" install --upgrade pip setuptools wheel
"${APP_DIR}/venv/bin/pip" install --no-cache-dir -r "${APP_DIR}/requirements.txt"

# 5. Configure MySQL Database & Restore Data
echo "[5/8] Configuring MySQL database & user privileges..."
sudo systemctl start mysql
sudo systemctl enable mysql

sudo mysql << 'EOF'
CREATE DATABASE IF NOT EXISTS face_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'face_user'@'localhost' IDENTIFIED BY 'Attendance@2026';
ALTER USER 'face_user'@'localhost' IDENTIFIED BY 'Attendance@2026';
GRANT ALL PRIVILEGES ON face_system.* TO 'face_user'@'localhost';
CREATE USER IF NOT EXISTS 'face_user'@'127.0.0.1' IDENTIFIED BY 'Attendance@2026';
ALTER USER 'face_user'@'127.0.0.1' IDENTIFIED BY 'Attendance@2026';
GRANT ALL PRIVILEGES ON face_system.* TO 'face_user'@'127.0.0.1';
FLUSH PRIVILEGES;
EOF

# Restore database dump if dump exists and database is empty
TABLE_COUNT=$(sudo mysql -D face_system -se "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'face_system';")
if [ "${TABLE_COUNT}" -eq 0 ] && [ -f "${APP_DIR}/database/backups/pre_cleanup_backup_20260913_093613.sql" ]; then
    echo "[*] Restoring production database dump (pre_cleanup_backup_20260913_093613.sql)..."
    sudo mysql face_system < "${APP_DIR}/database/backups/pre_cleanup_backup_20260913_093613.sql"
    echo "[OK] Production database restored successfully."
else
    echo "[i] Tables already present in face_system (${TABLE_COUNT} tables found)."
fi

# 6. Create Environment File (.env)
echo "[6/8] Writing environment file .env..."
cat << 'EOF' > "${APP_DIR}/.env"
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=face_user
MYSQL_PASSWORD=Attendance@2026
MYSQL_DB=face_system
ATTENDANCE_BASE_DIR=/home/ubuntu/attendance-system
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
EOF
chmod 600 "${APP_DIR}/.env"

# 7. Configure and Register systemd Service
echo "[7/8] Configuring systemd daemon (attendance.service)..."
sudo tee /etc/systemd/system/attendance.service > /dev/null << 'EOF'
[Unit]
Description=Face Attendance SaaS Central Server
After=network.target mysql.service

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/attendance-system
EnvironmentFile=/home/ubuntu/attendance-system/.env
ExecStart=/home/ubuntu/attendance-system/venv/bin/python run_server.py --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable attendance
sudo systemctl restart attendance

# 8. Configure Nginx Reverse Proxy
echo "[8/8] Configuring Nginx reverse proxy on port 80..."
sudo tee /etc/nginx/sites-available/attendance > /dev/null << 'EOF'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    client_max_body_size 60M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Real-Time Server-Sent Events (SSE) live feed support
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400s;
    }
}
EOF

sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/attendance /etc/nginx/sites-enabled/attendance
sudo nginx -t
sudo systemctl restart nginx

echo "================================================================"
echo "  PROVISIONING FINISHED! RUNNING HEALTH CHECKS...              "
echo "================================================================"
sleep 4

echo "[*] Systemd Service Status:"
sudo systemctl status attendance --no-pager -l || true

echo "[*] MySQL Table Check:"
sudo mysql -u face_user -pAttendance@2026 face_system -e "SELECT id, slug, name, tenant_type FROM tenants;"

echo "[*] Internal API Health Check:"
curl -I http://127.0.0.1:8000/
curl -s http://127.0.0.1:8000/api/v1/branding | head -n 10
echo ""
echo "[*] Nginx Port 80 Check:"
curl -I http://127.0.0.1/

echo "================================================================"
echo "  [SUCCESS] Server is live at: http://16.171.10.243/          "
echo "================================================================"
