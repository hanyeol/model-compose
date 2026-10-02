# 微调 typed-decision 模型 · Nimble 驱动

通过 [Bespoke Nimble](https://github.com/bespokelabsai/nimble) 的 candidate-token 交叉熵,在标注好的 `{state, schema, answers}` 数据集上为 Qwen3.5-9B 挂载 LoRA 适配器并进行微调。

训练器通过 [mindor-nimble-trainer](https://github.com/hanyeol/mindor-nimble-trainer) 包连接 —— 该包复用了 `nimble.training.schema_train` 的 primitives (`CandidateCollator`、`CandidateTrainer`、`prepare_prompts`、`choice_key`、`load_base`),并在其之上叠加了对 model-compose 友好的数据集形态。

## 数据集格式

每一行是一个 JSON 对象:

```json
{
  "state": "User said: book me a flight to Tokyo tomorrow.",
  "schema": {
    "intent":   { "type": "choice", "options": ["buy", "ask", "complain"] },
    "urgent":   { "type": "noul" },
    "priority": { "type": "score", "options": ["low", "medium", "high"] }
  },
  "answers": {
    "intent":   "buy",
    "urgent":   true,
    "priority": "high"
  }
}
```

每行按被回答的 schema 字段展开为一条训练样本 —— Nimble 把每个字段视为独立的 candidate-classification 样本。训练器会把字段再规范化为上游 `prepare_prompts()` 期望的形状(`choice` 带显式 choices、`score` 带数字字符串等级、`noul` 不带选项)。

[`train.jsonl`](./train.jsonl) 中包含了一个 3 行的玩具数据集。

## 运行

```bash
model-compose run train --input '{
  "dataset":    "./train.jsonl",
  "output_dir": "./output/nimble",
  "num_epochs": 3
}'
```

输出目录是 HuggingFace 风格的 LoRA 适配器目录,外加 `schema_config.json` —— 和上游 `nimble.training.schema_train` 的产物完全一致。在 `typed-decision` 推理组件中加载即可:

```yaml
components:
  - id: scorer
    type: model
    task: typed-decision
    family: nimble
    model: ./output/nimble
    base_model: Qwen/Qwen3.5-9B
```

## 平台

Nimble 的 CUDA 评分器需要 `torch>=2.8` 和支持 bf16 的 GPU;训练器沿用同样的 pin。在 Apple Silicon 上,训练器跑在 MLX / `mlx-lm` 之上;在 Linux x86_64 或 aarch64 上,则跑在 CUDA 之上。Nimble 上游不支持其他平台(Darwin x86_64、Windows),在 setup 阶段就会失败。
