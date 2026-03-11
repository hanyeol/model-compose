from typing import Optional, Dict, List, Any
from mindor.dsl.schema.component import AgentComponentConfig
from mindor.dsl.schema.action import ActionConfig, AgentActionConfig, AgentModelConfig
from mindor.core.component import ComponentService, ComponentGlobalConfigs, ComponentResolver, create_component
from mindor.core.workflow import Workflow, WorkflowResolver, create_workflow
from mindor.core.workflow.tool import WorkflowToolGenerator, WorkflowTool
from mindor.core.workflow.schema import create_workflow_schemas
from ..base import ComponentType, register_component
from ..context import ComponentActionContext
import asyncio, ulid, json

_JSON_SCHEMA_TYPE_MAP = { "int": "integer", "float": "number", "bool": "boolean", "list[dict]": "array" }

class AgentAction:
    def __init__(self, action: AgentActionConfig, config: AgentComponentConfig, global_configs: ComponentGlobalConfigs, tools: Dict[str, WorkflowTool], function_schemas: List[Dict[str, Any]]):
        self.action: AgentActionConfig = action
        self.config: AgentComponentConfig = config
        self.global_configs: ComponentGlobalConfigs = global_configs
        self.tools: Dict[str, WorkflowTool] = tools
        self.function_schemas: List[Dict[str, Any]] = function_schemas

    async def run(self, context: ComponentActionContext) -> Any:
        messages: List[Dict[str, Any]] = await self._build_initial_messages(context)

        model_config = self.action.model
        model_component = self._create_component(model_config.component)
        if not model_component.started:
            await model_component.start()

        max_iteration_count = self.action.max_iteration_count or self.config.max_iteration_count
        tools = self.function_schemas if self.function_schemas else None
        streaming = await context.render_variable(self.action.streaming)

        if streaming:
            async def _stream_message_generator():
                for message in messages:
                    yield message

                for _ in range(max_iteration_count):
                    model_input = await self._render_model_input(context, model_config.input, messages, tools)
                    response = await model_component.run(model_config.action, ulid.ulid(), model_input)

                    assistant_message = await self._build_assistant_message(response)
                    messages.append(assistant_message)
                    yield assistant_message

                    tool_calls = self._extract_tool_calls(response)
                    if not tool_calls:
                        break

                    tool_messages = await asyncio.gather(*[self._execute_tool_call(tc) for tc in tool_calls])
                    for tool_message in tool_messages:
                        messages.append(tool_message)
                        yield tool_message

            return _stream_message_generator()

        for _ in range(max_iteration_count):
            model_input = await self._render_model_input(context, model_config.input, messages, tools)
            response = await model_component.run(model_config.action, ulid.ulid(), model_input)

            assistant_message = await self._build_assistant_message(response)
            messages.append(assistant_message)
 
            tool_calls = self._extract_tool_calls(response)
            if not tool_calls:
                break

            tool_messages = await asyncio.gather(*[self._execute_tool_call(tc) for tc in tool_calls])
            for tool_message in tool_messages:
                messages.append(tool_message)

        return messages

    async def _execute_tool_call(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        tool_name = tool_call["function"]["name"]
        tool_arguments = tool_call["function"].get("arguments", {})
        if isinstance(tool_arguments, str):
            tool_arguments = json.loads(tool_arguments)

        if tool_name in self.tools:
            result = await self.tools[tool_name].fn(**tool_arguments)
            content = json.dumps(result) if isinstance(result, (dict, list)) else str(result)
        else:
            content = f"Error: Unknown tool '{tool_name}'"

        return { "role": "tool", "tool_call_id": tool_call.get("id", ""), "content": content }

    def _create_component(self, component_id: str) -> ComponentService:
        _, config = ComponentResolver(self.global_configs.components).resolve(component_id)
        return create_component(component_id, config, self.global_configs, daemon=False)

    async def _render_model_input(self, context: ComponentActionContext, input_mapping: Dict[str, Any], messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
        context.register_source("messages", messages)
        if tools:
            context.register_source("tools", tools)

        return await context.render_variable(input_mapping)

    def _extract_tool_calls(self, response: Any) -> Optional[List[Dict[str, Any]]]:
        if isinstance(response, dict):
            return response.get("tool_calls")
        return None

    def _extract_content(self, response: Any) -> Any:
        if isinstance(response, dict):
            return response.get("content", response)
        return response

    async def _build_initial_messages(self, context: ComponentActionContext) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = []

        if self.action.system_prompt:
            system = await context.render_variable(self.action.system_prompt)
            messages.append({ "role": "system", "content": system if isinstance(system, str) else json.dumps(system) })

        user_input = self.action.user_prompt
        user = (await context.render_variable(user_input)) if user_input else context.input
        messages.append({ "role": "user", "content": user if isinstance(user, str) else json.dumps(user) })

        return messages

    async def _build_assistant_message(self, response: Any) -> Dict[str, Any]:
        if isinstance(response, dict):
            message: Dict[str, Any] = {"role": "assistant"}
            if "content" in response:
                message["content"] = response["content"]
            if "tool_calls" in response:
                message["tool_calls"] = response["tool_calls"]
            return message
        return { "role": "assistant", "content": str(response) }

async def _build_function_schema(name: str, tool: WorkflowTool) -> Dict[str, Any]:
    properties: Dict[str, Any] = {}
    required: List[str] = []

    for param in tool.parameters:
        prop: Dict[str, Any] = { "type": _JSON_SCHEMA_TYPE_MAP.get(param.type, "string") }
        if param.description:
            prop["description"] = param.description
        if param.default is not None:
            prop["default"] = param.default
        if param.required:
            required.append(param.name)
        properties[param.name] = prop

    schema: Dict[str, Any] = {
        "type": "function",
        "function": {
            "name": name,
            "parameters": {"type": "object", "properties": properties}
        }
    }

    if tool.description:
        schema["function"]["description"] = tool.description
    if required:
        schema["function"]["parameters"]["required"] = required

    return schema

@register_component(ComponentType.AGENT)
class AgentComponent(ComponentService):
    def __init__(self, id: str, config: AgentComponentConfig, global_configs: ComponentGlobalConfigs, daemon: bool):
        super().__init__(id, config, global_configs, daemon)

        self.tools: Optional[Dict[str, WorkflowTool]] = None
        self.function_schemas: Optional[List[Dict[str, Any]]] = None

    async def _start(self) -> None:
        self.tools = await self._generate_tools()
        self.function_schemas = await asyncio.gather(*[ _build_function_schema(name, tool) for name, tool in self.tools.items() ])
        await super()._start()

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await AgentAction(action, self.config, self.global_configs, self.tools, self.function_schemas).run(context)

    async def _generate_tools(self) -> Dict[str, WorkflowTool]:
        workflow_schemas = create_workflow_schemas(self.global_configs.workflows, self.global_configs.components)
        tools: Dict[str, WorkflowTool] = {}

        for workflow_id in self.config.tools:
            if workflow_id not in workflow_schemas:
                raise ValueError(f"Workflow not found for tool: {workflow_id}")

            workflow = workflow_schemas[workflow_id]
            tool = WorkflowToolGenerator().generate(workflow_id, workflow, self._run_workflow)
            tools[workflow.name or workflow_id] = tool

        return tools

    async def _run_workflow(self, workflow_id: str, input: Any) -> Any:
        workflow = create_workflow(*WorkflowResolver(self.global_configs.workflows).resolve(workflow_id), self.global_configs)
        return await workflow.run(ulid.ulid(), input)
