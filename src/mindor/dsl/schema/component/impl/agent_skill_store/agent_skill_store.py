from typing import Any, Literal, List
from pydantic import BaseModel, Field, model_validator
from mindor.dsl.schema.action import AgentSkillStoreActionConfig
from ..common import CommonComponentConfig, ComponentType

class AgentSkillRepositoryActions(BaseModel):
    list: str = Field(default="list", description="Action id on the repository component used to list entries.")
    get: str = Field(default="get", description="Action id on the repository component used to fetch a single entry.")

class AgentSkillRepositoryConfig(BaseModel):
    component: str = Field(..., description="ID of the component acting as the skill repository.")
    actions: AgentSkillRepositoryActions = Field(
        default_factory=AgentSkillRepositoryActions,
        description="Mapping from skill_store operation to the repository component's action id.",
    )

    @model_validator(mode="before")
    def inflate_component(cls, values: Any):
        if isinstance(values, str):
            return { "component": values }
        return values

class AgentSkillStoreComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.AGENT_SKILL_STORE]
    repository: AgentSkillRepositoryConfig = Field(..., description="Component providing the underlying storage for skills.")
    actions: List[AgentSkillStoreActionConfig] = Field(default_factory=list, description="Actions this skill store exposes to workflows.")
