from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from dataclasses import dataclass, asdict
from pydantic import BaseModel
from mindor.dsl.schema.workflow import WorkflowConfig, WorkflowVariableConfig, WorkflowVariableGroupConfig
from mindor.dsl.schema.job import ActionJobConfig
from mindor.dsl.schema.component import ComponentConfig
import re, json

@dataclass
class WorkflowVariableAnnotation:
    name: str
    value: str

@dataclass
class WorkflowVariable:
    name: Optional[str]
    type: str
    subtype: Optional[str]
    format: Optional[str]
    default: Optional[Any]
    annotations: Optional[List[WorkflowVariableAnnotation]]
    internal: bool

    def __eq__(self, other):
        if not isinstance(other, WorkflowVariable):
            return False
        if self.name is None or other.name is None:
            return False
        return self.name == other.name

    def __hash__(self):
        return hash(self.name) if self.name is not None else id(self)

@dataclass
class WorkflowVariableGroup:
    name: Optional[str]
    variables: List[WorkflowVariable]
    repeat_count: int

class WorkflowVariableResolver:
    def __init__(self):
        self.patterns: Dict[str, re.Pattern] = {
            "variable": re.compile(
                r"""\$\{                                                          # ${ 
                    (?:\s*([a-zA-Z_][^.\[\s]*))(?:\[([0-9]+)\])?                  # key: input, result[0], etc.
                    (?:\.([^\s|}]+))?                                             # path: key, key.path[0], etc.
                    (?:\s*as\s*([^\s/;}]+)(?:/([^\s;}]+))?(?:;([^\s}]+))?)?       # type/subtype;format
                    (?:\s*\|\s*((?:\$\{[^}]+\}|\\[$@{}]|(?!\s*(?:@\(|\$\{)).)+))? # default value after `|`
                    (?:\s*(@\(\s*[\w]+\s+(?:\\[$@{}]|(?!\s*\$\{).)+\)))?          # annotations
                \s*\}""",                                                         # }
                re.VERBOSE,
            ),
            "annotation": {
                "outer": re.compile(r"^@\(|\)$"),
                "delimiter": re.compile(r"\)\s+@\("),
                "inner": re.compile(r"([\w]+)\s+(.+)"),
            }
        }

    def _enumerate_input_variables(self, value: Any, wanted_key: str, internal: bool = False) -> List[WorkflowVariable]:
        if isinstance(value, str):
            variables: List[WorkflowVariable] = []

            for m in self.patterns["variable"].finditer(value):
                key, index, path, type, subtype, format, default, annotations = m.group(1, 2, 3, 4, 5, 6, 7, 8)

                if type and default:
                    default = self._parse_value_as_type(default, type)

                if annotations:
                    annotations = self._parse_annotations(annotations)

                if key == wanted_key:
                    variables.append(WorkflowVariable(
                        name=path, 
                        type=type or "string", 
                        subtype=subtype,
                        format=format,
                        default=default,
                        annotations=annotations,
                        internal=internal
                    ))

            return variables

        if isinstance(value, BaseModel):
            return self._enumerate_input_variables(value.model_dump(exclude_none=True), wanted_key, internal)
        
        if isinstance(value, dict):
            return sum([ self._enumerate_input_variables(v, wanted_key, internal) for v in value.values() ], [])

        if isinstance(value, list):
            return sum([ self._enumerate_input_variables(v, wanted_key, internal) for v in value ], [])
        
        return []

    def _enumerate_output_variables(self, name: Optional[str], value: Any, internal: bool = False) -> List[WorkflowVariable]:
        variables: List[WorkflowVariable] = []
        
        if isinstance(value, str):
            for m in self.patterns["variable"].finditer(value):
                key, index, path, type, subtype, format, default, annotations = m.group(1, 2, 3, 4, 5, 6, 7, 8)

                if type and default:
                    default = self._parse_value_as_type(default, type)

                if annotations:
                    annotations = self._parse_annotations(annotations)

                variables.append(WorkflowVariable(
                    name=name,
                    type=type or "string",
                    subtype=subtype,
                    format=format,
                    default=default,
                    annotations=annotations,
                    internal=internal
                ))
            
            return variables
        
        if isinstance(value, BaseModel):
            return self._enumerate_output_variables(name, value.model_dump(exclude_none=True), internal)
        
        if isinstance(value, dict):
            return sum([ self._enumerate_output_variables(f"{name}.{k}" if name else f"{k}", v, internal) for k, v in value.items() ], [])

        if isinstance(value, list):
            return sum([ self._enumerate_output_variables(f"{name}[{i}]" if name else f"[{i}]", v, internal) for i, v in enumerate(value) ], [])
        
        return []

    def _to_variable_config_list(self, variables: List[Union[WorkflowVariable, WorkflowVariableGroup]]) -> List[Union[WorkflowVariableConfig, WorkflowVariableGroupConfig]]:
        configs: List[Union[WorkflowVariableConfig, WorkflowVariableGroupConfig]] = []
        seen_single: Set[WorkflowVariable] = set()

        for item in variables:
            if isinstance(item, WorkflowVariableGroup):
                group: List[WorkflowVariableConfig] = []
                seen_in_group: Set[WorkflowVariable] = set()
                for variable in item.variables:
                    if variable not in seen_in_group:
                        group.append(self._to_variable_config(variable))
                        seen_in_group.add(variable)
                configs.append(WorkflowVariableGroupConfig(name=item.name, variables=group, repeat_count=item.repeat_count))
            else:
                if item not in seen_single:
                    configs.append(self._to_variable_config(item))
                    seen_single.add(item)

        return configs
    
    def _to_variable_config(self, variable: WorkflowVariable) -> WorkflowVariableConfig:
        config_dict = asdict(variable)

        if variable.type in [ "image", "audio", "video", "file", "select" ] and variable.subtype:
            config_dict["options"] = variable.subtype.split(",")
        
        if variable.annotations is None:
            config_dict["annotations"] = []

        return WorkflowVariableConfig(**config_dict)

    def _parse_value_as_type(self, value: Any, type: str) -> Any:
        if type == "integer":
            return int(value)
        
        if type == "number":
            return float(value)

        if type == "boolean":
            return str(value).lower() in [ "true", "1" ]
        
        if type == "json":
            return json.loads(value)
 
        return value
    
    def _parse_annotations(self, value: str) -> List[WorkflowVariableAnnotation]:
        parts: List[str] = re.split(self.patterns["annotation"]["delimiter"], re.sub(self.patterns["annotation"]["outer"], "", value))
        annotations: List[WorkflowVariableAnnotation] = []

        for part in parts:
            m = re.match(self.patterns["annotation"]["inner"], part.strip())
            
            if not m:
                continue

            name, value = m.group(1, 2)
            annotations.append(WorkflowVariableAnnotation(name=name, value=value))

        return annotations

