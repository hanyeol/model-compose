# Docker Runtime (커스텀 이미지)

기성 Docker 이미지(`nginx:alpine`)를 `http-server` 컴포넌트 뒤의 컨테이너로 실행합니다. `image:`를 설정하면 이는 **CUSTOM 이미지**로 표시되며 — model-compose는 빌드도, 파생 이미지 레이어링도, IPC 핸드셰이크도 수행하지 않습니다 (컴포넌트는 컨테이너 내부에서 일반 HTTP로 통신합니다).

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

## 실행 방법

```bash
model-compose up
model-compose run --input '{"path": "index.html"}'
# -> {"body": "<h1>Hello from nginx</h1>\n"}

model-compose run --input '{"path": "data.json"}'
# -> {"body": "{\"message\": \"hi from JSON\"}\n"}
```

## 언제 사용하나

- 컴포넌트가 실제로는 감싸고 있는 일반 HTTP 서비스인 경우 (nginx, vLLM, llama-server, gradio 등).
- 큐레이션된 이미지를 가지고 있으며 mindor의 이미지 레이어링을 완전히 건너뛰고 싶을 때.

## `docker-shell` / `docker-model`과 다른 점

- `mindor/component-*` 이미지가 절대 빌드되지 않습니다.
- docker attach를 통한 IPC가 없음 — 컨트롤러는 `port:` 필드를 통해 일반 HTTP로 컴포넌트에 접근합니다.
- 여기서는 `container_name:`과 `ports:`가 중요한 손잡이(knob)이며, 나머지는 모두 `docker create`로 전달됩니다.
