from typing import Dict, List, Set
from mindor.dsl.schema.compose import ComposeConfig
from mindor.dsl.schema.job.impl.action import ActionJobConfig
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
        for i, component in enumerate(self.config.components):
            cid = component.id
            if cid == "__component__":
                continue
            if cid in seen:
                self.errors.append(
                    f"components[{i}].id: Duplicate component ID '{cid}' (first seen at components[{seen[cid]}])"
                )
            else:
                seen[cid] = i

    def _validate_duplicate_workflow_ids(self):
        seen: Dict[str, int] = {}
        for i, workflow in enumerate(self.config.workflows):
            wid = workflow.id
            if wid == "__workflow__":
                continue
            if wid in seen:
                self.errors.append(
                    f"workflows[{i}].id: Duplicate workflow ID '{wid}' (first seen at workflows[{seen[wid]}])"
                )
            else:
                seen[wid] = i

    def _validate_duplicate_job_ids(self):
        for wi, workflow in enumerate(self.config.workflows):
            seen: Dict[str, int] = {}
            for ji, job in enumerate(workflow.jobs):
                jid = job.id
                if jid == "__job__":
                    continue
                if jid in seen:
                    self.errors.append(
                        f"workflows[{wi}].jobs[{ji}].id: Duplicate job ID '{jid}' in workflow '{workflow.id}'"
                    )
                else:
                    seen[jid] = ji

    def _validate_component_references(self):
        component_ids = {c.id for c in self.config.components}
        has_default = (
            len(self.config.components) == 1
            or any(c.default for c in self.config.components)
        )

        for wi, workflow in enumerate(self.config.workflows):
            for ji, job in enumerate(workflow.jobs):
                if not isinstance(job, ActionJobConfig):
                    continue
                if not isinstance(job.component, str):
                    continue

                comp_ref = job.component
                if comp_ref == "__default__":
                    if not has_default and len(self.config.components) > 1:
                        self.errors.append(
                            f"workflows[{wi}].jobs[{ji}].component: Uses default component but multiple components exist and none has 'default: true'"
                        )
                elif comp_ref not in component_ids:
                    self.errors.append(
                        f"workflows[{wi}].jobs[{ji}].component: References non-existent component '{comp_ref}'"
                    )

    def _validate_action_references(self):
        component_map = {c.id: c for c in self.config.components}

        for wi, workflow in enumerate(self.config.workflows):
            for ji, job in enumerate(workflow.jobs):
                if not isinstance(job, ActionJobConfig):
                    continue

                action_ref = job.action
                if action_ref == "__default__":
                    continue

                if isinstance(job.component, str):
                    if job.component == "__default__":
                        continue
                    component = component_map.get(job.component)
                    if component is None:
                        continue
                else:
                    component = job.component

                action_ids = {a.id for a in component.actions}
                if action_ref not in action_ids:
                    self.errors.append(
                        f"workflows[{wi}].jobs[{ji}].action: References non-existent action '{action_ref}' on component '{component.id}'"
                    )

    def _validate_workflow_references(self):
        workflow_ids = {w.id for w in self.config.workflows}
        has_default = (
            len(self.config.workflows) == 1
            or any(w.default for w in self.config.workflows)
        )

        for ci, component in enumerate(self.config.components):
            if not isinstance(component, WorkflowComponentConfig):
                continue
            for ai, action in enumerate(component.actions):
                if not isinstance(action, WorkflowActionConfig):
                    continue
                wf_ref = action.workflow
                if wf_ref == "__default__":
                    if not has_default and len(self.config.workflows) > 1:
                        self.errors.append(
                            f"components[{ci}].actions[{ai}].workflow: Uses default workflow but multiple workflows exist and none has 'default: true'"
                        )
                elif wf_ref not in workflow_ids:
                    self.errors.append(
                        f"components[{ci}].actions[{ai}].workflow: References non-existent workflow '{wf_ref}'"
                    )

        for li, listener in enumerate(self.config.listeners):
            if not isinstance(listener, HttpTriggerListenerConfig):
                continue
            for ti, trigger in enumerate(listener.triggers):
                wf_ref = trigger.workflow
                if wf_ref == "__default__":
                    if not has_default and len(self.config.workflows) > 1:
                        self.errors.append(
                            f"listeners[{li}].triggers[{ti}].workflow: Uses default workflow but multiple workflows exist and none has 'default: true'"
                        )
                elif wf_ref not in workflow_ids:
                    self.errors.append(
                        f"listeners[{li}].triggers[{ti}].workflow: References non-existent workflow '{wf_ref}'"
                    )

    def _validate_job_graphs(self):
        for wi, workflow in enumerate(self.config.workflows):
            if not workflow.jobs:
                continue

            job_ids = {job.id for job in workflow.jobs}

            for ji, job in enumerate(workflow.jobs):
                for dep_id in job.depends_on:
                    if dep_id == job.id:
                        self.errors.append(
                            f"workflows[{wi}].jobs[{ji}].depends_on: Job '{job.id}' depends on itself"
                        )
                    elif dep_id not in job_ids:
                        self.errors.append(
                            f"workflows[{wi}].jobs[{ji}].depends_on: Job '{job.id}' references non-existent job '{dep_id}'"
                        )

                for target_id in job.get_routing_jobs():
                    if target_id not in job_ids:
                        self.errors.append(
                            f"workflows[{wi}].jobs[{ji}]: Routing target '{target_id}' does not exist in workflow '{workflow.id}'"
                        )

            entry_jobs = [j for j in workflow.jobs if not j.depends_on]
            if not entry_jobs:
                self.errors.append(
                    f"workflows[{wi}]: Workflow '{workflow.id}' has no entry job (all jobs have depends_on)"
                )

            self._validate_no_cycles(wi, workflow.id, {j.id: j for j in workflow.jobs})

    def _validate_no_cycles(self, wi: int, workflow_id: str, job_map: dict):
        visiting: Set[str] = set()
        visited: Set[str] = set()

        def dfs(job_id: str):
            if job_id in visiting:
                self.errors.append(
                    f"workflows[{wi}]: Dependency cycle detected involving job '{job_id}' in workflow '{workflow_id}'"
                )
                return
            if job_id in visited or job_id not in job_map:
                return
            visiting.add(job_id)
            for dep_id in job_map[job_id].depends_on:
                dfs(dep_id)
            visiting.remove(job_id)
            visited.add(job_id)

        for job_id in job_map:
            if job_id not in visited:
                dfs(job_id)
