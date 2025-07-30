FROM ubuntu:22.04

WORKDIR /app

RUN apt update && apt install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    gcc \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3.11 /usr/bin/python && \
    ln -sf /usr/bin/python3.11 /usr/bin/python3

RUN python -m pip install --upgrade pip
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

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src .
COPY webui ./webui
COPY model-compose.yml .

CMD [ "python", "-m", "mindor.cli.compose", "up" ]
