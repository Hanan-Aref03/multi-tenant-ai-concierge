# Stage 1 -- build the React widget bundle
FROM node:20-alpine AS widget-builder
WORKDIR /widget
COPY widget/package*.json ./
RUN npm ci --prefer-offline
COPY widget/ ./
RUN npm run build

# Stage 2 -- Python API + widget static files
FROM python:3.11-slim AS api
WORKDIR /workspace

COPY backend/requirements.txt /workspace/backend/
RUN pip install --no-cache-dir -r /workspace/backend/requirements.txt

COPY backend/ /workspace/backend/
COPY widget/public/ /workspace/widget/public/
COPY --from=widget-builder /widget/dist /workspace/widget/dist/

WORKDIR /workspace/backend

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
