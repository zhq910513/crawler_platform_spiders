# Agent 更新与断点恢复说明

`crawler_platform_spiders` 不负责 Agent 更新，也不主动向平台注册 Release。

Agent 只执行 `crawler_platform` 下发的 Run Snapshot：

```text
releaseId
imageRepository
imageDigest
entryModule
entryFunction
parametersSnapshot
configBindingsSnapshot
credentialBindingsSnapshot
```

同一个 Run 的 retry 必须继续使用原 Snapshot。新 Release 只影响后续新建 Run，不打断正在运行或已经排队的 Run。
