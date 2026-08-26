#!/usr/bin/env bash
# ── Container entrypoint ─────────────────────────────────────────────────────
# Applies database migrations (Postgres) before handing off to the CMD.
# For the default SQLite mode this is a fast no-op-safe upgrade.
set -euo pipefail

echo "[entrypoint] DATABASE_URL=${DATABASE_URL:-sqlite (default)}"

# Wait for Postgres to accept connections when running against a server DB.
if [[ "${DATABASE_URL:-}" == postgres* ]]; then
  echo "[entrypoint] waiting for Postgres..."
  python - <<'PY'
import os, time, sys
import sqlalchemy as sa
url = os.environ["DATABASE_URL"]
for attempt in range(30):
    try:
        sa.create_engine(url).connect().close()
        print("[entrypoint] Postgres is ready.")
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        print(f"[entrypoint] not ready ({attempt+1}/30): {exc}")
        time.sleep(2)
sys.exit("[entrypoint] Postgres never became ready")
PY
fi

echo "[entrypoint] running migrations (alembic upgrade head)..."
alembic upgrade head || echo "[entrypoint] alembic failed/absent — falling back to create_all at startup"

exec "$@"
