from typing import Optional, Mapping
from mindor.core.foundation.requirement_manager import RequirementManager
from mindor.core.foundation.package import mindor as mindor_package
import asyncio

class RuntimeManager(RequirementManager):
    """Base for runtime managers that orchestrate an isolated runtime (venv,
    container, remote pod, native host). Inherits requirement declaration /
    install from `RequirementManager`; subclasses layer their own lifecycle
    (setup/teardown + start/stop or launch/terminate)."""

    async def _upload_mindor_source(
        self,
        url: str,
        auth_token: str,
        headers: Optional[Mapping[str, str]] = None,
        timeout: float = 60.0,
    ) -> int:
        """Package the host mindor source and POST it to a receiver running
        inside the isolated environment, authenticated via a shared bearer
        token. Attaches ``X-Mindor-Version`` so the receiver can respond 304
        when its cache already matches — the body is still streamed on the
        wire, but no extract / reinstall happens on the pod side.
        ``headers`` carries extra request headers for callers that need
        them. Retries connect-refused / transient errors until ``timeout``
        is exhausted (the receiver typically takes a few seconds after the
        pod reaches RUNNING to bind its port). Returns the HTTP status
        (200 or 304)."""
        import aiohttp

        headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/octet-stream",
            "X-Mindor-Version": mindor_package.get_version(),
            **(headers or {}),
        }

        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        attempt = 0

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
            while True:
                attempt += 1

                try:
                    with mindor_package.package_to_tar() as tar_file:
                        async with session.post(url, data=tar_file, headers=headers) as response:
                            if response.status not in (200, 304):
                                raise RuntimeError(f"source upload to {url} rejected: HTTP {response.status}")

                            return response.status
                except Exception as e:
                    if loop.time() > deadline:
                        raise TimeoutError(
                            f"source upload to {url} did not succeed within {timeout}s: {e}"
                        ) from e

                    await asyncio.sleep(min(10.0, 2.0 * attempt))

    def _get_mindor_upload_server_script(self) -> str:
        """Return the pod/remote-side single-shot HTTP upload receiver
        script (``runtime/bootstrap/scripts/upload_server/main.py``)
        verbatim. Transports materialize this on the target before running
        ``python3 <script> --port <p> --dest <d>`` — any shell quoting /
        escape is the transport's responsibility."""
        from importlib.resources import files

        package = files("mindor.core.runtime.bootstrap.scripts.upload_server")
        script_path = package / "main.py"

        return script_path.read_text()
