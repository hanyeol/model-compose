from typing import Optional, Union, Dict, List, Any
from mindor.dsl.schema.component import AgentComponentConfig, AgentModelConfig
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
        model_component: ComponentService,
        model_config: AgentModelConfig,
        tools: Dict[str, Union[WorkflowTool, ModelTool]],
        tool_schemas: List[Dict[str, Any]],
        instructions: Optional[str],
        max_iteration_count: int
    ):
        self.config: AgentActionConfig = config
        self.model_component: ComponentService = model_component
        self.model_config: AgentModelConfig = model_config
        self.tools: Dict[str, Union[WorkflowTool, ModelTool]] = tools
        self.tool_schemas: List[Dict[str, Any]] = tool_schemas
        self.instructions: Optional[str] = instructions
        self.max_iteration_count: int = max_iteration_count

    async def run(self, context: ComponentActionContext) -> Any:
        max_iteration_count = await context.render_scalar(self.config.max_iteration_count, int, self.max_iteration_count)
        streaming           = await context.render_variable(self.config.streaming)

        tools = self.tool_schemas if self.tool_schemas else None

        is_direct_output = not self.config.output or self.config.output == "${result}"

        initial_messages: List[Dict[str, Any]] = await self._build_initial_messages(context)
        messages: List[Dict[str, Any]] = []

        if streaming:
            async def _stream_message_generator():
                for _ in range(max_iteration_count):
                    input = await self._render_model_input(context, messages or initial_messages, tools)
                    response = await self.model_component.run(
                        self.model_config.action,
                        ulid.ulid(),
                        input,
                        workflow=context.workflow,
                        job_id=context.job_id
                    )
                    response = await self._render_model_response(context, response)

                    assistant_messages = await self._build_assistant_messages(response)
                    for assistant_message in assistant_messages:
                        messages.append(assistant_message)
                        await context.event_notifier.notify("internal", kind="message", output=assistant_message)
                        yield assistant_message

                    tool_calls = response.get("tool_calls")
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
                input = await self._render_model_input(context, messages or initial_messages, tools)
                response = await self.model_component.run(
                    self.model_config.action,
                    ulid.ulid(),
                    input,
                    workflow=context.workflow,
                    job_id=context.job_id
                )
                response = await self._render_model_response(context, response)

                assistant_messages = await self._build_assistant_messages(response)
                for assistant_message in assistant_messages:
                    messages.append(assistant_message)
                    await context.event_notifier.notify("internal", kind="message", output=assistant_message)

                tool_calls = response.get("tool_calls")
                if not tool_calls:
                    break

                tool_messages = await self._execute_tool_calls(tool_calls, context)
                for tool_message in tool_messages:
                    messages.append(tool_message)
                    await context.event_notifier.notify("internal", kind="tool", output=tool_message)

            context.register_source("result", messages)

            return (await context.render_variable(self.config.output)) if not is_direct_output else messages

    async def _build_initial_messages(self, context: ComponentActionContext) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = []

        if self.instructions:
            instructions = await context.render_variable(self.instructions)
            messages.extend(self._build_text_messages("system", instructions))

        if self.config.prompt:
            prompt = await context.render_variable(self.config.prompt)
            messages.extend(self._build_text_messages("user", prompt))

        return messages

    async def _build_assistant_messages(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        text = response.get("content")
        tool_calls = response.get("tool_calls") or []

        blocks: List[Dict[str, Any]] = []

        if text:
            blocks.append({ "type": "text", "text": text })

        for call in tool_calls:
            blocks.append({
                "type": "tool_call",
                "id": call.get("id", ""),
                "name": call.get("name", ""),
                "arguments": call.get("arguments", {}),
            })

        if not blocks:
            blocks.append({ "type": "text", "text": "" })

        return self._format_messages("assistant", blocks)

    async def _render_model_input(
        self,
        context: ComponentActionContext,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        context.register_source("messages", messages)

        if tools:
            context.register_source("tools", tools)

        return await context.render_variable(self.model_config.input)

    async def _render_model_response(
        self,
        context: ComponentActionContext,
        response: Any
    ) -> Any:
        if self.model_config.output:
            context.register_source("output", response)
            return await context.render_variable(self.model_config.output)

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

        workflow_blocks = iter(await self._execute_workflow_tool_calls(workflow_calls, context)) if workflow_calls else iter(())
        external_blocks = iter(await self._execute_external_tool_calls(external_calls, context)) if external_calls else iter(())

        blocks: List[Dict[str, Any]] = []
        for tool_call, tool_kind in zip(tool_calls, tool_kinds):
            if tool_kind == "workflow":
                blocks.append(next(workflow_blocks))
            elif tool_kind == "external":
                blocks.append(next(external_blocks))
            else:
                blocks.append({
                    "type": "tool_result",
                    "id": tool_call.get("id", ""),
                    "content": f"Error: Unknown tool '{tool_call.get('name', '')}'",
                    "is_error": True,
                })

        messages: List[Dict[str, Any]] = []
        for block in blocks:
            messages.extend(self._format_messages("tool", [block]))

        return messages

    async def _execute_workflow_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],
        context: ComponentActionContext
    ) -> List[Dict[str, Any]]:
        async def _execute_tool_call(tool_call: Dict[str, Any]) -> Dict[str, Any]:
            tool_name = tool_call["name"]
            tool_arguments = tool_call.get("arguments", {})
            call_id = tool_call.get("id", "")

            try:
                result = await self.tools[tool_name].function(**tool_arguments, context=context.workflow)
                content = json.dumps(result) if isinstance(result, (dict, list)) else str(result)

                return { "type": "tool_result", "id": call_id, "content": content }
            except Exception as e:
                return {
                    "type": "tool_result",
                    "id": call_id,
                    "content": f"{type(e).__name__}: {e}",
                    "is_error": True,
                }

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

        blocks: List[Dict[str, Any]] = []
        for tool_call in tool_calls:
            call_id = tool_call.get("id", "")
            if call_id in tool_results:
                result = tool_results[call_id]
                content = json.dumps(result) if isinstance(result, (dict, list)) else str(result)
                blocks.append({ "type": "tool_result", "id": call_id, "content": content })
            else:
                blocks.append({
                    "type": "tool_result",
                    "id": call_id,
                    "content": f"Error: no result provided for tool_call '{call_id}'",
                    "is_error": True,
                })

        return blocks

    def _build_text_messages(self, role: str, text: str) -> List[Dict[str, Any]]:
        return self._format_messages(role, [{ "type": "text", "text": text }])

    def _format_messages(self, role: str, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [ { "role": role, "blocks": blocks } ]

@register_component(ComponentType.AGENT)
class AgentComponent(ComponentService):
    config: AgentComponentConfig

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
        if context.workflow_delegate is None:
            workflow = create_workflow(*WorkflowResolver(self.global_configs.workflows).resolve(workflow_id), self.global_configs)
            task_id = context.task_id if context else ulid.ulid()
            interrupt_handler = context.interrupt_handler if context else None

            return await workflow.run(task_id, input, interrupt_handler)

        return await context.workflow_delegate(workflow_id, input, context.interrupt_handler)

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await AgentAction(
            action,
            self.model_component,
            self.config.model,
            self.tools,
            self.tool_schemas,
            self.config.instructions,
            self.config.max_iteration_count
        ).run(context)
