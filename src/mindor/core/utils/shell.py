from typing import Dict, List, Tuple, Optional
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
            raise RuntimeError(f"Command timed out: {' '.join(command)}")

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
