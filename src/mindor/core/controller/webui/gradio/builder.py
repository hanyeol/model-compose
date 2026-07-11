from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Callable, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.workflow import WorkflowVariableConfig, WorkflowVariableGroupConfig, WorkflowVariableType, WorkflowVariableFormat
from mindor.core.controller.base import TaskStatus, TaskState, TaskEvent, JobEvent, ComponentEvent
from mindor.core.workflow.schema import WorkflowSchema

from mindor.core.foundation.streaming.resources import StreamResource
from mindor.core.foundation.streaming.bytes import BytesStreamResource
from mindor.core.foundation.streaming.base64 import Base64StreamResource
from mindor.core.foundation.streaming.resources import save_stream_to_temporary_file
from mindor.core.foundation.streaming.url import DataUriStreamResource
from mindor.core.utils.transport.http_request import create_upload_file
from mindor.core.utils.transport.http_client import create_stream_with_url
from mindor.core.foundation.streaming.image import ImageStreamResource, load_image_from_stream
from mindor.core.foundation.streaming.audio import PcmStreamResource, WavStreamResource
from mindor.core.foundation.streaming.iterators import StreamIterator, StreamChunkIterator
from mindor.core.utils.event_queue import EventQueue
from PIL import Image as PILImage
from collections import deque
import gradio as gr
import asyncio, json, re

if TYPE_CHECKING:
    from mindor.core.controller.runner import ControllerRunner

_VARIABLE_NAME_REGEX = re.compile(r"^([^[]+)(?:\[(\w+)\])?$")

class ComponentGroup:
    def __init__(self, group: gr.Accordion, components: List[gr.Component]):
        self.group: gr.Accordion = group
        self.components: List[gr.Component] = components

class WorkflowLogPanel:
    def __init__(self):
        self.chatbot: Optional[gr.Chatbot] = None

    def build(self) -> List[gr.Component]:
        self.chatbot = gr.Chatbot(
            label="Log",
            min_height="80vh",
            buttons=[],
            editable=False,
            feedback_options=None,
            elem_classes=[ "log-panel-chatbot" ],
        )
        return [ self.chatbot ]

    def update(self, messages: List[Dict], spinner: Optional[Dict] = None) -> List[Any]:
        return [ [ *messages, spinner ] if spinner else list(messages) ]

    def clear(self) -> List[Any]:
        return [ [] ]

    def ignore(self) -> List[Any]:
        return [ gr.update() ]

