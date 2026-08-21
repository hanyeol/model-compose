from typing import Any, Awaitable, Callable, Dict, List, Tuple, Optional
from collections.abc import AsyncGenerator, AsyncIterable, AsyncIterator
from contextlib import asynccontextmanager
from asyncio.subprocess import Process
import asyncio, os, sys

async def run_command(
    command: List[str],
    input: Optional[bytes] = None,
    working_dir: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    timeout: Optional[float] = None
) -> Tuple[bytes, bytes, int]:
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=working_dir or os.getcwd(),
        env={ **os.environ, **(env or {}) },
        stdin=asyncio.subprocess.PIPE if input is not None else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(input=input), timeout=timeout)
    except asyncio.TimeoutError:
        if await kill_process(process, timeout=2.0):
            raise TimeoutError(f"Command timed out: {' '.join(command)}")
    except BaseException:
        # Includes asyncio.CancelledError: don't leave an orphaned child.
        await kill_process(process, timeout=2.0)
        raise

    return (stdout, stderr, process.returncode)

async def run_command_foreground(
    command: List[str],
    working_dir: Optional[str] = None,
    env: Dict[str, str] = None
) -> int:
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=working_dir or os.getcwd(),
        env={ **os.environ, **(env or {}) },
        stdout=sys.stdout,
        stderr=sys.stderr
    )

    try:
        await process.wait()
    except BaseException:
        # Includes asyncio.CancelledError: don't leave an orphaned child.
        await kill_process(process, timeout=2.0)
        raise

    return process.returncode

async def run_subprocess(
    command: List[str],
    source: Optional[AsyncIterable[bytes]] = None,
    stdout_handler: Optional[Callable[[asyncio.StreamReader], Awaitable[Any]]] = None,
    stderr_handler: Optional[Callable[[asyncio.StreamReader], Awaitable[Any]]] = None,
    working_dir: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    pass_fds: Tuple[int, ...] = (),
    on_started: Optional[Callable[[], Awaitable[None]]] = None,
) -> Tuple[Process, Any, Any]:
    """Run a command, optionally feeding stdin from `source`.

    `pass_fds` hands additional descriptors to the child (for tools like
    ffmpeg that can read a `pipe:<fd>` input beyond stdin). `on_started`
    runs once the child exists — that is where the caller closes its own
    copies of those descriptors and begins writing to them.
    """
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=working_dir or os.getcwd(),
        env={ **os.environ, **(env or {}) },
        stdin=asyncio.subprocess.PIPE if source is not None else None,
        stdout=asyncio.subprocess.PIPE if stdout_handler is not None else None,
        stderr=asyncio.subprocess.PIPE if stderr_handler is not None else None,
        pass_fds=pass_fds,
    )

    if on_started is not None:
        await on_started()

    feed_error: Optional[BaseException] = None

    async def _feed_stdin() -> None:
        nonlocal feed_error
        try:
            async for chunk in source:
                try:
                    process.stdin.write(chunk)
                    await process.stdin.drain()
                except (BrokenPipeError, ConnectionResetError):
                    break
        except asyncio.CancelledError:
            raise
        except BaseException as error:
            feed_error = error
        finally:
            try:
                process.stdin.close()
            except Exception:
                pass

    stdout_task = asyncio.create_task(stdout_handler(process.stdout)) if stdout_handler is not None else None
    stderr_task = asyncio.create_task(stderr_handler(process.stderr)) if stderr_handler is not None else None

    stdin_feeder = asyncio.create_task(_feed_stdin()) if source is not None else None

    stdout_result: Any = None
    stderr_result: Any = None

    try:
        if stdout_task is not None:
            stdout_result = await stdout_task
        if stderr_task is not None:
            stderr_result = await stderr_task
        await process.wait()
    finally:
        # On cancellation the handler tasks may still be blocked on `read()`. Cancel
        # them first so their transport can close, then kill the process.
        for task in (stdout_task, stderr_task, stdin_feeder):
            if task is None or task.done():
                continue
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

        await kill_process(process, timeout=2.0)

    if feed_error is not None:
        raise feed_error

    return process, stdout_result, stderr_result

