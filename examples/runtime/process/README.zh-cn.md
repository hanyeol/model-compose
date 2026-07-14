# Process Runtime

在**独立的操作系统进程**中运行模型 worker（通过 `multiprocessing`）。IPC 通过 `multiprocessing.Queue` 传输——没有套接字，也没有文件系统。

```yaml
component:
  runtime:
    type: process
    start_timeout: 120s
    env:
      TOKENIZERS_PARALLELISM: "false"
```

## 试用

```bash
model-compose up
model-compose run --input '{"text": "I love this project"}'
```

首次运行会下载模型（几百 MB）。后续运行会很快。

## 你能得到什么

- 模型加载和推理发生在子进程中，而不是控制器中。
- 原生库崩溃（segfault、OOM）只会杀死 worker，不会杀死控制器。
- `env:` 值*仅*作用于子进程，因此你可以在不污染控制器环境的情况下调整每个模型的旋钮，例如 `TOKENIZERS_PARALLELISM`、`CUDA_VISIBLE_DEVICES` 等。

## 对比

| 特性                       | `embedded` | `process` |
|----------------------------|:---------:|:---------:|
| 崩溃隔离                    |     ❌    |     ✅    |
| 独立的环境变量               |     ❌    |     ✅    |
| 依赖隔离                    |     ❌    |     ❌    |
| 启动开销                    |     0     |   ~数秒   |

如需依赖隔离，请参见 [`../virtualenv-python`](../virtualenv-python)。
