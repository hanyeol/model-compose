"""model-compose implementation of STT -> splitter -> embedding.

Drives an in-process ComposeManager. Reads the audio path from argv and
hands it to the workflow via `${env.BENCH_AUDIO_DIR}`. Drains the
workflow's output stream (embed vectors) to emit `pipeline.first_output`
and `pipeline.done`.

model-compose is a YAML-first orchestrator: stages, models, and their
lifecycle are defined in `model-compose.yml`. This driver only handles
what other framework driver files also handle — process args, kick off
the pipeline, and emit the two required timing events.
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


def emit(stage: str, event: str, **detail) -> None:
    payload = {"t": time.time(), "stage": stage, "event": event}
    if detail:
        payload["detail"] = detail
    print(json.dumps(payload), flush=True)


# ---------------- framework-specific code below ---------------------------

async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, type=Path,
                    help="path to 16 kHz mono WAV to feed the pipeline")
    args = ap.parse_args()

    audio_path = args.input.resolve()

    config = load_compose_config(str(CONFIG_PATH.parent), [CONFIG_PATH], env={
        "BENCH_AUDIO_DIR": str(audio_path.parent),
        "BENCH_AUDIO_FILE": audio_path.name,
    })

    # daemon=True forces component preload; run launch_services as a
    # background task and poll for `started` to skip its final wait.
    manager = ComposeManager(config, daemon=True)
    launch = asyncio.create_task(manager.launch_services(detach=False, verbose=False))

    while not manager.controller.started:
        await asyncio.sleep(0.05)

    emit("runtime", "ready")
    await asyncio.sleep(1)  # let the runner snapshot Ready RSS

    try:
        state = await manager.run_workflow(
            "__default__",
            {"audio_path": audio_path.name},
            output_path=None,
            verbose=False,
        )
        if state.error:
            emit("runtime", "error", detail=str(state.error))
            return

        first = True
        count = 0
        async for _ in state.output:
            count += 1
            if first:
                emit("pipeline", "first_output")
                first = False
        emit("pipeline", "done", count=count)
    finally:
        await manager.terminate_services(verbose=False)
        launch.cancel()
        try:
            await launch
        except (asyncio.CancelledError, Exception):
            pass


if __name__ == "__main__":
    asyncio.run(main())
