from typing import BinaryIO, Type
from mindor.core.foundation.runtime.ipc_message import IpcMessage
from mindor.core.foundation.runtime.ipc_stdio_channel import IpcStdioWorkerFactory
from mindor.core.component.runtime.common import ComponentRuntimeWorker
from mindor.core.component.runtime.base.ipc_message import IpcStartPayload

def stdio_worker_factory(worker_class: Type[ComponentRuntimeWorker]) -> IpcStdioWorkerFactory:
    """Build an `IpcStdioChannel` factory that constructs `worker_class` from a START payload."""
    def _factory(message: IpcMessage, ipc_in: BinaryIO, ipc_out: BinaryIO) -> ComponentRuntimeWorker:
        payload = IpcStartPayload.model_validate(message.payload or {})

        return worker_class(
            payload.component_id,
            payload.component_config,
            payload.global_configs,
            ipc_in,
            ipc_out,
        )

    return _factory
