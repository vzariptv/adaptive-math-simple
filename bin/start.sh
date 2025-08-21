#!/usr/bin/env bash
set -e

# Ensure we run from project root
cd "$(dirname "$0")/.."

# run migrations if possible
export FLASK_APP=wsgi.py
flask db upgrade || true

# optionally create an admin user on start (guarded by env var)
if [ "${CREATE_ADMIN_ON_START}" = "true" ]; then
  echo "[start] CREATE_ADMIN_ON_START=true -> creating admin if missing"
  flask create-admin || true
fi

# start gunicorn
exec gunicorn wsgi:app
