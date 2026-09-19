from typing import Union, Optional
from pydantic import Field
from ..common import CommonMusicSourceSeparationModelActionConfig, CommonMusicSourceSeparationParamsConfig

class Mdx23cMusicSourceSeparationParamsConfig(CommonMusicSourceSeparationParamsConfig):
    chunk_size: Optional[Union[int, str]] = Field(default=None, description="Samples per inference chunk; larger values use more memory but run faster.")
    num_overlap: Optional[Union[int, str]] = Field(default=None, description="Number of overlapping chunks covering each output sample; higher values improve quality but are slower.")

class Mdx23cMusicSourceSeparationModelActionConfig(CommonMusicSourceSeparationModelActionConfig):
    params: Mdx23cMusicSourceSeparationParamsConfig = Field(default_factory=Mdx23cMusicSourceSeparationParamsConfig, description="MDX23C stem selection and inference quality parameters.")
