# Embedded Runtime

基线示例：shell 组件*直接在控制器进程内*运行。没有 IPC，没有子进程创建，也没有容器。

```yaml
component:
  runtime:
    type: embedded
```

## 试用

```bash
model-compose up
model-compose run --input '{"name": "Alice"}'
# -> {"greeting": "hello from Alice\n"}
```

## 何时使用

- 开发 / 冒烟测试。
- 廉价、安全且不需要依赖隔离的组件。
- 未提供 `runtime:` 块时 `native` 控制器的默认值。

## 何时不宜使用

- 重量级模型（它们会占用控制器线程）。
- 任何有可能因原生依赖不稳定而使控制器 segfault 的组件。
- 依赖版本与控制器冲突的组件。

对于这些情况，请参见 [`../process`](../process)、[`../virtualenv-python`](../virtualenv-python) 或 [`../docker-model`](../docker-model)。
