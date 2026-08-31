from typing import Type, Union, Literal, Optional, Dict, List, Set, Annotated, Any
from dataclasses import dataclass, asdict
from pydantic import BaseModel
from mindor.dsl.schema.workflow import WorkflowConfig, WorkflowVariableConfig, WorkflowVariableGroupConfig
from mindor.dsl.schema.job import JobConfig, InlineJobConfig, ComponentJobConfig, ForEachJobConfig, AccumulateJobConfig, PipelineJobConfig, OutputJobConfig, CompositeJobConfig
from mindor.dsl.schema.component import ComponentConfig, ComponentType
from mindor.dsl.schema.action import ActionConfig
from mindor.core.component import ComponentResolver, ActionResolver
from mindor.core.workflow import WorkflowResolver
import re, json

@dataclass
class WorkflowVariableAnnotation:
    name: str
    value: str

@dataclass
class WorkflowVariable:
    name: Optional[str]
    type: str
    is_list: bool
    subtype: Optional[str]
    attrs: Optional[Dict[str, str]]
    format: Optional[str]
    default: Optional[Any]
    annotations: Optional[List[WorkflowVariableAnnotation]]

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
    _TRANSFORM_OPERATOR_KEYS = { "*", "?", "+", "|" }

    def __init__(self):
        self.patterns: Dict[str, re.Pattern] = {
            "variable": re.compile(
                r"""\$\{                                                                                                # ${
                    (?:\s*([a-zA-Z_][^.\[\s]*(?:\[\])?))(?:\[(-?[0-9]+)\])?                                             # key: input, result[], result[0], result[-1], etc.
                    (?:\.([^\s|}]+))?                                                                                   # path: key, key.path[0], etc.
                    (?:\s*as\s*([^\s/;\[}]+)(\[\])?(?:/([^\s;\[}]+)(?:\[((?:\$\{[^}]*\}|[^\]])*)\])?)?(?:;([^\s}]+))?)? # type[]/subtype[attrs];format (attrs may contain nested ${...})
                    (?:\s*\|\s*((?:\$\{[^}]+\}|\\[$@{}]|(?!\s*(?:@\(|\$\{)).)+))?                                       # default value after `|`
                    (?:\s*(@\(\s*[\w]+\s+(?:\\[$@{}]|(?!\s*\$\{).)+\)))?                                                # annotations
                \s*\}""",                                                                                               # }
                re.VERBOSE,
            ),
            "annotation": {
                "outer": re.compile(r"^@\(|\)$"),
                "delimiter": re.compile(r"\)\s+@\("),
                "inner": re.compile(r"([\w]+)\s+(.+)"),
            }
        }

    def _enumerate_input_variables(self, value: Any, wanted_key: str) -> List[WorkflowVariable]:
        if isinstance(value, str):
            variables: List[WorkflowVariable] = []

            for m in self.patterns["variable"].finditer(value):
                key, index, path, type, is_list, subtype, attrs, format, default, annotations = m.group(1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
                is_list = bool(is_list)

                if attrs:
                    attrs = self._parse_attrs(attrs)

                if annotations:
                    annotations = self._parse_annotations(annotations)

                if default and type:
                    default = self._convert_value_to_type(default, type, is_list)

                if key == wanted_key:
                    variables.append(WorkflowVariable(
                        name=path,
                        type=type or "string",
                        is_list=is_list,
                        subtype=subtype,
                        attrs=attrs,
                        format=format,
                        default=default,
                        annotations=annotations,
                    ))

            return variables

        if isinstance(value, CompositeJobConfig):
            # Skip scope-isolated subtrees (e.g. pipeline `steps`) whose `${input}` refers to
            # the composite's own scope, not the enclosing workflow's `${input}`.
            excluded_fields = value.get_scope_isolated_fields()
            walkable_fields = [ name for name in value.__class__.model_fields if name not in excluded_fields ]
            return sum([ self._enumerate_input_variables(getattr(value, name), wanted_key) for name in walkable_fields ], [])

        if isinstance(value, BaseModel):
            return sum([ self._enumerate_input_variables(getattr(value, name), wanted_key) for name in value.__class__.model_fields ], [])

        if isinstance(value, dict):
            return sum([ self._enumerate_input_variables(v, wanted_key) for v in value.values() ], [])

        if isinstance(value, list):
            return sum([ self._enumerate_input_variables(v, wanted_key) for v in value ], [])

        return []

    def _enumerate_output_variables(self, name: Optional[str], value: Any) -> List[WorkflowVariable]:
        variables: List[WorkflowVariable] = []

        if isinstance(value, str):
            for match in self.patterns["variable"].finditer(value):
                variables.append(self._build_output_variable(name, match))
            return variables

        if isinstance(value, BaseModel):
            return self._enumerate_output_variables(name, value.model_dump(exclude_none=True))

        if isinstance(value, dict):
            if self._TRANSFORM_OPERATOR_KEYS & value.keys():
                # The whole dict is a DSL transformation (map/conditional/join/split), not a nested variable path.
                # Treat it as one variable at `name`, using the first referenced variable inside for type metadata.
                # For `*` map, the representative expression is entries["*"]["input"] (dict form) or entries["*"] itself.
                # Otherwise, fall back to the first variable found anywhere in the subtree.
                if "*" in value:
                    input = value["*"]["input"] if isinstance(value["*"], dict) and "input" in value["*"] else value["*"]
                    variables = self._enumerate_output_variables(None, input)
                else:
                    variables = sum([ self._enumerate_output_variables(None, v) for v in value.values() ], [])

                variable = variables[0] if variables else WorkflowVariable(
                    name=None,
                    type="string",
                    is_list=False,
                    subtype=None,
                    attrs=None,
                    format=None,
                    default=None,
                    annotations=None,
                )
                variable.name = name

                # A `*` map always yields a list, regardless of the inner expression's own list flag.
                if "*" in value:
                    variable.is_list = True

                return [ variable ]

            return sum([ self._enumerate_output_variables(f"{name}.{k}" if name else f"{k}", v) for k, v in value.items() ], [])

        if isinstance(value, list):
            return sum([ self._enumerate_output_variables(f"{name}[{i}]" if name else f"[{i}]", v) for i, v in enumerate(value) ], [])

        return []

    def _build_output_variable(self, name: Optional[str], match: re.Match) -> WorkflowVariable:
        key, index, path, type, is_list, subtype, attrs, format, default, annotations = match.group(1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
        is_list = bool(is_list)

        if attrs:
            attrs = self._parse_attrs(attrs)

        if annotations:
            annotations = self._parse_annotations(annotations)

        if default and type:
            default = self._convert_value_to_type(default, type, is_list)

        return WorkflowVariable(
            name=name,
            type=type or "string",
            is_list=is_list,
            subtype=subtype,
            attrs=attrs,
            format=format,
            default=default,
            annotations=annotations,
        )

    def _to_variable_config_list(self, variables: List[Union[WorkflowVariable, WorkflowVariableGroup]]) -> List[Union[WorkflowVariableConfig, WorkflowVariableGroupConfig]]:
        configs: List[Union[WorkflowVariableConfig, WorkflowVariableGroupConfig]] = []
        seen: Set[WorkflowVariable] = set()

        for item in variables:
            if isinstance(item, WorkflowVariableGroup):
                items: List[WorkflowVariableConfig] = []
                for config in self._to_variable_config_list(item.variables):
                    if isinstance(config, WorkflowVariableGroupConfig):
                        items.extend(config.variables)
                    else:
                        items.append(config)
                configs.append(WorkflowVariableGroupConfig(name=item.name, variables=items, repeat_count=item.repeat_count))
            elif item not in seen:
                if item.name is not None or len(configs) == 0:
                    configs.append(self._to_variable_config(item))
                seen.add(item)

        return configs
    
    def _to_variable_config(self, variable: WorkflowVariable) -> WorkflowVariableConfig:
        config_dict = asdict(variable)

        if variable.type in [ "select" ] and variable.subtype:
            config_dict["options"] = variable.subtype.split(",")

        if variable.annotations is None:
            config_dict["annotations"] = []

        return WorkflowVariableConfig(**config_dict)

    def _convert_value_to_type(self, value: str, type: str, is_list: bool) -> Any:
        if is_list:
            try:
                value = json.loads(self._quote_variable_references(value))
            except json.JSONDecodeError as e:
                raise ValueError(f"Expected a JSON list, but failed to parse: {e}") from e

            if not isinstance(value, list):
                raise ValueError(f"Expected a JSON list, got {type(value).__name__}")

            return value

        if type in [ "list", "object", "json" ]:
            try:
                value = json.loads(self._quote_variable_references(value))
            except json.JSONDecodeError as e:
                raise ValueError(f"Expected a JSON value, but failed to parse: {e}") from e

            if type == "list" and not isinstance(value, list):
                raise ValueError(f"Expected a JSON list, got {type(value).__name__}")

            if type == "object" and not isinstance(value, dict):
                raise ValueError(f"Expected a JSON object, got {type(value).__name__}")

            return value

        if type == "integer":
            return int(value)

        if type == "number":
            return float(value)

        if type == "boolean":
            return value.lower() in [ "true", "1" ]

        return value

    def _quote_variable_references(self, value: str) -> str:
        return self.patterns["variable"].sub(lambda m: '"' + m.group(0) + '"', value)

    def _parse_attrs(self, value: Optional[str]) -> Optional[Dict[str, str]]:
        attrs: Dict[str, str] = {}

        for pair in value.split(","):
            pair = pair.strip()
            if "=" in pair:
                k, _, v = pair.partition("=")
                attrs[k.strip()] = v.strip()

        return attrs

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
    def resolve(
        self,
        workflow: WorkflowConfig,
        workflows: List[WorkflowConfig],
        components: List[ComponentConfig]
    ) -> List[WorkflowVariableConfig]:
        return self._to_variable_config_list(self._resolve_workflow(workflow, workflows, components))

    def _resolve_workflow(
        self,
        workflow: WorkflowConfig,
        workflows: List[WorkflowConfig],
        components: List[ComponentConfig]
    ) -> List[WorkflowVariable]:
        variables: List[WorkflowVariable] = []

        for job in workflow.jobs:
            if isinstance(job, ComponentJobConfig) and (not job.input or job.input == "${input}"):
                variables.extend(self._resolve_job_component(job.component, job.action, workflows, components))
            else:
                variables.extend(self._enumerate_input_variables(job, "input"))

        if workflow.output is not None:
            variables.extend(self._enumerate_input_variables(workflow.output, "input"))

        return variables

    def _resolve_job_component(
        self,
        component: Union[str, ComponentConfig],
        action: str,
        workflows: List[WorkflowConfig],
        components: List[ComponentConfig]
    ) -> List[WorkflowVariable]:
        variables: List[WorkflowVariable] = []

        if isinstance(component, str):
            _, component = ComponentResolver(components).resolve(component, raise_on_error=False)
            if component:
                _, action = ActionResolver(component.actions).resolve(action, raise_on_error=False)
                if action:
                    variables.extend(self._resolve_component(component, action, workflows, components))
        else:
            _, action = ActionResolver(component.actions).resolve(action, raise_on_error=False)
            if action:
                variables.extend(self._resolve_component(component, action, workflows, components))

        return variables

    def _resolve_component(
        self,
        component: ComponentConfig,
        action: ActionConfig,
        workflows: List[WorkflowConfig],
        components: List[ComponentConfig]
    ) -> List[WorkflowVariable]:
        variables: List[WorkflowVariable] = []

        if component.type == ComponentType.WORKFLOW and (not action.input or action.input == "${input}"):
            _, workflow = WorkflowResolver(workflows).resolve(action.workflow, raise_on_error=False)
            if workflow:
                variables.extend(self._resolve_workflow(workflow, workflows, components))
            else:
                variables.extend(self._enumerate_input_variables(action, "input"))
        else:
            variables.extend(self._enumerate_input_variables(action, "input"))

        return variables

class WorkflowOutputVariableResolver(WorkflowVariableResolver):
    def resolve(
        self,
        workflow: WorkflowConfig,
        workflows: List[WorkflowConfig],
        components: List[ComponentConfig]
    ) -> List[WorkflowVariableConfig]:
        return self._to_variable_config_list(self._resolve_workflow(workflow, workflows, components))

    def _resolve_workflow(
        self,
        workflow: WorkflowConfig,
        workflows: List[WorkflowConfig],
        components: List[ComponentConfig],
    ) -> List[Union[WorkflowVariableConfig, WorkflowVariableGroupConfig]]:
        variables: List[Union[WorkflowVariable, WorkflowVariableGroup]] = []

        if workflow.output is None:
            for job in workflow.jobs:
                if not self._is_terminal_job(workflow, job.id):
                    continue

                job_variables: List[WorkflowVariable] = variables
                repeat_count: int = job.repeat_count if isinstance(job, ComponentJobConfig) and isinstance(job.repeat_count, int) else 0

                if repeat_count > 1:
                    variables.append(WorkflowVariableGroup(name=job.name or job.id, variables=(job_variables := []), repeat_count=repeat_count))

                if isinstance(job, ComponentJobConfig) and (not job.output or job.output == "${output}"):
                    job_variables.extend(self._resolve_job_component(job.component, job.action, workflows, components))
                elif isinstance(job, CompositeJobConfig) and (not job.output or job.output == "${output}"):
                    job_variables.extend(self._resolve_composite_job_output(job, workflows, components))
                else:
                    if isinstance(job, OutputJobConfig):
                        job_variables.extend(self._enumerate_output_variables(None, job.output))
        else:
            variables.extend(self._enumerate_output_variables(None, workflow.output))

        if not variables:
            variables.append(self._any_variable())

        return variables

    def _resolve_composite_job_output(
        self,
        job: CompositeJobConfig,
        workflows: List[WorkflowConfig],
        components: List[ComponentConfig]
    ) -> List[Union[WorkflowVariable, WorkflowVariableGroup]]:
        if isinstance(job, ForEachJobConfig):
            inline_variables = self._resolve_inline_job_output(job.do, workflows, components) or [ self._any_variable() ]
            return [ WorkflowVariableGroup(name=job.name or job.id, variables=inline_variables, repeat_count=0) ]

        if isinstance(job, AccumulateJobConfig):
            return self._resolve_inline_job_output(job.do, workflows, components) or [ self._any_variable() ]

        if isinstance(job, PipelineJobConfig):
            return self._resolve_inline_job_output(job.steps[-1], workflows, components) or [ self._any_variable() ]

        return []

    def _resolve_inline_job_output(
        self,
        job: InlineJobConfig,
        workflows: List[WorkflowConfig],
        components: List[ComponentConfig]
    ) -> List[Union[WorkflowVariable, WorkflowVariableGroup]]:
        if job.output and job.output != "${output}":
            return list(self._enumerate_output_variables(None, job.output))

        if isinstance(job, ComponentJobConfig):
            return self._resolve_job_component(job.component, job.action, workflows, components)

        if isinstance(job, (ForEachJobConfig, AccumulateJobConfig)):
            return self._resolve_inline_job_output(job.do, workflows, components)

        if isinstance(job, PipelineJobConfig):
            return self._resolve_inline_job_output(job.steps[-1], workflows, components)

        return []

    def _resolve_job_component(
        self,
        component: Union[str, ComponentConfig],
        action: str,
        workflows: List[WorkflowConfig],
        components: List[ComponentConfig]
    ) -> List[Union[WorkflowVariable, WorkflowVariableGroup]]:
        variables: List[Union[WorkflowVariable, WorkflowVariableGroup]] = []

        if isinstance(component, str):
            _, component = ComponentResolver(components).resolve(component, raise_on_error=False)
            if component:
                _, action = ActionResolver(component.actions).resolve(action, raise_on_error=False)
                if action:
                    variables.extend(self._resolve_component(component, action, workflows, components))
        else:
            _, action = ActionResolver(component.actions).resolve(action, raise_on_error=False)
            if action:
                variables.extend(self._resolve_component(component, action, workflows, components))

        return variables

    def _resolve_component(
        self,
        component: ComponentConfig,
        action: ActionConfig,
        workflows: List[WorkflowConfig],
        components: List[ComponentConfig]
    ) -> List[Union[WorkflowVariable, WorkflowVariableGroup]]:
        variables: List[Union[WorkflowVariable, WorkflowVariableGroup]] = []

        if component.type == ComponentType.WORKFLOW:
            _, workflow = WorkflowResolver(workflows).resolve(action.workflow, raise_on_error=False)
            if workflow:
                variables.extend(self._resolve_workflow(workflow, workflows, components))
            else:
                variables.extend(self._enumerate_output_variables(None, action.output))
        else:
            variables.extend(self._enumerate_output_variables(None, action.output))

        return variables

    def _is_terminal_job(self, workflow: WorkflowConfig, job_id: str) -> bool:
        return all(job_id not in self._flatten_job_depends_on(job) for job in workflow.jobs if job.id != job_id)

    def _flatten_job_depends_on(self, job: JobConfig) -> List[str]:
        return [ job_id for item in job.depends_on for job_id in (item if isinstance(item, list) else [ item ]) ]

    def _any_variable(self) -> WorkflowVariable:
        return WorkflowVariable(
            name=None,
            type="any",
            is_list=False,
            subtype=None,
            attrs=None,
            format=None,
            default=None,
            annotations=None,
        )

class WorkflowSchema:
    def __init__(
        self,
        workflow_id: str,
        name: Optional[str],
        title: Optional[str],
        description: Optional[str],
        input: List[WorkflowVariableConfig],
        output: List[Union[WorkflowVariableConfig, WorkflowVariableGroupConfig]],
        default: bool,
        private: bool = False
    ):
        self.workflow_id: str = workflow_id
        self.name: Optional[str] = name
        self.title: Optional[str] = title
        self.description: Optional[str] = description
        self.input: List[WorkflowVariableConfig] = input
        self.output: List[Union[WorkflowVariableConfig, WorkflowVariableGroupConfig]] = output
        self.default: bool = default
        self.private: bool = private

def create_workflow_schemas(workflows: List[WorkflowConfig], components: List[ComponentConfig], exclude_private: bool = False) -> Dict[str, WorkflowSchema]:
    schema: Dict[str, WorkflowSchema] = {}

    for workflow in workflows:
        if exclude_private and workflow.private:
            continue
        schema[workflow.id] = WorkflowSchema(
            workflow_id=workflow.id,
            name=workflow.name,
            title=workflow.title,
            description=workflow.description,
            input=WorkflowInputVariableResolver().resolve(workflow, workflows, components),
            output=WorkflowOutputVariableResolver().resolve(workflow, workflows, components),
            default=workflow.default,
            private=workflow.private
        )

    return schema
