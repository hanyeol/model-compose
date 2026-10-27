from typing import Union, Optional
from pydantic import Field
from .common import CommonModel3DLoaderActionConfig

class BlenderModel3DLoaderActionConfig(CommonModel3DLoaderActionConfig):
    object_name: Optional[str] = Field(default=None, description="Specific object or collection to export; whole scene when omitted.")
    apply_modifiers: Union[bool, str] = Field(default=True, description="Apply modifiers (subdivision, mirror, array, ...) before export.")
    include_materials: Union[bool, str] = Field(default=True, description="Include materials and textures in the exported mesh.")
    include_animations: Union[bool, str] = Field(default=False, description="Include armature and animation data (GLB/FBX only).")
