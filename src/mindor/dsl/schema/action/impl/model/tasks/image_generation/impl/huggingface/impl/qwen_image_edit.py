from typing import Union, Optional, List, Literal, Annotated
from pydantic import Field
from ...common import ImageGenerationActionMethod
from .common import CommonHuggingfaceImageGenerationModelGenerateActionConfig, CommonHuggingfaceImageGenerationParamsConfig

class QwenImageEditHuggingfaceImageGenerationParamsConfig(CommonHuggingfaceImageGenerationParamsConfig):
    inference_steps: Union[int, str] = Field(default=40, description="Number of denoising steps run during sampling.")
    true_cfg_scale: Union[float, str] = Field(default=4.0, description="True classifier-free guidance scale; values above 1.0 enable negative-prompt guidance.")
    max_sequence_length: Union[int, str] = Field(default=512, description="Maximum token length for the Qwen2.5-VL text encoder.")

class QwenImageEditHuggingfaceImageGenerationModelGenerateActionConfig(CommonHuggingfaceImageGenerationModelGenerateActionConfig):
    method: Literal[ImageGenerationActionMethod.GENERATE] = Field(default=ImageGenerationActionMethod.GENERATE)
    negative_prompt: Optional[Union[str, List[str]]] = Field(default=None, description="Negative prompt or prompts describing what to avoid.")
    image: Union[str, List[str]] = Field(description="Reference image or images used as the editing target; up to three images are supported.")
    params: QwenImageEditHuggingfaceImageGenerationParamsConfig = Field(default_factory=QwenImageEditHuggingfaceImageGenerationParamsConfig, description="Qwen-Image-Edit-specific generation parameters.")

QwenImageEditHuggingfaceImageGenerationModelActionConfig = Annotated[
    Union[
        QwenImageEditHuggingfaceImageGenerationModelGenerateActionConfig,
    ],
    Field(discriminator="method")
]
