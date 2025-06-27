from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel
from mindor.dsl.schema.workflow import WorkflowConfig, WorkflowVariableConfig
from mindor.dsl.schema.component import ComponentConfig
import re, json, io

class WorkflowVariableResolver:
    def __init__(self):
        self.patterns: Dict[str, re.Pattern] = {
            "variable": re.compile(
                r"""\$\{                                                             # ${ 
                    ([a-zA-Z_][^.\s]*)                                               # key: input, env, etc.
                    (?:\.([^\s\|\}]+))?                                              # path: key, key.path[0], etc.
                    (?:\s*as\s*([^\s\|\}/;]+)(?:/([^\s\|\};]+))?(?:;([^\s\|\}]+))?)? # type/subtype;format
                    (?:\s*\|\s*([^\}]+))?                                            # default value after `|`
                \}""",                                                               # }
                re.VERBOSE,
            )
        }

    def _enumerate_input_variables(self, value: Any, wanted_key: str) -> List[Tuple[str, str, str, Optional[Any]]]:
        if isinstance(value, str):
            variables: List[Tuple[str, str, str, str, Optional[Any]]] = []

            for match in self.patterns["variable"].finditer(value):
                key, path, type, subtype, format, default = match.group(1, 2, 3, 4, 5, 6)

                if type and default:
                    default = self._convert_type(default, type, subtype, format)

                if key == wanted_key:
                    variables.append((path, type or "string", subtype, format, default))

            return variables

        if isinstance(value, BaseModel):
            return self._enumerate_input_variables(value.model_dump(exclude_none=True), wanted_key)
        
        if isinstance(value, dict):
            return sum([ self._enumerate_input_variables(v, wanted_key) for v in value.values() ], [])

        if isinstance(value, list):
            return sum([ self._enumerate_input_variables(v, wanted_key) for v in value ], [])
        
        return []

    def _enumerate_output_variables(self, key: str, value: Any) -> List[Tuple[str, str, str, Optional[Any]]]:
        variables: List[Tuple[str, str, str, str, Optional[Any]]] = []
        
        if isinstance(value, str):
            for match in self.patterns["variable"].finditer(value):
                type, subtype, format, default = match.group(3, 4, 5, 6)

                if type and default:
                    default = self._convert_type(default, type, subtype, format)

                variables.append((key, type or "string", subtype, format, default))
            
            return variables
        
        if isinstance(value, BaseModel):
            return self._enumerate_output_variables(key, value.model_dump(exclude_none=True))
        
        if isinstance(value, dict):
            return sum([ self._enumerate_output_variables(f"{key}.{k}" if key else f"{k}", v) for k, v in value.items() ], [])

        if isinstance(value, list):
            return sum([ self._enumerate_output_variables(f"{key}[{i}]" if key else f"[{i}]", v) for i, v in enumerate(value) ], [])
        
        return []        

    def _convert_type(self, value: Any, type: str, subtype: str, format: Optional[str]) -> Any:
        if type == "number":
            return float(value)
        
        if type == "integer":
            return int(value)
        
        if type == "boolean":
            return str(value).lower() in [ "true", "1" ]
        
        if type == "json":
            return json.loads(value)
 
        return value

class WorkflowInputResolver(WorkflowVariableResolver):
    def resolve(self, workflow: WorkflowConfig, components: Dict[str, ComponentConfig]) -> List[WorkflowVariableConfig]:
        variables: List[Tuple[str, str, Optional[Any]]] = []

        for job in workflow.jobs.values():
            if not job.input or job.input == "${input}":
                action_id = job.action or "__default__"
                if isinstance(job.component, str):
                    component: Optional[ComponentConfig] = components[job.component] if job.component in components else None
                    if component:
                        variables.extend(self._enumerate_input_variables(component.actions[action_id], "input"))
                else:
                    variables.extend(self._enumerate_input_variables(job.component.actions[action_id], "input"))
            else:
                variables.extend(self._enumerate_input_variables(job.input, "input"))

        return [ WorkflowVariableConfig(name=name, type=type, subtype=subtype, format=format, default=default) for name, type, subtype, format, default in set(variables) ]

class WorkflowOutputResolver(WorkflowVariableResolver):
    def resolve(self, workflow: WorkflowConfig, components: Dict[str, ComponentConfig]) -> List[WorkflowVariableConfig]:
        variables: List[Tuple[str, str, str, Optional[Any]]] = []
        
        for job_id, job in workflow.jobs.items():
            if not self._is_terminal_job(workflow, job_id):
                continue
            
            if not job.output or job.output == "${output}":
                action_id = job.action or "__default__"
                if isinstance(job.component, str):
                    component: Optional[ComponentConfig] = components[job.component] if job.component in components else None
                    if component:
                        variables.extend(self._enumerate_output_variables(None, component.actions[action_id].output))
                else:
                    variables.extend(self._enumerate_output_variables(None, job.component.actions[action_id].output))
            else:
                variables.extend(self._enumerate_output_variables(None, job.output))

        return [ WorkflowVariableConfig(name=name, type=type, subtype=subtype, format=format, default=default) for name, type, subtype, format, default in set(variables) ]

    def _is_terminal_job(self, workflow: WorkflowConfig, job_id: str) -> bool:
        return all(job_id not in job.depends_on for other_id, job in workflow.jobs.items() if other_id != job_id)

class WorkflowSchema:
    def __init__(self, name: str, title: str, description: Optional[str], input: List[WorkflowVariableConfig], output: List[WorkflowVariableConfig]):
        self.name: str = name
        self.title: str = title
        self.description: Optional[str] = description
        self.input: List[WorkflowVariableConfig] = input
        self.output: List[WorkflowVariableConfig] = output
