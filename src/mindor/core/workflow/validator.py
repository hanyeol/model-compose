from typing import Dict, List, Set
from mindor.dsl.schema.workflow import WorkflowConfig
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.job import JobConfig
from mindor.dsl.schema.job.impl.component import ComponentJobConfig

class WorkflowValidator:
    def __init__(self, workflow: WorkflowConfig, components: List[ComponentConfig]):
        self.workflow: WorkflowConfig = workflow
        self.components: Dict[str, ComponentConfig] = { component.id: component for component in components }
        self.errors: List[str] = []

    def validate(self) -> List[str]:
        self.errors = []

        if self.workflow.jobs:
            self._validate_duplicate_job_ids()
            self._validate_component_references()
            self._validate_action_references()
            self.errors.extend(JobGraphValidator(self.workflow.jobs, self.workflow.id).validate())

        return self.errors

    def _validate_duplicate_job_ids(self) -> None:
        seen: Set[str] = set()

        for job in self.workflow.jobs:
            if job.id == "__job__":
                continue

            if job.id in seen:
                self.errors.append(
                    f"workflow '{self.workflow.id}'.job '{job.id}'.id: "
                    f"Duplicate job ID '{job.id}'"
                )
            else:
                seen.add(job.id)

    def _validate_component_references(self) -> None:
        has_default_component = (
            len(self.components) == 1 or any(component.default for component in self.components.values())
        )

        for job in self.workflow.jobs:
            if not isinstance(job, ComponentJobConfig):
                continue

            if not isinstance(job.component, str):
                continue

            if job.component == "__default__":
                if not has_default_component:
                    self.errors.append(
                        f"workflow '{self.workflow.id}'.job '{job.id}'.component: "
                        f"Uses default component but multiple components exist "
                        f"and none has 'default: true'"
                    )
            else:
                if job.component not in self.components:
                    self.errors.append(
                        f"workflow '{self.workflow.id}'.job '{job.id}'.component: "
                        f"References non-existent component '{job.component}'"
                    )

    def _validate_action_references(self) -> None:
        for job in self.workflow.jobs:
            if not isinstance(job, ComponentJobConfig):
                continue

            if isinstance(job.component, str):
                component = self.components.get(job.component)
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
                        f"workflow '{self.workflow.id}'.job '{job.id}'.action: "
                        f"Uses default action but component '{component.id}' "
                        f"has multiple actions and none has 'default: true'"
                    )
            else:
                action_ids = { action.id for action in component.actions }
                if job.action not in action_ids:
                    self.errors.append(
                        f"workflow '{self.workflow.id}'.job '{job.id}'.action: "
                        f"References non-existent action '{job.action}' "
                        f"on component '{component.id}'"
                    )

class JobGraphValidator:
    def __init__(self, jobs: List[JobConfig], workflow_id: str):
        self.jobs: Dict[str, JobConfig] = { job.id: job for job in jobs }
        self.workflow_id: str = workflow_id
        self.errors: List[str] = []

    def validate(self) -> List[str]:
        self.errors = []

        self._validate_job_references()
        self._validate_entry_job_exists()
        self._validate_no_dependency_cycles()

        return self.errors

    def _validate_job_references(self) -> None:
        for job in self.jobs.values():
            for dependency_id in self._flatten_job_depends_on(job):
                if dependency_id == job.id:
                    self.errors.append(
                        f"workflow '{self.workflow_id}'.job '{job.id}'.depends_on: "
                        f"Job '{job.id}' depends on itself"
                    )
                    continue

                if dependency_id not in self.jobs:
                    self.errors.append(
                        f"workflow '{self.workflow_id}'.job '{job.id}'.depends_on: "
                        f"Job '{job.id}' references non-existent job '{dependency_id}'"
                    )
                    continue

            for target_job_id in job.get_routing_jobs():
                if target_job_id not in self.jobs:
                    self.errors.append(
                        f"workflow '{self.workflow_id}'.job '{job.id}': "
                        f"Routing target '{target_job_id}' does not exist"
                    )

    def _validate_entry_job_exists(self) -> None:
        entry_jobs = [ job for job in self.jobs.values() if not job.depends_on ]

        if not entry_jobs:
            self.errors.append(
                f"workflow '{self.workflow_id}': "
                f"has no entry job (all jobs have depends_on)"
            )

    def _validate_no_dependency_cycles(self) -> None:
        visiting: Set[str] = set()
        visited: Set[str] = set()

        def _detect_cycle(job_id: str):
            if job_id in visiting:
                self.errors.append(
                    f"workflow '{self.workflow_id}': "
                    f"Dependency cycle detected involving job '{job_id}'"
                )
                return

            if job_id in visited or job_id not in self.jobs:
                return

            visiting.add(job_id)

            for dependency_id in self._flatten_job_depends_on(self.jobs[job_id]):
                _detect_cycle(dependency_id)

            visiting.remove(job_id)
            visited.add(job_id)

        for job in self.jobs.values():
            if job.id not in visited:
                _detect_cycle(job.id)

    def _flatten_job_depends_on(self, job: JobConfig) -> List[str]:
        return [ job_id for item in job.depends_on for job_id in (item if isinstance(item, list) else [ item ]) ]
