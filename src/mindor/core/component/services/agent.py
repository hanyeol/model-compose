from typing import Optional, Union, Dict, List, Any
from mindor.dsl.schema.component import AgentComponentConfig
from mindor.dsl.schema.action import ActionConfig, AgentActionConfig
from mindor.dsl.schema.common.model.tool import ModelTool
from mindor.core.component import ComponentService, ComponentGlobalConfigs
from mindor.core.workflow import WorkflowResolver, WorkflowContext, create_workflow
from mindor.core.workflow.interrupt import InterruptPoint
from mindor.core.workflow.tool import WorkflowToolGenerator, WorkflowTool
from mindor.core.workflow.schema import create_workflow_schemas
from ..base import ComponentType, register_component
from ..context import ComponentActionContext
import asyncio, ulid, json

class AgentAction:
    def __init__(
        self,
        config: AgentActionConfig,
        component_config: AgentComponentConfig,
        model_component: ComponentService,
        tools: Dict[str, Union[WorkflowTool, ModelTool]],
        tool_schemas: List[Dict[str, Any]]
    ):
        self.config: AgentActionConfig = config
        self.component_config: AgentComponentConfig = component_config
        self.model_component: ComponentService = model_component
        self.tools: Dict[str, Union[WorkflowTool, ModelTool]] = tools
        self.tool_schemas: List[Dict[str, Any]] = tool_schemas

    async def run(self, context: ComponentActionContext) -> Any:
        max_iteration_count = await context.render_variable(self.config.max_iteration_count) if self.config.max_iteration_count else None
        streaming           = await context.render_variable(self.config.streaming)

        max_iteration_count = max_iteration_count or self.component_config.max_iteration_count
        tools = self.tool_schemas if self.tool_schemas else None

        initial_messages: List[Dict[str, Any]] = await self._build_initial_messages(context)
        messages: List[Dict[str, Any]] = []

        if streaming:
            async def _stream_message_generator():
                for _ in range(max_iteration_count):
                    model_input = await self._render_model_input(context, messages or initial_messages, tools)
                    response = await self.model_component.run(self.component_config.model.action, ulid.ulid(), model_input, workflow=context.workflow, job_id=context.job_id)
                    response = await self._render_model_response(context, response)

                    assistant_message = await self._build_assistant_message(response)
                    messages.append(assistant_message)
                    await context.event_notifier.notify("internal", kind="message", output=assistant_message)
                    yield assistant_message

                    tool_calls = self._extract_tool_calls(response)
                    if not tool_calls:
                        break

                    tool_messages = await self._execute_tool_calls(tool_calls, context)
                    for tool_message in tool_messages:
                        messages.append(tool_message)
                        await context.event_notifier.notify("internal", kind="tool", output=tool_message)
                        yield tool_message

            return _stream_message_generator()
        else:
            for _ in range(max_iteration_count):
                model_input = await self._render_model_input(context, messages or initial_messages, tools)
                response = await self.model_component.run(self.component_config.model.action, ulid.ulid(), model_input, workflow=context.workflow, job_id=context.job_id)
                response = await self._render_model_response(context, response)

                assistant_message = await self._build_assistant_message(response)
                messages.append(assistant_message)
                await context.event_notifier.notify("internal", kind="message", output=assistant_message)

                tool_calls = self._extract_tool_calls(response)
                if not tool_calls:
                    break

                tool_messages = await self._execute_tool_calls(tool_calls, context)
                for tool_message in tool_messages:
                    messages.append(tool_message)
                    await context.event_notifier.notify("internal", kind="tool", output=tool_message)

            context.register_source("result", messages)

            return (await context.render_variable(self.config.output)) if self.config.output else messages

    async def _build_initial_messages(self, context: ComponentActionContext) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = []

        if self.component_config.instructions:
            instructions = await context.render_variable(self.component_config.instructions)
            messages.append({ "role": "system", "content": instructions })

        if self.config.prompt:
            prompt = await context.render_variable(self.config.prompt)
            messages.append({ "role": "user", "content": prompt })

        return messages

    async def _build_assistant_message(self, response: Any) -> Dict[str, Any]:
        if isinstance(response, dict):
            message: Dict[str, Any] = { "role": "assistant" }
            if "content" in response:
                message["content"] = response["content"]
            if "tool_calls" in response:
                message["tool_calls"] = response["tool_calls"]
            return message

        return { "role": "assistant", "content": str(response) }

    async def _render_model_input(
        self,
        context: ComponentActionContext,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        context.register_source("messages", messages)

        if tools:
            context.register_source("tools", tools)

        return await context.render_variable(self.component_config.model.input)

    async def _render_model_response(
        self,
        context: ComponentActionContext,
        response: Any
    ) -> Any:
        if self.component_config.model.output:
            context.register_source("response", response)
            return await context.render_variable(self.component_config.model.output)

        return response

    async def _execute_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],
        context: ComponentActionContext
    ) -> List[Dict[str, Any]]:
        tool_kinds: List[str] = []
        workflow_calls: List[Dict[str, Any]] = []
        external_calls: List[Dict[str, Any]] = []

        for tool_call in tool_calls:
            tool = self.tools.get(tool_call.get("name", ""))
            if isinstance(tool, WorkflowTool):
                tool_kinds.append("workflow")
                workflow_calls.append(tool_call)
            elif isinstance(tool, ModelTool):
                tool_kinds.append("external")
                external_calls.append(tool_call)
            else:
                tool_kinds.append("unknown")

        workflow_messages = iter(await self._execute_workflow_tool_calls(workflow_calls, context)) if workflow_calls else iter(())
        external_messages = iter(await self._execute_external_tool_calls(external_calls, context)) if external_calls else iter(())

        messages: List[Dict[str, Any]] = []
        for tool_call, tool_kind in zip(tool_calls, tool_kinds):
            if tool_kind == "workflow":
                messages.append(next(workflow_messages))
            elif tool_kind == "external":
                messages.append(next(external_messages))
            else:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.get("id", ""),
                    "content": f"Error: Unknown tool '{tool_call.get('name', '')}'"
                })

        return messages

    async def _execute_workflow_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],
        context: ComponentActionContext
    ) -> List[Dict[str, Any]]:
        async def _execute_tool_call(tool_call: Dict[str, Any]) -> Dict[str, Any]:
            tool_name = tool_call["name"]
            tool_arguments = tool_call.get("arguments", {})

            if isinstance(tool_arguments, str):
                tool_arguments = json.loads(tool_arguments)

            result = await self.tools[tool_name].function(**tool_arguments, context=context.workflow)
            content = json.dumps(result) if isinstance(result, (dict, list)) else str(result)

            return { "role": "tool", "tool_call_id": tool_call.get("id", ""), "content": content }

        return list(await asyncio.gather(*[ _execute_tool_call(tool_call) for tool_call in tool_calls ]))

    async def _execute_external_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],
        context: ComponentActionContext
    ) -> List[Dict[str, Any]]:
        # NOTE: Reuses the enclosing ComponentJob's job_id/run_id and phase="after".
        # If the same job also declares a static `interrupt.after` in its config,
        # the two points collide on the same (task_id, job_id, run_id, phase) key
        # in InterruptHandler._points — do not mix them.
        future = asyncio.get_running_loop().create_future()
        point = InterruptPoint(
            task_id=context.workflow.task_id,
            job_id=context.job_id,
            run_id=context.run_id,
            phase="after",
            message="Agent is waiting for tool results.",
            metadata={
                "kind": "tool_calls",
                "tool_calls": [
                    {
                        "id": tool_call.get("id", ""),
                        "name": tool_call.get("name", ""),
                        "arguments": tool_call.get("arguments", {})
                    }
                    for tool_call in tool_calls
                ]
            },
            future=future
        )

        answer = await context.workflow.interrupt_handler.interrupt(point)
        tool_results = answer if isinstance(answer, dict) else {}

        messages: List[Dict[str, Any]] = []
        for tool_call in tool_calls:
            call_id = tool_call.get("id", "")
            if call_id in tool_results:
                result = tool_results[call_id]
                content = json.dumps(result) if isinstance(result, (dict, list)) else str(result)
            else:
                content = f"Error: no result provided for tool_call '{call_id}'"
            messages.append({ "role": "tool", "tool_call_id": call_id, "content": content })

        return messages

    def _extract_content(self, response: Any) -> Any:
        if isinstance(response, dict):
            return response.get("content", response)

        return response

    def _extract_tool_calls(self, response: Any) -> Optional[List[Dict[str, Any]]]:
        if isinstance(response, dict):
            return response.get("tool_calls")

        return None

