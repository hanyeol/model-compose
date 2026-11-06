from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Type, Optional, Dict, List, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.action import ModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.utils.streamer import SyncGeneratorStreamer
from .....base import ComponentActionContext
from .....base.huggingface.streamer import BatchTextIteratorStreamer
from ..base import HuggingfaceSpeechToTextTaskAction, HuggingfaceSpeechToTextBaseDriver
from threading import Thread
import asyncio

if TYPE_CHECKING:
    from transformers import PreTrainedModel, ProcessorMixin

# Placeholder identifier passed to VoxtralProcessor.apply_transcription_request;
# the processor only stores it in the OpenAI-style transcription request's
# `model` field (optional in the upstream schema) and never dereferences it,
# so any non-empty string works regardless of how the model was provisioned.
_DEFAULT_MODEL_ID = "voxtral"

class VoxtralHuggingfaceSpeechToTextTaskAction(HuggingfaceSpeechToTextTaskAction):
    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        if params["span"] is not None:
            raise ValueError("`span` is not supported by the huggingface Voxtral speech-to-text driver.")

        if params["return_timestamps"]:
            raise ValueError("`return_timestamps` is not supported by the huggingface Voxtral speech-to-text driver.")

        max_output_length = await context.render_variable(self.config.max_output_length)

        generation_params: Dict[str, Any] = await self._resolve_generation_params(context)

        if max_output_length is not None:
            generation_params["max_new_tokens"] = max_output_length

        params["generation"] = generation_params

        return params

    async def _transcribe_batch(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Union[List[str], List[AsyncIterator[str]]]:
        waveforms = await self._preprocess_audio(audios)
        language  = params["language"] or "en"

        def _transcribe() -> Union[List[str], List[Any]]:
            import torch

            inputs = self.processor.apply_transcription_request(
                language=language,
                audio=waveforms,
                model_id=_DEFAULT_MODEL_ID,
                sampling_rate=16000,
                return_tensors="pt",
            )
            inputs = inputs.to(self.device, dtype=self.model.dtype)

            stopping_criteria = self._build_stopping_criteria(cancellation_token)

            if streaming:
                streamer = BatchTextIteratorStreamer(
                    self.processor.tokenizer,
                    batch_size=len(waveforms),
                    skip_prompt=True,
                    skip_special_tokens=True
                )

                def _run():
                    try:
                        with torch.inference_mode():
                            self.model.generate(
                                **inputs,
                                **params["generation"],
                                stopping_criteria=stopping_criteria,
                                streamer=streamer,
                            )
                    finally:
                        streamer.end()

                Thread(target=_run, daemon=True).start()

                return [ streamer[index] for index in range(len(waveforms)) ]

            with torch.inference_mode():
                predicted_ids = self.model.generate(
                    **inputs,
                    **params["generation"],
                    stopping_criteria=stopping_criteria,
                )

            # Voxtral emits the full prompt + transcription; strip the prompt tokens so
            # only the transcription text remains.
            predicted_ids = predicted_ids[:, inputs["input_ids"].shape[1]:]

            return self.processor.batch_decode(predicted_ids, skip_special_tokens=True)

        results = await self._run_in_executor(_transcribe)

        if streaming:
            loop = asyncio.get_running_loop()
            return [ SyncGeneratorStreamer(streamer, loop) for streamer in results ]

        return results

class VoxtralHuggingfaceSpeechToTextTaskDriver(HuggingfaceSpeechToTextBaseDriver):
    def _get_model_class(self) -> Type[PreTrainedModel]:
        from transformers import VoxtralForConditionalGeneration
        return VoxtralForConditionalGeneration

    def _get_processor_class(self) -> Type[ProcessorMixin]:
        from transformers import VoxtralProcessor
        return VoxtralProcessor

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await VoxtralHuggingfaceSpeechToTextTaskAction(
            action,
            self.model,
            self.processor,
            self.device,
        ).run(context)