class WorkflowInputVariableResolver(WorkflowVariableResolver):
    def resolve(self, workflow: WorkflowConfig, components: Dict[str, ComponentConfig]) -> List[WorkflowVariableConfig]:
        variables: List[WorkflowVariable] = []

        for job in workflow.jobs.values():
            if isinstance(job, ActionJobConfig) and (not job.input or job.input == "${input}"):
                action_id = job.action or "__default__"
                if isinstance(job.component, str):
                    component: Optional[ComponentConfig] = components[job.component] if job.component in components else None
                    if component:
                        action = component.actions[action_id] if action_id in component.actions else None
                        if action:
                            variables.extend(self._enumerate_input_variables(action, "input", internal=True))
                else:
                    action = job.component.actions[action_id] if action_id in job.component.actions else None
                    if action:
                        variables.extend(self._enumerate_input_variables(action, "input", internal=True))
            else:
                variables.extend(self._enumerate_input_variables(job, "input"))

        return self._to_variable_config_list(variables)

class WorkflowOutputVariableResolver(WorkflowVariableResolver):
    def resolve(self, workflow: WorkflowConfig, components: Dict[str, ComponentConfig]) -> List[Union[WorkflowVariableConfig, WorkflowVariableGroupConfig]]:
        variables: List[Union[WorkflowVariable, WorkflowVariableGroup]] = []

        for job_id, job in workflow.jobs.items():
            if not self._is_terminal_job(workflow, job_id):
                continue

            job_variables: List[WorkflowVariable] = variables
            repeat_count: int = job.repeat_count if isinstance(job.repeat_count, int) else 0

            if repeat_count != 1:
                variables.append(WorkflowVariableGroup(variables=(job_variables := []), repeat_count=repeat_count))

            if isinstance(job, ActionJobConfig) and (not job.output or job.output == "${output}"):
                action_id = job.action or "__default__"
                if isinstance(job.component, str):
                    component: Optional[ComponentConfig] = components[job.component] if job.component in components else None
                    if component:
                        action = component.actions[action_id] if action_id in component.actions else None
                        if action:
                            job_variables.extend(self._enumerate_output_variables(None, action.output, internal=True))
                else:
                    action = job.component.actions[action_id] if action_id in job.component.actions else None
                    if action:
                        job_variables.extend(self._enumerate_output_variables(None, action.output, internal=True))
            else:
                job_variables.extend(self._enumerate_output_variables(None, job.output))

        return self._to_variable_config_list(variables)

    def _is_terminal_job(self, workflow: WorkflowConfig, job_id: str) -> bool:
        return all(job_id not in job.depends_on for other_id, job in workflow.jobs.items() if other_id != job_id)

class WorkflowSchema:
    def __init__(
        self, 
        name: Optional[str], 
        title: Optional[str], 
        description: Optional[str], 
        input: List[WorkflowVariableConfig], 
        output: List[Union[WorkflowVariableConfig, WorkflowVariableGroupConfig]]
    ):
        self.name: str = name
        self.title: str = title
        self.description: Optional[str] = description
        self.input: List[WorkflowVariableConfig] = input
        self.output: List[Union[WorkflowVariableConfig, WorkflowVariableGroupConfig]] = output

def create_workflow_schema(workflows: Dict[str, WorkflowConfig], components: Dict[str, ComponentConfig]) -> Dict[str, WorkflowSchema]:
    schema: Dict[str, WorkflowSchema] = {}

    for workflow_id, workflow in workflows.items():
        schema[workflow_id] = WorkflowSchema(
            name=workflow.name,
            title=workflow.title, 
            description=workflow.description,
            input=WorkflowInputVariableResolver().resolve(workflow, components),
            output=WorkflowOutputVariableResolver().resolve(workflow, components)
        )

    return schema
