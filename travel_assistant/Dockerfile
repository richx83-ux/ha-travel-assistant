# Multi-stage: build React UI then copy into the HA add-on image
FROM node:20-alpine AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ .
RUN npm run build

# Final image
FROM ghcr.io/home-assistant/base:latest

RUN apk add --no-cache \
    python3 \
    py3-pip \
    sqlite \
    tzdata \
    && (apk add --no-cache py3-pillow || true) \
    && pip3 install --no-cache-dir --break-system-packages \
    fastapi==0.115.0 \
    uvicorn[standard]==0.30.6 \
    jinja2==3.1.4 \
    python-multipart==0.0.9 \
    aiosqlite==0.20.0 \
    openpyxl==3.1.5

WORKDIR /app

COPY app/ /app/
COPY --from=ui /ui/dist /app/static/react
COPY run.sh /

RUN mkdir -p /app/static /app/templates && chmod a+x /run.sh

CMD [ "/run.sh" ]
