from typing import Union, Optional, List
from pydantic import Field, model_validator
from ...common import CommonActionConfig

class CommonCameraPoseEstimatorActionConfig(CommonActionConfig):
    images: Optional[Union[str, List[str]]] = Field(default=None, description="Image or list of images the reconstruction is built from; when omitted, images already present under the workspace's images/ subfolder are used.")
    workspace_dir: Optional[str] = Field(default=None, description="Directory holding the COLMAP workspace (images/, database.db, sparse/); defaults to `.workspace/<component-id>/<run-id>/` when omitted.")
    batch_size: Union[int, str] = Field(default=1, description="Number of scenes processed per batch when the input is a list or stream of scenes.")

    @model_validator(mode="after")
    def validate_images_or_workspace(self):
        if self.images is None and self.workspace_dir is None:
            raise ValueError("Either 'images' or 'workspace_dir' must be provided")
        return self
