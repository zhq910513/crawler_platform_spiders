#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${ENV_FILE:-.env.platform}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

VERSION="${RELEASE_VERSION:-$(cat VERSION)}"
IMAGE_REPOSITORY="${IMAGE_REPOSITORY:-crawler_platform_spiders}"
IMAGE_TAG="${IMAGE_TAG:-$VERSION}"
IMAGE_REF="${IMAGE_REPOSITORY}:${IMAGE_TAG}"
PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
DOCKERFILE="${DOCKERFILE:-Dockerfile}"
PUSH_IMAGE="${PUSH_IMAGE:-1}"
DRY_RUN="${DRY_RUN:-0}"
BUILD_SHA="${GIT_COMMIT:-$(git rev-parse --short=12 HEAD 2>/dev/null || echo unknown)}"

python scripts/sync_sch.py --check
python scripts/validate_tasks.py
python -m compileall -q crawler_foundation crawler_platform_spiders.py crawler_runtime spiders open_api plugins scripts

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker 不存在，无法构建镜像" >&2
  exit 1
fi

docker build --build-arg PIP_INDEX_URL="$PIP_INDEX_URL" --build-arg CRAWLER_RELEASE_VERSION="$VERSION" --build-arg CRAWLER_BUILD_SHA="$BUILD_SHA" -f "$DOCKERFILE" -t "$IMAGE_REF" .

if [[ "$PUSH_IMAGE" == "1" ]]; then
  docker push "$IMAGE_REF"
fi

if [[ -z "${IMAGE_DIGEST:-}" ]]; then
  if [[ "$PUSH_IMAGE" == "1" ]]; then
    REPO_DIGEST="$(docker inspect --format='{{index .RepoDigests 0}}' "$IMAGE_REF" 2>/dev/null || true)"
    if [[ "$REPO_DIGEST" == *"@sha256:"* ]]; then
      IMAGE_DIGEST="${REPO_DIGEST#*@}"
    fi
  fi
  if [[ -z "${IMAGE_DIGEST:-}" ]]; then
    IMAGE_DIGEST="$(docker inspect --format='{{.Id}}' "$IMAGE_REF")"
    echo "WARNING: 未取得 registry manifest digest，暂用本地 image id。多 Agent 生产发布请设置 PUSH_IMAGE=1 并使用镜像仓库 digest。" >&2
  fi
fi

ARGS=(
  --env-file "$ENV_FILE"
  --image-repository "$IMAGE_REPOSITORY"
  --image-digest "$IMAGE_DIGEST"
  --release-version "$VERSION"
  --git-commit "$BUILD_SHA"
)
if [[ "$DRY_RUN" == "1" ]]; then
  ARGS+=(--dry-run)
fi

python scripts/platform_register.py "${ARGS[@]}"
