# Rayan owns the guardrails service shell.
FROM python:3.11-slim

WORKDIR /workspace

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY . /workspace

EXPOSE 8011

HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8011/healthz')" || exit 1

CMD ["uvicorn", "apps.guardrails.app.main:app", "--host", "0.0.0.0", "--port", "8011"]
