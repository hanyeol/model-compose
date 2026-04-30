FROM nvcr.io/nvidia/pytorch:24.07-py3

WORKDIR /app

RUN apt-get update && apt-get install -y ffmpeg git && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/microsoft/VibeVoice.git /app/vibevoice
WORKDIR /app/vibevoice
RUN pip install -e ".[streamingtts]"
RUN pip uninstall -y flash-attn || true

EXPOSE 3000

CMD ["python", "demo/vibevoice_realtime_demo.py", "--model_path", "microsoft/VibeVoice-Realtime-0.5B", "--port", "3000", "--device", "cuda"]
