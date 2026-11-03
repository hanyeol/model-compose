# Vast.ai 运行时（Whisper 语音转写）

在远程 [Vast.ai](https://vast.ai/) GPU 实例上运行 Whisper `large-v3-turbo`
语音转文本模型。放入一个短音频文件，即可拿到转写结果。

在转向更大的模型之前，用这个示例端到端地验证 `vastai` 运行时 — Whisper
的权重仅 ~1.6 GB，在单张 RTX 4090 上几秒钟就能加载完成。

## 先决条件

1. 已设置账单的 [Vast.ai](https://vast.ai/) 账号。
2. 在 Vast.ai 控制台中创建的**网络卷**。20 GB 卷足以容纳 Whisper 和 pip
   缓存。记下卷 ID。
3. 你的 [Vast.ai API 密钥](https://cloud.vast.ai/account/)。

## 环境配置

在此目录中创建一个 `.env` 文件（或在 shell 中导出变量）：

```bash
VASTAI_API_KEY=your-vastai-api-key
VASTAI_VOLUME_ID=your-volume-id
```

## 如何运行

```bash
model-compose up
model-compose run --input '{"audio": "./sample.wav"}'
```

首次执行 `model-compose up` 时会做什么：

1. 销毁上一次会话遗留的、标签为 `mindor-whisper` 的孤立实例。
2. 在 Vast.ai 市场中搜索已验证主机上最便宜的 RTX 4090 报价并租用。
   大约需要 30–90 秒才会进入 `running` 状态。
3. 实例会把 model-compose 安装到该卷的 pip 缓存中，并在 Vast 映射的主机
   端口上启动一个 WebSocket worker。
4. model-compose 使用按会话生成的 bearer token 通过
   `ws://<public_ip>:<mapped_port>` 连接。此时组件即可使用。

当你随后运行 `model-compose run` 时：

- 音频通过 WS 连接转发，Whisper 在实例的 GPU 上运行，然后返回转写结果。
- 最后一次请求之后 5 分钟，实例会被自动停止，暂停 GPU 计费。网络卷
  （以及其中缓存的权重）会保留。下次运行时同一个实例会在几秒内恢复。

## 清理

`model-compose down` 会销毁实例。网络卷 model-compose 从不触碰；当你不再
需要它时，请在控制台手动删除。

如果想要在多次重启之间保留实例，请使用 `model-compose stop` 而不是
`down` — stop 会让实例保持已配置状态（仅暂停），下次 `start` 时能在几秒
内恢复。

## 成本概览

- RTX 4090 verified 主机：运行时每小时约 $0.25–0.45
- 20 GB 网络卷：按主机计价（通常每月几美分）
- 针对此示例的单次转写在不到一分钟的 GPU 时间内就能完成，因此每次运行的
  主要成本是首次请求时 ~30–90 秒的冷启动。

## 为什么此示例选择 Vast.ai

Whisper 本身并*不需要*远程 GPU — 这个示例的意义在于用一个足够小、迭代成本
低的模型，把 Vast.ai 运行时流水线的每一环（搜索报价、创建实例、引导启动、
WS 接入、空闲停止、恢复）都走一遍。等到端到端跑通之后，替换
`component.model` 和 GPU 类型即可验证更大的工作负载。
