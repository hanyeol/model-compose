# Docker Runtime（标准镜像）

在使用**标准 mindor 运行时镜像** `mindor/component:<version>` 构建的 Docker 容器内运行 worker。IPC 通过 docker 守护进程的 attach stdin/stdout 流传输，因此在 Linux 原生环境和 macOS Docker Desktop 上都可以直接工作，无需额外设置。

```yaml
component:
  runtime:
    type: docker
    # no image / build → the standard image is used
```

## 前置条件

- Docker 守护进程正在运行（macOS/Windows 上是 Docker Desktop，Linux 上是 dockerd）。

## 试用

```bash
model-compose up
model-compose run --input '{}'
# -> {"uname": "Linux <container-id> ... #1 SMP ... GNU/Linux"}
```

首次 `up` 会在本地构建标准镜像（需几分钟），或者从已发布的位置拉取。后续运行只需几秒即可启动容器。

## 镜像种类

| 种类      | 触发条件                                                      |
|-----------|-------------------------------------------------------------|
| STANDARD  | 无 `image:` / `build:` / 项目级 `requirements.txt`。         |
| DERIVED   | 项目存在非空的 `requirements.txt`（在其之上追加）。            |
| CUSTOM    | 指定了 `image:` 或 `build:`（参见 [../docker-custom-image](../docker-custom-image)）。 |

## 何时使用

- 希望在各处使用相同运行时镜像的 CI 环境。
- 需要将组件与宿主系统库（`libc`、`libstdc++` 等）隔离。
- 在 macOS 上运行需要 Linux 专用库的组件。

## 对比

| 特性                 | `virtualenv` | `docker` |
|----------------------|:-----------:|:--------:|
| 系统库隔离            |      ❌     |     ✅   |
| 跨架构/平台           |      ❌     |     ✅   |
| 启动开销              |    ~5-30s   |  ~5-30s  |
| 冷启动开销            |   1-3 分钟  | 1-10 分钟 |
