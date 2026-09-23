from __future__ import annotations

from typing import Dict, List, Any, Tuple
from .files import get_temporary_path
import shutil

# yt-dlp names for the JS runtimes it will drive for YouTube's EJS solver.
# quickjs is omitted from auto-detection because it is rarely installed
# standalone; users who want it should list it explicitly.
_JS_RUNTIME_CANDIDATES: Tuple[str, ...] = ("deno", "node", "bun")

def detect_js_runtimes() -> Dict[str, str]:
    """Probe PATH for known JS runtimes and return a {name: path} mapping.

    YouTube's EJS solver needs a JS runtime; when the caller hasn't configured
    one, auto-detecting keeps yt-dlp off the deprecated fallback path (and the
    accompanying warning).
    """
    runtimes: Dict[str, str] = {}

    for name in _JS_RUNTIME_CANDIDATES:
        path = shutil.which(name)

        if path:
            runtimes[name] = path

    return runtimes

def create_cookies_file(cookies: List[Dict[str, Any]]) -> str:
    path = get_temporary_path("txt")

    # Python's http.cookiejar refuses to load the file without this magic
    # header line, and yt-dlp defers to that loader.
    lines = [ "# Netscape HTTP Cookie File" ]

    for cookie in cookies:
        name  = cookie.get("name")
        value = cookie.get("value")

        if name is None or value is None:
            continue

        domain = str(cookie.get("domain") or "")

        # Netscape's include-subdomains flag is inferred from a leading dot
        # on the domain — CDP/Playwright follow the same convention.
        include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
        cookie_path = str(cookie.get("path") or "/")
        secure = "TRUE" if cookie.get("secure") else "FALSE"

        # CDP reports session cookies with expires=-1 and Playwright with
        # expires=-1 or expires=0; the Netscape format only accepts a
        # non-negative unix timestamp (0 means session cookie). Coerce
        # any negative or unparseable value to 0.
        try:
            expiry = int(float(cookie.get("expires", 0)))
        except (TypeError, ValueError):
            expiry = 0
        expiry_field = str(max(expiry, 0))

        # httpOnly cookies use the `#HttpOnly_` prefix on the domain per
        # curl/wget convention, which yt-dlp's loader recognizes.
        if cookie.get("httpOnly"):
            domain = f"#HttpOnly_{domain}"

        lines.append("\t".join([ domain, include_subdomains, cookie_path, secure, expiry_field, str(name), str(value) ]))

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return path
