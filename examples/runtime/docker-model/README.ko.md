# Docker Runtime (모델이 포함된 파생 이미지)

[`../docker-shell`](../docker-shell)과 동일한 Docker 백엔드이지만, 이 디렉토리에는 `requirements.txt`가 있어 model-compose가 표준 런타임 이미지 위에 `transformers` + `torch`가 설치된 **파생(DERIVED) 이미지** (`mindor/component-<project>:<version>`)를 빌드합니다.

```yaml
component:
  runtime:
    type: docker
    volumes:
      - ./.hf-cache:/root/.cache/huggingface
```

## 실행 방법

```bash
model-compose up
model-compose run --input '{"text": "the weather is lovely"}'
```

첫 `up`은 느립니다 (이미지 빌드 + 모델 다운로드). 이후 실행은 빠릅니다:
- 이미지는 `mindor.requirements-sha256` 레이블 아래 캐시되고,
- HuggingFace 캐시가 바인드 마운트되어, 컨테이너 재시작 후에도 모델 파일이 유지됩니다.

## 언제 사용하나

- 의존성 + 시스템 격리 그리고 개발 머신 간에 안정된 런타임 환경을 원하는 로컬 모델.
- 호스트에 없는 Linux 시스템 라이브러리가 필요한 컴포넌트.

## 참고

- `requirements.txt`가 변경되면 자동으로 재빌드됩니다.
- 모델 재다운로드를 강제하려면 `.hf-cache/`를 삭제하세요.
