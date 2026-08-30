from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import SftpFileStoreActionConfig
from mindor.dsl.schema.transport.ssh import SshConnectionConfig
from .common import CommonFileStoreComponentConfig, FileStoreDriver

class SftpFileStoreComponentConfig(CommonFileStoreComponentConfig):
    driver: Literal[FileStoreDriver.SFTP]
    connection: SshConnectionConfig = Field(..., description="SSH connection settings used to reach the SFTP server.")
    actions: List[SftpFileStoreActionConfig] = Field(default_factory=list)
