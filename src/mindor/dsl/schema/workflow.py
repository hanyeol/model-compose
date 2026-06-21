from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator, field_validator
from .job import JobConfig, JobType, DelayJobMode

class WorkflowVariableType(str, Enum):
    # Primitive data types
    STRING       = "string"
    TEXT         = "text"
    INTEGER      = "integer"
    NUMBER       = "number"
    BOOLEAN      = "boolean"
    LIST         = "list"
    OBJECT       = "object"
    JSON         = "json"
    # Encoded data
    BASE64       = "base64"
    MARKDOWN     = "markdown"
    # Media
    IMAGE        = "image"
    AUDIO        = "audio"
    VIDEO        = "video"
    FILE         = "file"
    # Streaming
    EVENT_STREAM = "event-stream"
    # UI-related types
    SELECT       = "select"
    # No output
    NONE         = "none"

class WorkflowVariableFormat(str, Enum):
    PATH     = "path"
    URL      = "url"
    DATA_URI = "data-uri"
    BASE64   = "base64"

class WorkflowVariableAnnotationConfig(BaseModel):
    name: str = Field(..., description="Name of the annotation.")
    value: str = Field(..., description="Description of the annotation.")

class WorkflowVariableConfig(BaseModel):
    name: Optional[str] = Field(default=None, description="The name of the variable.")
    type: WorkflowVariableType = Field(..., description="Type of the variable.")
    is_list: bool = Field(default=False, description="Whether the variable is a list of `type` (corresponds to the `[]` marker in DSL).")
    subtype: Optional[str] = Field(default=None, description="Subtype of the variable.")

    @model_validator(mode="before")
    def normalize_list_marker(cls, values: Any):
        if isinstance(values, dict):
            type_value = values.get("type")
            if isinstance(type_value, str) and type_value.endswith("[]"):
                values["type"] = type_value[:-2]
                values["is_list"] = True
        return values
    attrs: Optional[Dict[str, str]] = Field(default=None, description="Attributes of the variable (e.g. sample_rate, channels for pcm).")
    format: Optional[WorkflowVariableFormat] = Field(default=None, description="Format of the variable.")
    options: Optional[List[str]] = Field(default=None, description="List of valid options for file or select type.")
    required: bool = Field(default=False, description="Whether this variable is required.")
    default: Optional[Any] = Field(default=None, description="Default value if not provided.")
    annotations: List[WorkflowVariableAnnotationConfig] = Field(default_factory=list, description="Annotations of the variable.")
    internal: bool = Field(default=False, description="Whether this variable is for internal use.")

    def get_annotation_value(self, name: str) -> Optional[str]:
        if self.annotations:
            return next((annotation.value for annotation in self.annotations if annotation.name == name), None)
        return None

class WorkflowVariableGroupConfig(BaseModel):
    name: Optional[str] = Field(default=None, description="The name of the group of variables.")
    variables: List[WorkflowVariableConfig] = Field(default_factory=list, description="List of variables included in this group.")
    repeat_count: int = Field(default=1, description="The number of times this group of variables should be repeated.")

class WorkflowConfig(BaseModel):
    id: str = Field(default="__workflow__", description="ID of workflow.")
    name: Optional[str] = Field(default=None, description="Name of workflow.")
    title: Optional[str] = Field(default=None, description="Title of workflow.")
    description: Optional[str] = Field(default=None, description="Description of workflow.")
    jobs: List[JobConfig] = Field(default_factory=list, description="List of jobs that define the execution steps.")
    output: Optional[Any] = Field(default=None, description="The output data returned from this workflow. Accepts any type.")
    default: bool = Field(default=False, description="Whether this workflow should be used as the default.")
    private: bool = Field(default=False, description="Whether this workflow is private and should not be exposed externally.")

    @model_validator(mode="before")
    def normalize_jobs(cls, values: Dict[str, Any]):
        values = cls.inflate_single_job(values)
        if "jobs" in values:
           cls.fill_missing_job_type(values["jobs"])
           cls.fill_missing_delay_job_mode(values["jobs"])
        return values

    @classmethod
    def inflate_single_job(cls, values: Dict[str, Any]):
        if "jobs" not in values:
            job_values = values.pop("job", None)
            if job_values:
                values["jobs"] = [ job_values ]
        return values

    @classmethod
    def fill_missing_job_type(cls, jobs: List[Any]):
        for job in jobs:
            if "type" not in job:
                job["type"] = JobType.COMPONENT

    @classmethod
    def fill_missing_delay_job_mode(cls, jobs: List[Any]):
        for job in jobs:
            if job["type"] == "delay" and "mode" not in job:
                job["mode"] = DelayJobMode.TIME_INTERVAL

    @field_validator("id")
    def validate_id(cls, value):
        if value == "__default__":
            raise ValueError("Workflow id cannot be '__default__'")
        return value
