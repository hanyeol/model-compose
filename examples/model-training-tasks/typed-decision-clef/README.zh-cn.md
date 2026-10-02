# 微调 typed-decision 模型 · Clef 驱动

在标注好的 `{state, schema, answers}` 数据集上微调 [Cloudflare Clef](https://huggingface.co/Cloudflare/clef) 的 `joint_schema_model`。

训练器通过 [mindor-clef-trainer](https://github.com/hanyeol/mindor-clef-trainer) 包连接:`model-compose` 预配基础检查点,将数据集交给 `clef_trainer.train(...)`,然后把 Clef 运行时所需的粘合件(处理器配置、`joint_schema_model.py`)复制进输出检查点目录。

## 数据集格式

每一行是一个 JSON 对象,包含三个字段 —— 和 typed-decision 推理输入相同的结构,再加上一个按问题 id 索引的标注 `answers` 映射:

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

`noul` 答案是原生布尔值;`choice` 和 `score` 答案是选项标签(字符串)。训练器会在计算每问损失之前,把每个答案映射到对应的 logit 索引。

[`train.jsonl`](./train.jsonl) 中包含了一个 3 行的玩具数据集。

## 运行

```bash
model-compose run train --input '{
  "dataset":    "./train.jsonl",
  "output_dir": "./output/clef",
  "num_epochs": 3
}'
```

输出目录可以直接替换 `Cloudflare/clef` 快照路径 —— 让推理侧的 `typed-decision` 组件指向它,就能提供微调后的模型:

```yaml
components:
  - id: scorer
    type: model
    task: typed-decision
    family: clef
    model: ./output/clef
```

## 损失函数

按问题的损失在每条记录内求和并取平均:

| 问题类型      | 损失                                                                                   |
|---------------|----------------------------------------------------------------------------------------|
| `choice`      | 在 `option_ids` 上的交叉熵                                                             |
| `noul`        | 在 `(true, false)` 上的交叉熵                                                          |
| `score`       | 对所选选项索引(从低到高排序)的 ordinal MSE;在训练器组件上设 `score_ordinal=False` 可切换为普通交叉熵 |

每种问题类型的权重(`choice_loss_weight`、`noul_loss_weight`、`score_loss_weight`)在训练器组件级别可调。
