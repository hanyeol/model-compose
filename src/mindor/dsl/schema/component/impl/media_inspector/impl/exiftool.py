from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import ExiftoolMediaInspectorActionConfig
from .common import CommonMediaInspectorComponentConfig, MediaInspectorDriverType

class ExiftoolMediaInspectorComponentConfig(CommonMediaInspectorComponentConfig):
    driver: Literal[MediaInspectorDriverType.EXIFTOOL]
    actions: List[ExiftoolMediaInspectorActionConfig] = Field(default_factory=list)
