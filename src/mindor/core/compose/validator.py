from typing import Dict, List, Set
from mindor.dsl.schema.compose import ComposeConfig
from mindor.dsl.schema.job.impl.component import ComponentJobConfig
from mindor.dsl.schema.action.impl.workflow import WorkflowActionConfig
from mindor.dsl.schema.listener.impl.http_trigger import HttpTriggerListenerConfig
from mindor.dsl.schema.component.impl.workflow import WorkflowComponentConfig

class ComposeValidator:
    def __init__(self, config: ComposeConfig):
        self.config = config
        self.errors: List[str] = []

    def validate(self) -> List[str]:
        self.errors = []

        self._validate_duplicate_component_ids()
        self._validate_duplicate_workflow_ids()
        self._validate_duplicate_job_ids()
        self._validate_component_references()
        self._validate_action_references()
        self._validate_workflow_references()
        self._validate_job_graphs()

        return self.errors

    def _validate_duplicate_component_ids(self):
        seen: Dict[str, int] = {}

        for component_index, component in enumerate(self.config.components):
            if component.id == "__component__":
                continue

            if component.id in seen:
                self.errors.append(
                    f"components[{component_index}].id: "
                    f"Duplicate component ID '{component.id}' "
                    f"(first seen at components[{seen[component.id]}])"
                )
            else:
                seen[component.id] = component_index

    def _validate_duplicate_workflow_ids(self):
        seen: Dict[str, int] = {}

        for workflow_index, workflow in enumerate(self.config.workflows):
            if workflow.id == "__workflow__":
                continue

            if workflow.id in seen:
                self.errors.append(
                    f"workflows[{workflow_index}].id: "
                    f"Duplicate workflow ID '{workflow.id}' "
                    f"(first seen at workflows[{seen[workflow.id]}])"
                )
            else:
                seen[workflow.id] = workflow_index

    def _validate_duplicate_job_ids(self):
        for workflow_index, workflow in enumerate(self.config.workflows):
            seen: Dict[str, int] = {}

            for job_index, job in enumerate(workflow.jobs):
                if job.id == "__job__":
                    continue

                if job.id in seen:
                    self.errors.append(
                        f"workflows[{workflow_index}].jobs[{job_index}].id: "
                        f"Duplicate job ID '{job.id}' in workflow '{workflow.id}'"
                    )
                else:
                    seen[job.id] = job_index

    def _validate_component_references(self):
        component_ids = { component.id for component in self.config.components}
        has_default_component = (
            len(self.config.components) == 1 or any(component.default for component in self.config.components)
        )

        for workflow_index, workflow in enumerate(self.config.workflows):
            for job_index, job in enumerate(workflow.jobs):
                if not isinstance(job, ComponentJobConfig):
                    continue

                if not isinstance(job.component, str):
                    continue

                if job.component == "__default__":
                    if not has_default_component:
                        self.errors.append(
                            f"workflows[{workflow_index}].jobs[{job_index}].component: "
                            f"Uses default component but multiple components exist "
                            f"and none has 'default: true'"
                        )
                else:
                    if job.component not in component_ids:
                        self.errors.append(
                            f"workflows[{workflow_index}].jobs[{job_index}].component: "
                            f"References non-existent component '{job.component}'"
                        )

    def _validate_action_references(self):
        component_map = { component.id: component for component in self.config.components }

        for workflow_index, workflow in enumerate(self.config.workflows):
            for job_index, job in enumerate(workflow.jobs):
                if not isinstance(job, ComponentJobConfig):
                    continue

                if isinstance(job.component, str):
                    component = component_map.get(job.component)
                    if component is None:
                        continue
                else:
                    component = job.component

                if job.action == "__default__":
                    has_default_action = (
                        len(component.actions) == 1 or any(action.default for action in component.actions)
                    )
                    if not has_default_action:
                        self.errors.append(
                            f"workflows[{workflow_index}].jobs[{job_index}].action: "
                            f"Uses default action but component '{component.id}' "
                            f"has multiple actions and none has 'default: true'"
                        )
                else:
                    action_ids = { action.id for action in component.actions }
                    if job.action not in action_ids:
                        self.errors.append(
                            f"workflows[{workflow_index}].jobs[{job_index}].action: "
                            f"References non-existent action '{job.action}' "
                            f"on component '{component.id}'"
                        )

    def _validate_workflow_references(self):
        workflow_ids = { workflow.id for workflow in self.config.workflows }
        has_default_workflow = (
            len(self.config.workflows) == 1
            or any(w.default for w in self.config.workflows)
        )

        for component_index, component in enumerate(self.config.components):
            if not isinstance(component, WorkflowComponentConfig):
                continue

            for action_index, action in enumerate(component.actions):
                if not isinstance(action, WorkflowActionConfig):
                    continue

                if action.workflow == "__default__":
                    if not has_default_workflow:
                        self.errors.append(
                            f"components[{component_index}].actions[{action_index}].workflow: "
                            f"Uses default workflow but multiple workflows exist "
                            f"and none has 'default: true'"
                        )
                else:
                    if action.workflow not in workflow_ids:
                        self.errors.append(
                            f"components[{component_index}].actions[{action_index}].workflow: "
                            f"References non-existent workflow '{action.workflow}'"
                        )

        for listener_index, listener in enumerate(self.config.listeners):
            if not isinstance(listener, HttpTriggerListenerConfig):
                continue

            for trigger_index, trigger in enumerate(listener.triggers):
                if trigger.workflow == "__default__":
                    if not has_default_workflow:
                        self.errors.append(
                            f"listeners[{listener_index}].triggers[{trigger_index}].workflow: "
                            f"Uses default workflow but multiple workflows exist "
                            f"and none has 'default: true'"
                        )
                else:
                    if trigger.workflow not in workflow_ids:
                        self.errors.append(
                            f"listeners[{listener_index}].triggers[{trigger_index}].workflow: "
                            f"References non-existent workflow '{trigger.workflow}'"
                        )

    def _validate_job_graphs(self):
        for workflow_index, workflow in enumerate(self.config.workflows):
            if not workflow.jobs:
                continue

            job_ids = { job.id for job in workflow.jobs }

            for job_index, job in enumerate(workflow.jobs):
                for dependency_id in job.depends_on:
                    if dependency_id == job.id:
                        self.errors.append(
                            f"workflows[{workflow_index}].jobs[{job_index}].depends_on: "
                            f"Job '{job.id}' depends on itself"
                        )
                        continue

                    if dependency_id not in job_ids:
                        self.errors.append(
                            f"workflows[{workflow_index}].jobs[{job_index}].depends_on: "
                            f"Job '{job.id}' references non-existent job '{dependency_id}'"
                        )
                        continue

                for target_job_id in job.get_routing_jobs():
                    if target_job_id not in job_ids:
                        self.errors.append(
                            f"workflows[{workflow_index}].jobs[{job_index}]: "
                            f"Routing target '{target_job_id}' does not exist "
                            f"in workflow '{workflow.id}'"
                        )

            entry_jobs = [ job for job in workflow.jobs if not job.depends_on ]
            if not entry_jobs:
                self.errors.append(
                    f"workflows[{workflow_index}]: "
                    f"Workflow '{workflow.id}' has no entry job "
                    f"(all jobs have depends_on)"
                )

            self._validate_no_cycles(workflow_index, workflow.id, { job.id: job for job in workflow.jobs })

    def _validate_no_cycles(self, workflow_index: int, workflow_id: str, job_map: dict):
        visiting: Set[str] = set()
        visited: Set[str] = set()

        def _detect_cycle(job_id: str):
            if job_id in visiting:
                self.errors.append(
                    f"workflows[{workflow_index}]: "
                    f"Dependency cycle detected involving job '{job_id}' "
                    f"in workflow '{workflow_id}'"
                )
                return

            if job_id in visited or job_id not in job_map:
                return

            visiting.add(job_id)

            for dependency_id in job_map[job_id].depends_on:
                _detect_cycle(dependency_id)

            visiting.remove(job_id)
            visited.add(job_id)

        for job in job_map.values():
            if job.id not in visited:
                _detect_cycle(job.id)
