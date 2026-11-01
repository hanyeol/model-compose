# Remote Process Runtime (SSH 主机上的 shell)

在通过 SSH 访问的**远程主机上的 worker 进程**中运行 `shell` 组件。控制器仍留在本地机器上，worker 是控制器在远程端启动的 `python -m mindor.core.component.runtime.process.remote`,shell 命令在该主机的 worker 本地 shell 中执行。

使用此示例以无依赖的工作负载对 `process + remote` 运行时进行端到端验证。一旦跑通，就可以把 `shell` 换成任何其他使用 `runtime: process` 的组件 —— 远程接线方式完全相同。

## 前置要求

远程主机需要:

- 基于密钥认证的 SSH 访问。
- 一个能够 `import mindor` 的 Python 解释器。最简单的方式是安装本项目(`pip install -e .` 或发布后的 `pip install model-compose`),安装到登录 shell 的 `python` 能看到的系统或用户 site-packages 中。
- 远程用户 `$PATH` 中可访问的 `python` 可执行文件。

无守护进程、无容器、无卷挂载 —— 仅需 SSH 和 Python。

## 设置

将 `.env.sample` 复制为 `.env` 并填入你的 SSH 细节:

```bash
cp .env.sample .env
```

```bash
REMOTE_HOST=gpu-box.example.com
REMOTE_USER=hanyeol
REMOTE_SSH_KEY=~/.ssh/id_ed25519
REMOTE_WORKING_DIR=/home/hanyeol/Projects/model-compose
```

`REMOTE_WORKING_DIR` 是 worker 启动 Python 前 `cd` 进入的目录。将其指向远程的 mindor 检出/安装位置，这样 `import mindor` 才能正确解析。

密钥必须未加密或可通过本地 SSH agent 访问;尚未支持 agent 回退和加密密钥。

## 试跑

```bash
model-compose up
model-compose run --input '{}'
```

预期输出:

```
hello from <remote-hostname>: Linux <remote-hostname> 6.x.x-generic ... x86_64 GNU/Linux
```

`hostname` 和 `uname -a` 在**远程主机上**求值,因此与本地机器的输出不匹配就确认 worker 确实在那里运行。

`model-compose up` 做的事:

1. 以 `REMOTE_USER` 的身份打开到 `REMOTE_HOST` 的 SSH 连接。
2. 在远程端启动 `python -m mindor.core.component.runtime.process.remote`,exec 通道的 stdin/stdout 承载 IPC 流(带帧的消息),stderr 承载日志输出。
3. 将组件 config 作为 IPC START 消息发送。远程 worker 在同一进程内启动 `shell` 组件。

然后当你执行 `model-compose run`:

- 输入通过 SSH exec 通道转发,shell 命令在远程主机运行,stdout 被返回。

`model-compose down` 关闭 SSH 连接;远程 worker 进程随之退出。

## 为什么选用这个示例

`shell` 没有模型权重、没有 GPU、没有 pip 安装 —— 它把远程进程管道逻辑与其他所有元素隔离开。如果这一轮往返能跑通,就说明 SSH 传输、exec 通道、worker 握手全部健康;更重的 `process + remote` 工作负载中出现的失败是工作负载本身的问题,而不是运行时的问题。