class GradioWebUIBuilder:
    def build(
        self,
        workflow_schemas: Dict[str, WorkflowSchema],
        runner: Callable[[], ControllerRunner]
    ) -> Tuple[gr.Blocks, str]:
        with gr.Blocks() as blocks:
            for workflow_id, workflow in workflow_schemas.items():
                if len(workflow_schemas) > 1:
                    with gr.Tab(label=workflow.name or workflow_id):
                        self._build_workflow_section(workflow_id, workflow, runner)
                else:
                    self._build_workflow_section(workflow_id, workflow, runner)

        return blocks, self._global_css()

    def _build_workflow_section(self,
        workflow_id: str,
        workflow: WorkflowSchema,
        runner: Callable[[], ControllerRunner]
    ) -> gr.Column:
        log_message_queue: EventQueue = EventQueue()

        with gr.Column() as section:
            gr.Markdown(f"## **{workflow.title or 'Untitled Workflow'}**")

            if workflow.description:
                gr.Markdown(f"📝 {workflow.description}")

            with gr.Row(equal_height=True):
                with gr.Column(scale=2, elem_classes=["input-output-column"]):
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
                    output_tree: List[Union[gr.Component, List[ComponentGroup]]] = [ self._build_output_component(variable) for variable in workflow.output ]

                    if not output_tree:
                        output_tree = [ gr.Textbox(label="", lines=10, interactive=False, buttons=["copy"]) ]

                    output_components = self._flatten_output_components(output_tree)
                    media_components = [ component for component in output_components if self._is_media_component(component) ]

                with gr.Column(scale=1):
                    log_panel = WorkflowLogPanel()
                    log_components = log_panel.build()

            def _run_button_running():
                return gr.update(value="⏳ Running...", interactive=False)

            def _run_button_ready():
                return gr.update(value="🚀 Run Workflow", interactive=True)

            def _resume_button_running():
                return gr.update(value="⏳ Resuming...", interactive=False)

            def _resume_button_ready():
                return gr.update(value="▶️ Resume", interactive=True)

            async def _on_workflow_event(event):
                for message in self._log_messages_for_event(event):
                    log_message_queue.put(message)

            async def _run_workflow(*args):
                log_message_queue.reset()

                yield [
                    _run_button_running(),
                    *self._clear_interrupt_updates(),
                    *self._clear_output_updates(output_components),
                    *log_panel.update([], self._log_spinner_message()),
                ]

                input = await self._build_input_value(args, workflow.input)
                task = asyncio.create_task(runner().run_workflow(workflow_id, input, on_event=_on_workflow_event))

                while not task.done():
                    if await log_message_queue.poll(timeout=0.1):
                        yield [
                            _run_button_running(),
                            *(gr.update() for _ in interrupt_components),
                            *(gr.update() for _ in output_components),
                            *log_panel.update(log_message_queue.get(consume=False), self._log_spinner_message()),
                        ]

                log_message_queue.drain()
                messages = log_message_queue.get(consume=False)

                if messages:
                    yield [
                        _run_button_running(),
                        *(gr.update() for _ in interrupt_components),
                        *(gr.update() for _ in output_components),
                        *log_panel.update(messages),
                    ]

                try:
                    state = task.result()
                except Exception as e:
                    yield [
                        _run_button_ready(),
                        *self._clear_interrupt_updates(),
                        *(gr.update() for _ in output_components),
                        *log_panel.update(messages),
                    ]
                    raise gr.Error(str(e))

                if state.status == TaskStatus.INTERRUPTED:
                    yield [
                        _run_button_running(),
                        *self._build_interrupt_updates(state),
                        *(gr.update() for _ in output_components),
                        *log_panel.update(messages),
                    ]
                    return

                if state.status == TaskStatus.FAILED:
                    yield [
                        _run_button_ready(),
                        *self._clear_interrupt_updates(),
                        *(gr.update() for _ in output_components),
                        *log_panel.update(messages),
                    ]
                    raise gr.Error(str(state.error))

                # Completed
                clear_interrupt = self._clear_interrupt_updates()
                log_done = log_panel.update(messages)

                output = state.output
                if output is None:
                    yield [
                        _run_button_ready(),
                        *clear_interrupt,
                        *(gr.update() for _ in output_components),
                        *log_done,
                    ]
                    return

                if len(workflow.output) == 1 and isinstance(output, (StreamIterator, AsyncIterator)):
                    async for updates in self._stream_output_updates(output, workflow.output[0], output_tree[0]):
                        yield [
                            _run_button_running(),
                            *clear_interrupt,
                            *updates,
                            *log_done,
                        ]

                    yield [
                        _run_button_ready(),
                        *clear_interrupt,
                        *(gr.update() for _ in output_components),
                        *log_done,
                    ]
                else:
                    if workflow.output:
                        updates = await self._resolve_output_updates(output, workflow.output, output_tree)
                    else:
                        updates = [ output ]

                    wait_for_media = self._has_pending_media_updates(updates, output_components, media_components)

                    if len(output_components) == 1:
                        updates = [ updates[0] if len(updates) == 1 else updates ]

                    yield [
                        _run_button_running() if wait_for_media else _run_button_ready(),
                        *clear_interrupt,
                        *updates,
                        *log_done,
                    ]

            async def _resume_workflow(ui_state: Optional[Dict[str, str]], answer_text: str):
                yield [
                    _run_button_running(),
                    _resume_button_running(),
                    *(gr.update() for _ in interrupt_components),
                    *(gr.update() for _ in output_components),
                    *log_panel.update(log_message_queue.get(consume=False), self._log_spinner_message()),
                ]

                task_id, job_id = ui_state["task_id"], ui_state["job_id"]

                # Parse answer: try JSON first, fallback to string
                answer = answer_text
                if answer_text:
                    try:
                        answer = json.loads(answer_text)
                    except (json.JSONDecodeError, TypeError):
                        pass

                try:
                    await runner().resume_workflow(task_id, job_id, answer if answer_text else None)
                    task = asyncio.create_task(runner().wait_for_completion(task_id))
                except Exception as e:
                    yield [
                        _run_button_ready(),
                        _resume_button_ready(),
                        *self._clear_interrupt_updates(),
                        *(gr.update() for _ in output_components),
                        *log_panel.ignore(),
                    ]
                    raise gr.Error(str(e))

                while not task.done():
                    if await log_message_queue.poll(timeout=0.1):
                        yield [
                            _run_button_running(),
                            _resume_button_running(),
                            *(gr.update() for _ in interrupt_components),
                            *(gr.update() for _ in output_components),
                            *log_panel.update(log_message_queue.get(consume=False), self._log_spinner_message()),
                        ]

                log_message_queue.drain()
                messages = log_message_queue.get(consume=False)

                if messages:
                    yield [
                        _run_button_running(),
                        _resume_button_running(),
                        *(gr.update() for _ in interrupt_components),
                        *(gr.update() for _ in output_components),
                        *log_panel.update(messages),
                    ]

                try:
                    state = task.result()
                except Exception as e:
                    yield [
                        _run_button_ready(),
                        _resume_button_ready(),
                        *self._clear_interrupt_updates(),
                        *(gr.update() for _ in output_components),
                        *log_panel.update(messages),
                    ]
                    raise gr.Error(str(e))

                if state.status == TaskStatus.INTERRUPTED:
                    yield [
                        _run_button_running(),
                        _resume_button_ready(),
                        *self._build_interrupt_updates(state),
                        *(gr.update() for _ in output_components),
                        *log_panel.update(messages),
                    ]
                    return

                if state.status == TaskStatus.FAILED:
                    yield [
                        _run_button_ready(),
                        _resume_button_ready(),
                        *self._clear_interrupt_updates(),
                        *(gr.update() for _ in output_components),
                        *log_panel.update(messages),
                    ]
                    raise gr.Error(str(state.error))

                # Completed
                clear_interrupt = self._clear_interrupt_updates()
                log_done = log_panel.update(messages)

                output = state.output
                if output is None:
                    yield [
                        _run_button_ready(),
                        _resume_button_ready(),
                        *clear_interrupt,
                        *(gr.update() for _ in output_components),
                        *log_done,
                    ]
                    return

                if len(workflow.output) == 1 and isinstance(output, (StreamIterator, AsyncIterator)):
                    async for updates in self._stream_output_updates(output, workflow.output[0], output_tree[0]):
                        yield [
                            _run_button_running(),
                            _resume_button_ready(),
                            *clear_interrupt,
                            *updates,
                            *log_done,
                        ]

                    yield [
                        _run_button_ready(),
                        _resume_button_ready(),
                        *clear_interrupt,
                        *(gr.update() for _ in output_components),
                        *log_done,
                    ]
                else:
                    if workflow.output:
                        updates = await self._resolve_output_updates(output, workflow.output, output_tree)
                    else:
                        updates = [ output ]

                    wait_for_media = self._has_pending_media_updates(updates, output_components, media_components)

                    if len(output_components) == 1:
                        updates = [ updates[0] if len(updates) == 1 else updates ]

                    yield [
                        _run_button_running() if wait_for_media else _run_button_ready(),
                        _resume_button_ready(),
                        *clear_interrupt,
                        *updates,
                        *log_done,
                    ]

            run_button.click(
                fn=_run_workflow,
                inputs=input_components,
                outputs=[ run_button, *interrupt_components, *output_components, *log_components ]
            )

            resume_button.click(
                fn=_resume_workflow,
                inputs=[ interrupt_state, interrupt_answer ],
                outputs=[ run_button, resume_button, *interrupt_components, *output_components, *log_components ]
            )

            for component in media_components:
                component.change(fn=_run_button_ready, inputs=None, outputs=run_button)

        return section

    def _build_input_component(self, variable: WorkflowVariableConfig) -> gr.Component:
        label = (variable.name or "") + (" *" if variable.required else "") + (f" (default: {variable.default})" if variable.default is not None else "")
        info = variable.get_annotation_value("description") or ""
        default = variable.default

        if variable.format == WorkflowVariableFormat.PATH:
            return gr.Textbox(label=label, value="", info=info, placeholder="Enter a file path (e.g. /path/to/file)")

        if variable.format == WorkflowVariableFormat.URL:
            return gr.Textbox(label=label, value="", info=info, placeholder="Enter a URL (e.g. https://example.com/file)")

        if variable.format == WorkflowVariableFormat.DATA_URI:
            return gr.Textbox(label=label, value="", info=info, placeholder="Enter a data URI (e.g. data:image/png;base64,iVBORw0K...)")

        if variable.format == WorkflowVariableFormat.BASE64:
            return gr.Textbox(label=label, value="", info=info, placeholder="Enter a base64-encoded string")

        if variable.type == WorkflowVariableType.STRING:
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
            return gr.Textbox(label=label, value=json.dumps(default, ensure_ascii=False) if default else "", info=info)

        if variable.type == WorkflowVariableType.IMAGE:
            return gr.Image(label=label, type="filepath")

        if variable.type == WorkflowVariableType.AUDIO:
            return gr.Audio(label=label, sources=[ "upload", "microphone" ], type="filepath")

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
        if self._is_media_variable(variable) and variable.format is None:
            return create_upload_file(value, variable.type.value, variable.subtype) if value is not None else None

        if variable.type == WorkflowVariableType.INTEGER:
            return int(value) if value != "" else None

        return value if value != "" else None

    def _build_interrupt_components(self):
        message  = gr.Markdown("")
        metadata = gr.JSON(label="Metadata", visible=False)
        answer   = gr.Textbox(label="Answer", lines=2, placeholder="Press Resume to continue, or type an answer (JSON or text)")

        return [ message, metadata, answer ]

    def _build_interrupt_updates(self, state: TaskState) -> List[Any]:
        interrupt = state.interrupt
        ui_state = { "task_id": state.task_id, "job_id": interrupt.job_id if interrupt else None }
        message = (interrupt.message if interrupt else None) or "The workflow is waiting for your input."
        metadata = interrupt.metadata if interrupt else None

        return [
            ui_state,
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
            gr.update(value=None),
        ]

    def _build_output_component(self, variable: Union[WorkflowVariableConfig, WorkflowVariableGroupConfig]) -> Union[gr.Component, List[ComponentGroup]]:
        if isinstance(variable, WorkflowVariableGroupConfig):
            groups: List[ComponentGroup] = []
            for index in range(variable.repeat_count if variable.repeat_count != 0 else 1):
                label = variable.name + (f" #{index + 1}" if variable.repeat_count != 0 else "")
                with gr.Accordion(label=label, open=True) as group:
                    components = [ self._build_output_component(v) for v in variable.variables ]
                groups.append(ComponentGroup(group, components))
            return groups

        label = variable.name or ""
        info = variable.get_annotation_value("description") or ""

        if variable.type in (WorkflowVariableType.STRING, WorkflowVariableType.BASE64):
            return gr.Textbox(label=label, interactive=False, info=info, buttons=["copy"])

        if variable.type in (WorkflowVariableType.NUMBER, WorkflowVariableType.INTEGER):
            return gr.Textbox(label=label, interactive=False, info=info, buttons=["copy"])

        if variable.type == WorkflowVariableType.TEXT:
            return gr.Textbox(label=label, lines=5, max_lines=30, interactive=False, info=info, buttons=["copy"])

        if variable.type == WorkflowVariableType.MARKDOWN:
            return gr.Markdown(label=label)

        if variable.type == WorkflowVariableType.JSON or (variable.type == WorkflowVariableType.OBJECT and variable.is_list):
            return gr.JSON(label=label)

        if variable.type == WorkflowVariableType.IMAGE:
            if variable.is_list:
                return gr.Gallery(label=label, interactive=False)
            return gr.Image(label=label, interactive=False)

        if variable.type == WorkflowVariableType.AUDIO:
            return gr.Audio(label=label)

        if variable.type == WorkflowVariableType.VIDEO:
            if variable.is_list:
                return gr.Gallery(label=label, interactive=False)
            return gr.Video(label=label)

        if variable.type == WorkflowVariableType.FILE:
            return gr.File(label=label, interactive=False)

        if variable.type == WorkflowVariableType.STREAM:
            if variable.subtype == "json":
                return gr.JSON(label=label)
            return gr.Textbox(label=label, lines=5, max_lines=30, interactive=False, info=info, buttons=["copy"])

        if variable.type == WorkflowVariableType.ANY:
            return gr.JSON(label=label)

        if variable.type == WorkflowVariableType.NONE:
            return gr.Markdown(value="")

        return gr.Textbox(label=label, info=f"Unsupported type: {variable.type}")

    def _flatten_output_components(self, components: List[Union[gr.Component, List[ComponentGroup]]]) -> List[gr.Component]:
        flattened = []

        for component in components:
            if isinstance(component, list): # List[ComponentGroup]]
                for group in component:
                    flattened.extend(group.components)
            else:
                flattened.append(component)

        return flattened

    def _clear_output_updates(self, components: List[gr.Component]) -> List[Any]:
        updates = []

        for component in components:
            if isinstance(component, gr.Markdown):
                updates.append(gr.update(value=""))
            else:
                updates.append(gr.update(value=None))

        return updates

    async def _resolve_output_updates(
        self,
        output: Any,
        variables: List[Union[WorkflowVariableConfig, WorkflowVariableGroupConfig]],
        components: List[Union[gr.Component, List[ComponentGroup]]]
    ) -> List[Any]:
        updates: List[Any] = []

        for variable, component in zip(variables, components):
            if isinstance(variable, WorkflowVariableGroupConfig):
                values = (self._resolve_variable_output(output, variable) if isinstance(output, dict) and variable.name else output) or ()
                for index, group in enumerate(component):
                    if index == len(component) - 1:
                        value = values[-1] if values else None
                    else:
                        value = values[index] if index < len(values) else None
                    if value is None:
                        updates.extend(gr.update() for _ in group.components)
                    else:
                        updates.extend(await self._resolve_output_updates(value, variable.variables, group.components))
            else:
                value = self._resolve_variable_output(output, variable)
                updates.append(await self._convert_output_value(value, variable))

        return updates

    async def _stream_output_updates(
        self,
        stream: AsyncIterator,
        variable: Union[WorkflowVariableConfig, WorkflowVariableGroupConfig],
        component: Union[gr.Component, List[ComponentGroup]],
    ) -> AsyncIterator[List[Any]]:
        is_fragmented = stream.is_fragmented if isinstance(stream, StreamChunkIterator) else None

        if isinstance(variable, WorkflowVariableGroupConfig):
            window: deque = deque(maxlen=len(component))
            async for chunk in stream:
                window.append(chunk)
                updates: List[Any] = []
                for index, group in enumerate(component):
                    value = window[index] if index < len(window) else None
                    if value is None:
                        updates.extend(gr.update() for _ in group.components)
                    else:
                        updates.extend(await self._resolve_output_updates(value, variable.variables, group.components))
                yield updates
            return

        concat = is_fragmented if is_fragmented is not None else (self._is_string_variable(variable) and not variable.is_list)
        buffer: Union[str, List[Any]] = "" if concat else []
        async for chunk in stream:
            value = await self._convert_output_value(self._resolve_variable_output(chunk, variable), variable)
            if value is None:
                continue
            if isinstance(buffer, str):
                buffer += value
            else:
                buffer.append(value)
            yield [ buffer ]

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

    def _has_pending_media_updates(
        self,
        updates: List[Any],
        output_components: List[gr.Component],
        media_components: List[gr.Component]
    ) -> bool:
        if not media_components or len(updates) != len(output_components):
            return bool(media_components) and False if not media_components else False

        for update, component in zip(updates, output_components):
            if component in media_components and update is not None:
                return True

        return False

    async def _convert_output_value(self, value: Any, variable: WorkflowVariableConfig) -> Any:
        if variable.type == WorkflowVariableType.NONE:
            return f"✅ {variable.name}" if variable.name else "✅ Completed"

        if variable.type in (WorkflowVariableType.STRING, WorkflowVariableType.TEXT):
            return self._convert_value_to_string(value, variable.subtype, variable.format)

        if variable.type == WorkflowVariableType.IMAGE:
            if variable.is_list:
                if isinstance(value, list):
                    return [ await self._load_image_from_value(v, variable.format) for v in value ]
                return None
            return await self._load_image_from_value(value, variable.format)

        if variable.type in (WorkflowVariableType.AUDIO, WorkflowVariableType.VIDEO, WorkflowVariableType.FILE):
            if variable.is_list:
                if isinstance(value, list):
                    return [ await self._save_value_to_temporary_file(v, variable.subtype, variable.format) for v in value ]
                return None
            return await self._save_value_to_temporary_file(value, variable.subtype, variable.format)

        if variable.type == WorkflowVariableType.STREAM:
            if variable.subtype == "json":
                return value
            return self._convert_value_to_string(value, variable.subtype, variable.format)

        return value

    def _convert_value_to_string(self, value: Any, subtype: Optional[str], format: Optional[WorkflowVariableFormat]) -> Optional[str]:
        if isinstance(value, (dict, list)):
            return json.dumps(value)

        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")

        if value is not None:
            return str(value)

        return None

    async def _load_image_from_value(self, value: Any, format: Optional[WorkflowVariableFormat]) -> Optional[PILImage.Image]:
        if format == WorkflowVariableFormat.URL and isinstance(value, str):
            return await load_image_from_stream(await create_stream_with_url(value))

        if format == WorkflowVariableFormat.DATA_URI and isinstance(value, (str, StreamResource)):
            return await load_image_from_stream(DataUriStreamResource(value))

        if format == WorkflowVariableFormat.BASE64 and isinstance(value, str):
            return await load_image_from_stream(Base64StreamResource(value))

        if isinstance(value, ImageStreamResource):
            return value.image

        if isinstance(value, StreamResource):
            return await load_image_from_stream(value)

        if isinstance(value, PILImage.Image):
            return value

        return None

    async def _save_value_to_temporary_file(self, value: Any, subtype: Optional[str], format: Optional[WorkflowVariableFormat]) -> Optional[str]:
        if format == WorkflowVariableFormat.PATH and isinstance(value, str):
            return value

        if format == WorkflowVariableFormat.URL and isinstance(value, str):
            return await save_stream_to_temporary_file(await create_stream_with_url(value), subtype)

        if format == WorkflowVariableFormat.DATA_URI and isinstance(value, (str, StreamResource)):
            return await save_stream_to_temporary_file(DataUriStreamResource(value), subtype)

        if format == WorkflowVariableFormat.BASE64 and isinstance(value, str):
            return await save_stream_to_temporary_file(Base64StreamResource(value), subtype)

        if isinstance(value, StreamResource):
            return await save_stream_to_temporary_file(value, subtype)

        if isinstance(value, bytes):
            return await save_stream_to_temporary_file(BytesStreamResource(value), subtype)

        return None

    def _is_string_variable(self, variable: WorkflowVariableConfig) -> bool:
        if variable.type in (
            WorkflowVariableType.STRING,
            WorkflowVariableType.TEXT,
            WorkflowVariableType.MARKDOWN,
            WorkflowVariableType.BASE64,
        ):
            return True

        if variable.type == WorkflowVariableType.STREAM and variable.subtype == "text":
            return True

        return False

    def _is_media_variable(self, variable: WorkflowVariableConfig) -> bool:
        return variable.type in (
            WorkflowVariableType.IMAGE,
            WorkflowVariableType.AUDIO,
            WorkflowVariableType.VIDEO,
            WorkflowVariableType.FILE
        )

    def _is_media_component(self, component: gr.Component) -> bool:
        return isinstance(component, (gr.Image, gr.Gallery, gr.Audio, gr.Video, gr.File))

    def _log_messages_for_event(self, event: Union[TaskEvent, JobEvent, ComponentEvent]) -> List[Dict]:
        if isinstance(event, TaskEvent):
            return self._log_messages_for_task_event(event)
        if isinstance(event, JobEvent):
            return self._log_messages_for_job_event(event)
        if isinstance(event, ComponentEvent):
            return self._log_messages_for_component_event(event)
        return []

    def _log_messages_for_task_event(self, event: TaskEvent) -> List[Dict]:
        title = self._log_format_task_title(event)
        if title is None:
            return []
        messages: List[Dict] = [ self._log_assistant_message(f"{title}\n`task_id: {event.task_id}`") ]
        if event.event == "started" and event.input is not None:
            messages.append(self._log_payload_message(event.input, title="Input"))
        if event.event == "failed" and event.error:
            messages.append(self._log_assistant_message(f"```\n{event.error}\n```", title="Error"))
        return messages

    def _log_messages_for_job_event(self, event: JobEvent) -> List[Dict]:
        title = self._log_format_job_title(event)
        messages: List[Dict] = [ self._log_assistant_message(f"{title}\n`job_type: {event.job_type}`") ]
        if event.event == "completed" and event.output is not None:
            messages.append(self._log_payload_message(event.output, title="Output"))
        if event.event == "failed" and event.error:
            messages.append(self._log_assistant_message(f"```\n{event.error}\n```", title="Error"))
        return messages

    def _log_messages_for_component_event(self, event: ComponentEvent) -> List[Dict]:
        title = self._log_format_component_title(event)
        messages: List[Dict] = [ self._log_assistant_message(f"{title}\n`component_type: {event.component_type}`\n`run_id: {event.run_id}`") ]
        if event.input is not None:
            messages.append(self._log_payload_message(event.input, title="Input"))
        if event.output is not None:
            messages.append(self._log_payload_message(event.output, title="Output"))
        if event.error:
            messages.append(self._log_assistant_message(f"```\n{event.error}\n```", title="Error"))
        return messages

    def _log_assistant_message(self, text: str, title: Optional[str] = None) -> Dict:
        message: Dict = {
            "role": "assistant",
            "content": [ {"type": "text", "text": text} ],
        }
        if title:
            message["metadata"] = { "title": title }
        return message

    def _log_payload_message(self, value: Any, title: Optional[str] = None) -> Dict:
        return self._log_assistant_message(self._log_format_payload(value) or "", title=title)

    def _log_spinner_message(self) -> Dict:
        return self._log_assistant_message("<span class=\"log-spinner\">Running...</span>")

    def _log_format_task_title(self, event: TaskEvent) -> Optional[str]:
        workflow_id = self._escape_markdown(event.workflow_id)
        if event.event == "started":
            return f"▶ Workflow '**{workflow_id}**' started"
        if event.event == "resumed":
            return f"▶ Workflow '**{workflow_id}**' resumed"
        if event.event == "interrupted":
            return f"⏸ Workflow '**{workflow_id}**' interrupted"
        if event.event == "completed":
            return f"✓ Workflow '**{workflow_id}**' completed"
        if event.event == "failed":
            return f"✗ Workflow '**{workflow_id}**' failed"
        return None

    def _log_format_job_title(self, event: JobEvent) -> str:
        job_id = self._escape_markdown(event.job_id)
        if event.event == "started":
            return f"▶ Job '**{job_id}**' started"
        if event.event == "completed":
            return f"✓ Job '**{job_id}**' completed · {event.elapsed:.2f}s"
        if event.event == "failed":
            return f"✗ Job '**{job_id}**' failed · {event.elapsed:.2f}s"
        if event.event == "routed":
            next_job_id = self._escape_markdown(event.next_job_id)
            return f"→ Job '**{job_id}**' routed to '**{next_job_id}**' · {event.elapsed:.2f}s"
        return f"• Job '**{job_id}**' {event.event}"

    def _log_format_component_title(self, event: ComponentEvent) -> str:
        component_id = self._escape_markdown(event.component_id)
        if event.event == "started":
            return f"▶ Component '**{component_id}**' started"
        if event.event == "completed":
            return f"✓ Component '**{component_id}**' completed"
        if event.event == "failed":
            return f"✗ Component '**{component_id}**' failed"
        if event.event == "internal":
            return f"└ Component '**{component_id}**' reported" + (f" · [{event.kind}]" if event.kind else "")
        return f"• Component '**{component_id}**' {event.event}"

    def _escape_markdown(self, value: str) -> str:
        return re.sub(r"([\\`*_{}\[\]()#+!~])", r"\\\1", value)

    def _log_format_payload(self, value: Any) -> Optional[str]:
        if isinstance(value, bytes):
            return f"_(bytes, {len(value)} bytes)_"
        if isinstance(value, str):
            return self._log_format_string(value)
        if isinstance(value, (dict, list)):
            return self._log_format_json(value)
        return str(value) if value is not None else None

    def _log_format_string(self, value: str) -> str:
        if len(value) > 200 or "\n" in value:
            return f"```\n{value}\n```"
        return value

    def _log_format_json(self, value: Any) -> str:
        try:
            text = json.dumps(value, ensure_ascii=False, indent=2, default=self._log_json_default)
        except Exception:
            text = repr(value)
        return f"```json\n{text}\n```"

    def _log_json_default(self, obj: Any) -> Any:
        if isinstance(obj, bytes):
            return f"<bytes len={len(obj)}>"
        return repr(obj)

    def _global_css(self) -> str:
        return """
        .log-panel-chatbot {
            flex-grow: 1 !important;
            flex-shrink: 1 !important;
            flex-basis: 0 !important;
            height: auto !important;
            min-height: 80vh !important;
            max-height: 100% !important;
            overflow: hidden !important;
        }
        .log-panel-chatbot * {
            min-height: 0 !important;
        }
        .log-panel-chatbot > .wrap,
        .log-panel-chatbot > .wrapper {
            height: 100% !important;
            max-height: 100% !important;
            overflow: hidden !important;
        }
        .log-panel-chatbot .bubble-wrap {
            flex-grow: 1 !important;
            max-height: 100% !important;
            overflow-y: auto !important;
        }
        .log-panel-chatbot .log-spinner {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
        }
        .log-panel-chatbot .log-spinner::before {
            content: "⠋";
            display: inline-block;
            width: 1em;
            animation: log-panel-spinner 0.8s steps(1, end) infinite;
        }
        @keyframes log-panel-spinner {
            0%   { content: "⠋"; }
            10%  { content: "⠙"; }
            20%  { content: "⠹"; }
            30%  { content: "⠸"; }
            40%  { content: "⠼"; }
            50%  { content: "⠴"; }
            60%  { content: "⠦"; }
            70%  { content: "⠧"; }
            80%  { content: "⠇"; }
            90%  { content: "⠏"; }
        }
        .input-output-column > * {
            flex-grow: 0 !important;
        }
        """
