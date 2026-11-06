# Two deployable services, one source tree.
#
#   docker build --target api     -t telcochurn-api:local .
#   docker build --target console -t telcochurn-console:local .
#
# `api` serves scoring; it needs the model bundle and nothing else.
# `console` serves the evidence console; it needs the *reports*, not the model,
# and deliberately does not install CatBoost or scikit-learn -- a read-only
# view of stored results has no business carrying a training stack.
#
# The console image is an **immutable evidence snapshot**: the artifacts are
# baked in at build time, so the image id and the evidence it serves move
# together.  `GET /api/deployment` returns a content address of exactly those
# artifacts.  Mount a newer report directory over /app/reports if you want a
# live view instead, and accept that the image no longer identifies it.

# --- shared base ----------------------------------------------------------
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src


# --- scoring API ----------------------------------------------------------
FROM base AS api

ENV TELCO_MODEL_PATH=/app/artifacts/models/champion.joblib

COPY requirements-api.txt ./
RUN pip install --no-cache-dir -r requirements-api.txt \
    && pip install --no-cache-dir --no-deps .

COPY artifacts/models/champion.joblib ./artifacts/models/champion.joblib

USER 65532:65532
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready')"]
CMD ["uvicorn", "telco_churn.api:app", "--host", "0.0.0.0", "--port", "8000"]


# --- evidence console -----------------------------------------------------
FROM base AS console

ENV TELCO_ARTIFACT_ROOT=/app \
    TELCO_CONSOLE_HOST=0.0.0.0 \
    TELCO_CONSOLE_PORT=8050

COPY requirements-console.txt ./
RUN pip install --no-cache-dir -r requirements-console.txt \
    && pip install --no-cache-dir --no-deps .

# The evidence snapshot.  Read-only at runtime: the console never writes here.
COPY configs ./configs
COPY reports ./reports
COPY docs/CLAIM_LEDGER_V4.md ./docs/CLAIM_LEDGER_V4.md

USER 65532:65532
EXPOSE 8050
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8050/health/ready')"]
CMD ["python", "-m", "telco_churn.dashboard"]
