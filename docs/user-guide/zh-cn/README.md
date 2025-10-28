# Model-Compose 用户指南

欢迎使用 **model-compose** 用户指南！本综合文档将帮助您掌握声明式 AI 工作流编排——从基础概念到高级部署策略。

---

## 🚀 快速开始

初次使用 model-compose？从这里开始：

1. **[入门指南](./01-getting-started.md)** - 安装、第一个工作流和基础概念
2. **[核心概念](./02-core-concepts.md)** - 理解控制器、组件和工作流
3. **[CLI 使用](./03-cli-usage.md)** - 掌握命令行界面

---

## 📚 完整目录

**[→ 完整目录](./00-table-of-contents.md)**

### 核心主题

#### 基础
- [入门指南](./01-getting-started.md) - 安装并运行您的第一个工作流
- [核心概念](./02-core-concepts.md) - 架构和关键组件
- [CLI 使用](./03-cli-usage.md) - 命令参考和示例

#### 构建工作流
- [组件配置](./04-component-configuration.md) - 定义可重用组件
- [编写工作流](./05-writing-workflows.md) - 创建多步骤流水线
- [变量绑定](./12-variable-binding.md) - 数据流和转换

#### 控制器与界面
- [控制器配置](./06-controller-configuration.md) - HTTP 和 MCP 服务器
- [Web UI 配置](./07-webui-configuration.md) - 可视化工作流管理

#### AI 模型
- [本地 AI 模型](./08-local-ai-models.md) - 在本地运行模型
- [外部服务集成](./10-external-service-integration.md) - 连接 OpenAI、Claude 等
- [流式模式](./11-streaming-mode.md) - 实时输出流

#### 系统集成
- [系统集成](./13-system-integration.md) - 监听器、触发器和网关
  - HTTP 回调监听器 - 处理异步 webhooks
  - HTTP 触发监听器 - 事件驱动工作流
  - 网关支持 - 安全地暴露本地服务

#### 部署与生产
- [部署](./14-deployment.md) - Docker、云和生产最佳实践
- [实践示例](./15-practical-examples.md) - 真实世界用例
- [故障排除](./16-troubleshooting.md) - 常见问题和解决方案

---

## 🎯 通过示例学习

寻找实践示例？查看：

- **[实践示例](./15-practical-examples.md)** - 完整的工作示例：
  - 聊天机器人（OpenAI、Claude）
  - 语音生成流水线
  - 图像分析和编辑
  - 使用向量数据库的 RAG 系统
  - 使用 MCP 的 Slack 机器人
  - 多模态工作流

- **[示例目录](../../../examples/)** - 可直接运行的 YAML 配置

---

## 🔍 快速参考

### 常见任务

| 我想要... | 参考... |
|--------------|----------|
| 安装并运行第一个工作流 | [入门指南](./01-getting-started.md) |
| 调用外部 API（OpenAI、Claude） | [外部服务集成](./10-external-service-integration.md) |
| 运行本地 AI 模型 | [本地 AI 模型](./08-local-ai-models.md) |
| 创建多步骤工作流 | [编写工作流](./05-writing-workflows.md) |
| 实时流式输出 | [流式模式](./11-streaming-mode.md) |
| 处理 webhooks 和回调 | [系统集成](./13-system-integration.md) |
| 部署到生产环境 | [部署](./14-deployment.md) |
| 构建聊天机器人 | [实践示例 § 15.1](./15-practical-examples.md#151-构建聊天机器人) |
| 设置 RAG 系统 | [实践示例 § 15.4](./15-practical-examples.md#154-rag-系统使用向量数据库) |
| 调试问题 | [故障排除](./16-troubleshooting.md) |

### 关键概念

- **控制器（Controller）**：托管工作流的 HTTP 或 MCP 服务器
- **组件（Component）**：可重用的定义（API 调用、模型、命令）
- **工作流（Workflow）**：命名的作业序列
- **作业（Job）**：执行组件的单个步骤
- **监听器（Listener）**：接收 HTTP 回调或触发工作流
- **网关（Gateway）**：将本地服务隧道到互联网

---

## 🛠 配置参考

寻找特定的配置选项？

- **[完整配置架构](./17-appendix.md#171-完整配置文件架构)** - 完整 YAML 参考
- **[组件类型](./04-component-configuration.md#41-组件类型)** - 所有可用组件类型
- **[变量绑定语法](./12-variable-binding.md)** - 完整变量参考

---

## 💡 学习建议

1. **从简单开始**：从[入门指南](./01-getting-started.md)开始
2. **实践操作**：尝试[实践示例](./15-practical-examples.md)
3. **循序渐进**：一次添加一个功能
4. **探索**：查看[示例目录](../../../examples/)获取灵感
5. **提问**：如果遇到困难，请提交[问题](https://github.com/hanyeol/model-compose/issues)

---

## 🤝 贡献文档

发现错误或想改进文档？

1. Fork 本仓库
2. 编辑 `docs/user-guide/zh-cn/` 中的 Markdown 文件
3. 提交 pull request

我们感谢所有贡献！

---

## 📬 获取帮助

- **文档问题**：[提交问题](https://github.com/hanyeol/model-compose/issues)
- **问题咨询**：[GitHub 讨论区](https://github.com/hanyeol/model-compose/discussions)
- **错误报告**：[问题跟踪器](https://github.com/hanyeol/model-compose/issues)

---

## 📖 其他语言

- **🌍 English**: [English User Guide](../README.md)
- **🇰🇷 한국어**: [한국어 사용자 가이드](../ko/README.md)

---

**开始编排吧！🎉**
