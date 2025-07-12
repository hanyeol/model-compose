from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.controller import ControllerConfig
from mindor.core.workflow.schema import WorkflowSchema
from mindor.core.utils.mcp_client import McpClient, ContentBlock, TextContent, ImageContent, AudioContent
from mindor.core.utils.streaming import StreamResource, FileStreamResource, Base64StreamResource
from mindor.core.utils.streaming import encode_stream_to_base64
from mindor.core.utils.http_client import create_stream_with_url
from mindor.core.utils.image import load_image_from_stream
from .runner import ControllerClient
import json, os

class McpControllerClient(ControllerClient):
    def __init__(self, config: ControllerConfig):
        super().__init__(config)

        self.client: McpClient = McpClient(self._resolve_controller_url())

    async def run_workflow(self, workflow_id: Optional[str], input: Any, workflow: WorkflowSchema) -> Any:
        return await self._call_tool(workflow_id, input, workflow)

    async def close(self) -> None:
        await self.client.close()

    def _resolve_controller_url(self) -> str:
        return f"http://localhost:{self.config.port}{self.config.base_path or ''}"

    async def _call_tool(self, name: str, arguments: Optional[Dict[str, Any]], workflow: WorkflowSchema) -> Any:
        contents = await self.client.call_tool(name, arguments)

        if len(workflow.output) == 1 and not workflow.output[0].name:
            content, variable = contents[0], workflow.output[0]
            type, subtype, format = variable.type.value, variable.subtype, variable.format.value if variable.format else None
            return await self._convert_output_value(content, type, subtype, format)
        
        output = {}
        for content, variable in zip(contents, workflow.output):
            type, subtype, format = variable.type.value, variable.subtype, variable.format.value if variable.format else None
            output[variable.name or "output"] = await self._convert_output_value(content, type, subtype, format)
        return output

    async def _convert_output_value(self, content: ContentBlock, type: str, subtype: Optional[str], format: Optional[str]) -> Any:
        if isinstance(content, TextContent):
            if type in [ "json", "object[]" ]:
                return json.loads(content.text)
            if type in [ "image", "audio", "video", "file" ]:
                if not format and os.path.exists(content.text):
                    return FileStreamResource(content.text)
                if format == "base64": # content.text is path
                    return await encode_stream_to_base64(FileStreamResource(content.text))
            return content.text

        if isinstance(content, (ImageContent, AudioContent)):
            return content.data

        return None

    async def _load_image_from_value(self, value: Any, subtype: Optional[str], format: Optional[str]) -> Optional[str]:
        if format == "base64" and isinstance(value, str):
            return await load_image_from_stream(Base64StreamResource(value), subtype)

        if format == "url" and isinstance(value, str):
            return await load_image_from_stream(await create_stream_with_url(value), subtype)

        if isinstance(value, StreamResource):
            return await load_image_from_stream(value, subtype)

        return None
