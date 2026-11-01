# Remote VirtualEnv Runtime (远程 venv 内的 shell)

在通过 SSH 访问的**远程主机上的 venv 隔离 worker** 中运行 `shell` 组件。控制器仍留在本地机器上,venv 在远程文件系统上 SSH 用户的 ``working_dir`` 下创建,worker 是在该 venv 内启动的 `python -m mindor.core.component.runtime.virtualenv.remote`。

使用此示例对 `virtualenv + remote` 运行时进行端到端验证。venv provisioning 是惰性的 —— 首次 `up` 会创建它并安装 `mindor` + 其运行时要求;后续运行在数秒内复用同一个 venv。

## 前置要求

远程主机需要:

- 基于密钥认证的 SSH 访问。
- 一个能够在用户 interactive shell 下 `import mindor` 的 Python 解释器 (pyenv、系统 python、或在 `.bashrc` 中 activate 的 venv 均可)。运行时通过 `sys.executable` 解析它。
- 可用的 `python -m venv` (标准库 —— 无需额外安装)。
- 可选: `$PATH` 上的 `uv` 会显著加快 requirement 安装速度,并支持 venv 间的 wheel 缓存共享。未找到 `uv` 时,运行时回退到 venv 的 `pip`。

远程的 mindor 通过 venv 的 site-packages 中的 `mindor.pth` 文件连接 (editable-install 方式),因此设置期间主机与远程之间没有字节传输。

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

`REMOTE_WORKING_DIR` 同时扮演两个角色:
- SSH 会话在解析 python / mindor 之前 `cd` 进入的目录。
- venv 路径的锚点 (`{working_dir}/.runtime/components/<id>/venv`)。

将其指向远程的 mindor 检出/安装位置,这样 `import mindor` 才能正确解析。

## 试跑

```bash
model-compose up
model-compose run --input '{}'
```

预期输出:

```
hello from <remote-hostname>: Linux <remote-hostname> ... x86_64 GNU/Linux via /home/.../.runtime/components/__component__/venv/bin/python
```

`hostname`、`uname -a`、`sys.executable` 全部在**远程主机上**求值,且 python 路径报告的是 **venv 的**解释器 —— 这就确认了 shell 命令在 venv 内运行。

首次启动时 `model-compose up` 做的事:

1. 以 `REMOTE_USER` 的身份打开到 `REMOTE_HOST` 的 SSH 连接。
2. 解析远程用户的 python (interactive-shell 的 `sys.executable`) 以及 `import mindor` 所在的目录。
3. 通过 `<remote-python> -m venv ...` 创建 `{REMOTE_WORKING_DIR}/.runtime/components/__component__/venv` (已存在则 skip)。
4. 在 venv 的 site-packages 内写入指向远程 mindor 源的 `mindor.pth`。
5. 为 mindor 运行时要求运行 `uv pip install` (或 venv pip)。第二次启动完全 skip 第 3–5 步。
6. 从 venv 通过 exec 通道启动 `python -m mindor.core.component.runtime.virtualenv.remote`。stdio 承载 IPC 流。

然后当你执行 `model-compose run`:

- 输入通过 SSH exec 通道转发,shell 命令在远程主机的 venv 内运行,stdout 被返回。

`model-compose down` 关闭 SSH 连接,worker 随之退出。磁盘上的 venv 保留以供下一次 `up` 使用。

## 为什么选用这个示例

`shell` 没有模型权重、没有 GPU、没有项目特定的要求 —— 它把远程 venv 管道逻辑与其他所有元素隔离开。如果这一轮往返能跑通,就说明 SSH 传输、venv provisioning、mindor 源连接、worker 握手全部健康;更重的 `virtualenv + remote` 工作负载中出现的失败是工作负载本身的问题,而不是运行时的问题。
