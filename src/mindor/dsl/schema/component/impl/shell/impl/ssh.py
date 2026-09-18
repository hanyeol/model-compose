from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import SshShellActionConfig
from mindor.dsl.schema.transport.ssh import SshConnectionConfig
from .common import CommonShellComponentConfig, ShellDriverType

class SshShellComponentConfig(CommonShellComponentConfig):
    driver: Literal[ShellDriverType.SSH]
    connection: SshConnectionConfig = Field(..., description="SSH connection settings used to reach the remote host.")
    actions: List[SshShellActionConfig] = Field(default_factory=list)
