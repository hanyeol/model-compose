# RunPod Runtime (Whisper transcription)

Runs the Whisper `large-v3-turbo` speech-to-text model on a remote
[RunPod](https://www.runpod.io/) GPU pod. Pick a short audio file, drop it in,
get the transcription back.

Use this example to validate the `runpod` runtime end-to-end before moving on
to larger models — Whisper weights are only ~1.6 GB and the model loads in
seconds on a single RTX 4090.

## Prerequisites

1. A [RunPod](https://www.runpod.io/) account with billing set up.
2. A **network volume** created in the RunPod dashboard, in a data center
   that has RTX 4090 availability. A 20 GB volume (~$1.4/month) is plenty
   for Whisper plus the pip cache. Note the volume ID.
3. Your [RunPod API key](https://www.runpod.io/console/user/settings).

## Setup

Create a `.env` file in this directory (or export the variables in your
shell):

```bash
RUNPOD_API_KEY=your-runpod-api-key
RUNPOD_VOLUME_ID=your-volume-id
```

## Try it

```bash
model-compose up
model-compose run --input '{"audio": "./sample.wav"}'
```

What `model-compose up` does on first launch:

1. Terminates any orphan pod named `mindor-whisper` from a previous
   session.
2. Creates a new RTX 4090 pod in the data center that holds your network
   volume. Expect ~30–90 s to reach `RUNNING` on the Community cloud.
3. The pod installs model-compose from GitHub into the volume's pip cache
   and starts a WebSocket worker.
4. model-compose connects over `wss://<pod_id>-8000.proxy.runpod.net` with
   a per-session bearer token. The component is now ready.

When you then `model-compose run`:

- The audio is forwarded over the WS proxy, Whisper runs on the pod's GPU,
  and the transcription is returned.
- Five minutes after the last request, the pod is stopped automatically,
  pausing GPU billing. The volume (and its cached weights) survive. The
  next run resumes the same pod in seconds.

## Clean up

`model-compose down` terminates the pod. The network volume is never touched
by model-compose; delete it manually from the dashboard when you no longer
need it.

If you want to keep the pod across restarts, run `model-compose stop`
instead of `down` — stop keeps the pod provisioned (just paused), so the
next `start` resumes it in seconds.

## Cost sketch

- RTX 4090 Community: ~$0.34–0.44 / hour while running
- 20 GB network volume: ~$1.4 / month
- A single transcription against this example runs in well under a minute
  of GPU time, so the dominant per-run cost is the ~30–90 s cold start on
  the first request.

## Why RunPod for this example

Whisper by itself doesn't *need* a remote GPU — this example exists to
exercise every part of the RunPod runtime pipeline (pod create, bootstrap,
WS attach, idle stop, resume) with a model small enough that iteration is
cheap. Once this works end-to-end, swap `component.model` and the GPU type
to validate larger workloads.
