from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import ExiftoolMediaInspectorActionConfig
from .common import CommonMediaInspectorComponentConfig, MediaInspectorDriver

class ExiftoolMediaInspectorComponentConfig(CommonMediaInspectorComponentConfig):
    driver: Literal[MediaInspectorDriver.EXIFTOOL]
    actions: List[ExiftoolMediaInspectorActionConfig] = Field(default_factory=list)
