"""Drive an implementation subprocess and measure it against scenario.md.

    python -m benchmarks.common.runner \\
        --impl benchmarks/audio-streaming-pipeline/langgraph \\
        --input benchmarks/audio-streaming-pipeline/data/sample.wav

The runner:
  1. Reads the WAV in 100 ms chunks.
  2. Spawns the implementation (`python pipeline.py`).
  3. Waits for `runtime.ready` on stdout (all models loaded).
  4. Pipes chunks to its stdin at real-time pace; TTFR/E2E are measured
     from this point, so cold-load time is excluded.
  5. Reads JSONL events from its stdout, feeds them to MetricsCollector.
  6. Samples RSS/CPU/threads every 100 ms via psutil.
  7. On process exit, validates and prints a summary.

Implementations only need to: preload all models, emit `runtime.ready`,
then read length-prefixed audio frames from stdin and emit the required
per-stage events.
"""
from __future__ import annotations

import argparse
import json
import struct
import subprocess
import sys
import threading
import time
import wave
from pathlib import Path

import psutil

from benchmarks.common.metrics import MetricsCollector, SystemSample

CHUNK_MS = 100
SAMPLE_RATE = 16000
BYTES_PER_SAMPLE = 2  # int16 mono
CHUNK_BYTES = int(SAMPLE_RATE * CHUNK_MS / 1000) * BYTES_PER_SAMPLE  # 3200


