from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator, field_validator
from .component import ComponentConfig

class JobConfig(BaseModel):
    component: Optional[Union[str, 'ComponentConfig']] = Field(default="__default__", description="The component to execute. Can be a string identifier or a ComponentConfig object.")
    action: Optional[str] = Field(default="__default__", description="The action to invoke within the component. Defaults to '__default__'.")
    input: Optional[Any] = Field(default=None, description="The input data passed to the component. Can be of any type.")
    output: Optional[Any] = Field(default=None, description="The expected output data from the component. Can be of any type.")
    repeat_count: Optional[Union[int, str]] = Field(default=1, description="Number of times to repeat the component execution. Must be at least 1.")
    depends_on: Optional[List[str]] = Field(default_factory=list, description="List of job names that this job depends on. Ensures execution order.")

    @field_validator("repeat_count")
    def validate_repeat_count(cls, value):
        if isinstance(value, int) and value < 1:
            raise ValueError("'repeat_count' must be at least 1")
        return value

class WorkflowVariableType(str, Enum):
    # Primitive data types
    STRING  = "string"
    TEXT    = "text"
    INTEGER = "integer"
    NUMBER  = "number"
    BOOLEAN = "boolean"
    JSON    = "json"
    # Encoded data
    BASE64  = "base64"
    # Media and files
    IMAGE   = "image"
    AUDIO   = "audio"
    VIDEO   = "video"
    FILE    = "file"
    # UI-related types
    SELECT  = "select"

class WorkflowVariableFormat(str, Enum):
    BASE64 = "base64"
    URL    = "url"
    PATH   = "path"
    STREAM = "stream"

class WorkflowVariableConfig(BaseModel):
    name: Optional[str] = Field(default=None, description="The name of the variable")
    type: WorkflowVariableType = Field(..., description="Type of the variable")
    subtype: Optional[str] = Field(default=None, description="Subtype of the variable")
    format: Optional[WorkflowVariableFormat] = Field(default=None, description="Format of the variable")
    options: Optional[List[str]] = Field(default=None, description="List of valid options for select type")
    required: bool = Field(default=False, description="Whether this variable is required")
    default: Optional[Any] = Field(default=None, description="Default value if not provided")
    description: Optional[str] = Field(default=None, description="Description of the variable")

class WorkflowVariableGroupConfig(BaseModel):
    name: Optional[str] = Field(default=None, description="The name of the group of variables")
    variables: List[WorkflowVariableConfig] = Field(default_factory=list, description="List of variables included in this group")
    repeat_count: int = Field(default=1, description="The number of times this group of variables should be repeated")

class WorkflowConfig(BaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    jobs: Optional[Dict[str, JobConfig]] = Field(default_factory=dict)
    default: bool = False

    @model_validator(mode="before")
    def inflate_single_job(cls, values: Dict[str, Any]):
        if "jobs" not in values:
            job_keys = set(JobConfig.model_fields.keys())
            if any(k in values for k in job_keys):
                values["jobs"] = { "__default__": { k: values.pop(k) for k in job_keys if k in values } }
        return values
