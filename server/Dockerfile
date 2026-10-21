# N-Ways Addressing for Sierra Leone: the registry server.
# Build from the repository root:  docker build -f server/Dockerfile -t nways-sl-registry .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ADDRESSES_DB=/data/addresses.sqlite \
    REGISTRY=/app/registry \
    PORT=8080

RUN useradd --system --uid 10001 --home-dir /app --shell /usr/sbin/nologin registry \
 && mkdir -p /app /data \
 && chown registry:registry /data

WORKDIR /app
COPY --chown=registry:registry engine/reference/sl_address.py engine/reference/plate_names.py engine/reference/
COPY --chown=registry:registry engine/data/ engine/data/
COPY --chown=registry:registry registry/ registry/
COPY --chown=registry:registry server/ server/
COPY --chown=registry:registry LICENSE LICENSE-DATA LICENSE-DOCS NOTICE ./

USER registry
VOLUME ["/data"]
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
  CMD python3 -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/v1/health' % os.environ.get('PORT', '8080'), timeout=4)"

ENTRYPOINT ["sh", "/app/server/docker-entrypoint.sh"]
