# Multi-Tenant Face Recognition Attendance System - Cloud Deployment Guide

This guide provides everything needed to deploy this application to any cloud provider or Linux server (AWS EC2, Google Cloud Compute Engine, Microsoft Azure VM, DigitalOcean Droplet, Hetzner, Linode, Oracle Cloud, or On-Premise bare metal).

---

## 🚀 Quick Automated 1-Command Deployment

On any fresh Ubuntu (22.04 / 24.04 / 26.04) server:

```bash
# 1. Clone this repository
git clone https://github.com/prof-capatel/prof-capatel.git attendance-system
cd attendance-system

# 2. Run the automated setup script
chmod +x scripts/remote_setup.sh
./scripts/remote_setup.sh
```

The script automatically:
1. Creates a **3GB swap file** (ensuring smooth C++ compilation for `dlib` on 1GB RAM instances).
2. Installs all system dependencies (CMake, OpenCV/GTK, BLAS/LAPACK, Nginx, Python 3).
3. Creates a Python virtual environment and installs all dependencies.
4. Configures local MySQL database `face_system` and provisions user `face_user`.
5. Restores the production database schema and core whitelisted tenants.
6. Registers and starts the `attendance.service` systemd daemon (auto-starts on reboot).
7. Configures Nginx reverse proxy on Port 80 with real-time SSE streaming.

---

## 🔒 Automated SSL / TLS (HTTPS) Setup for Custom Domain

To secure the server with a valid Let's Encrypt SSL/TLS certificate for `curiosityhub.co.in` & `www.curiosityhub.co.in` and enforce HTTPS:

```bash
chmod +x scripts/setup_ssl.sh
./scripts/setup_ssl.sh
```

This sets up:
* **Let's Encrypt Certificate** covering both `curiosityhub.co.in` and `www.curiosityhub.co.in` via Certbot with automatic background renewal (`certbot.timer`).
* **Nginx Port 443** server block with modern TLS 1.2 / 1.3 ciphers, HTTP/2, and HSTS.
* **Automated 301 Redirection** from `http://` to `https://`.
* **Real-time SSE live streaming support** for facial recognition cameras without proxy buffering lag.

---

## ⚙️ Environment Configuration (`.env`)

Located at `/home/ubuntu/attendance-system/.env` (or in project root):

```ini
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=face_user
MYSQL_PASSWORD=Attendance@2026
MYSQL_DB=face_system
ATTENDANCE_BASE_DIR=/home/ubuntu/attendance-system
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
```

---

## 🛠️ Service Management Commands

```bash
# Check service status
sudo systemctl status attendance

# Restart attendance server
sudo systemctl restart attendance

# View live application logs
sudo journalctl -u attendance -f

# Reload Nginx
sudo nginx -t && sudo systemctl reload nginx
```

---

## 🌐 Firewall / Security Group Ports Required

Ensure your cloud provider firewall (Security Group) allows:
* **Port 22 (SSH)**: Remote terminal management.
* **Port 80 (HTTP)**: Web traffic and Let's Encrypt ACME challenges.
* **Port 443 (HTTPS)**: Encrypted SSL/TLS user traffic.
