from __future__ import annotations

import subprocess
import sys

def install_browser(browser: str) -> None:
    """Install a Playwright browser binary via `python -m playwright install`.

    Idempotent: Playwright's CLI checks the local cache and skips the
    download when the requested browser is already present (~0.3s on a
    warm cache). Safe to call from a component's `_setup` on every
    `model-compose up`.

    Raises `subprocess.CalledProcessError` on failure; captures stdout
    and stderr so the Playwright CLI output doesn't leak into the
    service log on the happy path.
    """
    subprocess.run(
        [ sys.executable, "-m", "playwright", "install", browser ],
        check=True,
        capture_output=True,
    )
