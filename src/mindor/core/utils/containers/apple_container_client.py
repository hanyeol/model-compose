from typing import Union, List, Optional
from mindor.core.logger import logging
import sys, shutil, asyncio

class AppleContainerClient:
    """Thin async wrapper around the Apple Container `container` CLI."""
    def __init__(self, verbose: bool = False):
        if shutil.which("container") is None:
            raise RuntimeError(
                "Apple Container CLI ('container') not found on PATH. "
                "Install it from https://github.com/apple/container to use runtime.type=apple-container. "
                "On non-macOS hosts, use runtime.type=docker instead."
            )

        self.verbose: bool = verbose

    async def run(
        self,
        command: Union[str, List[str]],
        args: Optional[List[str]] = None,
        raise_on_error: bool = True,
        capture_output: bool = True,
    ) -> asyncio.subprocess.Process:
        command = [ command ] if isinstance(command, str) else command
        command = [ "container", *command, *(args or []) ]

        logging.debug("Running: %s", " ".join(command))

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE if capture_output else sys.stdout,
            stderr=asyncio.subprocess.PIPE if capture_output else sys.stderr,
        )

        if raise_on_error:
            _, error = await process.communicate()
            if process.returncode != 0:
                error_message = error.decode() if error else "Unknown error"
                raise RuntimeError(f"Command '{' '.join(command)}' failed (exit {process.returncode}): {error_message}")

        return process