def read_chunks(wav_path: Path):
    with wave.open(str(wav_path), "rb") as w:
        assert w.getframerate() == SAMPLE_RATE, "input must be 16kHz"
        assert w.getnchannels() == 1, "input must be mono"
        assert w.getsampwidth() == BYTES_PER_SAMPLE, "input must be int16"
        while True:
            frames = w.readframes(SAMPLE_RATE * CHUNK_MS // 1000)
            if not frames:
                return
            yield frames


READY_TIMEOUT_SECONDS = 300


def pump_input(proc: subprocess.Popen, wav: Path, collector: MetricsCollector,
               slow_consumer_ms: int, ready: threading.Event) -> None:
    """Push audio chunks at real-time pace. Length-prefix each chunk.

    Blocks until `ready` is set so we don't start the clock while the
    implementation is still loading models.
    """
    try:
        if not ready.wait(timeout=READY_TIMEOUT_SECONDS):
            print("[runner] timed out waiting for runtime.ready",
                  file=sys.stderr)
            return
        collector.note_input_start()
        next_send = time.time()
        aborted = False
        for chunk in read_chunks(wav):
            now = time.time()
            if now < next_send:
                time.sleep(next_send - now)
            header = struct.pack(">I", len(chunk))
            try:
                proc.stdin.write(header + chunk)
                proc.stdin.flush()
            except (BrokenPipeError, ValueError):
                # Implementations that never open stdin (e.g. model-compose,
                # which reads the file directly) close the pipe. That's
                # expected; stop pumping but still mark the input as ended
                # so metrics have a boundary.
                aborted = True
                break
            next_send += CHUNK_MS / 1000
        if not aborted:
            try:
                proc.stdin.write(struct.pack(">I", 0))
                proc.stdin.flush()
                proc.stdin.close()
            except (BrokenPipeError, ValueError):
                pass
        collector.note_input_end()
    except Exception as e:
        print(f"[runner] input pump error: {e}", file=sys.stderr)


def snapshot_system(proc: subprocess.Popen) -> SystemSample:
    """Force an immediate RSS/CPU/thread sample of proc + children.

    Used at instant events like `runtime.ready`. Doesn't rely on the
    periodic sampler (which may be up to 100 ms stale).
    """
    p = psutil.Process(proc.pid)
    with p.oneshot():
        rss = p.memory_info().rss
        cpu = p.cpu_percent(None)
        threads = p.num_threads()
    for child in p.children(recursive=True):
        try:
            with child.oneshot():
                rss += child.memory_info().rss
                cpu += child.cpu_percent(None)
                threads += child.num_threads()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return SystemSample(t=time.time(), rss_bytes=rss,
                        cpu_percent=cpu, num_threads=threads)


def pump_output(proc: subprocess.Popen, collector: MetricsCollector,
                slow_consumer_ms: int, event_log: Path,
                ready: threading.Event) -> None:
    with event_log.open("w") as log:
        for raw in proc.stdout:
            line = raw.decode("utf-8", errors="replace")
            log.write(line)
            collector.ingest(line)
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("stage") == "runtime" and ev.get("event") == "ready":
                try:
                    collector.note_ready(snapshot_system(proc))
                except psutil.NoSuchProcess:
                    pass
                ready.set()
            if slow_consumer_ms and ev.get("stage") == "pipeline":
                # Only throttle pipeline-tail events; other events flow freely.
                time.sleep(slow_consumer_ms / 1000)


def sample_resources(proc: subprocess.Popen, collector: MetricsCollector,
                     stop: threading.Event) -> None:
    """Sample RSS, CPU%, and thread count every 100 ms.

    Rolls up child processes too so multi-process pipelines don't
    under-report. cpu_percent() needs a prior call to prime it — the
    first sample is skipped.
    """
    try:
        p = psutil.Process(proc.pid)
    except psutil.NoSuchProcess:
        return
    p.cpu_percent(None)  # prime

    while not stop.is_set() and proc.poll() is None:
        try:
            with p.oneshot():
                rss = p.memory_info().rss
                cpu = p.cpu_percent(None)
                threads = p.num_threads()
            for child in p.children(recursive=True):
                try:
                    with child.oneshot():
                        rss += child.memory_info().rss
                        cpu += child.cpu_percent(None)
                        threads += child.num_threads()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            collector.add_sample(rss, cpu, threads)
        except psutil.NoSuchProcess:
            return
        time.sleep(0.1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--impl", required=True, type=Path,
                    help="path to implementation dir containing pipeline.py")
    ap.add_argument("--input", required=True, type=Path,
                    help="path to 16kHz mono WAV input")
    ap.add_argument("--slow-consumer-ms", type=int, default=0,
                    help="artificial delay per index-stage event")
    ap.add_argument("--cancel-at-seconds", type=float, default=0,
                    help="send SIGTERM this many seconds after start")
    ap.add_argument("--results-dir", type=Path, default=None)
    args = ap.parse_args()

    impl_dir = args.impl.resolve()
    entry = impl_dir / "pipeline.py"
    if not entry.exists():
        # model-compose implementations use model-compose.yml + CLI.
        yml = impl_dir / "model-compose.yml"
        if yml.exists():
            cmd = ["model-compose", "-f", str(yml), "run", "audio-pipeline",
                   "--stream"]
        else:
            print(f"no pipeline.py or model-compose.yml in {impl_dir}",
                  file=sys.stderr)
            return 2
    else:
        # Every pipeline.py gets the input path via argv. Implementations
        # that consume audio from stdin (LangGraph) just ignore it;
        # implementations that read the file directly (model-compose) use
        # it and never read stdin.
        cmd = [sys.executable, str(entry), "--input", str(args.input.resolve())]

    results_dir = args.results_dir or (impl_dir / "results")
    results_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    event_log = results_dir / f"events-{stamp}.jsonl"
    summary_path = results_dir / f"summary-{stamp}.json"
    system_csv = results_dir / f"system-{stamp}.csv"

    collector = MetricsCollector()
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )

    stop = threading.Event()
    ready = threading.Event()
    threads = [
        threading.Thread(target=pump_input,
                         args=(proc, args.input, collector,
                               args.slow_consumer_ms, ready), daemon=True),
        threading.Thread(target=pump_output,
                         args=(proc, collector, args.slow_consumer_ms,
                               event_log, ready), daemon=True),
        threading.Thread(target=sample_resources,
                         args=(proc, collector, stop), daemon=True),
    ]
    for t in threads:
        t.start()

    cancel_latency: float | None = None
    if args.cancel_at_seconds > 0:
        time.sleep(args.cancel_at_seconds)
        cancel_start = time.time()
        proc.terminate()
        proc.wait(timeout=30)
        cancel_latency = round(time.time() - cancel_start, 4)
    else:
        proc.wait()

    stop.set()
    for t in threads:
        t.join(timeout=2)

    stderr = proc.stderr.read().decode("utf-8", errors="replace")
    if stderr.strip():
        print("[impl stderr]\n" + stderr, file=sys.stderr)

    # Dump the system-usage timeseries as CSV so it's easy to plot and
    # doesn't bloat summary.json. Times are relative to input_start.
    if collector.samples:
        t0 = collector.input_start_t or collector.samples[0].t
        with system_csv.open("w") as f:
            f.write("t_seconds,rss_mb,cpu_percent,num_threads\n")
            for s in collector.samples:
                f.write(f"{s.t - t0:.3f},{s.rss_bytes/1024/1024:.1f},"
                        f"{s.cpu_percent:.1f},{s.num_threads}\n")

    valid, errs = collector.is_valid()
    result: dict = {
        "impl": str(impl_dir.relative_to(Path.cwd())) if impl_dir.is_relative_to(Path.cwd()) else str(impl_dir),
        "input": str(args.input),
        "valid": valid,
        "errors": errs,
        "exit_code": proc.returncode,
        "cancel_latency_seconds": cancel_latency,
        "event_log": str(event_log),
        "system_csv": str(system_csv) if collector.samples else None,
    }
    if valid:
        result.update(collector.summary())

    summary_path.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    sys.exit(main())
