FROM python:3.12-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip wheel --no-build-isolation --wheel-dir /wheels .

FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates tini \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 crawler \
    && useradd --uid 10001 --gid crawler --create-home --shell /usr/sbin/nologin crawler

COPY --from=builder /wheels /wheels
RUN python -m pip install --no-index --find-links=/wheels crawler-platform-spiders \
    && rm -rf /wheels

COPY docker/entrypoint.sh /usr/local/bin/crawler-entrypoint
RUN chmod 0755 /usr/local/bin/crawler-entrypoint \
    && mkdir -p /run/crawler /tmp/crawler \
    && chown -R crawler:crawler /run/crawler /tmp/crawler

USER crawler
WORKDIR /app
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/crawler-entrypoint"]
