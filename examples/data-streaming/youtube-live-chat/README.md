# YouTube Live Chat — AI-Discovered Selectors

This example demonstrates a three-stage workflow:

1. **Snapshot** — `web-scraper` opens the YouTube live chat popout with JS
   rendering and returns the HTML fragment of the chat container only.
2. **Detect** — `http-client` sends that HTML to GPT-4o, which returns a
   JSON object naming the CSS selectors for each message, its id, the
   author, and the message body.
3. **Scrape** — a second `web-scraper` invocation plugs those selectors
   into a selector dict and pulls structured messages on a poll loop,
   deduped by a Redis-backed watermark.

The discovery step runs once per stream and is cached in Redis for 6
hours, so the recurring GPT cost is bounded.

## When to use this pattern

The point isn't really YouTube — for YouTube specifically you can hardcode
`yt-live-chat-text-message-renderer` + `#author-name` + `#message` and skip
the AI entirely. The interesting case is **a site whose markup you don't
know in advance, or whose class names rotate**. The same three-stage shape
applies: render → ask a model for selectors → scrape with them.

## Caveats

- Live chat HTML is heavily web-component-based; GPT may return
  tag-name selectors (e.g. `yt-live-chat-text-message-renderer`) rather
  than class-based ones. That's correct and expected.
- The initial `wait_for: yt-live-chat-text-message-renderer` in the
  snapshot component assumes at least one message has rendered. For a
  stream that just started with zero messages, you may need to wait
  longer or fall back to scraping the empty container.
- The polling workflow re-navigates the page every tick (this is how
  `web-scraper` works — it spawns a fresh Chromium context per call).
  For long-running observation you'll want the `web-browser` component
  with a persistent `session_id`, or a future `watch` mode on
  `web-scraper`. See the conversation that produced this example.

## Run

Prerequisites:
- Redis listening on `localhost:6379`
- `OPENAI_API_KEY` exported
- `SINK_URL` exported (the endpoint that will receive each batch of new
  messages; defaults to `http://localhost:9999` if unset so the config
  parses, but you'll want a real ingest endpoint to actually consume the
  stream)

```bash
export OPENAI_API_KEY=sk-...
export SINK_URL=http://localhost:9000          # your ingest endpoint

model-compose up

# Kick off for a specific live video
model-compose run __workflow__ \
  --input '{"video_id":"jfKfPfyJRdk","poll_interval":"3s"}'
```
