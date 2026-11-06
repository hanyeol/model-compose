from typing import Union, Optional, List
from pydantic import Field
from mindor.dsl.schema.common.model_3d import Model3DFormat
from ...common import CommonActionConfig

class CommonModel3DLoaderActionConfig(CommonActionConfig):
    source: Union[str, List[str]] = Field(..., description="3D model source as path, URL, upload stream, or raw bytes.")
    format: Union[Model3DFormat, str] = Field(default=Model3DFormat.GLB, description="Output format emitted into the pipeline.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of sources processed per batch.")
