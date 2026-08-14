from typing import Union, Literal, Optional, List, Dict, Any
from pydantic import Field, model_validator
from .common import CommonSystemConfig
from .types import SystemType

class DockerComposeSystemConfig(CommonSystemConfig):
    type: Literal[SystemType.DOCKER_COMPOSE] = Field(default=SystemType.DOCKER_COMPOSE, description="Type of system.")
    files: List[str] = Field(default_factory=list, description="Filesystem paths to the docker-compose files loaded for this system.")
    project_name: Optional[str] = Field(default=None, description="Docker Compose project name passed via the -p flag.")
    profiles: Optional[List[str]] = Field(default=None, description="Docker Compose profiles activated when the system starts.")
    env_file: Optional[str] = Field(default=None, description="Filesystem path to the environment file loaded by docker-compose.")
    build: bool = Field(default=False, description="Whether to build images before starting services (--build flag).")
    wait: bool = Field(default=True, description="Whether to wait for services to become healthy before continuing.")
    wait_timeout: Optional[Union[str, int, float]] = Field(default="60s", description="Maximum time to wait for services to become ready.")

    @model_validator(mode="before")
    def inflate_single_file(cls, values: Dict[str, Any]):
        if "files" not in values:
            file_value = values.pop("file", None)
            if file_value:
                values["files"] = [file_value]
        return values
