"""model-compose implementation of LLM -> sentence-splitter -> TTS.

Drives an in-process ComposeManager. Reads the prompt path from argv
and passes the prompt text into the workflow. Drains the workflow's
output stream (Kokoro PCM audio) to emit `pipeline.first_output` and
`pipeline.done`.

model-compose is a YAML-first orchestrator: stages, models, and their
lifecycle are defined in `model-compose.yml`. This driver only handles
what other framework driver files also handle — process args, kick off
the pipeline, and emit the required timing events.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from mindor.core.compose.manager import ComposeManager
from mindor.dsl.loader import load_compose_config


CONFIG_PATH = Path(__file__).parent / "model-compose.yml"

# Kokoro output: 24 kHz mono int16 PCM (see model-compose Kokoro service).
TTS_SAMPLE_RATE = 24000
TTS_CHANNELS = 1
TTS_BYTES_PER_SAMPLE = 2


def emit(stage: str, event: str, **detail) -> None:
    payload = {"t": time.time(), "stage": stage, "event": event}
    if detail:
        payload["detail"] = detail
    print(json.dumps(payload), flush=True)


# ---------------- framework-specific code below ---------------------------

async def _drain_audio(item) -> int:
    """Drain a single workflow output (one Kokoro segment) and return PCM byte count.

    The output is a PcmStreamResource; iterating its bytes lets us
    measure real audio length without keeping samples in memory.
    """
    total = 0
    async for chunk in item:
        total += len(chunk)
    return total


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, type=Path,
                    help="path to a text file containing the LLM prompt")
    args = ap.parse_args()

    prompt = args.input.read_text(encoding="utf-8").strip()

    config = load_compose_config(str(CONFIG_PATH.parent), [CONFIG_PATH], env={})

    manager = ComposeManager(config, daemon=True)
    launch = asyncio.create_task(manager.launch_services(detach=False, verbose=False))

    while not manager.controller.started:
        await asyncio.sleep(0.05)

    emit("runtime", "ready")
    await asyncio.sleep(1)  # let the runner snapshot Ready RSS

    try:
        state = await manager.run_workflow(
            "__default__",
            {"prompt": prompt},
            output_path=None,
            verbose=False,
        )
        if state.error:
            emit("runtime", "error", detail=str(state.error))
            return

        first = True
        count = 0
        total_bytes = 0
        async for item in state.output:
            count += 1
            if first:
                emit("pipeline", "first_output", sample_rate=TTS_SAMPLE_RATE)
                first = False
            total_bytes += await _drain_audio(item)

        audio_seconds = total_bytes / (TTS_SAMPLE_RATE * TTS_CHANNELS * TTS_BYTES_PER_SAMPLE)
        emit("pipeline", "done", count=count, audio_seconds=round(audio_seconds, 3))
    finally:
        await manager.terminate_services(verbose=False)
        launch.cancel()
        try:
            await launch
        except (asyncio.CancelledError, Exception):
            pass


if __name__ == "__main__":
    asyncio.run(main())
