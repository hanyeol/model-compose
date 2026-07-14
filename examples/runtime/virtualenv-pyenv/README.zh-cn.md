# VirtualEnv Runtime（`pyenv`）

与 [`../virtualenv-python`](../virtualenv-python) 相同，但 venv 是基于**通过 pyenv 安装的特定 Python 版本**创建的。当某个组件需要与控制器不同的 Python 版本时使用。

```yaml
component:
  runtime:
    type: virtualenv
    driver: pyenv
    python: "3.11.9"
    path: .venv/py311
```

## 前置条件

必须已安装 `pyenv`，并且所请求的版本必须已经存在：

```bash
pyenv install 3.11.9   # one-time
```

## 试用

```bash
model-compose up
model-compose run --input '{}'
# -> {"python_version": "Python 3.11.9\n"}
```

无论控制器使用的是什么，worker 子进程都会在 `~/.pyenv/versions/3.11.9/bin/python` 上运行。

## 何时使用

- 组件需要 Python 3.9，但控制器运行 Python 3.12（或反之）。
- 针对特定的解释器构建复现 bug。

如需同时锁定系统级依赖，请改用容器化——参见 [`../docker-model`](../docker-model)。
