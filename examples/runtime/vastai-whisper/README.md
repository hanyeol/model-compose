# Vast.ai Runtime (Whisper transcription)

Runs the Whisper `large-v3-turbo` speech-to-text model on a remote
[Vast.ai](https://vast.ai/) GPU instance. Pick a short audio file, drop it in,
get the transcription back.

Use this example to validate the `vastai` runtime end-to-end before moving on
to larger models — Whisper weights are only ~1.6 GB and the model loads in
seconds on a single RTX 4090.

## Prerequisites

1. A [Vast.ai](https://vast.ai/) account with billing set up.
2. A **network volume** created in the Vast.ai dashboard. A 20 GB volume is
   plenty for Whisper plus the pip cache. Note the volume ID.
3. Your [Vast.ai API key](https://cloud.vast.ai/account/).

## Setup

Create a `.env` file in this directory (or export the variables in your
shell):

```bash
VASTAI_API_KEY=your-vastai-api-key
VASTAI_VOLUME_ID=your-volume-id
```

## Try it

```bash
model-compose up
model-compose run --input '{"audio": "./sample.wav"}'
```

What `model-compose up` does on first launch:

1. Destroys any orphan instance labeled `mindor-whisper` from a previous
   session.
2. Searches the Vast.ai marketplace for the cheapest RTX 4090 offer on a
   verified host and rents it. Expect ~30–90 s to reach `running`.
3. The instance installs model-compose into the volume's pip cache and
   starts a WebSocket worker on the Vast-mapped host port.
4. model-compose connects over `ws://<public_ip>:<mapped_port>` with a
   per-session bearer token. The component is now ready.

When you then `model-compose run`:

- The audio is forwarded over the WS connection, Whisper runs on the
  instance's GPU, and the transcription is returned.
- Five minutes after the last request, the instance is stopped
  automatically, pausing GPU billing. The volume (and its cached weights)
  survive. The next run resumes the same instance in seconds.

## Clean up

`model-compose down` destroys the instance. The network volume is never
touched by model-compose; delete it manually from the dashboard when you
no longer need it.

If you want to keep the instance across restarts, run `model-compose stop`
instead of `down` — stop keeps the instance provisioned (just paused), so
the next `start` resumes it in seconds.

## Cost sketch

- RTX 4090 verified host: ~$0.25–0.45 / hour while running
- 20 GB network volume: priced per host (typically a few cents/month)
- A single transcription against this example runs in well under a minute
  of GPU time, so the dominant per-run cost is the ~30–90 s cold start on
  the first request.

## Why Vast.ai for this example

Whisper by itself doesn't *need* a remote GPU — this example exists to
exercise every part of the Vast.ai runtime pipeline (offer search, instance
create, bootstrap, WS attach, idle stop, resume) with a model small enough
that iteration is cheap. Once this works end-to-end, swap `component.model`
and the GPU type to validate larger workloads.
