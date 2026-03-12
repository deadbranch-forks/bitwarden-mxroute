# ── Development container ────────────────────────────────────
# Single-stage: keeps pip + build tools available for ad-hoc
# installs. Targets armv7l (Pi 3B+) with constrained resources.
#
# Usage:
#   docker compose -f docker-compose.yaml -f docker-compose.dev.yaml up
# ─────────────────────────────────────────────────────────────
FROM python:3.11-slim

# Minimal dev utilities — avoid bloating the image on a 1 GB Pi.
# curl: healthcheck / API poking
# procps: ps, top (container debugging)
# Less is intentional; reach for `docker exec` + these, not a
# full distro.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install prod deps first (layer cache), then dev extras.
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Dev-only packages — debugpy for remote attach, ipdb for
# interactive breakpoints, watchdog for file-change detection
# (gunicorn --reload uses polling otherwise, which is wasteful
# on the Pi's USB SSD).
RUN pip install --no-cache-dir \
    debugpy \
    ipdb \
    watchdog

# Source will be bind-mounted at runtime; this COPY is a
# fallback so the image works standalone too.
COPY server .

EXPOSE 6123
# debugpy listener
EXPOSE 5678

# Entrypoint handles optional debugpy activation via
# DEBUGPY_ENABLE=1, then execs gunicorn with reload.
COPY dev-entrypoint.py /usr/local/bin/dev-entrypoint.py
RUN chmod +x /usr/local/bin/dev-entrypoint.py

CMD ["python3", "/usr/local/bin/dev-entrypoint.py"]
