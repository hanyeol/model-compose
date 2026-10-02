# 微调 typed-decision 模型 · Kev 驱动

在标注好的 `{state, schema, answers}` 数据集上联合训练 [Kev](https://github.com/jaredpalmer/kev) 的 LoRA 适配器与 pointer head。

Kev 上游的训练是一个 1000+ 行的 CLI 脚本,紧耦合于其 suite / manifest 布局。本示例把核心训练循环(bf16 LoRA + pointer head,每个问题用 `kev.train.question_loss`)通过 [mindor-kev-trainer](https://github.com/hanyeol/mindor-kev-trainer) 包驱动 —— 该包把循环重写为普通的 `train(dataset, config)` 函数,并复用安装好的 `kev` 包中的 `kev.model.DecisionModel`、`kev.model.encode`、`kev.train.question_loss`。

## 范围

**支持**:单进程 LoRA + pointer-head 训练、bf16/fp16 autocast、linear warmup → linear decay 的 LR 调度、按 epoch 的检查点。

**不支持**:FSDP2 全量微调、Kev 的 micro-batch planner、置换 KL 正则化、anchor-KL 教师分布。这些功能请直接使用 `python -m kev.train`。

## 数据集格式

每一行是一个 JSON 对象:

```json
{
  "state": "User said: book me a flight to Tokyo tomorrow.",
  "schema": {
    "intent":   { "type": "choice", "options": ["buy", "ask", "complain"], "instructions": "..." },
    "urgent":   { "type": "noul",   "instructions": "..." },
    "priority": { "type": "score",  "options": ["low", "medium", "high"] }
  },
  "answers": {
    "intent":   "buy",
    "urgent":   true,
    "priority": "high"
  }
}
```

超出所配置 `max_state_length` / `max_branch_length` 预算的行会被跳过(与上游在 on-the-fly 构造 record 时相同的策略)。

[`train.jsonl`](./train.jsonl) 中包含了一个 3 行的玩具数据集。

## 运行

```bash
model-compose run train --input '{
  "dataset":    "./train.jsonl",
  "output_dir": "./output/kev",
  "num_epochs": 3
}'
```

输出目录包含 LoRA 适配器与 `pointer_head.pt` —— 直接用 Kev 的标准 loader 加载:

```yaml
components:
  - id: scorer
    type: model
    task: typed-decision
    family: kev
    model: ./output/kev
```

## 损失函数

按问题的损失直接取自 `kev.train.question_loss`:

- `choice`:在各选项上的交叉熵(通过 `question["target"]` 支持软目标)。
- `noul`:在 `(false, true)` 上的交叉熵。
- `score`:交叉熵加上有序 ranked-probability-score 项(由训练器上的 `ord_weight` 控制,默认 0.5)。
