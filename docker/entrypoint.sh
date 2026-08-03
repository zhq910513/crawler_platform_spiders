#!/bin/sh
set -eu

if [ "$#" -eq 0 ]; then
  set -- run --mode server --task-file /run/crawler/task.json --resources-file /run/crawler/resources.json --secrets-file /run/crawler/secrets.json --result-file /run/crawler/result.json --errors-file /run/crawler/errors.ndjson --last-error-file /run/crawler/last_error.json
fi

exec python -m crawler_platform_spiders "$@"
