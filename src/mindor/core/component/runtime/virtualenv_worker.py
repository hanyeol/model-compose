from __future__ import annotations

from typing import Any, Dict
from mindor.dsl.schema.runtime import EmbeddedRuntimeConfig
from mindor.core.component.component import create_component
from mindor.core.foundation.virtualenv_worker import VirtualEnvWorker
from mindor.core.utils.subprocess import SubprocessPipeChannel
import asyncio, os, sys

class ComponentVirtualEnvWorker(VirtualEnvWorker):
    """Component-specific worker that hosts an embedded-runtime component instance."""

    def __init__(
        self,
        component_id: str,
        component_config: Any,
        global_configs: Any,
        channel: SubprocessPipeChannel,
    ):
        super().__init__(component_id, channel)
        self.component_config = component_config
        self.global_configs = global_configs
        self.component = None

    async def _start(self) -> None:
        embedded_config = self.component_config.model_copy(deep=True)
        embedded_config.runtime = EmbeddedRuntimeConfig(type="embedded")

        self.component = create_component(
            self.worker_id,
            embedded_config,
            self.global_configs,
            daemon=True,
        )

        await self.component.setup()
        await self.component.start()

    async def _stop(self) -> None:
        if self.component is not None:
            try:
                await self.component.stop()
            finally:
                await self.component.teardown()

    async def _execute_task(self, payload: Dict[str, Any]) -> Any:
        return await self.component.run(
            payload["action_id"],
            payload["run_id"],
            payload["input"],
        )


def main() -> None:
    """Entrypoint when launched as `python -m mindor.core.component.runtime.virtualenv_worker`."""
    # Ensure stdout/stderr stay attached to the parent as log channels only;
    # the IPC protocol runs on the dedicated fd pair, not on stdout.
    try:
        sys.stdout.reconfigure(line_buffering=True)
        sys.stderr.reconfigure(line_buffering=True)
    except Exception:
        pass

    from pydantic import BaseModel
    from mindor.core.component.base import ComponentGlobalConfigs
    from mindor.dsl.schema.component import ComponentConfig

    # Wrap the INIT payload in a tiny BaseModel so Pydantic handles the discriminator
    # Union (ComponentConfig) and ComponentGlobalConfigs validation in one shot.
    class _InitPayload(BaseModel):
        component_id: str
        component_config: ComponentConfig
        global_configs: ComponentGlobalConfigs

    try:
        request_fd = int(os.environ["MINDOR_VENV_REQUEST_FD"])
        response_fd = int(os.environ["MINDOR_VENV_RESPONSE_FD"])
    except KeyError as e:
        raise RuntimeError(
            f"Missing IPC file descriptor environment variable: {e}. "
            f"This module must be launched by ComponentVirtualEnvRuntimeManager."
        ) from e

    channel = SubprocessPipeChannel(
        request_fd=request_fd,
        response_fd=response_fd,
    )

    init = channel.recv()
    if init is None or init.get("type") != "init":
        raise RuntimeError(
            f"Expected first IPC message of type 'init', got: {init!r}"
        )

    payload = _InitPayload.model_validate(init.get("payload") or {})
    component_id = payload.component_id
    component_config = payload.component_config
    global_configs = payload.global_configs

    worker = ComponentVirtualEnvWorker(
        component_id,
        component_config,
        global_configs,
        channel,
    )

    asyncio.run(worker.run())


if __name__ == "__main__":
    main()
