from typing import Union, Optional, Dict, List, Set, Tuple, Any
from mindor.dsl.schema.workflow import WorkflowConfig, WorkflowVariableConfig, WorkflowVariableGroupConfig
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.component.impl.agent import AgentComponentConfig
from mindor.dsl.schema.component.impl.workflow import WorkflowComponentConfig
from mindor.dsl.schema.job import JobConfig, ComponentJobConfig, ForEachJobConfig, PipelineJobConfig, AccumulateJobConfig
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
        return json.dumps({ key: value for key, value in schema.items() if value is not None }, indent=2, ensure_ascii=False)

    def _render_variable(self, variable: Union[WorkflowVariableConfig, WorkflowVariableGroupConfig]) -> Dict[str, Any]:
        if isinstance(variable, WorkflowVariableGroupConfig):
            return {
                "name": variable.name,
                "variables": [ self._render_variable(variable) for variable in variable.variables ],
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
        subgraph_workflows: Dict[str, Tuple[str, str]] = {}

        workflow_lines = self._render_workflow_graph(
            workflow_config,
            component_configs,
            workflow_configs,
            subgraph_workflows,
            prefix="",
        )
        diagram_lines.extend(workflow_lines)

        rendered_workflows: Set[str] = set()
        while rendered_workflows != subgraph_workflows.keys():
            for workflow_id, (source_node, link_label) in list(subgraph_workflows.items()):
                if workflow_id in rendered_workflows:
                    continue

                rendered_workflows.add(workflow_id)
                workflow = workflow_configs[workflow_id]

                if not workflow.jobs:
                    continue

                prefix = f"__w_{workflow_id}__"
                title = workflow.title or workflow_id
                diagram_lines.append(f'    subgraph {prefix}["{title}<br/>(workflow)"]')
                diagram_lines.append("    direction TB")
                workflow_lines = self._render_workflow_graph(
                    workflow,
                    component_configs,
                    workflow_configs,
                    subgraph_workflows,
                    prefix=f"{prefix}_",
                )
                diagram_lines.extend(workflow_lines)
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

    def _render_workflow_graph(
        self,
        workflow_config: WorkflowConfig,
        component_configs: Dict[str, ComponentConfig],
        workflow_configs: Dict[str, WorkflowConfig],
        subgraph_workflows: Dict[str, Tuple[str, str]],
        prefix: str
    ) -> List[str]:
        job_ids: Set[str] = { job.id for job in workflow_config.jobs }
        routing_targets: Set[str] = set()
        workflow_lines: List[str] = []

        input_node = f"{prefix}__input__"
        output_node = f"{prefix}__output__"

        for job in workflow_config.jobs:
            title = job.name or job.id
            label = f"{title}<br/>({job.type.value})"
            workflow_lines.append(f'    {prefix}{job.id}(("{label}"))')

        for job in workflow_config.jobs:
            job_lines = self._render_job_graph(
                job,
                f"{prefix}{job.id}",
                prefix,
                component_configs,
                workflow_configs,
                subgraph_workflows,
            )
            workflow_lines.extend(job_lines)

        for job in workflow_config.jobs:
            for target in job.get_routing_jobs():
                if target in job_ids:
                    routing_targets.add(target)
                    workflow_lines.append(f"    {prefix}{job.id} --> {prefix}{target}")

        for job in workflow_config.jobs:
            if not job.depends_on and job.id not in routing_targets:
                workflow_lines.append(f"    {input_node} --> {prefix}{job.id}")
                continue

            for or_group_index, item in enumerate(job.depends_on):
                if isinstance(item, list):
                    dependency_job_ids = [ job_id for job_id in item if job_id in job_ids ]

                    if not dependency_job_ids:
                        continue

                    if len(dependency_job_ids) == 1:
                        workflow_lines.append(f"    {prefix}{dependency_job_ids[0]} --> {prefix}{job.id}")
                        continue

                    merge_node = f"{prefix}__any_{job.id}_{or_group_index}__"
                    workflow_lines.append(f'    {merge_node}{{"any"}}')

                    for job_id in dependency_job_ids:
                        workflow_lines.append(f"    {prefix}{job_id} --> {merge_node}")

                    workflow_lines.append(f"    {merge_node} --> {prefix}{job.id}")
                elif item in job_ids:
                    workflow_lines.append(f"    {prefix}{item} --> {prefix}{job.id}")

        dependency_job_ids: Set[str] = { dependency for job in workflow_config.jobs for dependency in self._flatten_job_depends_on(job) }

        for job in workflow_config.jobs:
            if job.id not in dependency_job_ids and job.id not in routing_targets:
                workflow_lines.append(f"    {prefix}{job.id} --> {output_node}")

        workflow_lines.append(f"    {input_node}((Input))")
        workflow_lines.append(f"    {output_node}((Output))")

        return workflow_lines

    def _render_job_graph(
        self,
        job: JobConfig,
        parent_node: str,
        prefix: str,
        component_configs: Dict[str, ComponentConfig],
        workflow_configs: Dict[str, WorkflowConfig],
        subgraph_workflows: Dict[str, Tuple[str, str]],
    ) -> List[str]:
        if isinstance(job, ComponentJobConfig):
            return self._render_component(
                parent_node,
                "",
                "",
                job.component,
                component_configs,
                workflow_configs,
                subgraph_workflows,
            )

        job_lines: List[str] = []

        for inline_id, inline_label, inline_job in self._resolve_inline_jobs(job, parent_node):
            if isinstance(inline_job, ComponentJobConfig):
                component_lines = self._render_component(
                    parent_node,
                    inline_id,
                    inline_label,
                    inline_job.component,
                    component_configs,
                    workflow_configs,
                    subgraph_workflows,
                )
                job_lines.extend(component_lines)
            else:
                inline_lines = self._render_inline_job(
                    inline_job,
                    parent_node,
                    inline_id,
                    inline_label,
                    component_configs,
                    workflow_configs,
                    subgraph_workflows,
                )
                job_lines.extend(inline_lines)

        return job_lines

    def _render_inline_job(
        self,
        job: JobConfig,
        parent_node: str,
        inline_id: str,
        inline_label: str,
        component_configs: Dict[str, ComponentConfig],
        workflow_configs: Dict[str, WorkflowConfig],
        subgraph_workflows: Dict[str, Tuple[str, str]],
    ) -> List[str]:
        subgraph_label = f"{inline_label}<br/>(inline)" if inline_label else "inline"
        job_node = f"{inline_id}_job"
        inline_lines: List[str] = []

        inline_lines.append(f'    subgraph {inline_id}["{subgraph_label}"]')
        inline_lines.append("    direction TB")
        inline_lines.append(f'    {job_node}(("{job.type.value}"))')
        job_lines = self._render_job_graph(
            job,
            job_node,
            inline_id,
            component_configs,
            workflow_configs,
            subgraph_workflows,
        )
        inline_lines.extend(job_lines)
        inline_lines.append("    end")
        inline_lines.append(f"    {parent_node} -.-> {inline_id}")
        inline_lines.append(f"    {inline_id} -.-> {parent_node}")

        return inline_lines

    def _render_component(
        self,
        parent_node: str,
        inline_id: str,
        inline_label: str,
        component: Union[str, ComponentConfig],
        component_configs: Dict[str, ComponentConfig],
        workflow_configs: Dict[str, WorkflowConfig],
        subgraph_workflows: Dict[str, Tuple[str, str]],
    ) -> List[str]:
        component_node = f"{parent_node}__c_{inline_id}__" if inline_id else f"{parent_node}__c__"
        component_label = self._resolve_component_label(component, component_configs)
        if inline_label:
            component_label = f"{inline_label}<br/>{component_label}"
        component_lines: List[str] = [
            f'    {component_node}["{component_label}"]',
            f"    {parent_node} -.-> {component_node}",
            f"    {component_node} -.-> {parent_node}",
        ]

        for tool_workflow_id in self._resolve_agent_tool_workflows(component, component_configs, workflow_configs):
            if tool_workflow_id not in subgraph_workflows:
                subgraph_workflows[tool_workflow_id] = (component_node, "tool")

        for target_workflow_id in self._resolve_workflow_component_workflows(component, component_configs, workflow_configs):
            if target_workflow_id not in subgraph_workflows:
                subgraph_workflows[target_workflow_id] = (component_node, "invokes")

        return component_lines

    def _resolve_inline_jobs(self, job: JobConfig, parent_node: str) -> List[Tuple[str, str, JobConfig]]:
        if isinstance(job, (ForEachJobConfig, AccumulateJobConfig)):
            return [ (f"{parent_node}_do", "", job.do) ]

        if isinstance(job, PipelineJobConfig):
            return [ (f"{parent_node}_step_{index}", f"step {index}", step) for index, step in enumerate(job.steps) ]

        return []

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

    def _flatten_job_depends_on(self, job: JobConfig) -> List[str]:
        return [ job_id for item in job.depends_on for job_id in (item if isinstance(item, list) else [ item ]) ]
