#!/usr/bin/env bash
set -Eeuo pipefail
cat >&2 <<'MSG'
ERROR: scripts/build_and_register.sh 已废弃。

crawler_platform_spiders 是被动构建发现标准包，不主动 CI/CD，不保存平台 Token，
也不主动调用 crawler_platform 注册 Release。

请由 crawler_platform 构建中心 / 构建执行器调用：
  bash scripts/platform_build_contract.sh

该脚本只做 discovery、contract validation、compile、manifest 生成，不推送镜像、不注册平台。
MSG
exit 2
