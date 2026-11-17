from typing import Union, Literal, Optional, List, Annotated, Any
from enum import Enum
from pydantic import Field
from .common import CommonActionConfig

class AgentSkillStoreActionMethod(str, Enum):
    LIST = "list"
    GET  = "get"
    FIND = "find"

class CommonAgentSkillStoreActionConfig(CommonActionConfig):
    method: AgentSkillStoreActionMethod = Field(..., description="Skill catalog operation this action performs.")

class AgentSkillStoreListActionConfig(CommonAgentSkillStoreActionConfig):
    method: Literal[AgentSkillStoreActionMethod.LIST]
    tags: Any = Field(default=None, description="Return only skills that match every tag. May be a single tag list, a batch of lists, or a stream.")
    batch_size: Optional[int] = Field(default=None, ge=1, description="Batch size when parsing skills from the repository.")

class AgentSkillStoreGetActionConfig(CommonAgentSkillStoreActionConfig):
    method: Literal[AgentSkillStoreActionMethod.GET]
    name: Any = Field(..., description="Name of the skill to retrieve. May be a single string, a list, or a stream.")
    batch_size: Optional[int] = Field(default=None, ge=1, description="Batch size when name is a list or stream.")

class AgentSkillStoreFindActionConfig(CommonAgentSkillStoreActionConfig):
    method: Literal[AgentSkillStoreActionMethod.FIND]
    query: Any = Field(..., description="Text matched against skill name, description, and tags. May be a single string, a list, or a stream.")
    tags: Any = Field(default=None, description="Restrict the search to skills tagged with every tag. May be a single tag list, a batch of lists, or a stream.")
    limit: Optional[int] = Field(default=None, ge=1, description="Maximum number of matches returned per query.")
    batch_size: Optional[int] = Field(default=None, ge=1, description="Batch size when query is a list or stream.")

AgentSkillStoreActionConfig = Annotated[
    Union[
        AgentSkillStoreListActionConfig,
        AgentSkillStoreGetActionConfig,
        AgentSkillStoreFindActionConfig,
    ],
    Field(discriminator="method")
]
