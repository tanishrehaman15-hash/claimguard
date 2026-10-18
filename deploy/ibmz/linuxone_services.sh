#!/usr/bin/env bash
# Run ClaimGuard as always-on services on IBM LinuxONE (RHEL 9, s390x).
#   dashboard -> :8501 (and :80 via nginx)    API -> :8000
# Usage (as the deploy user, with sudo):  ./deploy/ibmz/linuxone_services.sh
set -euo pipefail
APP="$(cd "$(dirname "$0")/../.." && pwd)"
USER_NAME="$(id -un)"
PY="$APP/.venv/bin/python"

sudo tee /etc/systemd/system/claimguard-dashboard.service >/dev/null <<EOF
[Unit]
Description=ClaimGuard dashboard (Streamlit)
After=network-online.target

[Service]
User=$USER_NAME
WorkingDirectory=$APP
ExecStart=$PY -m streamlit run dashboard/app.py --server.address 0.0.0.0 --server.port 8501 --server.headless true --browser.gatherUsageStats false --client.toolbarMode viewer
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/claimguard-api.service >/dev/null <<EOF
[Unit]
Description=ClaimGuard scoring API (FastAPI)
After=network-online.target

[Service]
User=$USER_NAME
WorkingDirectory=$APP
ExecStart=$PY -m uvicorn claimguard.api:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# nginx on :80 so the dashboard is reachable on the default HTTP port (websocket-aware).
sudo dnf install -y -q nginx
sudo tee /etc/nginx/conf.d/claimguard.conf >/dev/null <<'EOF'
map $http_upgrade $connection_upgrade { default upgrade; '' close; }
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host $host;
    }
    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
EOF
# Remove the stock default_server block so ours wins.
sudo sed -i 's/listen       80 default_server;/listen       80;/; s/listen       \[::\]:80 default_server;/listen       [::]:80;/' /etc/nginx/nginx.conf
sudo setsebool -P httpd_can_network_connect 1 2>/dev/null || true

if systemctl is-active --quiet firewalld; then
  sudo firewall-cmd --permanent --add-service=http --add-port=8501/tcp --add-port=8000/tcp && sudo firewall-cmd --reload
fi

sudo systemctl daemon-reload
sudo systemctl enable --now claimguard-dashboard claimguard-api nginx
sudo systemctl restart claimguard-dashboard claimguard-api nginx
sleep 5
systemctl --no-pager --lines=0 status claimguard-dashboard claimguard-api nginx | grep -E "●|Active"
