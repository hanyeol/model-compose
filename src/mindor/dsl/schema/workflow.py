from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator, field_validator
from .job import JobConfig, JobType
from .utils.annotation import get_model_union_keys

class WorkflowVariableType(str, Enum):
    # Primitive data types
    STRING   = "string"
    TEXT     = "text"
    INTEGER  = "integer"
    NUMBER   = "number"
    BOOLEAN  = "boolean"
    JSON     = "json"
    OBJECTS  = "object[]"
    # Encoded data
    BASE64   = "base64"
    MARKDOWN = "markdown"
    # Media and files
    IMAGE    = "image"
    AUDIO    = "audio"
    VIDEO    = "video"
    FILE     = "file"
    # UI-related types
    SELECT   = "select"

class WorkflowVariableFormat(str, Enum):
    BASE64 = "base64"
    URL    = "url"
    PATH   = "path"
    STREAM = "stream"

class WorkflowVariableAnnotationConfig(BaseModel):
    name: str = Field(..., description="The name of the annotation.")
    value: str = Field(..., description="Description of the annotation.")

class WorkflowVariableConfig(BaseModel):
    name: Optional[str] = Field(default=None, description="The name of the variable.")
    type: WorkflowVariableType = Field(..., description="Type of the variable.")
    subtype: Optional[str] = Field(default=None, description="Subtype of the variable.")
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
    name: Optional[str] = Field(default=None)
    title: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    jobs: Dict[str, JobConfig] = Field(default_factory=dict)
    default: bool = Field(default=False)

    @model_validator(mode="before")
    def normalize_jobs(cls, values: Dict[str, Any]):
        values = cls.inflate_single_job(values)
        if "jobs" in values:
           cls.set_default_job_type(values["jobs"])
        return values

    @classmethod
    def inflate_single_job(cls, values: Dict[str, Any]):
        if "jobs" not in values:
            job_keys = set(get_model_union_keys(JobConfig))
            if any(k in values for k in job_keys):
                values["jobs"] = { "__default__": { k: values.pop(k) for k in job_keys if k in values } }
        return values
    
    @classmethod
    def set_default_job_type(cls, jobs: Dict[str, Any]):
        for job in jobs.values():
            if "type" not in job:
                job["type"] = JobType.ACTION
