from typing import Any, Awaitable, Callable, Dict, List, Tuple, Optional
from collections.abc import AsyncIterable, AsyncIterator
from contextlib import asynccontextmanager
from asyncio.subprocess import Process
import asyncio, os, sys

async def run_command(
    command: List[str],
    working_dir: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    timeout: Optional[float] = None
) -> Tuple[bytes, bytes, int]:
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=working_dir or os.getcwd(),
        env={ **os.environ, **(env or {}) },
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        if await kill_process(process):
            raise TimeoutError(f"Command timed out: {' '.join(command)}")

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

    await process.wait()

    return process.returncode

async def run_subprocess(
    command: List[str],
    source: Optional[AsyncIterable[bytes]] = None,
    stdout_handler: Optional[Callable[[asyncio.StreamReader], Awaitable[Any]]] = None,
    stderr_handler: Optional[Callable[[asyncio.StreamReader], Awaitable[Any]]] = None,
    working_dir: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
) -> Tuple[Process, Any, Any]:
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=working_dir or os.getcwd(),
        env={ **os.environ, **(env or {}) },
        stdin=asyncio.subprocess.PIPE if source is not None else None,
        stdout=asyncio.subprocess.PIPE if stdout_handler is not None else None,
        stderr=asyncio.subprocess.PIPE if stderr_handler is not None else None,
    )

    async def _feed_stdin() -> None:
        try:
            async for chunk in source:
                try:
                    process.stdin.write(chunk)
                    await process.stdin.drain()
                except (BrokenPipeError, ConnectionResetError):
                    break
        finally:
            try:
                process.stdin.close()
            except Exception:
                pass

    stdout_task = asyncio.create_task(stdout_handler(process.stdout)) if stdout_handler is not None else None
    stderr_task = asyncio.create_task(stderr_handler(process.stderr)) if stderr_handler is not None else None
    
    stdin_feeder = asyncio.create_task(_feed_stdin()) if source is not None else None

    try:
        stdout_result = await stdout_task if stdout_task is not None else None
        stderr_result = await stderr_task if stderr_task is not None else None
        await process.wait()
    finally:
        await kill_process(process)
        if stdin_feeder is not None:
            await stdin_feeder

    return process, stdout_result, stderr_result

@asynccontextmanager
async def stream_subprocess(
    command: List[str],
    source: Optional[AsyncIterable[bytes]] = None,
    stdout_handler: Optional[Callable[[asyncio.StreamReader], AsyncIterator[Any]]] = None,
    stderr_handler: Optional[Callable[[asyncio.StreamReader], Awaitable[None]]] = None,
    working_dir: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
) -> AsyncIterator[Tuple[Process, AsyncIterator[Any], Optional[asyncio.Task]]]:
    """Spawn a subprocess and expose its stdout as an async iterator while it runs.

    The caller consumes `stdout_iterator` directly. `stdout_handler` is a factory that takes
    the process's stdout reader and returns an async iterator of items to be yielded.
    `stderr_handler` runs as a background task — typically used to drain stderr and
    side-band data (e.g. timestamps, error lines) via closure variables.

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
    )

    async def _feed_stdin() -> None:
        try:
            async for chunk in source:
                try:
                    process.stdin.write(chunk)
                    await process.stdin.drain()
                except (BrokenPipeError, ConnectionResetError):
                    break
        finally:
            try:
                process.stdin.close()
            except Exception:
                pass

    stdin_feeder = asyncio.create_task(_feed_stdin()) if source is not None else None
    stderr_task = asyncio.create_task(stderr_handler(process.stderr)) if stderr_handler is not None else None
    stdout_iterator = stdout_handler(process.stdout)

    try:
        yield process, stdout_iterator, stderr_task
    finally:
        await kill_process(process)

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

async def kill_process(process: Process) -> bool:
    if process.returncode is None:
        process.kill()
        try:
            await process.wait()
        except Exception as e:
            pass
        return True
    else:
        return False
