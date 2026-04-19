#!/bin/sh
set -eu

python - <<'PY'
import os
import time

import psycopg

database_url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://", 1)

for attempt in range(30):
    try:
        with psycopg.connect(database_url):
            break
    except Exception:
        if attempt == 29:
            raise
        time.sleep(2)
PY

exec uvicorn app.main:app --host 0.0.0.0 --port 8000

