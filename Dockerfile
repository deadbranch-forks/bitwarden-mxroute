# Production compose file
# ── Build stage ──────────────────────────────────────────────
FROM python:3.14-slim-trixie AS build

WORKDIR /build
COPY requirements.txt .
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

# ── Runtime stage ────────────────────────────────────────────
FROM python:3.14-slim-trixie
WORKDIR /app
COPY --from=build /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY server .
EXPOSE 6123
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "6123", "--workers", "1"]
