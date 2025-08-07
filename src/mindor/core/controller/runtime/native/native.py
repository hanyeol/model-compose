from mindor.core.logger import logging
import sys, os, subprocess

class DetachedNativeRuntimeLauncher:
    async def launch(self) -> None:
        command = [ sys.executable ] + [ arg for arg in sys.argv if arg not in ( "--detach", "-d" ) ]
        env = os.environ.copy()

        logging.debug(f"Detaching and spawning: %s", " ".join(command))

        subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            env=env,
            close_fds=True,
            start_new_session=True,
        )
