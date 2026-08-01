from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Optional, Dict, List, Any
from collections.abc import AsyncIterator
from mindor.core.utils.streamer import SyncGeneratorStreamer
from mindor.dsl.schema.component import HuggingfaceSpeechToTextModelArchitecture
from mindor.dsl.schema.action import ModelActionConfig, HuggingfaceSpeechToTextModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.audio import AudioBufferStreamer
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.logger import logging
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import ComponentActionContext
from ...base.huggingface.multimodal import HuggingfaceMultimodalModelTaskService
from ...base.huggingface.streamer import BatchTextIteratorStreamer
from ...base.huggingface.cancellation import create_cancellation_criteria
from .common import SpeechToTextTaskAction
from threading import Thread
import asyncio

if TYPE_CHECKING:
    from transformers import PreTrainedModel, ProcessorMixin, StoppingCriteriaList
    import numpy as np
    import torch

class HuggingfaceSpeechToTextTaskAction(SpeechToTextTaskAction):
    def __init__(
        self,
        config: HuggingfaceSpeechToTextModelActionConfig,
        model: PreTrainedModel,
        processor: ProcessorMixin,
        device: torch.device
    ):
        super().__init__(config, device)

        self.model: PreTrainedModel = model
        self.processor: ProcessorMixin = processor

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        task              = await context.render_variable(self.config.task) if self.config.task is not None else None
        max_output_length = await context.render_variable(self.config.max_output_length) if self.config.max_output_length is not None else None
        chunk_length      = await context.render_variable(self.config.chunk_length) if self.config.chunk_length is not None else None

        generation_params: Dict[str, Any] = await self._resolve_generation_params(context)

        if params["language"] is not None:
            generation_params["language"] = params["language"]

        if task is not None:
            generation_params["task"] = task

        if max_output_length is not None:
            generation_params["max_new_tokens"] = max_output_length

        # HF expects `return_timestamps=True` for segment-level and `"word"` for word-level.
        if params["return_timestamps"]:
            generation_params["return_timestamps"] = "word" if params["timestamp_level"] == "word" else True

        params["generation"]   = generation_params
        params["chunk_length"] = chunk_length

        return params

    async def _resolve_generation_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        num_beams                   = await context.render_variable(self.config.params.num_beams)
        temperature                 = await context.render_variable(self.config.params.temperature)
        compression_ratio_threshold = await context.render_variable(self.config.params.compression_ratio_threshold)
        logprob_threshold           = await context.render_variable(self.config.params.logprob_threshold)
        no_speech_threshold         = await context.render_variable(self.config.params.no_speech_threshold)

        params: Dict[str, Any] = {
            "num_beams": num_beams,
        }

        if temperature is not None:
            params["temperature"] = temperature
            if temperature > 0:
                params["do_sample"] = True

        if compression_ratio_threshold is not None:
            params["compression_ratio_threshold"] = compression_ratio_threshold
        if logprob_threshold is not None:
            params["logprob_threshold"] = logprob_threshold
        if no_speech_threshold is not None:
            params["no_speech_threshold"] = no_speech_threshold

        return params

    async def _transcribe_batch(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Union[List[str], List[AsyncIterator[str]], List[List[Dict[str, Any]]], List[AsyncIterator[Dict[str, Any]]]]:
        loop = asyncio.get_running_loop()

        # Audio preprocessing is real async IO (stream reads), so keep it on
        # the loop instead of the executor thread.
        waveforms = await self._preprocess_audio(audios)

        return_timestamps = params["generation"].get("return_timestamps")

        # Timestamp extraction requires the full generated sequence for post-processing,
        # so streaming timestamps are emitted after generation completes rather than
        # token-by-token.
        native_streaming = streaming and not return_timestamps

        def _transcribe() -> Union[List[str], List[List[Dict[str, Any]]], List[Any]]:
            import torch

            input_features = self.processor(
                waveforms,
                sampling_rate=16000,
                return_tensors="pt",
                padding=True,
                chunk_length=params["chunk_length"]
            )
            input_features = input_features.to(self.device)

            stopping_criteria = self._build_stopping_criteria(cancellation_token)

            if native_streaming:
                streamer = BatchTextIteratorStreamer(
                    self.processor.tokenizer,
                    batch_size=len(waveforms),
                    skip_prompt=True,
                    skip_special_tokens=True
                )

                def _run():
                    try:
                        with torch.inference_mode():
                            self.model.generate(**input_features, **params["generation"], stopping_criteria=stopping_criteria, streamer=streamer)
                    except BaseException:
                        logging.exception("Whisper streaming generate failed")
                    finally:
                        streamer.end()

                Thread(target=_run, daemon=True).start()

                return [ streamer[index] for index in range(len(waveforms)) ]

            with torch.inference_mode():
                if return_timestamps == "word":
                    outputs = self.model.generate(
                        **input_features,
                        **params["generation"],
                        return_dict_in_generate=True,
                        stopping_criteria=stopping_criteria,
                    )
                    predicted_ids  = outputs["sequences"]
                    word_segments  = outputs.get("segments")
                else:
                    predicted_ids  = self.model.generate(**input_features, **params["generation"], stopping_criteria=stopping_criteria)
                    word_segments  = None

            if not return_timestamps:
                return self.processor.batch_decode(predicted_ids, skip_special_tokens=True)

            if return_timestamps == "word":
                return self._decode_word_level_segments(word_segments)

            return self._decode_segment_level_segments(predicted_ids)

        results = await self._run_in_executor(_transcribe)

        if native_streaming:
            return [ SyncGeneratorStreamer(streamer, loop) for streamer in results ]

        # Timestamped generation cannot stream token-by-token, so re-emit the
        # collected segments one by one to preserve the AsyncIterator interface
        # expected by downstream jobs.
        if streaming and return_timestamps:
            streams: List[AsyncIterator[Dict[str, Any]]] = []
            for segments in results:
                async def _stream_chunk_generator(segments=segments):
                    for segment in segments:
                        yield segment
                streams.append(_stream_chunk_generator())
            return streams

        return results

    def _decode_segment_level_segments(self, predicted_ids: Any) -> List[List[Dict[str, Any]]]:
        time_precision = self._get_time_precision()

        results: List[List[Dict[str, Any]]] = []
        for index in range(predicted_ids.shape[0]):
            _, optional = self.processor.tokenizer._decode_asr(
                [ { "tokens": predicted_ids[index:index + 1] } ],
                return_timestamps=True,
                return_language=False,
                time_precision=time_precision,
            )
            results.append([
                {
                    "text":       chunk["text"],
                    "start_time": float(chunk["timestamp"][0]) if chunk["timestamp"][0] is not None else 0.0,
                    "end_time":   float(chunk["timestamp"][1]) if chunk["timestamp"][1] is not None else 0.0,
                }
                for chunk in optional.get("chunks", [])
            ])

        return results

    def _decode_word_level_segments(self, batch_segments: Optional[List[List[Dict[str, Any]]]]) -> List[List[Dict[str, Any]]]:
        time_precision = self._get_time_precision()

        results: List[List[Dict[str, Any]]] = []
        for segments in batch_segments or []:
            result: List[Dict[str, Any]] = []
            for segment in segments:
                tokens           = segment["tokens"].unsqueeze(0)
                token_timestamps = segment["token_timestamps"].unsqueeze(0)

                _, optional = self.processor.tokenizer._decode_asr(
                    [ { "tokens": tokens, "token_timestamps": token_timestamps } ],
                    return_timestamps="word",
                    return_language=False,
                    time_precision=time_precision,
                )

                words = [
                    {
                        "text":       chunk["text"],
                        "start_time": float(chunk["timestamp"][0]) if chunk["timestamp"][0] is not None else 0.0,
                        "end_time":   float(chunk["timestamp"][1]) if chunk["timestamp"][1] is not None else 0.0,
                    }
                    for chunk in optional.get("chunks", [])
                ]
    
                result.append({
                    "text":       "".join(word["text"] for word in words),
                    "start_time": float(segment["start"]),
                    "end_time":   float(segment["end"]),
                    "words":      words,
                })

            results.append(result)

        return results

    def _get_time_precision(self) -> float:
        return self.processor.feature_extractor.chunk_length / self.model.config.max_source_positions

    async def _preprocess_audio(self, audios: List[MediaSource]) -> List[np.ndarray]:
        waveforms: List[np.ndarray] = []

        for audio in audios:
            waveform, _ = await AudioBufferStreamer(audio, sample_rate=16000, channel="mono").collect()
            waveforms.append(waveform)

        return waveforms

    def _build_stopping_criteria(self, cancellation_token: Optional[CancellationToken]) -> Optional[StoppingCriteriaList]:
        from transformers import StoppingCriteriaList

        criteria = []

        if cancellation_token:
            criteria.append(create_cancellation_criteria(cancellation_token))

        return StoppingCriteriaList(criteria) if criteria else None

@register_model_task_service(ModelTaskType.SPEECH_TO_TEXT, ModelDriver.HUGGINGFACE)
class HuggingfaceSpeechToTextTaskService(HuggingfaceMultimodalModelTaskService):
    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await HuggingfaceSpeechToTextTaskAction(action, self.model, self.processor, self.device).run(context)

    def _get_model_class(self) -> Type[PreTrainedModel]:
        if self.config.architecture == HuggingfaceSpeechToTextModelArchitecture.AUTO:
            from transformers import AutoModelForSpeechSeq2Seq
            return AutoModelForSpeechSeq2Seq

        if self.config.architecture == HuggingfaceSpeechToTextModelArchitecture.WHISPER:
            from transformers import WhisperForConditionalGeneration
            return WhisperForConditionalGeneration

        raise ValueError(f"Unknown architecture: {self.config.architecture}")

    def _get_processor_class(self) -> Type[ProcessorMixin]:
        if self.config.architecture == HuggingfaceSpeechToTextModelArchitecture.AUTO:
            from transformers import AutoProcessor
            return AutoProcessor

        if self.config.architecture == HuggingfaceSpeechToTextModelArchitecture.WHISPER:
            from transformers import WhisperProcessor
            return WhisperProcessor

        raise ValueError(f"Unknown architecture: {self.config.architecture}")

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [
            "transformers>=4.21.0",
            "torch",
            "torchaudio",
            "accelerate",
            "soxr",
        ]