@register_component(ComponentType.AGENT)
class AgentComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: AgentComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.model_component: Optional[ComponentService] = None
        self.tools: Optional[Dict[str, Union[WorkflowTool, ModelTool]]] = None
        self.tool_schemas: Optional[List[Dict[str, Any]]] = None

    async def _start(self) -> None:
        self.model_component = self._create_component(self.config.model.component)
        self.tools, self.tool_schemas = await self._generate_tools()

        await super()._start()

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await AgentAction(action, self.config, self.model_component, self.tools, self.tool_schemas).run(context)

    async def _generate_tools(self) -> tuple[Dict[str, Union[WorkflowTool, ModelTool]], List[Dict[str, Any]]]:
        workflow_schemas = create_workflow_schemas(self.global_configs.workflows, self.global_configs.components)
        tools: Dict[str, Union[WorkflowTool, ModelTool]] = {}
        tool_schemas: List[Dict[str, Any]] = []

        for tool in self.config.tools:
            if isinstance(tool, str):
                if tool not in workflow_schemas:
                    raise LookupError(f"Workflow not found for tool: {tool}")

                workflow = workflow_schemas[tool]
                workflow_tool = WorkflowToolGenerator().generate(tool, workflow, self._run_workflow)
                tool_name = workflow.name or tool

                if tool_name in tools:
                    raise ValueError(f"Duplicate tool name '{tool_name}' in agent tools.")

                tools[tool_name] = workflow_tool
                tool_schemas.append(workflow_tool.as_model_tool(tool_name).model_dump(exclude_none=True))
            elif isinstance(tool, ModelTool):
                if tool.name in tools:
                    raise ValueError(f"Duplicate tool name '{tool.name}' in agent tools.")

                tools[tool.name] = tool
                tool_schemas.append(tool.model_dump(exclude_none=True))
            else:
                raise TypeError(f"Unsupported tool entry type: {type(tool).__name__}")

        return tools, tool_schemas

    async def _run_workflow(self, workflow_id: str, input: Any, context: Optional[WorkflowContext] = None) -> Any:
        workflow = create_workflow(*WorkflowResolver(self.global_configs.workflows).resolve(workflow_id), self.global_configs)
        task_id = context.task_id if context else ulid.ulid()
        interrupt_handler = context.interrupt_handler if context else None

        return await workflow.run(task_id, input, interrupt_handler)
