# VirtualEnv Runtime（Python `venv`）

在由 `python -m venv` 创建的**独立 Python 虚拟环境**中运行模型 worker。该目录下的 `requirements.txt` 只会将 `transformers` + `torch` 安装到该 venv 中——控制器的 site-packages 完全不会被触及。

```yaml
component:
  runtime:
    type: virtualenv
    driver: python
    path: .venv/classifier
```

## 试用

```bash
model-compose up
model-compose run --input '{"text": "You are a wonderful person"}'
```

首次 `up`：
- 在此文件旁创建 `.venv/classifier/`，
- 将 `requirements.txt` pip-install 到该 venv，
- 将 mindor 注入到 venv 的 site-packages 中，
- 在 `.venv/classifier/bin/python` 上启动 worker。

后续 `up` 会复用该 venv，除非 mindor 版本或 `requirements.txt` 发生变化。

## 你能得到什么

- `process` 提供的一切，加上：
- 每个组件独立的依赖版本。
- 不会有某个组件引入不兼容的 `torch` 从而破坏控制器安装的风险。

## 对比

| 特性                   | `process` | `virtualenv-python` |
|------------------------|:---------:|:-------------------:|
| 操作系统级隔离          |     ✅    |          ✅         |
| 依赖隔离                |     ❌    |          ✅         |
| Python 版本锁定         |     ❌    |          ❌         |

如需锁定 Python 版本，请参见 [`../virtualenv-pyenv`](../virtualenv-pyenv)。
如需系统级隔离，请参见 [`../docker-model`](../docker-model)。
