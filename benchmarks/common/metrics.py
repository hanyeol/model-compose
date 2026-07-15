"""Compute the benchmark's core metrics from a stream of JSONL events.

Every implementation emits JSONL to stdout. The two events we care about:

    {"t": <float>, "stage": "runtime",  "event": "ready"}
    {"t": <float>, "stage": "pipeline", "event": "first_output", ...}
    {"t": <float>, "stage": "pipeline", "event": "done",         ...}

`runtime.ready` marks the moment cold-load ends and timing starts.
`pipeline.first_output` is the time-to-first-output at the tail of the
pipeline — this is what captures whether the framework actually
pipelines across stages. `pipeline.done` is E2E.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SystemSample:
    t: float
    rss_bytes: int
    cpu_percent: float
    num_threads: int


@dataclass
class MetricsCollector:
    input_start_t: Optional[float] = None
    input_end_t: Optional[float] = None
    first_output_t: Optional[float] = None
    done_t: Optional[float] = None
    ready_sample: Optional[SystemSample] = None
    backlog_max: dict[str, int] = field(default_factory=dict)
    samples: list[SystemSample] = field(default_factory=list)

    def note_input_start(self) -> None:
        if self.input_start_t is None:
            self.input_start_t = time.time()

    def note_input_end(self) -> None:
        if self.input_end_t is None:
            self.input_end_t = time.time()

    def note_ready(self, sample: SystemSample) -> None:
        """Snapshot system state at the moment `runtime.ready` arrived."""
        if self.ready_sample is None:
            self.ready_sample = sample

    def ingest(self, line: str) -> None:
        line = line.strip()
        if not line:
            return
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            return

        stage = ev.get("stage")
        event = ev.get("event")
        t = float(ev.get("t", time.time()))

        if stage == "pipeline" and event == "first_output" and self.first_output_t is None:
            self.first_output_t = t
        if stage == "pipeline" and event == "done":
            self.done_t = t

        if event == "backlog" and stage:
            depth = int(ev.get("depth", 0))
            if depth > self.backlog_max.get(stage, 0):
                self.backlog_max[stage] = depth

    def add_sample(self, rss_bytes: int, cpu_percent: float,
                   num_threads: int) -> None:
        self.samples.append(SystemSample(
            t=time.time(),
            rss_bytes=rss_bytes,
            cpu_percent=cpu_percent,
            num_threads=num_threads,
        ))

    def is_valid(self) -> tuple[bool, list[str]]:
        errs: list[str] = []
        if self.input_start_t is None:
            errs.append("no input_start recorded (runtime.ready never seen?)")
        if self.first_output_t is None:
            errs.append("missing pipeline.first_output")
        if self.done_t is None:
            errs.append("missing pipeline.done")
        return (not errs, errs)

    def _percentile(self, values: list[float], p: float) -> float:
        if not values:
            return 0.0
        s = sorted(values)
        k = (len(s) - 1) * p
        f = int(k)
        c = min(f + 1, len(s) - 1)
        return s[f] + (s[c] - s[f]) * (k - f)

    def summary(self) -> dict:
        assert self.input_start_t is not None
        assert self.first_output_t is not None
        assert self.done_t is not None

        ttfo = round(self.first_output_t - self.input_start_t, 4)
        e2e = round(self.done_t - self.input_start_t, 4)

        rss_series = [s.rss_bytes for s in self.samples]
        cpu_series = [s.cpu_percent for s in self.samples]
        thread_series = [s.num_threads for s in self.samples]

        rss = {
            "ready_mb": round(self.ready_sample.rss_bytes / 1024 / 1024, 1) if self.ready_sample else 0.0,
            "peak_bytes": max(rss_series, default=0),
            "peak_mb": round(max(rss_series, default=0) / 1024 / 1024, 1),
            "mean_mb": round(sum(rss_series) / len(rss_series) / 1024 / 1024, 1) if rss_series else 0.0,
            "p95_mb": round(self._percentile(rss_series, 0.95) / 1024 / 1024, 1),
            "final_mb": round(rss_series[-1] / 1024 / 1024, 1) if rss_series else 0.0,
        }
        cpu = {
            "peak_percent": round(max(cpu_series, default=0.0), 1),
            "mean_percent": round(sum(cpu_series) / len(cpu_series), 1) if cpu_series else 0.0,
            "p95_percent": round(self._percentile(cpu_series, 0.95), 1),
        }
        threads = {
            "peak": max(thread_series, default=0),
            "final": thread_series[-1] if thread_series else 0,
        }

        return {
            "ttfo_seconds": ttfo,
            "e2e_seconds": e2e,
            "rss": rss,
            "cpu": cpu,
            "threads": threads,
            "backlog_max": dict(self.backlog_max),
            "sample_count": len(self.samples),
        }
