from mindor.core.logger import logging
from pathlib import Path
import sys, os, subprocess

class ControllerNativeRuntimeManager:
    async def launch_detached(self) -> None:
        command = [ sys.executable ] + [ arg for arg in sys.argv if arg not in ( "--detach", "-d" ) ]
        env = os.environ.copy()

        logging.debug(f"Detaching and spawning: %s", " ".join(command))

        if sys.platform == "win32":
            # Windows: detach from console and create a new process group so the
            # child survives parent exit and Ctrl-C in the parent console.
            platform_params = {
                "creationflags": (
                    subprocess.DETACHED_PROCESS
                    | subprocess.CREATE_NEW_PROCESS_GROUP
                    | subprocess.CREATE_NO_WINDOW
                ),
            }
        else:
            # POSIX: setsid() puts the child in a new session with no controlling
            # terminal, so SIGHUP on terminal close does not reach it.
            platform_params = { "start_new_session": True }

        subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            env=env,
            close_fds=True,
            **platform_params,
        )

    async def stop(self) -> None:
        stop_file = Path.cwd() / ".stop"
        stop_file.touch()
