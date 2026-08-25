#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUTPUT_MANIFEST="${OUTPUT_MANIFEST:-.release/crawler_manifest.json}"
mkdir -p "$(dirname "$OUTPUT_MANIFEST")"

python scripts/sync_sch.py --check
python scripts/validate_tasks.py
python -m compileall -q crawler_foundation crawler_platform_spiders.py crawler_runtime spiders open_api plugins scripts
python scripts/build_manifest.py --output "$OUTPUT_MANIFEST"

echo "PASSIVE_BUILD_CONTRACT_OK manifest=$OUTPUT_MANIFEST"