@asynccontextmanager
async def stream_subprocess(
    command: List[str],
    source: Optional[AsyncIterable[bytes]] = None,
    stdout_handler: Optional[Callable[[asyncio.StreamReader], AsyncIterator[Any]]] = None,
    stderr_handler: Optional[Callable[[asyncio.StreamReader], Awaitable[None]]] = None,
    working_dir: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    pass_fds: Tuple[int, ...] = (),
    on_started: Optional[Callable[[], Awaitable[None]]] = None,
) -> AsyncGenerator[Tuple[Process, AsyncIterator[Any], Optional[asyncio.Task]], None]:
    """Spawn a subprocess and expose its stdout as an async iterator while it runs.

    The caller consumes `stdout_iterator` directly. `stdout_handler` is a factory that takes
    the process's stdout reader and returns an async iterator of items to be yielded.
    `stderr_handler` runs as a background task — typically used to drain stderr and
    side-band data (e.g. timestamps, error lines) via closure variables.

    `pass_fds` hands additional descriptors to the child (for tools like ffmpeg
    that can read a `pipe:<fd>` input beyond stdin). `on_started` runs once the
    child exists — that is where the caller closes its own copies of those
    descriptors and begins writing to them.

    On context exit (including consumer break or exception): the process is killed,
    stdin stdin_feeder is awaited, and `stderr_task` is awaited so the caller can inspect
    the returncode and any drained stderr.
    """
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=working_dir or os.getcwd(),
        env={ **os.environ, **(env or {}) },
        stdin=asyncio.subprocess.PIPE if source is not None else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE if stderr_handler is not None else None,
        pass_fds=pass_fds,
    )

    if on_started is not None:
        await on_started()

    feed_error: Optional[BaseException] = None

    async def _feed_stdin() -> None:
        nonlocal feed_error
        try:
            async for chunk in source:
                try:
                    process.stdin.write(chunk)
                    await process.stdin.drain()
                except (BrokenPipeError, ConnectionResetError):
                    break
        except asyncio.CancelledError:
            raise
        except BaseException as error:
            feed_error = error
        finally:
            try:
                process.stdin.close()
            except Exception:
                pass

    stdin_feeder = asyncio.create_task(_feed_stdin()) if source is not None else None
    stderr_task = asyncio.create_task(stderr_handler(process.stderr)) if stderr_handler is not None else None

    if stdout_handler is not None:
        stdout_iterator = stdout_handler(process.stdout)
    else:
        # No stdout consumer: expose an async generator that silently drains the
        # pipe so the child never blocks on backpressure. The `if False: yield`
        # keeps this a generator function (not a coroutine) without ever yielding.
        async def _drain_stdout() -> AsyncIterator[Any]:
            while True:
                chunk = await process.stdout.read(65536)
                if not chunk:
                    return
                if False:  # pragma: no cover — never yields; drains only
                    yield chunk
        stdout_iterator = _drain_stdout()

    async def _finalize() -> None:
        await kill_process(process, timeout=2.0)

        if stdin_feeder is not None:
            try:
                await stdin_feeder
            except Exception:
                pass

        if stderr_task is not None:
            try:
                await stderr_task
            except Exception:
                pass

    try:
        yield process, stdout_iterator, stderr_task
    except BaseException:
        await _finalize()
        raise
    else:
        await _finalize()

        if feed_error is not None:
            raise feed_error

async def kill_process(process: Process, timeout: Optional[float] = None) -> bool:
    if process.returncode is None:
        process.kill()
        try:
            if timeout is not None:
                # Bounded wait: `process.wait()` can hang on some platforms if
                # the child's pipes still hold buffered data even after SIGKILL.
                # Callers on a cancellation path can opt in to a hard cap.
                await asyncio.wait_for(process.wait(), timeout=timeout)
            else:
                await process.wait()
        except (asyncio.TimeoutError, Exception):
            pass
        return True
    else:
        return False
