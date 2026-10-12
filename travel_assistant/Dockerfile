# Home Assistant Supervisor no longer injects BUILD_FROM (BuildKit migration, 2026).
# Use the multi-arch base image directly.
FROM ghcr.io/home-assistant/base:latest

# Install Python and dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-sqlite \
    && pip3 install --no-cache-dir --break-system-packages \
    fastapi==0.115.0 \
    uvicorn[standard]==0.30.6 \
    jinja2==3.1.4 \
    python-multipart==0.0.9 \
    aiosqlite==0.20.0

# Working directory
WORKDIR /app

# Copy application
COPY app/ /app/
COPY run.sh /

# Ensure static dir exists even if empty in the source tree
RUN mkdir -p /app/static /app/templates && chmod a+x /run.sh

CMD [ "/run.sh" ]
