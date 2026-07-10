from typing import Optional, Dict, List, Any
from mindor.dsl.schema.component import AgentComponentConfig
from mindor.dsl.schema.action import ActionConfig, AgentActionConfig
from mindor.core.component import ComponentService, ComponentGlobalConfigs
from mindor.core.workflow import Workflow, WorkflowResolver, create_workflow
from mindor.core.workflow.tool import WorkflowToolGenerator, WorkflowTool
from mindor.core.workflow.schema import create_workflow_schemas
from ...base import ComponentType, register_component
from ...context import ComponentActionContext
import asyncio, ulid, json

class AgentAction:
    def __init__(
        self,
        config: AgentActionConfig,
        component_config: AgentComponentConfig,
        model_component: ComponentService,
        tools: Dict[str, WorkflowTool],
        tool_schemas: List[Dict[str, Any]]
    ):
        self.config: AgentActionConfig = config
        self.component_config: AgentComponentConfig = component_config
        self.model_component: ComponentService = model_component
        self.tools: Dict[str, WorkflowTool] = tools
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
                    response = await self.model_component.run(self.component_config.model.action, ulid.ulid(), model_input)
                    response = await self._render_model_response(context, response)

                    assistant_message = await self._build_assistant_message(response)
                    messages.append(assistant_message)
                    await context.event_notifier.notify("internal", kind="message", output=assistant_message)
                    yield assistant_message

                    tool_calls = self._extract_tool_calls(response)
                    if not tool_calls:
                        break

                    tool_messages = await asyncio.gather(*[self._execute_tool_call(tc, context) for tc in tool_calls])
                    for tool_message in tool_messages:
                        messages.append(tool_message)
                        await context.event_notifier.notify("internal", kind="tool", output=tool_message)
                        yield tool_message

            return _stream_message_generator()
        else:
            for _ in range(max_iteration_count):
                model_input = await self._render_model_input(context, messages or initial_messages, tools)
                response = await self.model_component.run(self.component_config.model.action, ulid.ulid(), model_input)
                response = await self._render_model_response(context, response)

                assistant_message = await self._build_assistant_message(response)
                messages.append(assistant_message)
                await context.event_notifier.notify("internal", kind="message", output=assistant_message)

                tool_calls = self._extract_tool_calls(response)
                if not tool_calls:
                    break

                tool_messages = await asyncio.gather(*[ self._execute_tool_call(tool_call, context) for tool_call in tool_calls ])
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

    async def _execute_tool_call(self, tool_call: Dict[str, Any], context: ComponentActionContext) -> Dict[str, Any]:
        tool_name = tool_call["name"]
        tool_arguments = tool_call.get("arguments", {})

        if isinstance(tool_arguments, str):
            tool_arguments = json.loads(tool_arguments)

        if tool_name in self.tools:
            result = await self.tools[tool_name].function(**tool_arguments, context=context.workflow)
            content = json.dumps(result) if isinstance(result, (dict, list)) else str(result)
        else:
            content = f"Error: Unknown tool '{tool_name}'"

        return { "role": "tool", "tool_call_id": tool_call.get("id", ""), "content": content }

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
        self.tools: Optional[Dict[str, WorkflowTool]] = None
        self.tool_schemas: Optional[List[Dict[str, Any]]] = None

    async def _start(self) -> None:
        self.model_component = self._create_component(self.config.model.component)
        self.tools = await self._generate_tools()
        self.tool_schemas = [ tool.as_model_tool(name).model_dump(exclude_none=True) for name, tool in self.tools.items() ]

        await super()._start()

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await AgentAction(action, self.config, self.model_component, self.tools, self.tool_schemas).run(context)

    async def _generate_tools(self) -> Dict[str, WorkflowTool]:
        workflow_schemas = create_workflow_schemas(self.global_configs.workflows, self.global_configs.components)
        tools: Dict[str, WorkflowTool] = {}

        for workflow_id in self.config.tools:
            if workflow_id not in workflow_schemas:
                raise LookupError(f"Workflow not found for tool: {workflow_id}")

            workflow = workflow_schemas[workflow_id]
            tool = WorkflowToolGenerator().generate(workflow_id, workflow, self._run_workflow)
            tools[workflow.name or workflow_id] = tool

        return tools

    async def _run_workflow(self, workflow_id: str, input: Any, context=None) -> Any:
        workflow = create_workflow(*WorkflowResolver(self.global_configs.workflows).resolve(workflow_id), self.global_configs)
        task_id = context.task_id if context else ulid.ulid()
        interrupt_handler = context.interrupt_handler if context else None

        return await workflow.run(task_id, input, interrupt_handler)
