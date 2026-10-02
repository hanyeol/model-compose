from typing import Any, Dict, Literal, Union, List, Annotated
from pydantic import Field, model_validator
from mindor.dsl.utils.path import is_local_path
from mindor.dsl.schema.action import TypedDecisionModelActionConfig
from ..common import CommonTypedDecisionModelComponentConfig
from .common import TypedDecisionModelFamily
from ....common import ModelDriverType, ModelProvider, HuggingfaceModelConfig, LocalModelConfig

_DEFAULT_REPOSITORY = "Cloudflare/clef"

ClefTypedDecisionModelConfig = Annotated[
    Union[
        HuggingfaceModelConfig,
        LocalModelConfig,
    ],
    Field(discriminator="provider")
]

class ClefTypedDecisionModelComponentConfig(CommonTypedDecisionModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[TypedDecisionModelFamily.CLEF]
    model: ClefTypedDecisionModelConfig = Field(..., description="Clef checkpoint — a HuggingFace repo ID or a local directory bundling the joint_schema_model module.")
    device: str = Field(default="auto", description="Device placement passed to joint_schema_model.load_release_model.")
    actions: List[TypedDecisionModelActionConfig] = Field(default_factory=list, description="Actions this typed decision component exposes to workflows.")

    @model_validator(mode="before")
    def inflate_model(cls, values: Dict[str, Any]):
        model = values.get("model")
        if model is None:
            model = _DEFAULT_REPOSITORY
        if isinstance(model, str):
            if is_local_path(model):
                values["model"] = { "provider": ModelProvider.LOCAL, "path": model }
            else:
                values["model"] = { "provider": ModelProvider.HUGGINGFACE, "repository": model }
        return values
