from typing import Literal, Optional, List, Dict, Any
from pydantic import Field, model_validator
from .common import CommonSystemConfig
from .types import SystemType

class DockerComposeSystemConfig(CommonSystemConfig):
    type: Literal[SystemType.DOCKER_COMPOSE] = Field(default=SystemType.DOCKER_COMPOSE, description="Docker Compose system type.")
    files: List[str] = Field(default_factory=list, description="Paths to docker-compose files.")
    project_name: Optional[str] = Field(default=None, description="Docker Compose project name (-p flag).")
    profiles: Optional[List[str]] = Field(default=None, description="Docker Compose profiles to activate.")
    env_file: Optional[str] = Field(default=None, description="Path to environment file for docker-compose.")
    build: bool = Field(default=False, description="Whether to build images before starting (--build flag).")
    wait: bool = Field(default=True, description="Whether to wait for services to be healthy before proceeding.")
    wait_timeout: Optional[str] = Field(default="60s", description="Timeout for waiting for services to be ready.")

    @model_validator(mode="before")
    def inflate_single_file(cls, values: Dict[str, Any]):
        if "files" not in values:
            file_value = values.pop("file", None)
            if file_value:
                values["files"] = [file_value]
        return values
