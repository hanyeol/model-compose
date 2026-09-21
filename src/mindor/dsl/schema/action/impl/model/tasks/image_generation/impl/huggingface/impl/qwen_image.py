from typing import Union, Optional, List, Literal, Annotated
from pydantic import Field
from ...common import ImageGenerationActionMethod
from .common import CommonHuggingfaceImageGenerationModelActionConfig, CommonHuggingfaceImageGenerationParamsConfig

class QwenImageHuggingfaceImageGenerationParamsConfig(CommonHuggingfaceImageGenerationParamsConfig):
    inference_steps: Union[int, str] = Field(default=40, description="Number of denoising steps run during sampling.")
    true_cfg_scale: Union[float, str] = Field(default=1.0, description="True classifier-free guidance scale; values above 1.0 enable negative-prompt guidance.")

class QwenImageHuggingfaceImageGenerationGenerateModelActionConfig(CommonHuggingfaceImageGenerationModelActionConfig):
    method: Literal[ImageGenerationActionMethod.GENERATE] = Field(default=ImageGenerationActionMethod.GENERATE)
    negative_prompt: Optional[Union[str, List[str]]] = Field(default=None, description="Negative prompt or prompts describing what to avoid.")
    reference_image: Optional[Union[str, List[str]]] = Field(default=None, description="Optional reference image(s) used as visual conditioning for Qwen-Image.")
    params: QwenImageHuggingfaceImageGenerationParamsConfig = Field(default_factory=QwenImageHuggingfaceImageGenerationParamsConfig, description="Qwen-Image-specific generation parameters.")

QwenImageHuggingfaceImageGenerationModelActionConfig = Annotated[
    Union[
        QwenImageHuggingfaceImageGenerationGenerateModelActionConfig,
    ],
    Field(discriminator="method")
]
