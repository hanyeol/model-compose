from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import McpServerComponentConfig
from mindor.dsl.schema.action import ActionConfig, McpServerActionConfig
from mindor.core.utils.mcp_client import McpClient, ContentBlock, TextContent, ImageContent, AudioContent
from mindor.core.utils.shell import run_command_streaming
from ..base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ..context import ComponentActionContext

class McpServerAction:
    def __init__(self, config: McpServerActionConfig):
        self.config: McpServerActionConfig = config

    async def run(self, context: ComponentActionContext, client: McpClient) -> Any:
        tool      = await context.render_variable(self.config.tool)
        arguments = await context.render_variable(self.config.arguments)

        response = [ await self._convert_output_value(content) for content in await client.call_tool(tool, arguments) ]
        context.register_source("response", response)

        return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else response

    async def _convert_output_value(self, content: ContentBlock) -> Any:
        if isinstance(content, TextContent):
            return content.text

        if isinstance(content, (ImageContent, AudioContent)):
            return content.data

        return None

@register_component(ComponentType.MCP_SERVER)
class McpServerComponent(ComponentService):
    def __init__(self, id: str, config: McpServerComponentConfig, global_configs: ComponentGlobalConfigs, daemon: bool):
        super().__init__(id, config, global_configs, daemon)

        self.client: Optional[McpClient] = None 

    async def _setup(self) -> None:
        if self.config.manage.scripts.install:
            for command in self.config.manage.scripts.install:
                await run_command_streaming(command, self.config.manage.working_dir, self.config.manage.env)

        if self.config.manage.scripts.build:
            for command in self.config.manage.scripts.build:
                await run_command_streaming(command, self.config.manage.working_dir, self.config.manage.env)

    async def _teardown(self):
        if self.config.manage.scripts.clean:
            for command in self.config.manage.scripts.clean:
                await run_command_streaming(command, self.config.manage.working_dir, self.config.manage.env)

    async def _start(self) -> None:
        base_url = f"http://localhost:{self.config.port}" + (self.config.base_path or "")
        self.client = McpClient(base_url, self.config.headers)
        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()
        await self.client.close()
        self.client = None

    async def _serve(self) -> None:
        if self.config.manage.scripts.start:
            await run_command_streaming(self.config.manage.scripts.start, self.config.manage.working_dir, self.config.manage.env, block=False)

    async def _shutdown(self) -> None:
        pass

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await McpServerAction(action).run(context, self.client)
