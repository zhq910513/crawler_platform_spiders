FROM python:3.12-slim AS runtime

ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG CRAWLER_RELEASE_VERSION=1.0.15
ARG CRAWLER_BUILD_SHA=unknown
ARG CRAWLER_IMAGE_DIGEST=

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CRAWLER_RELEASE_VERSION=${CRAWLER_RELEASE_VERSION} \
    CRAWLER_BUILD_SHA=${CRAWLER_BUILD_SHA} \
    CRAWLER_IMAGE_DIGEST=${CRAWLER_IMAGE_DIGEST} \
    CRAWLER_WORK_DIR=/work \
    CRAWLER_LOG_DIR=/logs \
    CRAWLER_CACHE_DIR=/cache \
    CRAWLER_PROFILE_DIR=/profiles

WORKDIR /app

RUN python -m pip install --upgrade pip -i ${PIP_INDEX_URL}
COPY requirements.txt ./requirements.txt
RUN pip install -r requirements.txt -i ${PIP_INDEX_URL}

COPY . .
RUN pip install --no-build-isolation --no-deps -e . && mkdir -p /work /logs /cache /profiles && python -m compileall -q crawler_foundation crawler_platform_spiders.py crawler_runtime spiders open_api plugins

CMD ["python", "-m", "crawler_runtime", "--entrypoint", "spiders.system.health:run", "--kwargs-json", "{}"]
