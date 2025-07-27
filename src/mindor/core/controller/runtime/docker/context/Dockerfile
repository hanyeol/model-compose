FROM python:3.11-slim

WORKDIR /app

RUN apt update && apt install -y gcc

RUN pip install --no-cache-dir \
    click \
    pyyaml \
    pydantic \
    python-dotenv \
    aiohttp \
    requests \
    fastapi \
    uvicorn \
    'mcp>=1.10.1' \
    pyngrok \
    ulid \
    gradio \
    Pillow \
    'transformers>=4.21.0' \
    torch \
    sentencepiece \
    accelerate \
    docker

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY ./src /app/
COPY ./model-compose.yml /app/

CMD [ "python", "-m", "mindor.cli.compose", "up" ]
