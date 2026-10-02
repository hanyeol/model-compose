# 微调 typed-decision 模型 · Laya 驱动

在标注好的 `{state, schema, answers}` 数据集上微调 [Laya](https://github.com/NandhaKishorM/laya) 编码器 + 每问 head。

Laya 的上游训练仅以 notebook / 参考脚本形式提供;本示例通过 [mindor-laya-trainer](https://github.com/hanyeol/mindor-laya-trainer) 包驱动相同的训练配方(RLCD + 严格适当评分规则奖励 + GRPO 风格策略梯度,与软目标交叉熵混合;LBFGS 温度校准)。

## 数据集格式

每一行是一个 JSON 对象 —— 和 typed-decision 推理输入相同的结构,再加上一个标注 `answers` 映射:

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

答案值也可以是完整的概率字典(例如 `{"true": 0.9, "false": 0.1}`)—— 软目标通过 CE 项传播,行为与上游 notebook 一致。

[`train.jsonl`](./train.jsonl) 中包含了一个 3 行的玩具数据集。

## 运行

```bash
model-compose run train --input '{
  "dataset":    "./train.jsonl",
  "output_dir": "./output/laya",
  "num_epochs": 4
}'
```

输出目录是 `convaiinnovations/laya` 快照的直接替换品 —— 让推理侧的 `typed-decision` 组件指向它:

```yaml
components:
  - id: scorer
    type: model
    task: typed-decision
    family: laya
    model: ./output/laya
    preset: typed-decisions
```

## freeze_encoder

在训练器组件上设置 `freeze_encoder: true` 即可仅训练每问 head。编码器的优化器学习率被归零(不改 `requires_grad`,以便与梯度检查点兼容)—— 显存占用更低、速度更快。

## Preset

`preset` 字段决定从 Laya bundle 的哪个子目录做 warm-start(`english`、`multilingual`、`typed-decisions`)。`typed-decisions` 检查点已经针对 typed-decision 任务家族做过微调,在兼容数据上收敛最快。
