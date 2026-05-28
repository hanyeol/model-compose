from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Callable, Any
from mindor.dsl.schema.workflow import WorkflowVariableConfig, WorkflowVariableGroupConfig, WorkflowVariableType, WorkflowVariableFormat
from mindor.core.workflow.schema import WorkflowSchema

from mindor.core.utils.streaming import StreamResource, BytesStreamResource, Base64StreamResource
from mindor.core.utils.streaming import save_stream_to_temporary_file
from mindor.core.utils.http_request import create_upload_file
from mindor.core.utils.http_client import create_stream_with_url
from mindor.core.utils.image import load_image_from_stream
from mindor.core.utils.audio import PcmStreamResource, WavStreamResource
from mindor.core.utils.resolvers import FieldResolver
from PIL import Image as PILImage
import gradio as gr
import json, re

if TYPE_CHECKING:
    from mindor.core.controller.runner import ControllerRunner

_VARIABLE_NAME_REGEX = re.compile(r"^([^[]+)(?:\[(\w+)\])?$")

class ComponentGroup:
    def __init__(self, group: gr.Component, components: List[gr.Component]):
        self.group: gr.Component = group
        self.components: List[gr.Component] = components

class GradioWebUIBuilder:
    def __init__(self):
        self.field_resolver: FieldResolver = FieldResolver()

    def build(
        self,
        workflow_schemas: Dict[str, WorkflowSchema],
        runner: Callable[[], ControllerRunner]
    ) -> gr.Blocks:
        with gr.Blocks() as blocks:
            for workflow_id, workflow in workflow_schemas.items():
                if len(workflow_schemas) > 1:
                    with gr.Tab(label=workflow.name or workflow_id):
                        self._build_workflow_section(workflow_id, workflow, runner)
                else:
                    self._build_workflow_section(workflow_id, workflow, runner)

        return blocks

    def _build_workflow_section(self,
        workflow_id: str,
        workflow: WorkflowSchema,
        runner: Callable[[], ControllerRunner]
    ) -> gr.Column:
        with gr.Column() as section:
            gr.Markdown(f"## **{workflow.title or 'Untitled Workflow'}**")

            if workflow.description:
                gr.Markdown(f"📝 {workflow.description}")

            gr.Markdown("#### Input Parameters")
            input_components = [ self._build_input_component(variable) for variable in workflow.input ]

            run_button = gr.Button("🚀 Run Workflow", variant="primary")

            interrupt_state = gr.State(value=None)
            with gr.Column(visible=False) as interrupt_panel:
                interrupt_components = self._build_interrupt_components()
                interrupt_answer = interrupt_components[-1]
                resume_button = gr.Button("▶️ Resume", variant="primary")
            interrupt_components = [ interrupt_state, interrupt_panel, *interrupt_components ]

            gr.Markdown("#### Output Values")
            output_components = [ self._build_output_component(variable) for variable in workflow.output ]

            if not output_components:
                output_components = [ gr.Textbox(label="", lines=10, interactive=False, buttons=["copy"]) ]

            output_components = self._flatten_output_components(output_components)

            def _run_button_running():
                return gr.update(value="⏳ Running...", interactive=False)

            def _run_button_ready():
                return gr.update(value="🚀 Run Workflow", interactive=True)

            def _resume_button_running():
                return gr.update(value="⏳ Resuming...", interactive=False)

            def _resume_button_ready():
                return gr.update(value="▶️ Resume", interactive=True)

            async def _run_workflow(*args):
                yield [ _run_button_running(), *self._clear_interrupt_updates(), *self._clear_output_values(workflow.output) ]

                input  = await self._build_input_value(args, workflow.input)
                output = await runner().run_workflow(workflow_id, input, workflow)

                # Check if the result is an interrupted TaskResult
                if isinstance(output, dict) and output.get("status") == "interrupted" and "task_id" in output:
                    yield [ _run_button_running(), *self._build_interrupt_updates(output), *(gr.update() for _ in output_components) ]
                    return

                # Check if the result is a failed TaskResult
                if isinstance(output, dict) and output.get("status") == "failed":
                    yield [ _run_button_ready(), *self._clear_interrupt_updates(), *(gr.update() for _ in output_components) ]
                    raise gr.Error(str(output.get("error", "Workflow failed")))

                # Clear interrupt panel for normal results
                clear_interrupt = self._clear_interrupt_updates()

                if isinstance(output, StreamResource) and len(workflow.output) == 1 and isinstance(workflow.output[0], WorkflowVariableConfig):
                    if workflow.output[0].type in [ WorkflowVariableType.SSE_TEXT, WorkflowVariableType.SSE_JSON ]:
                        buffer = "" if workflow.output[0].type == WorkflowVariableType.SSE_TEXT else []
                        async for chunk in output:
                            chunk = await self._flatten_output_value(chunk, [ workflow.output[0]])
                            if workflow.output[0].type == WorkflowVariableType.SSE_TEXT:
                                buffer += chunk[0] or ""
                            else:
                                buffer.append(chunk[0])
                            yield [ _run_button_running(), *clear_interrupt, buffer ]
                        yield [ _run_button_ready(), *clear_interrupt, buffer ]
                    else:
                        result = await self._save_stream_to_temporary_file(output, workflow.output[0])
                        yield [ _run_button_ready(), *clear_interrupt, result ]
                else:
                    if workflow.output:
                        output = await self._flatten_output_value(output, workflow.output)
                    result = output[0] if len(output) == 1 else output
                    if isinstance(result, (list, tuple)):
                        yield [ _run_button_ready(), *clear_interrupt, *result ]
                    else:
                        yield [ _run_button_ready(), *clear_interrupt, result ]

            async def _resume_workflow(state: Optional[Dict[str, str]], answer_text: str):
                yield [ _run_button_running(), _resume_button_running(), *(gr.update() for _ in interrupt_components), *(gr.update() for _ in output_components) ]

                task_id, job_id = state["task_id"], state["job_id"]

                # Parse answer: try JSON first, fallback to string
                answer = answer_text
                if answer_text:
                    try:
                        answer = json.loads(answer_text)
                    except (json.JSONDecodeError, TypeError):
                        pass

                await runner().resume_workflow(task_id, job_id, answer if answer_text else None)
                result = await runner().wait_for_completion(task_id)

                if result.get("status") == "interrupted":
                    yield [ _run_button_running(), _resume_button_ready(), *self._build_interrupt_updates(result), *(gr.update() for _ in output_components) ]
                    return

                clear_interrupt = self._clear_interrupt_updates()

                # Check if the result is a failed TaskResult
                if result.get("status") == "failed":
                    yield [ _run_button_ready(), _resume_button_ready(), *self._clear_interrupt_updates(), *(gr.update() for _ in output_components) ]
                    raise gr.Error(str(result.get("error", "Workflow failed")))

                # Completed — fetch output
                output = await runner().get_task_output(task_id)
                if workflow.output and output is not None:
                    output = await self._flatten_output_value(output, workflow.output)
                    result = output[0] if len(output) == 1 else output
                else:
                    result = output

                if result is None:
                    yield [ _run_button_ready(), _resume_button_ready(), *clear_interrupt, *(gr.update() for _ in output_components) ]
                elif isinstance(result, (list, tuple)):
                    yield [ _run_button_ready(), _resume_button_ready(), *clear_interrupt, *result ]
                else:
                    yield [ _run_button_ready(), _resume_button_ready(), *clear_interrupt, result ]

            run_button.click(
                fn=_run_workflow,
                inputs=input_components,
                outputs=[ run_button, *interrupt_components, *output_components ]
            )

            resume_button.click(
                fn=_resume_workflow,
                inputs=[ interrupt_state, interrupt_answer ],
                outputs=[ run_button, resume_button, *interrupt_components, *output_components ]
            )

        return section

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

        if variable.type == WorkflowVariableType.LIST:
            return gr.Textbox(label=label, value=default or "", info=info)

        if variable.type == WorkflowVariableType.IMAGE:
            return gr.Image(label=label, type="filepath")

        if variable.type == WorkflowVariableType.AUDIO:
            return gr.Audio(label=label, type="filepath")

        if variable.type == WorkflowVariableType.VIDEO:
            return gr.Video(label=label)

        if variable.type == WorkflowVariableType.FILE:
            return gr.File(label=label)

        if variable.type == WorkflowVariableType.SELECT:
            return gr.Dropdown(choices=variable.options or [], label=label, value=default, info=info)

        return gr.Textbox(label=label, value=default, info=f"Unsupported type: {variable.type}")

    async def _build_input_value(self, arguments: List[Any], variables: List[WorkflowVariableConfig]) -> Any:
        if len(variables) == 1 and not variables[0].name:
            value, variable = arguments[0], variables[0]
            return await self._convert_input_value(value, variable)

        input: Dict[str, Any] = {}
        for value, variable in zip(arguments, variables):
            input[variable.name] = await self._convert_input_value(value, variable)
        return input

    async def _convert_input_value(self, value: Any, variable: WorkflowVariableConfig) -> Any:
        if self._is_media_variable(variable) and (not variable.internal or not variable.format):
            if variable.internal and variable.format and variable.format != "path":
                value = await self._save_value_to_temporary_file(value, variable.subtype, variable.attrs, variable.format)
            return create_upload_file(value, variable.type.value, variable.subtype) if value is not None else None

        if variable.type == WorkflowVariableType.INTEGER:
            return int(value) if value != "" else None

        if variable.type == WorkflowVariableType.LIST:
            return str(value).split(",")

        return value if value != "" else None

    async def _format_workflow_output(self, output: Any, workflow: WorkflowSchema) -> Optional[list]:
        if workflow.output and output is not None:
            output = await self._flatten_output_value(output, workflow.output)
        if output is None:
            return None
        result = output[0] if isinstance(output, (list, tuple)) and len(output) == 1 else output
        return list(result) if isinstance(result, (list, tuple)) else [result]

    def _build_interrupt_components(self):
        message  = gr.Markdown("")
        metadata = gr.JSON(label="Metadata", visible=False)
        answer   = gr.Textbox(label="Answer", lines=2, placeholder="Press Resume to continue, or type an answer (JSON or text)")

        return [ message, metadata, answer ]

    def _build_interrupt_updates(self, result: dict) -> List[Any]:
        interrupt = result.get("interrupt", {})
        state = { "task_id": result["task_id"], "job_id": interrupt.get("job_id") }
        message = interrupt.get("message") or "The workflow is waiting for your input."
        metadata = interrupt.get("metadata")

        return [
            state,
            gr.update(visible=True),
            gr.update(value=message),
            gr.update(value=metadata, visible=metadata is not None),
            gr.update(value=""),
        ]

    def _clear_interrupt_updates(self) -> List[Any]:
        return [
            None,
            gr.update(visible=False),
            gr.update(value=""),
            gr.update(value=None, visible=False),
            gr.update(value=""),
        ]

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
            return gr.Textbox(label=label, interactive=False, info=info, buttons=["copy"])

        if variable.type in [ WorkflowVariableType.NUMBER, WorkflowVariableType.INTEGER ]:
            return gr.Textbox(label=label, interactive=False, info=info, buttons=["copy"])

        if variable.type == WorkflowVariableType.TEXT:
            return gr.Textbox(label=label, lines=5, max_lines=30, interactive=False, info=info, buttons=["copy"])

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

        if variable.type == WorkflowVariableType.FILE:
            return gr.File(label=label)

        if variable.type in [ WorkflowVariableType.SSE_TEXT, WorkflowVariableType.SSE_JSON ]:
            return gr.Textbox(label=label, lines=5, max_lines=30, interactive=False, info=info, buttons=["copy"])

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

    def _clear_output_values(self, variables: List[Union[WorkflowVariableConfig, WorkflowVariableGroupConfig]]) -> List[Any]:
        cleared = []
        for variable in variables:
            if isinstance(variable, WorkflowVariableGroupConfig):
                count = variable.repeat_count if variable.repeat_count != 0 else 100
                for _ in range(count):
                    cleared.extend(self._clear_output_values(variable.variables))
            else:
                cleared.append(gr.update(value=None) if variable.type != WorkflowVariableType.MARKDOWN else gr.update(value=""))
        return cleared

    async def _flatten_output_value(
        self,
        output: Any,
        variables: List[Union[WorkflowVariableConfig, WorkflowVariableGroupConfig]]
    ) -> Any:
        flattened = []
        for variable in variables:
            if isinstance(variable, WorkflowVariableGroupConfig):
                group = self._resolve_variable_output(output, variable)
                for value in group or ():
                    flattened.extend(await self._flatten_output_value(value, variable.variables))
            else:
                value = self._resolve_variable_output(output, variable)
                flattened.append(await self._convert_output_value(value, variable))
        return flattened

    def _resolve_variable_output(
        self,
        output: Any,
        variable: Union[WorkflowVariableConfig, WorkflowVariableGroupConfig]
    ) -> Any:
        if isinstance(output, dict) and variable.name:
            m = re.match(_VARIABLE_NAME_REGEX, variable.name)
            if not m:
                return None

            name, index = m.group(1, 2)
            if name not in output:
                return None

            if isinstance(output[name], list) and index:
                if int(index) < len(output[name]):
                    return output[name][int(index)]
                return None

            return output[name]

        return None if variable.name else output

    async def _convert_output_value(self, value: Any, variable: WorkflowVariableConfig) -> Any:
        if variable.type == WorkflowVariableType.SSE_JSON:
            return self._resolve_json_field_from_bytes(value, variable.subtype, variable.format)

        if variable.type == WorkflowVariableType.SSE_TEXT:
            return self._convert_value_to_string(value, variable.subtype, variable.format)

        if variable.type in [ WorkflowVariableType.STRING, WorkflowVariableType.TEXT ]:
            return self._convert_value_to_string(value, variable.subtype, variable.format)

        if variable.type == WorkflowVariableType.IMAGE:
            return await self._load_image_from_value(value, variable.subtype, variable.format)

        if variable.type in [ WorkflowVariableType.AUDIO, WorkflowVariableType.VIDEO, WorkflowVariableType.FILE ]:
            return await self._save_value_to_temporary_file(value, variable.subtype, variable.attrs, variable.format)

        return value

    def _convert_value_to_string(self, value: Any, subtype: Optional[str], format: Optional[WorkflowVariableFormat]) -> Optional[str]:
        if isinstance(value, (dict, list)):
            return json.dumps(value)

        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")

        if value is not None:
            return str(value)

        return None

    def _resolve_json_field_from_bytes(self, value: Any, subtype: Optional[str], format: Optional[WorkflowVariableFormat]) -> Optional[Any]:
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

    async def _save_value_to_temporary_file(self, value: Any, subtype: Optional[str], attrs: Optional[Dict[str, str]], format: Optional[WorkflowVariableFormat]) -> Optional[str]:
        if format == WorkflowVariableFormat.BASE64 and isinstance(value, str):
            return await save_stream_to_temporary_file(Base64StreamResource(value), subtype)

        if format == WorkflowVariableFormat.URL and isinstance(value, str):
            return await save_stream_to_temporary_file(await create_stream_with_url(value), subtype)

        if format == WorkflowVariableFormat.PATH and isinstance(value, str):
            return value

        if isinstance(value, StreamResource):
            return await save_stream_to_temporary_file(value, subtype)

        if isinstance(value, bytes):
            return await save_stream_to_temporary_file(BytesStreamResource(value), subtype)

        return None

    async def _save_stream_to_temporary_file(self, stream: StreamResource, variable: WorkflowVariableConfig) -> Optional[str]:
        if variable.type == WorkflowVariableType.AUDIO and variable.subtype == "pcm":
            return await save_stream_to_temporary_file(WavStreamResource(PcmStreamResource(stream, variable.attrs)), "wav")

        return await save_stream_to_temporary_file(stream, variable.subtype)

    def _is_media_variable(self, variable: WorkflowVariableConfig) -> bool:
        return variable.type in [ WorkflowVariableType.IMAGE, WorkflowVariableType.AUDIO, WorkflowVariableType.VIDEO, WorkflowVariableType.FILE ]
