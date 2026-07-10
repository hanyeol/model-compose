# Component services are loaded on demand by create_component() using the
# convention: ComponentType value ↔ module path
# (e.g. "web-browser" ↔ services/web_browser, "shell" ↔ services/shell).
# Do not eagerly import services here — it forces every component's
# dependencies (playwright, ffmpeg wrappers, transformers, ...) to load even
# when the compose file never mentions them.
