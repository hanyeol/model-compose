from typing import Union, Optional, Dict, List, Set, Tuple, Any
from mindor.dsl.schema.workflow import WorkflowConfig, WorkflowVariableConfig, WorkflowVariableGroupConfig
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.component.impl.agent import AgentComponentConfig
from mindor.dsl.schema.component.impl.workflow import WorkflowComponentConfig
from mindor.dsl.schema.job import ComponentJobConfig, ForEachJobConfig
from mindor.core.workflow.schema import WorkflowSchema
import json, zlib, base64

class WorkflowSchemaRenderer:
    def render(self, workflow: WorkflowSchema) -> str:
        schema: Dict[str, Any] = {
            "workflow_id": workflow.workflow_id,
            "title": workflow.title,
            "description": workflow.description,
            "input": [ self._render_variable(variable) for variable in workflow.input ],
            "output": [ self._render_variable(variable) for variable in workflow.output ],
        }
        return json.dumps({ k: v for k, v in schema.items() if v is not None }, indent=2, ensure_ascii=False)

    def _render_variable(self, variable: Union[WorkflowVariableConfig, WorkflowVariableGroupConfig]) -> Dict[str, Any]:
        if isinstance(variable, WorkflowVariableGroupConfig):
            return {
                "name": variable.name,
                "variables": [ self._render_variable(v) for v in variable.variables ],
                "repeat_count": variable.repeat_count,
            }
        return variable.model_dump(exclude_none=True, exclude_defaults=True)

