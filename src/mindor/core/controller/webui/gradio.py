from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Awaitable, Any
from mindor.dsl.schema.workflow import WorkflowVariableConfig, WorkflowVariableGroupConfig, WorkflowVariableType, WorkflowVariableFormat
from mindor.core.workflow.schema import WorkflowSchema
from mindor.core.utils.streaming import StreamResource, Base64StreamResource
from mindor.core.utils.streaming import save_stream_to_temporary_file
from mindor.core.utils.http_request import create_upload_file
from mindor.core.utils.http_client import create_stream_with_url
from mindor.core.utils.image import load_image_from_stream
from mindor.core.utils.resolvers import FieldResolver
from PIL import Image as PILImage
import gradio as gr
import json

class ComponentGroup:
    def __init__(self, group: gr.Component, components: List[gr.Component]):
        self.group: gr.Component = group
        self.components: List[gr.Component] = components

class GradioWebUIBuilder:
    def __init__(self):
        self.field_resolver: FieldResolver = FieldResolver()

    def build(self, workflow_schemas: Dict[str, WorkflowSchema], workflow_runner: Callable[[Optional[str], Any], Awaitable[Any]]) -> gr.Blocks:
        with gr.Blocks() as blocks:
            for workflow_id, workflow in workflow_schemas.items():
                async def _run_workflow(input: Any, workflow_id=workflow_id) -> Any:
                    return await workflow_runner(workflow_id, input)

                if len(workflow_schemas) > 1:
                    with gr.Tab(label=workflow.name or workflow_id):
                        self._build_workflow_section(workflow, _run_workflow)
                else:
                    self._build_workflow_section(workflow, _run_workflow)

        return blocks

    def _build_workflow_section(self, workflow: WorkflowSchema, runner: Callable[[Any], Awaitable[Any]]) -> gr.Column:
        with gr.Column() as section:
            gr.Markdown(f"## **{workflow.title or 'Untitled Workflow'}**")

            if workflow.description:
                gr.Markdown(f"📝 {workflow.description}")

            gr.Markdown("#### 📥 Input Parameters")
            input_components = [ self._build_input_component(variable) for variable in workflow.input ]
            run_button = gr.Button("🚀 Run Workflow", variant="primary")

            gr.Markdown("#### 📤 Output Values")
            output_components = [ self._build_output_component(variable) for variable in workflow.output ]

            if not output_components:
                output_components = [ gr.Textbox(label="", lines=10, interactive=False, show_copy_button=True) ]

            async def _run_workflow(*args):
                input = await self._build_input_value(args, workflow.input)
                output = await runner(input)

                if len(workflow.output) == 1 and self._is_streaming_variable(workflow.output[0]):
                    buffer = "" if workflow.output[0].type == WorkflowVariableType.TEXT else []
                    async for chunk in output:
                        chunk = await self._flatten_output_value(chunk, [ workflow.output[0]])
                        if workflow.output[0].type == WorkflowVariableType.TEXT:
                            buffer += chunk[0] or ""
                        else:
                            buffer.append(chunk[0])
                        yield buffer
                else:
                    if workflow.output:
                        output = await self._flatten_output_value(output, workflow.output)
                    yield output[0] if len(output) == 1 else output

            run_button.click(
                fn=_run_workflow,
                inputs=input_components,
                outputs=self._flatten_output_components(output_components)
            )

        return section

    def _is_streaming_variable(self, variable: Union[WorkflowVariableConfig, WorkflowVariableGroupConfig]) -> bool:
        if isinstance(variable, WorkflowVariableConfig):
            return variable.format in [ WorkflowVariableFormat.SSE_JSON, WorkflowVariableFormat.SSE_TEXT ]
        return False

    def _build_input_component(self, variable: WorkflowVariableConfig) -> gr.Component:
        label = (variable.name or "") + (" *" if variable.required else "") + (f" (default: {variable.default})" if variable.default is not None else "")
        info = variable.get_annotation_value("description") or ""
        default = variable.default

        if variable.type == WorkflowVariableType.STRING or variable.format in [ WorkflowVariableFormat.BASE64, WorkflowVariableFormat.URL ]:
            return gr.Textbox(label=label, value="", info=info)
        
        if variable.type == WorkflowVariableType.TEXT:
            return gr.Textbox(label=label, value="", lines=5, max_lines=15, info=info)

        if variable.type == WorkflowVariableType.INTEGER:
            return gr.Textbox(label=label, value="", info=info)

        if variable.type == WorkflowVariableType.NUMBER:
            return gr.Number(label=label, value="", info=info)

        if variable.type == WorkflowVariableType.BOOLEAN:
            return gr.Checkbox(label=label, value=default or False, info=info)
        
        if variable.type == WorkflowVariableType.IMAGE:
            return gr.Image(label=label, type="filepath")

        if variable.type == WorkflowVariableType.AUDIO:
            return gr.Audio(label=label, type="filepath")

        if variable.type == WorkflowVariableType.VIDEO:
            return gr.Video(label=label, type="filepath")

        if variable.type == WorkflowVariableType.FILE:
            return gr.File(label=label)

        if variable.type == WorkflowVariableType.SELECT:
            return gr.Dropdown(choices=variable.options or [], label=label, value=default, info=info)

        return gr.Textbox(label=label, value=default, info=f"Unsupported type: {variable.type}")
    
    async def _build_input_value(self, arguments: List[Any], variables: List[WorkflowVariableConfig]) -> Any:
        if len(variables) == 1 and not variables[0].name:
            value, variable = arguments[0], variables[0]
            return await self._convert_input_value(value, variable.type, variable.subtype, variable.format, variable.internal)

        input: Dict[str, Any] = {}
        for value, variable in zip(arguments, variables):
            input[variable.name] = await self._convert_input_value(value, variable.type, variable.subtype, variable.format, variable.internal)
        return input

    async def _convert_input_value(self, value: Any, type: WorkflowVariableType, subtype: Optional[str], format: Optional[WorkflowVariableFormat], internal: bool) -> Any:
        if type in [ WorkflowVariableType.IMAGE, WorkflowVariableType.AUDIO, WorkflowVariableType.VIDEO, WorkflowVariableType.FILE ] and (not internal or not format):
            if internal and format and format != "path":
                value = await self._save_value_to_temporary_file(value, subtype, format)
            return create_upload_file(value, type.value, subtype) if value is not None else None

        if type == WorkflowVariableType.INTEGER:
            return int(value) if value != "" else None

        return value if value != "" else None

    def _build_output_component(self, variable: Union[WorkflowVariableConfig, WorkflowVariableGroupConfig]) -> Union[gr.Component, List[ComponentGroup]]:
        if isinstance(variable, WorkflowVariableGroupConfig):
            groups: List[ComponentGroup] = []
            for index in range(variable.repeat_count if variable.repeat_count != 0 else 100):
                visible = True if variable.repeat_count != 0 or index == 0 else False
                with gr.Column(visible=visible) as group:
                    components = [ self._build_output_component(v) for v in variable.variables ]
                groups.append(ComponentGroup(group, components))
            return groups

        label = variable.name or ""
        info = variable.get_annotation_value("description") or ""

        if variable.type in [ WorkflowVariableType.STRING, WorkflowVariableType.BASE64 ]:
            return gr.Textbox(label=label, interactive=False, show_copy_button=True, info=info)

        if variable.type in [ WorkflowVariableType.NUMBER, WorkflowVariableType.INTEGER ]:
            return gr.Textbox(label=label, interactive=False, show_copy_button=True, info=info)

        if variable.type == WorkflowVariableType.TEXT:
            return gr.Textbox(label=label, lines=5, max_lines=30, interactive=False, show_copy_button=True, info=info)

        if variable.type == WorkflowVariableType.MARKDOWN:
            return gr.Markdown(label=label)
        
        if variable.type in [ WorkflowVariableType.JSON, WorkflowVariableType.OBJECTS ]:
            return gr.JSON(label=label)

        if variable.type == WorkflowVariableType.IMAGE:
            return gr.Image(label=label, interactive=False)

        if variable.type == WorkflowVariableType.AUDIO:
            return gr.Audio(label=label)

        if variable.type == WorkflowVariableType.VIDEO:
            return gr.Video(label=label)

        return gr.Textbox(label=label, info=f"Unsupported type: {variable.type}")

    def _flatten_output_components(self, components: List[Union[gr.Component, List[ComponentGroup]]]) -> List[gr.Component]:
        flattened = []
        for item in components:
            if isinstance(item, list):
                for group in item:
                    flattened.extend(group.components)
            else:
                flattened.append(item)
        return flattened
    
    async def _flatten_output_value(self, output: Any, variables: List[Union[WorkflowVariableConfig, WorkflowVariableGroupConfig]]) -> Any:
        flattened = []
        for variable in variables:
            if isinstance(variable, WorkflowVariableGroupConfig):
                group = output[variable.name] if isinstance(output, dict) and variable.name in output else None if variable.name else output
                for value in group or ():
                    flattened.extend(await self._flatten_output_value(value, variable.variables))
            else:
                value = output[variable.name] if isinstance(output, dict) and variable.name in output else None if variable.name else output
                flattened.append(await self._convert_output_value(value, variable.type, variable.subtype, variable.format, variable.internal))
        return flattened

    async def _convert_output_value(self, value: Any, type: WorkflowVariableType, subtype: Optional[str], format: Optional[WorkflowVariableFormat], internal: bool) -> Any:
        if format == WorkflowVariableFormat.SSE_JSON:
            return await self._resolve_json_field_from_bytes(value, subtype, format)

        if type in [ WorkflowVariableType.STRING, WorkflowVariableType.TEXT ]:
            return await self._convert_value_to_string(value, subtype, format)

        if type == WorkflowVariableType.IMAGE:
            return await self._load_image_from_value(value, subtype, format)

        if type in [ WorkflowVariableType.AUDIO, WorkflowVariableType.VIDEO ]:
            return await self._save_value_to_temporary_file(value, subtype, format)

        return value

    async def _convert_value_to_string(self, value: Any, subtype: Optional[str], format: Optional[WorkflowVariableFormat]) -> Optional[str]:
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")

        if value is not None:
            return str(value)

        return None
    
    async def _resolve_json_field_from_bytes(self, value: Any, subtype: Optional[str], format: Optional[WorkflowVariableFormat]) -> Optional[Any]:
        try:
            return self.field_resolver.resolve(json.loads(value), subtype)
        except Exception:
            return None

    async def _load_image_from_value(self, value: Any, subtype: Optional[str], format: Optional[WorkflowVariableFormat]) -> Optional[PILImage.Image]:
        if format == WorkflowVariableFormat.BASE64 and isinstance(value, str):
            return await load_image_from_stream(Base64StreamResource(value), subtype)

        if format == WorkflowVariableFormat.URL and isinstance(value, str):
            return await load_image_from_stream(await create_stream_with_url(value), subtype)

        if isinstance(value, StreamResource):
            return await load_image_from_stream(value, subtype)

        return None

    async def _save_value_to_temporary_file(self, value: Any, subtype: Optional[str], format: Optional[WorkflowVariableFormat]) -> Optional[str]:
        if format == WorkflowVariableFormat.BASE64 and isinstance(value, str):
            return await save_stream_to_temporary_file(Base64StreamResource(value), subtype)

        if format == WorkflowVariableFormat.URL and isinstance(value, str):
            return await save_stream_to_temporary_file(await create_stream_with_url(value), subtype)

        if isinstance(value, StreamResource):
            return await save_stream_to_temporary_file(value, subtype)

        return None
