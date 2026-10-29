#!/usr/bin/env bash
# ==============================================================================
# Script de Provisionamento Automatizado - Oracle Cloud Always Free (Porta 80)
# Projeto: Validador Neuro-Simbólico de Editais (Lei 13.303 + UFO-L)
# Compatível com: Canonical Ubuntu (22.04 / 24.04 LTS) e Oracle Linux (8 / 9)
# Uso: sudo bash deploy/setup_oracle_vps.sh
# ==============================================================================

set -euo pipefail

APP_NAME="mestrado-poc"
APP_DIR="/opt/mestrado_poc"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_USER="${SUDO_USER:-ubuntu}"

if [ "$(id -u)" -ne 0 ]; then
    echo "ERRO: Execute este script como root: sudo bash deploy/setup_oracle_vps.sh"
    exit 1
fi

echo "======================================================================"
echo "1/6 - Configurando Swap de 2GB (proteção de memória para 1GB RAM)..."
echo "======================================================================"
if ! swapon --show | grep -q "/swapfile"; then
    fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    if ! grep -q "/swapfile" /etc/fstab; then
        echo "/swapfile none swap sw 0 0" >> /etc/fstab
    fi
    echo "Swap de 2GB ativado com sucesso."
else
    echo "Swap já existente. Pulando..."
fi

echo "======================================================================"
echo "2/6 - Instalando dependências do sistema (Python, Nginx, SWI-Prolog)..."
echo "======================================================================"
if command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -y
    apt-get install -y python3 python3-venv python3-pip nginx git swi-prolog iptables-persistent
elif command -v dnf >/dev/null 2>&1; then
    dnf install -y python3 python3-pip nginx git
fi

echo "======================================================================"
echo "3/6 - Instalando aplicação em ${APP_DIR} e criando ambiente virtual..."
echo "======================================================================"
mkdir -p "${APP_DIR}"
cp -r "${SOURCE_DIR}/app.py" "${SOURCE_DIR}/requirements.txt" "${SOURCE_DIR}/README.md" "${APP_DIR}/"
cp -r "${SOURCE_DIR}/src" "${SOURCE_DIR}/dados" "${APP_DIR}/"

python3 -m venv "${APP_DIR}/.venv"
"${APP_DIR}/.venv/bin/pip" install --upgrade pip
"${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

if id "${APP_USER}" >/dev/null 2>&1; then
    chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"
fi

echo "======================================================================"
echo "4/6 - Criando serviço systemd (${APP_NAME}.service)..."
echo "======================================================================"
cat > "/etc/systemd/system/${APP_NAME}.service" <<EOF
[Unit]
Description=Validador Neuro-Simbolico de Editais (Streamlit)
After=network.target

[Service]
Type=simple
User=${APP_USER}
WorkingDirectory=${APP_DIR}
Environment="PATH=${APP_DIR}/.venv/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=-${APP_DIR}/.env
ExecStart=${APP_DIR}/.venv/bin/streamlit run ${APP_DIR}/app.py \
    --server.port=8501 \
    --server.address=127.0.0.1 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false \
    --browser.gatherUsageStats=false
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "${APP_NAME}.service"
systemctl restart "${APP_NAME}.service"

echo "======================================================================"
echo "5/6 - Configurando Nginx como Proxy Reverso na Porta 80 (HTTP)..."
echo "======================================================================"
NGINX_CONF="/etc/nginx/sites-available/${APP_NAME}"
if [ -d "/etc/nginx/sites-available" ]; then
    cat > "${NGINX_CONF}" <<'EOF'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }

    location /_stcore/stream {
        proxy_pass http://127.0.0.1:8501/_stcore/stream;
        proxy_http_version 1.1;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
EOF
    rm -f /etc/nginx/sites-enabled/default
    ln -sf "${NGINX_CONF}" "/etc/nginx/sites-enabled/${APP_NAME}"
else
    # Oracle Linux / RHEL usa /etc/nginx/conf.d/
    cat > "/etc/nginx/conf.d/${APP_NAME}.conf" <<'EOF'
server {
    listen 80;
    server_name _;
    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
EOF
fi

nginx -t
systemctl enable nginx
systemctl restart nginx

echo "======================================================================"
echo "6/6 - Liberando Porta 80 no Firewall Interno da VM Oracle Cloud..."
echo "======================================================================"
if command -v iptables >/dev/null 2>&1; then
    if ! iptables -C INPUT -p tcp --dport 80 -j ACCEPT 2>/dev/null; then
        iptables -I INPUT 1 -p tcp --dport 80 -j ACCEPT
    fi
    if command -v netfilter-persistent >/dev/null 2>&1; then
        netfilter-persistent save
    fi
fi

if command -v firewall-cmd >/dev/null 2>&1 && systemctl is-active --quiet firewalld; then
    firewall-cmd --permanent --add-service=http
    firewall-cmd --reload
fi

PUBLIC_IP=$(curl -s --max-time 5 ifconfig.me || hostname -I | awk '{print $1}')
echo "======================================================================"
echo "CONCLUÍDO COM SUCESSO!"
echo "Status do serviço Streamlit: $(systemctl is-active ${APP_NAME}.service)"
echo "Status do serviço Nginx:     $(systemctl is-active nginx)"
echo ""
echo "Acesse a ferramenta no navegador em:"
echo "  👉 http://${PUBLIC_IP}"
echo ""
echo "(Lembre-se de garantir que a Porta 80 TCP está liberada na Security List da VCN no Console da Oracle Cloud)"
echo "======================================================================"
