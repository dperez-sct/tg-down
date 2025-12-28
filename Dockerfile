FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    tini \
    procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

RUN mkdir -p /app/downloads /app/sessions \
    && addgroup --system app \
    && adduser --system --ingroup app app \
    && chown -R app:app /app

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD pgrep -f "python tg-down.py" || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
USER app
CMD ["python", "tg-down.py"]