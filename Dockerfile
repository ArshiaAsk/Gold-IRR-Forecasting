# Single-service image for the FastAPI model server and the Streamlit demo.
# Default command: the API on 8000. To run the UI from the same image:
#   docker run --rm -p 8501:8501 gold-irr-honest-forecasting \
#     streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0
#
# Python 3.12, pinned by tag and digest (linux/amd64 index digest).
FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive \
    APP_HOME=/app

WORKDIR ${APP_HOME}

# curl is only for the HEALTHCHECK. No build toolchain is needed: the runtime
# requirements ship manylinux cp312 wheels.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Non-root runtime user. UID is fixed so volume permissions are predictable.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p ${APP_HOME}/logs \
    && chown -R appuser:appuser ${APP_HOME}

# Application code and committed artifacts only. No raw data, no tests, no
# notebooks, and no legacy model files (the stale gold_lstm_v2.keras is excluded).
COPY --chown=appuser:appuser config/ ./config/
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser models/gold_lstm_stationary_v2.keras ./models/
COPY --chown=appuser:appuser models/gold_lstm_stationary_v2.metadata.json ./models/
COPY --chown=appuser:appuser models/scaler_X_stationary_v2.pkl ./models/
COPY --chown=appuser:appuser models/scaler_y_stationary_v2.pkl ./models/
COPY --chown=appuser:appuser results/ ./results/
COPY --chown=appuser:appuser data/sample/ ./data/sample/
COPY --chown=appuser:appuser streamlit_app.py ./

USER appuser

EXPOSE 8000 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=45s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
