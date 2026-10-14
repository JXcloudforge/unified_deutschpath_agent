FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STAGE2_DATA_PATH=/data \
    APP_ENV=production

WORKDIR /app
COPY pyproject.toml README.md ./
COPY app ./app
COPY ui ./ui
RUN python -m pip install --no-cache-dir .

RUN useradd --system --uid 10001 --create-home deutschpath \
    && mkdir -p /data \
    && chown deutschpath:deutschpath /data
USER deutschpath

EXPOSE 8765 8501
CMD ["python", "-m", "uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8765"]
