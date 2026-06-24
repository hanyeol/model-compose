from __future__ import annotations

from typing import Any, Dict, IO, Optional
from pydantic import BaseModel
from datetime import date, datetime
from pathlib import Path, PurePath
import base64
import io
import json
import os
import socket

_BYTES_ENVELOPE_KEY = "__bytes__"

def _to_jsonable(value: Any) -> Any:
    """Recursively convert a Python value into a JSON-compatible form."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return { _BYTES_ENVELOPE_KEY: base64.b64encode(value).decode("ascii") }
    if isinstance(value, PurePath):
        return str(value)
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return { str(k): _to_jsonable(v) for k, v in value.items() }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, (io.IOBase, socket.socket)):
        raise TypeError(
            f"Cannot serialize {type(value).__name__} over SubprocessPipeChannel; "
            f"file-like objects and sockets must not be passed as IPC payload values."
        )
    if hasattr(value, "__aiter__") or hasattr(value, "__anext__"):
        raise TypeError(
            "Cannot serialize async iterator/streaming output over SubprocessPipeChannel; "
            "use RESULT_CHUNK/RESULT_END messages for streaming results."
        )
    raise TypeError(f"Cannot serialize value of type {type(value).__name__} over SubprocessPipeChannel")


def _from_jsonable(value: Any) -> Any:
    """Reverse the lightweight envelopes from `_to_jsonable`.

    Pydantic models, datetimes, and Paths are NOT auto-restored - the recipient is expected
    to validate the resulting dicts/strings against the schema it knows about.
    """
    if isinstance(value, dict):
        if set(value.keys()) == { _BYTES_ENVELOPE_KEY }:
            return base64.b64decode(value[_BYTES_ENVELOPE_KEY])
        return { k: _from_jsonable(v) for k, v in value.items() }
    if isinstance(value, list):
        return [_from_jsonable(v) for v in value]
    return value


def dumps(message: Any) -> bytes:
    """Serialize a message dict to a single JSON line (terminated with `\\n`)."""
    encoded = json.dumps(_to_jsonable(message), ensure_ascii=False, separators=(",", ":"))
    return (encoded + "\n").encode("utf-8")


def loads(line: bytes) -> Any:
    """Deserialize a single JSON line back into a Python value."""
    return _from_jsonable(json.loads(line.decode("utf-8")))

class SubprocessPipeChannel:
    """Bidirectional JSON-lines channel over two OS pipe file descriptors.

    `request_fd` is read for incoming messages, `response_fd` is written to for outgoing
    messages. The constructor takes ownership of the fds and closes them on `.close()`.
    """

    def __init__(self, request_fd: int, response_fd: int):
        self._reader: IO[bytes] = os.fdopen(request_fd, "rb", buffering=0)
        self._writer: IO[bytes] = os.fdopen(response_fd, "wb", buffering=0)
        self._closed = False

    def send(self, message: Dict[str, Any]) -> None:
        if self._closed:
            raise RuntimeError("SubprocessPipeChannel is closed")
        self._writer.write(dumps(message))

    def recv(self) -> Optional[Dict[str, Any]]:
        if self._closed:
            return None
        line = self._reader.readline()
        if not line:
            return None
        return loads(line)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._reader.close()
        except Exception:
            pass
        try:
            self._writer.close()
        except Exception:
            pass

    def __enter__(self) -> "SubprocessPipeChannel":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
