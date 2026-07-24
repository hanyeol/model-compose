from __future__ import annotations

from typing import Optional
from collections.abc import AsyncIterable
import asyncio, os

class SubprocessStreamChannel:
    """Unidirectional async byte stream channel to a subprocess over an inherited fd.

    Unlike `SubprocessPipeChannel` (bidirectional length-prefixed IPC), this
    channel is a raw one-way byte feeder: the child inherits `read_fd` via
    `pass_fds` and reads it as its own input (e.g., ffmpeg's `pipe:<fd>`),
    while the parent pumps bytes from an `AsyncIterable[bytes]` source into
    the write end in the background.

    Lifecycle, in order:
      1. construct        — allocates the pipe; `read_fd` is for `pass_fds`
      2. spawn the child  — pass `read_fd` through `pass_fds`
      3. `start()`        — drops the parent's read end and begins pumping
      4. `close()`        — cancels the pump and releases the write end

    `start()` must run after the spawn: closing the read end early would
    hand the child a dead pipe, and writing before the child exists would
    fill the 64K kernel buffer with nobody draining it.
    """
    def __init__(self, source: AsyncIterable[bytes]):
        self._source: AsyncIterable[bytes] = source
        self._read_fd: Optional[int] = None
        self._write_fd: Optional[int] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._task: Optional[asyncio.Task] = None
        self._closed = False

        self._read_fd, self._write_fd = os.pipe()
        os.set_blocking(self._write_fd, False)

    @property
    def read_fd(self) -> Optional[int]:
        """The read end to hand to the child via `pass_fds`."""
        return self._read_fd

    async def start(self) -> None:
        loop = asyncio.get_running_loop()

        # The child inherited `read_fd` through `pass_fds`, so drop our copy
        # here — otherwise ffmpeg never sees EOF when we close the write end.
        if self._read_fd is not None:
            try:
                os.close(self._read_fd)
            except OSError:
                pass
            self._read_fd = None

        # FlowControlMixin gives us the drain()/backpressure half of a
        # StreamWriter without a matching reader, which is exactly what a
        # write-only pipe needs.
        transport, protocol = await loop.connect_write_pipe(
            lambda: asyncio.streams.FlowControlMixin(loop=loop),
            os.fdopen(self._write_fd, "wb", 0),
        )
        self._write_fd = None  # the transport owns it from here on
        self._writer = asyncio.StreamWriter(transport, protocol, None, loop)
        self._task = asyncio.create_task(self._feed())

    async def close(self) -> None:
        if self._closed:
            return

        self._closed = True

        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass

        # Safety net for the "spawn failed before start()" path — normally
        # start() has already dropped this.
        if self._read_fd is not None:
            try:
                os.close(self._read_fd)
            except OSError:
                pass
            self._read_fd = None

        if self._write_fd is not None:
            try:
                os.close(self._write_fd)
            except OSError:
                pass
            self._write_fd = None

    async def _feed(self) -> None:
        try:
            async for chunk in self._source:
                try:
                    self._writer.write(chunk)
                    await self._writer.drain()
                except (BrokenPipeError, ConnectionResetError):
                    break
        finally:
            # Closing the write end is what signals EOF to the child; without
            # it the reader waits forever on an input that will never end.
            try:
                self._writer.close()
            except Exception:
                pass
