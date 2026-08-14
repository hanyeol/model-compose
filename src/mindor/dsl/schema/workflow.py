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
    STREAM       = "stream"
    # UI-related types
    SELECT       = "select"
    # Fallback for unresolved schemas
    ANY          = "any"
    # No output
    NONE         = "none"

class WorkflowVariableFormat(str, Enum):
    PATH     = "path"
    URL      = "url"
    DATA_URI = "data-uri"
    BASE64   = "base64"

class WorkflowVariableAnnotationConfig(BaseModel):
    name: str = Field(..., description="Name of the annotation.")
    value: str = Field(..., description="Value assigned to the annotation.")

class WorkflowVariableConfig(BaseModel):
    name: Optional[str] = Field(default=None, description="Name of the workflow variable.")
    type: WorkflowVariableType = Field(..., description="Type of the workflow variable.")
    is_list: bool = Field(default=False, description="Whether the variable holds a list of `type` (matches the `[]` marker in DSL).")
    subtype: Optional[str] = Field(default=None, description="Refined subtype narrowing the variable's `type`.")

    @model_validator(mode="before")
    def normalize_list_marker(cls, values: Any):
        if isinstance(values, dict):
            type_value = values.get("type")
            if isinstance(type_value, str) and type_value.endswith("[]"):
                values["type"] = type_value[:-2]
                values["is_list"] = True
        return values
    attrs: Optional[Dict[str, str]] = Field(default=None, description="Type-specific attributes for the variable (e.g., sample_rate, channels for pcm).")
    format: Optional[WorkflowVariableFormat] = Field(default=None, description="Encoding format applied to the variable's value (e.g., path, url, data-uri, base64).")
    options: Optional[List[str]] = Field(default=None, description="Allowed values for the variable when `type` is `file` or `select`.")
    required: bool = Field(default=False, description="Whether the variable must be supplied.")
    default: Optional[Any] = Field(default=None, description="Default value used when the variable is not supplied.")
    annotations: List[WorkflowVariableAnnotationConfig] = Field(default_factory=list, description="Custom annotations attached to the variable.")

    def get_annotation_value(self, name: str) -> Optional[str]:
        if self.annotations:
            return next((annotation.value for annotation in self.annotations if annotation.name == name), None)
        return None

class WorkflowVariableGroupConfig(BaseModel):
    name: Optional[str] = Field(default=None, description="Name of the variable group.")
    variables: List[WorkflowVariableConfig] = Field(default_factory=list, description="Variables that belong to this group.")
    repeat_count: int = Field(default=1, description="Number of times the variable group is repeated.")

class WorkflowConfig(BaseModel):
    id: str = Field(default="__workflow__", description="ID of workflow.")
    name: Optional[str] = Field(default=None, description="Name of workflow.")
    title: Optional[str] = Field(default=None, description="Title of workflow shown in the Web UI and docs.")
    description: Optional[str] = Field(default=None, description="Human-readable description of what the workflow does.")
    jobs: List[JobConfig] = Field(default_factory=list, description="Jobs that make up the workflow's execution steps.")
    output: Optional[Any] = Field(default=None, description="Output mapping that transforms and extracts values from the workflow's result.")
    default: bool = Field(default=False, description="Whether to use this workflow when none is explicitly selected.")
    private: bool = Field(default=False, description="Whether the workflow is hidden from external clients.")

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
