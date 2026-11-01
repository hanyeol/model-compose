from typing import Optional
from pydantic import BaseModel, Field
from .types import RemoteTransportType

class CommonRemoteTransportConfig(BaseModel):
    type: RemoteTransportType = Field(..., description="Type of remote transport used to reach the host.")
    working_dir: Optional[str] = Field(default=None, description="Base directory on the remote host used for provisioning and caches.")
