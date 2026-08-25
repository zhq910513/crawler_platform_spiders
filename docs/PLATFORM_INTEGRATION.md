# crawler_platform 集成说明

自 v1.0.17 起，`crawler_platform_spiders` 不再主动调用平台 API 注册 Release，也不在仓库中保存平台 Token、Discovery Token 或镜像仓库推送凭据。

标准方式：由 `crawler_platform` 构建中心 / 构建执行器拉取本仓库源码，并调用：

```bash
bash scripts/platform_build_contract.sh
```

该脚本只负责：

```text
Discovery
Contract Validation
Python compile
Manifest 生成
```

输出：

```text
.release/crawler_manifest.json
```

后续镜像构建、镜像推送、imageDigest 读取、Release 登记、Manifest Diff、Release 激活、Production Task 绑定和 Run 调度都属于 `crawler_platform`。

详见：

```text
docs/PASSIVE_PLATFORM_BUILD_CONTRACT_1.0.17.md
```