class WorkflowFlowRenderer:
    def render(
        self,
        workflow_config: WorkflowConfig,
        workflow_configs: Dict[str, WorkflowConfig],
        component_configs: Dict[str, ComponentConfig]
    ) -> str:
        if not workflow_config.jobs:
            return "_No jobs defined._"

        diagram_lines: List[str] = [ "graph TD" ]
        referenced_workflows: Dict[str, Tuple[str, str]] = {}

        self._render_workflow_jobs(workflow_config, component_configs, workflow_configs, referenced_workflows, diagram_lines, prefix="")

        for workflow_id, (source_node, link_label) in referenced_workflows.items():
            sub_workflow = workflow_configs[workflow_id]

            if not sub_workflow.jobs:
                continue

            prefix = f"__w_{workflow_id}__"
            title = sub_workflow.title or workflow_id
            diagram_lines.append(f'    subgraph {prefix}["{title}<br/>(workflow)"]')
            diagram_lines.append("    direction TB")
            self._render_workflow_jobs(sub_workflow, component_configs, workflow_configs, referenced_workflows, diagram_lines, prefix=f"{prefix}_")
            diagram_lines.append("    end")
            diagram_lines.append(f"    {source_node} -. {link_label} .- {prefix}")

        diagram = "\n".join(diagram_lines)
        viewer_url = self._build_mermaid_viewer_url(diagram)

        return "\n".join([
            "```mermaid",
            diagram,
            "```",
            "",
            f'<a href="{viewer_url}" target="_blank" style="text-decoration: none;">🔍</a> <a href="{viewer_url}" target="_blank">Open in Mermaid Live Viewer</a>',
        ])

    def _render_workflow_jobs(
        self,
        workflow_config: WorkflowConfig,
        component_configs: Dict[str, ComponentConfig],
        workflow_configs: Dict[str, WorkflowConfig],
        referenced_workflows: Dict[str, Tuple[str, str]],
        lines: List[str],
        prefix: str
    ) -> None:
        job_ids: Set[str] = { job.id for job in workflow_config.jobs }
        routing_targets: Set[str] = set()

        input_node = f"{prefix}__input__"
        output_node = f"{prefix}__output__"

        for job in workflow_config.jobs:
            title = job.name or job.id
            label = f"{title}<br/>({job.type.value})"
            lines.append(f'    {prefix}{job.id}(("{label}"))')

        for job in workflow_config.jobs:
            component = self._resolve_job_component(job)

            if component is None:
                continue

            component_node = f"{prefix}__c_{job.id}__"
            lines.append(f'    {component_node}["{self._resolve_component_label(component, component_configs)}"]')
            lines.append(f"    {prefix}{job.id} --> {component_node}")
            lines.append(f"    {component_node} -.-> {prefix}{job.id}")

            for tool_workflow_id in self._resolve_agent_tool_workflows(component, component_configs, workflow_configs):
                if tool_workflow_id not in referenced_workflows:
                    referenced_workflows[tool_workflow_id] = (component_node, "tool")

            for target_workflow_id in self._resolve_workflow_component_workflows(component, component_configs, workflow_configs):
                if target_workflow_id not in referenced_workflows:
                    referenced_workflows[target_workflow_id] = (component_node, "invokes")

        for job in workflow_config.jobs:
            for target in job.get_routing_jobs():
                if target in job_ids:
                    routing_targets.add(target)
                    lines.append(f"    {prefix}{job.id} -.-> {prefix}{target}")

        for job in workflow_config.jobs:
            if not job.depends_on and job.id not in routing_targets:
                lines.append(f"    {input_node} --> {prefix}{job.id}")
            else:
                for dependent in job.depends_on:
                    if dependent in job_ids:
                        lines.append(f"    {prefix}{dependent} -.-> {prefix}{job.id}")

        dependents: Set[str] = { dependent for job in workflow_config.jobs for dependent in job.depends_on }

        for job in workflow_config.jobs:
            if job.id not in dependents and job.id not in routing_targets:
                lines.append(f"    {prefix}{job.id} --> {output_node}")

        lines.append(f"    {input_node}((Input))")
        lines.append(f"    {output_node}((Output))")

    def _resolve_job_component(self, job: Any) -> Optional[Union[str, ComponentConfig]]:
        if isinstance(job, ComponentJobConfig):
            return job.component

        if isinstance(job, ForEachJobConfig):
            return job.do.component

        return None

    def _resolve_component_config(self, component: Union[str, ComponentConfig], component_configs: Dict[str, ComponentConfig]) -> Optional[ComponentConfig]:
        if not isinstance(component, str):
            return component

        if component == "__default__":
            if len(component_configs) == 1:
                return next(iter(component_configs.values()))
            return next((config for config in component_configs.values() if config.default), None)

        return component_configs.get(component)

    def _resolve_component_label(self, component: Union[str, ComponentConfig], component_configs: Dict[str, ComponentConfig]) -> str:
        config = self._resolve_component_config(component, component_configs)

        if config is not None:
            return f"{config.id}<br/>({config.type.value})"

        return f"{component}<br/>(unknown)"

    def _resolve_agent_tool_workflows(
        self,
        component: Union[str, ComponentConfig],
        component_configs: Dict[str, ComponentConfig],
        workflow_configs: Dict[str, WorkflowConfig]
    ) -> List[str]:
        config = self._resolve_component_config(component, component_configs)

        if not isinstance(config, AgentComponentConfig):
            return []

        return [ tool for tool in config.tools if isinstance(tool, str) and tool in workflow_configs ]

    def _resolve_workflow_component_workflows(
        self,
        component: Union[str, ComponentConfig],
        component_configs: Dict[str, ComponentConfig],
        workflow_configs: Dict[str, WorkflowConfig]
    ) -> List[str]:
        config = self._resolve_component_config(component, component_configs)

        if not isinstance(config, WorkflowComponentConfig):
            return []

        return [ action.workflow for action in config.actions if action.workflow in workflow_configs ]

    def _build_mermaid_viewer_url(self, diagram: str) -> str:
        contents = json.dumps({
            "code": diagram,
            "mermaid": json.dumps({ "theme": "default" }),
        })
        compressed = zlib.compress(contents.encode("utf-8"), 9)
        encoded = base64.urlsafe_b64encode(compressed).decode("ascii").rstrip("=")
        return f"https://mermaid.live/view#pako:{encoded}"
