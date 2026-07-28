from typing import Dict, List
from mindor.dsl.schema.compose import ComposeConfig
from mindor.dsl.schema.action.impl.workflow import WorkflowActionConfig
from mindor.dsl.schema.listener.impl.http_trigger import HttpTriggerListenerConfig
from mindor.dsl.schema.component.impl.workflow import WorkflowComponentConfig
from mindor.core.workflow.validator import WorkflowValidator

class ComposeValidator:
    def __init__(self, config: ComposeConfig):
        self.config = config
        self.errors: List[str] = []

    def validate(self) -> List[str]:
        self.errors = []

        self._validate_duplicate_component_ids()
        self._validate_duplicate_workflow_ids()
        self._validate_workflow_references()
        self._validate_workflows()

        return self.errors

    def _validate_duplicate_component_ids(self):
        seen: set = set()

        for component in self.config.components:
            if component.id == "__component__":
                continue

            if component.id in seen:
                self.errors.append(
                    f"component '{component.id}'.id: "
                    f"Duplicate component ID '{component.id}'"
                )
            else:
                seen.add(component.id)

    def _validate_duplicate_workflow_ids(self):
        seen: set = set()

        for workflow in self.config.workflows:
            if workflow.id == "__workflow__":
                continue

            if workflow.id in seen:
                self.errors.append(
                    f"workflow '{workflow.id}'.id: "
                    f"Duplicate workflow ID '{workflow.id}'"
                )
            else:
                seen.add(workflow.id)

    def _validate_workflow_references(self):
        workflow_ids = { workflow.id for workflow in self.config.workflows }
        has_default_workflow = (
            len(self.config.workflows) == 1 or any(workflow.default for workflow in self.config.workflows)
        )

        for component in self.config.components:
            if not isinstance(component, WorkflowComponentConfig):
                continue

            for action in component.actions:
                if not isinstance(action, WorkflowActionConfig):
                    continue

                if action.workflow == "__default__":
                    if not has_default_workflow:
                        self.errors.append(
                            f"component '{component.id}'.action '{action.id}'.workflow: "
                            f"Uses default workflow but multiple workflows exist "
                            f"and none has 'default: true'"
                        )
                else:
                    if action.workflow not in workflow_ids:
                        self.errors.append(
                            f"component '{component.id}'.action '{action.id}'.workflow: "
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

    def _validate_workflows(self):
        for workflow in self.config.workflows:
            self.errors.extend(WorkflowValidator(workflow, self.config.components).validate())
