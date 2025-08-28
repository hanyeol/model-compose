from typing import Dict, List, Tuple, Optional
from asyncio.subprocess import Process
import asyncio, os

async def run_command_streaming(
    command: List[str],
    working_dir: Optional[str] = None,
    env: Dict[str, str] = None
) -> None:
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=working_dir or os.getcwd(),
        env={ **os.environ, **(env or {}) },
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    async def _stream_output(pipe: asyncio.StreamReader) -> None:
        while True:
            line = await pipe.readline()
            if not line:
                break
            print(line.decode().rstrip())

    await asyncio.gather(
        _stream_output(process.stdout),
        _stream_output(process.stderr),
        process.wait()
    )

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
            raise RuntimeError(f"Command timed out: {' '.join(command)}")

    return (stdout, stderr, process.returncode)

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
