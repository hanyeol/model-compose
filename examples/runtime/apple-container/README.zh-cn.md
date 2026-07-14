# Apple Container Runtime

仅限 macOS 的后端。使用 Apple 原生的 [`container`](https://github.com/apple/container) CLI 而不是 Docker Desktop。IPC 的引导方式与 Docker 后端相同，但通过 `container start -a -i <name>` 子进程的 stdin/stdout 传输。

```yaml
component:
  runtime:
    type: apple-container
```

## 前置条件

- 已安装并配置了 Apple `container` CLI 的 macOS。
- 推荐 Apple Silicon（M 系列）。

验证：

```bash
container --version
```

## 试用

```bash
model-compose up
model-compose run --input '{}'
# -> {"uname": "Linux <container-id> ... aarch64 GNU/Linux"}
```

## 何时使用

- 希望在不运行 Docker Desktop 的情况下使用原生容器化的 macOS 环境。
- 所有你会用 `../docker-shell` 的场景，但在 Apple Silicon 上无需承担 Docker Desktop 的开销。

## 注意事项

- `apple-container` 的 DSL 与 `docker` 非常相似（image、volumes、ports、environment 等），因此在两者之间迁移基本只需修改 `runtime.type`。
- `image:` 可以指向任何 `container` CLI 能够拉取的 OCI 镜像。
