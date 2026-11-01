from abc import abstractmethod
from mindor.dsl.schema.controller import ControllerConfig
from mindor.core.runtime.manager import RuntimeManager
from .base.specs import ControllerRuntimeSpecs

class ControllerRuntimeManager(RuntimeManager):
    """Controller-side lifecycle manager base.

    Owns a controller runtime's launch/terminate/start/stop sequence. Concrete
    subclasses implement each lifecycle hook; the Backend-based container
    managers live in `ControllerContainerRuntimeManager`.
    """
    def __init__(self, config: ControllerConfig, verbose: bool = False):
        self.config: ControllerConfig = config
        self.verbose: bool = verbose

    @abstractmethod
    async def launch(self, specs: ControllerRuntimeSpecs, detach: bool) -> None:
        """Provision the runtime from scratch and start it."""

    @abstractmethod
    async def terminate(self) -> None:
        """Tear down the runtime that `launch()` provisioned."""

    @abstractmethod
    async def start(self) -> None:
        """Start an already-provisioned runtime (idempotent)."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop a running runtime without removing it (idempotent)."""
