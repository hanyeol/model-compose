from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.system import SystemConfig
from mindor.dsl.schema.system.impl.types import SystemType
from mindor.core.foundation import AsyncService
from mindor.core.logger import logging

class SystemService(AsyncService):
    def __init__(self, id: str, config: SystemConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: SystemConfig = config

    async def _install_package(self, package_spec: str, repository: Optional[str]) -> None:
        logging.info(f"Installing required module: {package_spec}")
        await super()._install_package(package_spec, repository)

def register_system(type: SystemType):
    def decorator(cls: Type[SystemService]) -> Type[SystemService]:
        SystemRegistry[type] = cls
        return cls
    return decorator

SystemRegistry: Dict[SystemType, Type[SystemService]] = {}
