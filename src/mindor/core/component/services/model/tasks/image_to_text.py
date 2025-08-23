from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Protocol, Any
from mindor.dsl.schema.component import ModelComponentConfig, ImageToTextModelArchitecture
from mindor.dsl.schema.action import ModelActionConfig, ImageToTextModelActionConfig
from mindor.core.utils.streamer import AsyncStreamer
from mindor.core.logger import logging
from ..base import ModelTaskService, ModelTaskType, register_model_task_service
from ..base import ComponentActionContext
from transformers import PreTrainedModel, PreTrainedTokenizer, ProcessorMixin, GenerationMixin, TextIteratorStreamer
from PIL import Image as PILImage
from threading import Thread
from torch import Tensor
import torch, asyncio

class WithTokenizer(Protocol):
    tokenizer: PreTrainedTokenizer

class ImageToTextTaskAction:
    def __init__(self, config: ImageToTextModelActionConfig, model: PreTrainedModel, processor: ProcessorMixin, device: torch.device):
        self.config: ImageToTextModelActionConfig = config
        self.model: Union[PreTrainedModel, GenerationMixin] = model
        self.processor: Union[ProcessorMixin, WithTokenizer] = processor
        self.device: torch.device = device

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        image: Union[PILImage.Image, List[PILImage.Image]] = await context.render_image(self.config.image)
        prompt: Optional[Union[str, List[str]]] = await context.render_variable(self.config.prompt)

        batch_size = await context.render_variable(self.config.params.batch_size)
        stream     = await context.render_variable(self.config.stream)

        is_single_input: bool = bool(not isinstance(images, list))
        images: List[PILImage.Image] = [ image ] if is_single_input else image
        prompts: Optional[List[str]] = [ prompt ] if is_single_input else prompt
        results = []

        if stream and (batch_size != 1 or len(images) != 1):
            raise ValueError("Streaming mode only supports a single input image with batch size of 1.")

        streamer = TextIteratorStreamer(self.processor.tokenizer, skip_prompt=True, skip_special_tokens=True) if stream else None
        for index in range(0, len(images), batch_size):
            batch_images = images[index:index + batch_size]
            batch_prompts = prompts[index:index + batch_size] if prompts else None
            
            inputs: Tensor = self.processor(images=batch_images, text=batch_prompts, return_tensors="pt")
            inputs = inputs.to(self.device)

            def _generate():
                with torch.inference_mode():
                    outputs = self.model.generate(
                        **inputs,
                        streamer=streamer
                    )

                outputs = self.processor.tokenizer.batch_decode(outputs, skip_special_tokens=True)
                results.extend(outputs)

            if stream:
                thread = Thread(target=_generate)
                thread.start()
            else:
                _generate()

        if stream:
            async def _stream_output_generator():
                async for chunk in AsyncStreamer(streamer, loop):
                    if chunk:
                        context.register_source("result[]", chunk)
                        yield (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else chunk

            return _stream_output_generator()
        else:
            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else result

@register_model_task_service(ModelTaskType.IMAGE_TO_TEXT)
class ImageToTextTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[Union[PreTrainedModel, GenerationMixin]] = None
        self.processor: Optional[ProcessorMixin] = None
        self.device: Optional[torch.device] = None

    async def _serve(self) -> None:
        try:
            self.model = self._load_pretrained_model()
            self.processor = self._load_pretrained_processor()
            self.device = self._get_model_device(self.model)
            logging.info(f"Model and processor loaded successfully on device '{self.device}': {self.config.model}")
        except Exception as e:
            logging.error(f"Failed to load model '{self.config.model}': {e}")
            raise

    async def _shutdown(self) -> None:
        self.model = None
        self.processor = None
        self.device = None

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await ImageToTextTaskAction(action, self.model, self.processor, self.device).run(context, loop)

    def _get_model_class(self) -> Type[PreTrainedModel]:
        if self.config.architecture == ImageToTextModelArchitecture.BLIP:
            from transformers import BlipForConditionalGeneration
            return BlipForConditionalGeneration

        if self.config.architecture == ImageToTextModelArchitecture.BLIP2:
            from transformers import Blip2ForConditionalGeneration
            return Blip2ForConditionalGeneration

        if self.config.architecture == ImageToTextModelArchitecture.GIT:
            from transformers import GitForCausalLM
            return GitForCausalLM

        if self.config.architecture == ImageToTextModelArchitecture.PIX2STRUCT:
            from transformers import Pix2StructForConditionalGeneration
            return Pix2StructForConditionalGeneration

        if self.config.architecture == ImageToTextModelArchitecture.DONUT:
            from transformers import VisionEncoderDecoderModel # Donut uses this
            return VisionEncoderDecoderModel

        if self.config.architecture == ImageToTextModelArchitecture.KOSMOS2:
            from transformers import Kosmos2ForConditionalGeneration
            return Kosmos2ForConditionalGeneration
        
        raise ValueError(f"Unknown architecture: {self.config.architecture}")

    def _get_processor_class(self) -> Type[ProcessorMixin]:
        if self.config.architecture == ImageToTextModelArchitecture.BLIP:
            from transformers import BlipProcessor
            return BlipProcessor

        if self.config.architecture == ImageToTextModelArchitecture.BLIP2:
            from transformers import Blip2Processor
            return Blip2Processor

        if self.config.architecture == ImageToTextModelArchitecture.GIT:
            from transformers import GitProcessor
            return GitProcessor

        if self.config.architecture == ImageToTextModelArchitecture.PIX2STRUCT:
            from transformers import Pix2StructProcessor
            return Pix2StructProcessor

        if self.config.architecture == ImageToTextModelArchitecture.DONUT:
            from transformers import DonutProcessor
            return DonutProcessor

        if self.config.architecture == ImageToTextModelArchitecture.KOSMOS2:
            from transformers import Kosmos2Processor
            return Kosmos2Processor

        raise ValueError(f"Unknown architecture: {self.config.architecture}")
