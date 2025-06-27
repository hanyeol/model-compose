from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Awaitable, Any
from mindor.dsl.schema.workflow import WorkflowVariableConfig
from mindor.core.utils.http_client import HttpStreamResource
from mindor.core.utils.image import load_image_from_stream
from mindor.core.utils.streaming import Base64StreamResource, save_stream_to_temporary_file
from .schema import WorkflowSchema
import gradio as gr

class GradioWebUIBuilder:
    def build(self, schema: Dict[str, WorkflowSchema], runner: Callable[[Optional[str], Any], Awaitable[Any]]) -> gr.Blocks:
        with gr.Blocks() as blocks:
            for workflow_id, workflow in schema.items():
                async def run_workflow(input: Any, workflow_id=workflow_id) -> Any:
                    return await runner(workflow_id, input)

                if len(schema) > 1:
                    with gr.Tab(label=workflow.name or workflow_id):
                        self._build_workflow_section(workflow, run_workflow)
                else:
                    self._build_workflow_section(workflow, run_workflow)

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
                output_components = gr.Textbox(label="", lines=8, interactive=False, show_copy_button=True)

            async def run_workflow(*args):
                input = { variable.name: value for variable, value in zip(workflow.input, args) }
                output = await runner(input)

                if workflow.output:
                    if isinstance(output, dict):
                        output = [ await self._convert_type(output[variable.name], variable.type, variable.subtype, variable.format) for variable in workflow.output ]
                        output = output[0] if len(output) == 1 else output
                    else:
                        variable = workflow.output[0]
                        output = await self._convert_type(output, variable.type, variable.subtype, variable.format)

                return output

            run_button.click(
                fn=run_workflow,
                inputs=input_components,
                outputs=output_components
            )

        return section

    def _build_input_component(self, variable: WorkflowVariableConfig) -> gr.Component:
        label = variable.name + (" *" if variable.required else "") + (f" (default: {variable.default})" if variable.default else "")
        info = variable.description or ""
        default = variable.default

        if variable.type == "string":
            return gr.Textbox(label=label, value="", info=info)

        if variable.type == "number":
            return gr.Number(label=label, value="", precision=None, info=info)
        
        if variable.type == "integer":
            return gr.Number(label=label, value="", precision=0, info=info)
        
        if variable.type == "boolean":
            return gr.Checkbox(label=label, value=default or False, info=info)

        if variable.type == "file":
            return gr.File(label=label, file_types=["*"], info=info)

        if variable.type == "select":
            return gr.Dropdown(choices=variable.options or [], label=label, value=default, info=info)
        
        return gr.Textbox(label=label, value=default, info=f"Unsupported type: {variable.type}")

    def _build_output_component(self, variable: WorkflowVariableConfig) -> gr.Component:
        label = variable.name or ""
        info = variable.description or ""

        if variable.type == "string":
            return gr.Textbox(label=label, interactive=False, show_copy_button=True, info=info)
        
        if variable.type == "image":
            return gr.Image(label=label, interactive=False)
        
        if variable.type == "audio":
            return gr.Audio(label=label)
    
        return gr.Textbox(label=label, info=f"Unsupported type: {variable.type}")

    async def _convert_type(self, value: Any, type: Optional[str], subtype: Optional[str], format: Optional[str]) -> Any:
        if type == "image":
            if format == "base64" and isinstance(value, str):
                return await load_image_from_stream(Base64StreamResource(value), subtype)
            if isinstance(value, HttpStreamResource):
                return await load_image_from_stream(value, subtype)
            return None

        if type == "audio":
            if format == "base64" and isinstance(value, str):
                return await save_stream_to_temporary_file(Base64StreamResource(value), subtype)
            if isinstance(value, HttpStreamResource):
                return await save_stream_to_temporary_file(value, subtype)
            return None

        return value
