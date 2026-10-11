ARG BUILD_FROM=ghcr.io/home-assistant/base:latest
FROM $BUILD_FROM

# Install Python and dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    && pip3 install --no-cache-dir --break-system-packages \
       fastapi==0.115.0 \
       "uvicorn[standard]==0.30.6" \
       jinja2==3.1.4 \
       python-multipart==0.0.9 \
       aiosqlite==0.20.0

# Working directory
WORKDIR /app

# Copy application
COPY app/ /app/
COPY run.sh /

RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
