#!/usr/bin/env bash
set -e

echo "================================================================"
echo "  AWS EC2 SSL/TLS SETUP & NGINX HTTPS CONFIGURATION SCRIPT     "
echo "================================================================"

IP_ADDR="16.171.10.243"
DOMAIN="16.171.10.243.sslip.io"
SSL_DIR="/etc/ssl/attendance"

# 1. Install Certbot & Nginx Certbot plugin
echo "[1/5] Installing certbot and python3-certbot-nginx..."
sudo DEBIAN_FRONTEND=noninteractive apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y certbot python3-certbot-nginx openssl

# 2. Generate strong OpenSSL Self-Signed Certificate with IP SAN (Fallback & Direct IP)
echo "[2/5] Creating OpenSSL Certificate with IP SAN for ${IP_ADDR}..."
sudo mkdir -p "${SSL_DIR}"

cat << 'EOF' > /tmp/openssl_san.cnf
[req]
default_bits       = 2048
prompt             = no
default_md         = sha256
distinguished_name = dn
x509_extensions    = v3_req

[dn]
C = US
ST = State
L = City
O = AttendanceSystem
OU = Server
CN = 16.171.10.243

[v3_req]
subjectAltName = @alt_names

[alt_names]
IP.1  = 16.171.10.243
DNS.1 = 16.171.10.243.sslip.io
DNS.2 = localhost
EOF

sudo openssl req -x509 -nodes -days 730 -newkey rsa:2048 \
    -keyout "${SSL_DIR}/attendance.key" \
    -out "${SSL_DIR}/attendance.crt" \
    -config /tmp/openssl_san.cnf

sudo chmod 600 "${SSL_DIR}/attendance.key"
sudo chmod 644 "${SSL_DIR}/attendance.crt"
echo "[OK] OpenSSL Certificate generated at ${SSL_DIR}/attendance.crt"

# 3. Attempt Let's Encrypt automated certificate issuance for sslip.io domain
echo "[3/5] Requesting Let's Encrypt Certificate for ${DOMAIN}..."
LE_SUCCESS=false

if sudo certbot certonly --nginx -d "${DOMAIN}" --register-unsafely-without-email --agree-tos --non-interactive; then
    echo "[OK] Let's Encrypt certificate successfully issued for ${DOMAIN}!"
    LE_SUCCESS=true
else
    echo "[!] Let's Encrypt rate-limited or challenge failed; falling back to SAN certificate."
fi

# 4. Configure Nginx HTTPS Server Block with modern ciphers and SSE streaming
echo "[4/5] Updating Nginx configuration for HTTPS & HTTP redirect..."

if [ "$LE_SUCCESS" = true ]; then
    CRT_PATH="/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"
    KEY_PATH="/etc/letsencrypt/live/${DOMAIN}/privkey.pem"
else
    CRT_PATH="${SSL_DIR}/attendance.crt"
    KEY_PATH="${SSL_DIR}/attendance.key"
fi

sudo tee /etc/nginx/sites-available/attendance > /dev/null << EOF
# 1. HTTP Server Block: Handles ACME challenges & redirects all HTTP to HTTPS
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    client_max_body_size 60M;

    # Let's Encrypt ACME Challenge
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    # Redirect all HTTP traffic to HTTPS
    location / {
        return 301 https://\$host\$request_uri;
    }
}

# 2. HTTPS Server Block: SSL/TLS with HTTP/2 & SSE reverse proxy
server {
    listen 443 ssl http2 default_server;
    listen [::]:443 ssl http2 default_server;
    server_name _;

    client_max_body_size 60M;

    ssl_certificate ${CRT_PATH};
    ssl_certificate_key ${KEY_PATH};

    # Modern SSL Security Configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:10m;
    ssl_session_tickets off;

    # HSTS (HTTP Strict Transport Security)
    add_header Strict-Transport-Security "max-age=63072000" always;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;

        # Real-Time Server-Sent Events (SSE) live stream support
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400s;
    }
}
EOF

# Test Nginx syntax and reload
sudo nginx -t
sudo systemctl restart nginx
echo "[OK] Nginx restarted with HTTPS on port 443."

# 5. Enable Certbot Auto-Renewal
echo "[5/5] Enabling automated SSL renewal timer..."
sudo systemctl enable certbot.timer || true
sudo systemctl start certbot.timer || true

echo "================================================================"
echo "  [SUCCESS] HTTPS DEPLOYMENT COMPLETE!                         "
echo "  Direct HTTPS IP  : https://${IP_ADDR}/                       "
echo "  Public Domain    : https://${DOMAIN}/                        "
echo "================================================================"
