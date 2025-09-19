from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, AsyncIterator, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.action import DatasetsLoadActionConfig
from ....context import ComponentActionContext

if TYPE_CHECKING:
    from datasets import Dataset

class CommonDatasetsProvider(ABC):
    def __init__(self, config: DatasetsLoadActionConfig):
        self.config: DatasetsLoadActionConfig = config

    @abstractmethod
    async def load(self, context: ComponentActionContext) -> Dataset:
        pass
