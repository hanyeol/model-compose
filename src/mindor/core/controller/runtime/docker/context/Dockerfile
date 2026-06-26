FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip

COPY runtime-requirements.txt /tmp/runtime-requirements.txt
RUN pip install --no-cache-dir -r /tmp/runtime-requirements.txt \
    && rm /tmp/runtime-requirements.txt

COPY src/mindor /usr/local/lib/python3.11/site-packages/mindor

WORKDIR /workspace

CMD [ "python", "-m", "mindor.cli.compose", "up" ]
