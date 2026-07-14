# Docker Runtime（自定义镜像）

将现成的 Docker 镜像（`nginx:alpine`）作为 `http-server` 组件背后的容器运行。设置 `image:` 会将其标记为 **CUSTOM 镜像**——model-compose 不会执行构建、不会进行派生镜像分层、也不会进行 IPC 握手（组件在容器内直接通过普通 HTTP 通信）。

```yaml
component:
  type: http-server
  runtime:
    type: docker
    image: nginx:alpine
    ports:
      - "8090:80"
    volumes:
      - ./html:/usr/share/nginx/html:ro
```

## 试用

```bash
model-compose up
model-compose run --input '{"path": "index.html"}'
# -> {"body": "<h1>Hello from nginx</h1>\n"}

model-compose run --input '{"path": "data.json"}'
# -> {"body": "{\"message\": \"hi from JSON\"}\n"}
```

## 何时使用

- 组件实际上是你正在包装的普通 HTTP 服务（nginx、vLLM、llama-server、gradio 等）。
- 你已经拥有精心打磨好的镜像，并希望完全跳过 mindor 的镜像分层。

## 与 `docker-shell` / `docker-model` 的区别

- 不会构建任何 `mindor/component-*` 镜像。
- 没有通过 docker attach 的 IPC——控制器通过 `port:` 字段以常规 HTTP 访问组件。
- 这里的关键旋钮是 `container_name:` 和 `ports:`；其他所有内容都会透传给 `docker create`。
