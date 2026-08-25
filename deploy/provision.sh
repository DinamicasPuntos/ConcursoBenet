#!/usr/bin/env bash
set -euo pipefail

cd /var/www/concurso-benet/backend
python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt

DB_PASSWORD="$(openssl rand -hex 24)"
APP_SECRET="$(openssl rand -hex 32)"

sudo mysql <<SQL
CREATE DATABASE IF NOT EXISTS concurso_benet CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'benet_app'@'localhost' IDENTIFIED BY '${DB_PASSWORD}';
ALTER USER 'benet_app'@'localhost' IDENTIFIED BY '${DB_PASSWORD}';
GRANT ALL PRIVILEGES ON concurso_benet.* TO 'benet_app'@'localhost';
FLUSH PRIVILEGES;
SQL

cat > .env <<EOF
BENET_DB_HOST=127.0.0.1
BENET_DB_PORT=3306
BENET_DB_USER=benet_app
BENET_DB_PASSWORD=${DB_PASSWORD}
BENET_DB_NAME=concurso_benet
BENET_SECRET_KEY=${APP_SECRET}
BENET_API_PUBLIC_BASE=https://dinamicas-back.duckdns.org/concurso-benet-api
EOF

mysql -u benet_app -p"${DB_PASSWORD}" concurso_benet < deploy/schema.sql
mysql -u benet_app -p"${DB_PASSWORD}" concurso_benet < admin.sql
.venv/bin/python importar_pdvs.py
