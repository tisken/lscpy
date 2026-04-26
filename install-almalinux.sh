#!/bin/bash
# ============================================================
# LSC - Log Source Checker - Instalación en AlmaLinux 9
# ============================================================
set -e

APP_DIR="/opt/lsc"
APP_USER="lsc"
PYTHON="python3.11"
VENV="$APP_DIR/.venv"

echo "=== LSC Installer para AlmaLinux 9 ==="

# 1. Dependencias del sistema
echo "[1/6] Instalando dependencias del sistema..."
dnf install -y epel-release
dnf install -y python3.11 python3.11-pip python3.11-devel \
    gcc libffi-devel \
    pango gdk-pixbuf2 cairo \
    git

# 2. Usuario del sistema
echo "[2/6] Creando usuario $APP_USER..."
id $APP_USER &>/dev/null || useradd -r -s /sbin/nologin -d $APP_DIR $APP_USER

# 3. Clonar o actualizar repo
echo "[3/6] Descargando código..."
if [ -d "$APP_DIR/.git" ]; then
    cd $APP_DIR && git pull origin main
else
    git clone https://github.com/tisken/lscpy.git $APP_DIR
fi

# 4. Entorno virtual + dependencias Python
echo "[4/6] Instalando dependencias Python..."
cd $APP_DIR
$PYTHON -m venv $VENV
$VENV/bin/pip install --upgrade pip
$VENV/bin/pip install -r requirements.txt

# 5. Permisos
echo "[5/6] Configurando permisos..."
chown -R $APP_USER:$APP_USER $APP_DIR
chmod 750 $APP_DIR

# 6. Servicio systemd
echo "[6/6] Instalando servicio systemd..."
cat > /etc/systemd/system/lsc.service << EOF
[Unit]
Description=Log Source Checker (LSC)
After=network.target

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
ExecStart=$VENV/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
Environment=PATH=$VENV/bin:/usr/bin:/bin

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable lsc
systemctl start lsc

echo ""
echo "=== LSC instalado correctamente ==="
echo "URL:    http://$(hostname -I | awk '{print $1}'):8000"
echo "Login:  admin / admin (se pide cambiar en primer acceso)"
echo ""
echo "Comandos útiles:"
echo "  systemctl status lsc    # Ver estado"
echo "  systemctl restart lsc   # Reiniciar"
echo "  journalctl -u lsc -f    # Ver logs"
