#!/usr/bin/env bash
set -e

echo "================================================================"
echo "  AWS EC2 SSL/TLS & CUSTOM DOMAIN HTTPS SETUP SCRIPT           "
echo "  Domain: curiosityhub.co.in / www.curiosityhub.co.in          "
echo "  Server: 16.171.10.243                                        "
echo "================================================================"

IP_ADDR="16.171.10.243"
DOMAIN_APEX="curiosityhub.co.in"
DOMAIN_WWW="www.curiosityhub.co.in"
EMAIL="prof.capatel@gmail.com"
SSL_DIR="/etc/ssl/attendance"

# 1. Install Certbot, Python3 Nginx plugin, and OpenSSL
echo "[1/6] Installing certbot, python3-certbot-nginx, and openssl..."
sudo DEBIAN_FRONTEND=noninteractive apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y certbot python3-certbot-nginx openssl nginx

# 2. Ensure ACME Webroot Directory & Permissions
echo "[2/6] Preparing ACME challenge directory..."
sudo mkdir -p /var/www/html/.well-known/acme-challenge
sudo chown -R www-data:www-data /var/www/html
sudo chmod -R 755 /var/www/html

# 3. Generate OpenSSL SAN Certificate (Resilient Instant Fallback)
echo "[3/6] Generating OpenSSL SAN Certificate for ${DOMAIN_APEX}, ${DOMAIN_WWW}, and ${IP_ADDR}..."
sudo mkdir -p "${SSL_DIR}"

cat << EOF > /tmp/openssl_san.cnf
[req]
default_bits       = 2048
prompt             = no
default_md         = sha256
distinguished_name = dn
x509_extensions    = v3_req

[dn]
C = IN
ST = Gujarat
L = Ahmedabad
O = CuriosityHub
OU = Production
CN = ${DOMAIN_APEX}

[v3_req]
subjectAltName = @alt_names

[alt_names]
DNS.1 = ${DOMAIN_APEX}
DNS.2 = ${DOMAIN_WWW}
DNS.3 = 16.171.10.243.sslip.io
DNS.4 = localhost
IP.1  = ${IP_ADDR}
EOF

sudo openssl req -x509 -nodes -days 730 -newkey rsa:2048 \
    -keyout "${SSL_DIR}/attendance.key" \
    -out "${SSL_DIR}/attendance.crt" \
    -config /tmp/openssl_san.cnf

sudo chmod 600 "${SSL_DIR}/attendance.key"
sudo chmod 644 "${SSL_DIR}/attendance.crt"
echo "[OK] OpenSSL SAN fallback certificate ready at ${SSL_DIR}/attendance.crt"

# 4. Bootstrap Initial Nginx Port 80 for ACME Challenge Validation
echo "[4/6] Ensuring Port 80 is listening for Let's Encrypt validation..."
sudo tee /etc/nginx/sites-available/attendance > /dev/null << EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name ${DOMAIN_APEX} ${DOMAIN_WWW} ${IP_ADDR} _;

    client_max_body_size 60M;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto http;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/attendance /etc/nginx/sites-enabled/attendance
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx

# 5. Request Trusted Let's Encrypt Certificate covering both apex and www domains
echo "[5/6] Requesting Let's Encrypt SSL/TLS Certificate from CA..."
LE_SUCCESS=false

if sudo certbot certonly --webroot -w /var/www/html \
    -d "${DOMAIN_APEX}" \
    -d "${DOMAIN_WWW}" \
    --agree-tos \
    --no-eff-email \
    --email "${EMAIL}" \
    --non-interactive \
    --expand; then
    echo "[OK] Let's Encrypt certificate successfully issued for ${DOMAIN_APEX} & ${DOMAIN_WWW}!"
    LE_SUCCESS=true
elif sudo certbot certonly --nginx \
    -d "${DOMAIN_APEX}" \
    -d "${DOMAIN_WWW}" \
    --agree-tos \
    --no-eff-email \
    --email "${EMAIL}" \
    --non-interactive \
    --expand; then
    echo "[OK] Let's Encrypt certificate issued via Nginx plugin!"
    LE_SUCCESS=true
else
    echo "[!] Let's Encrypt challenge encountered a rate limit or DNS propagation delay. Using OpenSSL SAN certificate."
fi

# 6. Configure Final Production Nginx Virtual Host (HTTPS Enforced + SSE Reverse Proxy)
echo "[6/6] Writing final Nginx HTTPS configuration..."

if [ -f "/etc/letsencrypt/live/${DOMAIN_APEX}/fullchain.pem" ]; then
    CRT_PATH="/etc/letsencrypt/live/${DOMAIN_APEX}/fullchain.pem"
    KEY_PATH="/etc/letsencrypt/live/${DOMAIN_APEX}/privkey.pem"
elif [ -f "/etc/letsencrypt/live/${DOMAIN_WWW}/fullchain.pem" ]; then
    CRT_PATH="/etc/letsencrypt/live/${DOMAIN_WWW}/fullchain.pem"
    KEY_PATH="/etc/letsencrypt/live/${DOMAIN_WWW}/privkey.pem"
else
    CRT_PATH="${SSL_DIR}/attendance.crt"
    KEY_PATH="${SSL_DIR}/attendance.key"
fi

echo "  -> Using Certificate: ${CRT_PATH}"
echo "  -> Using Private Key: ${KEY_PATH}"

sudo tee /etc/nginx/sites-available/attendance > /dev/null << EOF
# 1. HTTP Server Block: Handles ACME challenges & 301 redirects all HTTP to HTTPS
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name ${DOMAIN_APEX} ${DOMAIN_WWW} ${IP_ADDR} _;

    client_max_body_size 60M;

    # Let's Encrypt ACME challenge path
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    # Redirect all HTTP traffic to HTTPS
    location / {
        return 301 https://\$host\$request_uri;
    }
}

# 2. HTTPS Server Block: Modern TLS 1.2/1.3, HTTP/2, HSTS & SSE reverse proxy
server {
    listen 443 ssl http2 default_server;
    listen [::]:443 ssl http2 default_server;
    server_name ${DOMAIN_APEX} ${DOMAIN_WWW} ${IP_ADDR} _;

    client_max_body_size 60M;

    ssl_certificate ${CRT_PATH};
    ssl_certificate_key ${KEY_PATH};

    # Modern Robust SSL Ciphers & Protocols
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:10m;
    ssl_session_tickets off;

    # HSTS (HTTP Strict Transport Security)
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;

        # Real-Time Server-Sent Events (SSE) live camera stream support
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400s;
    }
}
EOF

# Test Nginx syntax and restart
sudo nginx -t
sudo systemctl restart nginx
echo "[OK] Nginx reloaded with HTTPS on port 443."

# Enable automatic Certbot background renewal timer
sudo systemctl enable certbot.timer || true
sudo systemctl start certbot.timer || true

echo "================================================================"
echo "  [SUCCESS] HTTPS DEPLOYMENT & SSL CONFIGURATION COMPLETE!     "
echo "  Primary Domain  : https://${DOMAIN_APEX}/                    "
echo "  WWW Subdomain   : https://${DOMAIN_WWW}/                     "
echo "  Direct IP Access: https://${IP_ADDR}/                        "
echo "================================================================"
