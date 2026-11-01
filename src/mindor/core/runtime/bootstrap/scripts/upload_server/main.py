#!/usr/bin/env python3
"""Pod/remote-side single-shot HTTP upload receiver for the host mindor
source. The host POSTs a gzipped tar via `RuntimeManager._upload_mindor_source`
and this script receives it on the target.

Materialized by whichever transport the subclass uses (heredoc in a shell
command, scp over SSH, etc.) and run with::

    python3 main.py --port <p> --upload-path <d>

Depends only on the Python stdlib so the target doesn't need mindor on
PATH yet. Reads ``MINDOR_WORKER_AUTH_TOKEN`` and ``MINDOR_SRC_VERSION``
from env.

Exit codes:
  0  — new source extracted (caller should pip-install bootstrap deps)
  10 — cached version already matched (caller can skip reinstall)
  non-zero other — caller should abort.
"""

import argparse, gzip, hmac, io, os, pathlib, shutil, sys, tarfile, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

def _build_handler(
    auth_token: str,
    cached_version: str,
    upload_path: pathlib.Path,
    result: dict,
    done: threading.Event
):
    version_file = upload_path / ".version"

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            header = self.headers.get("Authorization", "")

            if not header.lower().startswith("bearer ") or not hmac.compare_digest(
                header[len("bearer "):].strip(), auth_token
            ):
                self._discard_body()
                self.send_response(401)
                self.end_headers()

                result["code"] = 2
                done.set()

                return

            host_version = self.headers.get("X-Mindor-Version", "")
            content_length = int(self.headers.get("Content-Length", "0"))

            if host_version and host_version == cached_version:
                # Already up to date — discard the body so the client's
                # send completes cleanly, then signal cache hit.
                self._discard_body(content_length)
                self.send_response(304)
                self.end_headers()

                result["code"] = 10
                done.set()

                return

            body = self.rfile.read(content_length)

            try:
                with gzip.GzipFile(fileobj=io.BytesIO(body)) as gz:
                    with tarfile.open(fileobj=gz, mode="r") as tar:
                        mindor_dir = upload_path / "mindor"

                        if mindor_dir.exists():
                            shutil.rmtree(mindor_dir)

                        tar.extractall(path=str(upload_path))

                # Drop the previous version marker — the caller writes a fresh
                # one only after pip install completes successfully, so a crash
                # between extract and install cannot be mistaken for a cache
                # hit on the next launch.
                if version_file.exists():
                    version_file.unlink()
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(str(e).encode("utf-8"))

                result["code"] = 3
                done.set()

                return

            self.send_response(200)
            self.end_headers()

            result["code"] = 0
            done.set()

        def _discard_body(self, length=None):
            if length is None:
                length = int(self.headers.get("Content-Length", "0"))

            while length > 0:
                chunk = self.rfile.read(min(length, 65536))

                if not chunk:
                    break

                length -= len(chunk)

        def log_message(self, format, *args):
            sys.stderr.write("upload: " + (format % args) + "\n")

    return Handler

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--upload-path", required=True)
    args = parser.parse_args()

    auth_token = os.environ.get("MINDOR_WORKER_AUTH_TOKEN", "")

    if not auth_token:
        sys.stderr.write("upload: MINDOR_WORKER_AUTH_TOKEN env is required\n")
        return 2

    upload_path = pathlib.Path(args.upload_path)
    upload_path.mkdir(parents=True, exist_ok=True)
    version_file = upload_path / ".version"
    cached_version = version_file.read_text().strip() if version_file.exists() else ""

    # Shared mutable state so the handler can hand its outcome back to the
    # main thread (which decides the process exit code).
    result: dict = {"code": None}
    done = threading.Event()

    handler = _build_handler(auth_token, cached_version, upload_path, result, done)
    server = HTTPServer(("0.0.0.0", args.port), handler)

    threading.Thread(target=server.serve_forever, daemon=True).start()
    done.wait()
    server.shutdown()

    return result["code"] if result["code"] is not None else 4

if __name__ == "__main__":
    sys.exit(main())
