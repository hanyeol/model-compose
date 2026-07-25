"""Drive an implementation subprocess and measure it against scenario.md.

    python benchmarks/llm-tts-streaming/common/benchmark.py \\
        --impl benchmarks/llm-tts-streaming/langgraph \\
        --input benchmarks/llm-tts-streaming/data/prompt.txt

Unlike the stt-embed-streaming harness, this benchmark's input is a
single text prompt, not a stream of audio frames. The harness:

  1. Reads the prompt from `--input` (one text file).
  2. Spawns the implementation (`python pipeline.py --input <path>`);
     the implementation reads the same file to get the prompt text.
  3. Waits for `runtime.ready` on stdout (all models loaded).
  4. Starts the clock the instant `runtime.ready` arrives. No further
     input is pushed — the pipeline drives itself from the prompt.
  5. Reads JSONL events from stdout, feeds them to MetricsCollector.
  6. Samples RSS/CPU/threads every 100 ms via psutil.
  7. On process exit, computes RTF (E2E / audio_seconds) from
     `pipeline.done`'s detail.

Implementations must emit, on top of the required three events, a
`pipeline.done` whose detail includes:
  - `audio_seconds` : float, total playback seconds of generated audio
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from benchmarks.common.metrics import MetricsCollector, SystemSample


READY_TIMEOUT_SECONDS = 300


def snapshot_system(proc: subprocess.Popen) -> SystemSample:
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
                ready: threading.Event,
                done_detail: dict) -> None:
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
                # This runner has no separate input pump: `ready` is when
                # the pipeline starts working, so it's also `input_start`.
                collector.note_input_start()
                collector.note_input_end()
                ready.set()
            if ev.get("stage") == "pipeline" and ev.get("event") == "done":
                detail = ev.get("detail") or {}
                if "audio_seconds" in detail:
                    done_detail["audio_seconds"] = float(detail["audio_seconds"])
            if slow_consumer_ms and ev.get("stage") == "pipeline":
                time.sleep(slow_consumer_ms / 1000)


def sample_resources(proc: subprocess.Popen, collector: MetricsCollector,
                     stop: threading.Event) -> None:
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
                    help="path to a text file containing the LLM prompt")
    ap.add_argument("--slow-consumer-ms", type=int, default=0,
                    help="artificial delay per pipeline-stage event")
    ap.add_argument("--cancel-at-seconds", type=float, default=0,
                    help="send SIGTERM this many seconds after start")
    ap.add_argument("--results-dir", type=Path, default=None)
    args = ap.parse_args()

    impl_dir = args.impl.resolve()
    entry = impl_dir / "pipeline.py"
    if not entry.exists():
        print(f"no pipeline.py in {impl_dir}", file=sys.stderr)
        return 2

    prompt_path = args.input.resolve()
    prompt_text = prompt_path.read_text(encoding="utf-8").strip()

    cmd = [sys.executable, str(entry), "--input", str(prompt_path)]

    results_dir = args.results_dir or (impl_dir / "results")
    results_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    event_log = results_dir / f"events-{stamp}.jsonl"
    summary_path = results_dir / f"summary-{stamp}.json"
    system_csv = results_dir / f"system-{stamp}.csv"

    collector = MetricsCollector()
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )

    stop = threading.Event()
    ready = threading.Event()
    done_detail: dict = {}
    threads = [
        threading.Thread(target=pump_output,
                         args=(proc, collector, args.slow_consumer_ms,
                               event_log, ready, done_detail), daemon=True),
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
        "input": str(prompt_path),
        "prompt_chars": len(prompt_text),
        "valid": valid,
        "errors": errs,
        "exit_code": proc.returncode,
        "cancel_latency_seconds": cancel_latency,
        "event_log": str(event_log),
        "system_csv": str(system_csv) if collector.samples else None,
    }
    if valid:
        summary = collector.summary()
        audio_seconds = done_detail.get("audio_seconds")
        if audio_seconds and audio_seconds > 0:
            summary["audio_seconds"] = round(audio_seconds, 3)
            summary["rtf"] = round(summary["e2e_seconds"] / audio_seconds, 4)
        result.update(summary)

    summary_path.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    sys.exit(main())
