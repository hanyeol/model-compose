from pydantic import BaseModel
from mindor.dsl.schema.component import ComponentConfig
from mindor.core.component.base import ComponentGlobalConfigs

class IpcStartPayload(BaseModel):
    """START message payload carrying the embedded component's config bundle."""
    component_id: str
    component_config: ComponentConfig
    global_configs: ComponentGlobalConfigs
