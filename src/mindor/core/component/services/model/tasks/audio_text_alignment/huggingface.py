from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import HuggingfaceAudioTextAlignmentModelArchitecture
from mindor.dsl.schema.action import ModelActionConfig, AudioTextAlignmentModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.audio import AudioBufferStreamer
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.logger import logging
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import ComponentActionContext
from ...base.huggingface.multimodal import HuggingfaceMultimodalModelTaskService
from .common import AudioTextAlignmentTaskAction
import asyncio

if TYPE_CHECKING:
    from transformers import PreTrainedModel, ProcessorMixin
    import numpy as np
    import torch

_DEFAULT_SAMPLE_RATE = 16000

class HuggingfaceAudioTextAlignmentTaskAction(AudioTextAlignmentTaskAction):
    def __init__(
        self,
        config: AudioTextAlignmentModelActionConfig,
        model: PreTrainedModel,
        processor: ProcessorMixin,
        device: torch.device,
    ):
        super().__init__(config, device)

        self.model: PreTrainedModel = model
        self.processor: ProcessorMixin = processor
        self.sample_rate: int = self._resolve_sample_rate(processor)

    @staticmethod
    def _resolve_sample_rate(processor: ProcessorMixin) -> int:
        feature_extractor = getattr(processor, "feature_extractor", None)
        sample_rate = getattr(feature_extractor, "sampling_rate", None) if feature_extractor is not None else None

        if sample_rate is None:
            logging.warning(
                "Processor %s does not expose feature_extractor.sampling_rate; falling back to %d Hz.",
                type(processor).__name__, _DEFAULT_SAMPLE_RATE,
            )
            return _DEFAULT_SAMPLE_RATE

        return int(sample_rate)

    async def _align_batch(
        self,
        audios: List[MediaSource],
        texts: List[str],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[List[Dict[str, Any]]]:
        results: List[List[Dict[str, Any]]] = []

        for audio, text in zip(audios, texts):
            results.append(await self._align(audio, text, params))

        return results

    async def _align(self, audio: MediaSource, text: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        from torchaudio.functional import forced_align, merge_tokens
        import torch

        words = self._split_words(text)
        if not words:
            return []

        target_ids = self._encode_transcript(" ".join(words))
        if not target_ids:
            return []

        log_probs, total_samples = await self._stream_log_probs(audio, params)  # (1, T, V)

        # torchaudio's forced_align has no MPS kernel — run it on CPU for
        # backends without a native implementation. CUDA / CPU keep the forward
        # device to avoid an unnecessary copy.
        alignment_device = torch.device("cpu") if log_probs.device.type in [ "mps" ] else log_probs.device
        log_probs = log_probs.to(alignment_device)

        blank_id = self._get_blank_id()
        targets = torch.tensor([ target_ids ], dtype=torch.int32, device=alignment_device)

        aligned_tokens, alignment_scores = forced_align(log_probs, targets, blank=blank_id)
        token_spans = merge_tokens(aligned_tokens[0], alignment_scores[0], blank=blank_id)

        seconds_per_frame = self._get_seconds_per_frame(total_samples, log_probs.shape[1])
        word_pieces = self._group_word_pieces(target_ids, words)

        segments: List[Dict[str, Any]] = []
        span_iterator = iter(token_spans)

        for piece_count, word in word_pieces:
            spans = [ next(span_iterator) for _ in range(piece_count) ]
            if not spans:
                continue

            start_frame = spans[0].start
            end_frame   = spans[-1].end
            confidence  = sum(float(s.score) for s in spans) / len(spans)

            segment: Dict[str, Any] = {
                "text":       word,
                "start_time": float(start_frame * seconds_per_frame),
                "end_time":   float(end_frame   * seconds_per_frame),
            }

            if params["return_confidence"]:
                segment["confidence"] = confidence

            segments.append(segment)

        return segments

    async def _stream_log_probs(self, audio: MediaSource, params: Dict[str, Any]) -> Tuple[torch.Tensor, int]:
        # Stream fixed-size windows, forward each on-device, and stitch the emissions
        # on CPU. Peak VRAM is bounded by the window regardless of audio length.
        import torch

        chunk_samples   = int(params["chunk_length"]  * self.sample_rate)
        overlap_samples = int(params["chunk_overlap"] * self.sample_rate)
        stride_samples  = chunk_samples - overlap_samples

        chunks: List[torch.Tensor] = []
        chunk_index = 0

        streamer = AudioBufferStreamer(audio, channel="mono", sample_rate=self.sample_rate)
        async for chunk, is_last in streamer.stream(chunk_samples, overlap_samples):
            chunks.append(await self._forward_and_trim(chunk.waveform, overlap_samples, chunk_index, is_last=is_last))
            chunk_index += 1

        if not chunks:
            raise ValueError("Audio stream produced no frames; cannot run alignment.")

        # Approximate total-audio length as the last window's right edge. When the
        # final chunk is zero-padded, this over-estimates by at most chunk_overlap
        # seconds — acceptable for word-level timestamps.
        total_samples = max(0, chunk_index - 1) * stride_samples + chunk_samples
        stitched = torch.cat(chunks, dim=1).to(self.device)

        return stitched, total_samples

    async def _forward_and_trim(
        self,
        waveform: np.ndarray,
        overlap_samples: int,
        chunk_index: int,
        is_last: bool,
    ) -> torch.Tensor:
        log_probs = await asyncio.to_thread(self._forward_chunk, waveform)  # (1, t, V) on device

        # Drop overlap frames on the inner edges so each output frame comes from the
        # chunk with the most context around it: trim the leading half from non-first
        # chunks and the trailing half from non-last chunks.
        downsample_ratio = waveform.shape[-1] / log_probs.shape[1]
        overlap_frames   = int(round(overlap_samples / downsample_ratio))
        trim_head        = overlap_frames // 2 if chunk_index > 0 else 0
        trim_tail        = overlap_frames - overlap_frames // 2 if not is_last else 0

        tail_index = log_probs.shape[1] - trim_tail
        if tail_index <= trim_head:
            return log_probs[:, :0, :].cpu()

        return log_probs[:, trim_head:tail_index, :].cpu()

    def _forward_chunk(self, waveform: np.ndarray) -> torch.Tensor:
        import torch

        # AudioBufferStreamer yields (channels, samples); Wav2Vec2's feature extractor
        # expects a 1-D mono waveform per example, so squeeze the channel axis.
        if waveform.ndim == 2:
            waveform = waveform[0] if waveform.shape[0] == 1 else waveform.mean(axis=0)

        inputs = self.processor(
            waveform,
            sampling_rate=self.sample_rate,
            return_tensors="pt",
            padding=False,
        )
        input_values = inputs["input_values"].to(self.device)
        attention_mask = inputs.get("attention_mask")
        if attention_mask is not None:
            attention_mask = attention_mask.to(self.device)

        with torch.inference_mode():
            logits = self.model(input_values, attention_mask=attention_mask).logits
            return torch.log_softmax(logits, dim=-1)

    def _split_words(self, text: str) -> List[str]:
        return [ token for token in text.strip().split() if token ]

    def _encode_transcript(self, transcript: str) -> List[int]:
        # CTC tokenizers expect uppercase for many English models; the tokenizer
        # itself handles casing where relevant. We pass the raw transcript and
        # skip special tokens so the id list matches the CTC target sequence.
        encoded = self.processor.tokenizer(transcript, add_special_tokens=False, return_attention_mask=False)
        return list(encoded["input_ids"])

    def _group_word_pieces(self, target_ids: List[int], words: List[str]) -> List[Tuple[int, str]]:
        """Return (num_tokens_for_word, word_text) pairs by walking target_ids and
        splitting at the CTC word-delimiter token (e.g. '|' for Wav2Vec2)."""
        delimiter_id = self._get_word_delimiter_id()

        groups: List[Tuple[int, str]] = []
        cursor = 0
        for word in words:
            count = 0
            while cursor < len(target_ids) and target_ids[cursor] != delimiter_id:
                count += 1
                cursor += 1
            # Skip the delimiter itself between words.
            if cursor < len(target_ids) and target_ids[cursor] == delimiter_id:
                cursor += 1
            groups.append((count, word))

        return groups

    def _get_blank_id(self) -> int:
        pad_id = getattr(self.processor.tokenizer, "pad_token_id", None)
        if pad_id is not None:
            return int(pad_id)
        # Wav2Vec2 CTC convention: blank is index 0.
        return 0

    def _get_word_delimiter_id(self) -> Optional[int]:
        delimiter = getattr(self.processor.tokenizer, "word_delimiter_token", None)
        if delimiter is None:
            return None
        return self.processor.tokenizer.convert_tokens_to_ids(delimiter)

    def _get_seconds_per_frame(self, num_samples: int, num_frames: int) -> float:
        if num_frames > 0:
            return (num_samples / self.sample_rate) / num_frames
        return 0.0

@register_model_task_service(ModelTaskType.AUDIO_TEXT_ALIGNMENT, ModelDriver.HUGGINGFACE)
class HuggingfaceAudioTextAlignmentTaskService(HuggingfaceMultimodalModelTaskService):
    def get_setup_requirements(self) -> Optional[List[str]]:
        return [
            "transformers>=4.21.0",
            "torch",
            "torchaudio>=2.1",
            "accelerate",
            "soxr",
        ]

    def _get_model_class(self) -> Type[PreTrainedModel]:
        if self.config.architecture == HuggingfaceAudioTextAlignmentModelArchitecture.AUTO:
            from transformers import AutoModelForCTC
            return AutoModelForCTC

        if self.config.architecture == HuggingfaceAudioTextAlignmentModelArchitecture.WAV2VEC2:
            from transformers import Wav2Vec2ForCTC
            return Wav2Vec2ForCTC

        raise ValueError(f"Unknown architecture: {self.config.architecture}")

    def _get_processor_class(self) -> Type[ProcessorMixin]:
        if self.config.architecture == HuggingfaceAudioTextAlignmentModelArchitecture.AUTO:
            from transformers import AutoProcessor
            return AutoProcessor

        if self.config.architecture == HuggingfaceAudioTextAlignmentModelArchitecture.WAV2VEC2:
            from transformers import Wav2Vec2Processor
            return Wav2Vec2Processor

        raise ValueError(f"Unknown architecture: {self.config.architecture}")

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await HuggingfaceAudioTextAlignmentTaskAction(action, self.model, self.processor, self.device).run(context)
