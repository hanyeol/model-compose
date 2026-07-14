# Docker Runtime（带模型的派生镜像）

与 [`../docker-shell`](../docker-shell) 相同的 Docker 后端，但此目录包含 `requirements.txt`——因此 model-compose 会在标准运行时镜像之上构建一个安装了 `transformers` + `torch` 的**派生（DERIVED）镜像**（`mindor/component-<project>:<version>`）。

```yaml
component:
  runtime:
    type: docker
    volumes:
      - ./.hf-cache:/root/.cache/huggingface
```

## 试用

```bash
model-compose up
model-compose run --input '{"text": "the weather is lovely"}'
```

首次 `up` 较慢（镜像构建 + 模型下载）。后续运行速度很快：
- 镜像会以 `mindor.requirements-sha256` 标签缓存，
- HuggingFace 缓存以 bind-mount 方式挂载，因此模型文件可在容器重启后保留。

## 何时使用

- 需要依赖 + 系统隔离，同时希望在开发机之间保持稳定运行时环境的本地模型。
- 需要宿主机不具备的 Linux 系统库的任何组件。

## 注意事项

- 当 `requirements.txt` 改变时会自动重新构建。
- 删除 `.hf-cache/` 可强制重新下载模型。
