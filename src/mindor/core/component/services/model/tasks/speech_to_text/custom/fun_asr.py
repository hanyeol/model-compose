from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Dict, Optional, List, Tuple, Union, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import ModelComponentConfig, FunAsrSpeechToTextModelComponentConfig, HuggingfaceModelConfig
from mindor.dsl.schema.action import ModelActionConfig, FunAsrSpeechToTextModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.audio import AudioBufferStreamer
from mindor.core.foundation.streaming.media import MediaSource
from ......base import ComponentActionContext
from ....base import ModelTaskService
from ..common import SpeechToTextTaskAction

if TYPE_CHECKING:
    import torch

# Fun-ASR expects language names in Chinese, not ISO codes. Map the common
# ISO 639-1 codes our other STT drivers accept onto the Fun-ASR vocabulary.
_LANGUAGE_CODE_MAP: Dict[str, str] = {
    "zh":  "中文",
    "en":  "英文",
    "yue": "粤语",
    "ja":  "日文",
    "ko":  "韩文",
    "vi":  "越南文",
    "id":  "印尼文",
    "th":  "泰文",
    "ms":  "马来文",
    "fil": "菲律宾文",
    "tl":  "菲律宾文",
    "ar":  "阿拉伯文",
    "hi":  "印地文",
    "bg":  "保加利亚文",
    "hr":  "克罗地亚文",
    "cs":  "捷克文",
    "da":  "丹麦文",
    "nl":  "荷兰文",
    "et":  "爱沙尼亚文",
    "fi":  "芬兰文",
    "el":  "希腊文",
    "hu":  "匈牙利文",
    "ga":  "爱尔兰文",
    "lv":  "拉脱维亚文",
    "lt":  "立陶宛文",
    "mt":  "马耳他文",
    "pl":  "波兰文",
    "pt":  "葡萄牙文",
    "ro":  "罗马尼亚文",
    "sk":  "斯洛伐克文",
    "sl":  "斯洛文尼亚文",
    "sv":  "瑞典文",
}

class FunAsrSpeechToTextTaskAction(SpeechToTextTaskAction):
    def __init__(
        self,
        config: FunAsrSpeechToTextModelActionConfig,
        model: Any,
        inverse_text_normalization: bool,
        device: Optional[torch.device],
    ):
        super().__init__(config, device)

        self.model: Any = model
        self.inverse_text_normalization: bool = inverse_text_normalization

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        # Fun-ASR uses "itn" as the kwarg name for inverse text normalization.
        generation_params: Dict[str, Any] = { "itn": self.inverse_text_normalization }

        language = self._resolve_language(params["language"])

        if language is not None:
            generation_params["language"] = language

        params["generation"] = generation_params

        return params

    async def _transcribe_batch(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Union[List[str], List[AsyncIterator[str]], List[List[Dict[str, Any]]], List[AsyncIterator[Dict[str, Any]]]]:
        waveforms = await self._preprocess_audio(audios)

        # Fun-ASR-Nano rejects batch decoding (see model.inference_prepare); feed
        # samples one at a time and concatenate the results.
        def _transcribe() -> Union[List[str], List[List[Dict[str, Any]]]]:
            results: List[Any] = []

            for waveform in waveforms:
                result = self.model.generate(
                    input=[ waveform ],
                    cache={},
                    batch_size=1,
                    **params["generation"],
                )[0]
                results.append(self._to_segments(result) if params["return_timestamps"] else result.get("text", ""))

            return results

        results = await self._run_in_executor(_transcribe)

        # Fun-ASR has no token-level streaming; when streaming is requested we
        # still run the full inference per waveform and re-emit each collected
        # result as an async iterator to preserve the interface expected by
        # downstream jobs: segments one-by-one when timestamps are on,
        # otherwise the full transcript as a single chunk.
        if streaming:
            streams: List[AsyncIterator[Any]] = []
            for result in results:
                async def _stream_chunk_generator(result=result):
                    if isinstance(result, list):
                        for segment in result:
                            yield segment
                    else:
                        yield result
                streams.append(_stream_chunk_generator())
            return streams

        return results

    async def _preprocess_audio(self, audios: List[MediaSource]) -> List[torch.Tensor]:
        # Fun-ASR-Nano only recognises str (file path) or torch.Tensor waveforms
        # in its chatml wrapper. Feed 16 kHz mono tensors.
        import torch

        waveforms: List[torch.Tensor] = []

        for audio in audios:
            waveform, _ = await AudioBufferStreamer(audio, sample_rate=16000, channel="mono").collect()
            waveforms.append(torch.from_numpy(waveform))

        return waveforms

    def _resolve_language(self, language: Optional[str]) -> Optional[str]:
        # Fun-ASR expects Chinese names ("韩文" etc.); translate ISO codes.
        return _LANGUAGE_CODE_MAP.get(language.split("-")[0]) if language else None

    def _to_segments(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        # sentence_info is only populated when diarization is enabled; the base
        # model falls back to a single segment covering the whole utterance.
        sentence_info = result.get("sentence_info")
        if sentence_info:
            return [
                {
                    "text":       sentence.get("sentence", sentence.get("text", "")),
                    "start_time": float(sentence["start"]) / 1000.0 if sentence.get("start") is not None else 0.0,
                    "end_time":   float(sentence["end"]) / 1000.0 if sentence.get("end") is not None else 0.0,
                    "words":      None,
                }
                for sentence in sentence_info
            ]

        return [
            {
                "text":       result.get("text", ""),
                "start_time": 0.0,
                "end_time":   0.0,
                "words":      None,
            }
        ]

class FunAsrSpeechToTextTaskService(ModelTaskService):
    config: FunAsrSpeechToTextModelComponentConfig

    def __init__(self, id: str, config: FunAsrSpeechToTextModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[Any] = None
        self.device: Optional[torch.device] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "funasr>=1.3.26", "torch", "torchaudio", "numpy", "soxr" ]

    async def _load_model(self) -> None:
        self.model, self.device = await self._load_pretrained_model()

    async def _unload_model(self) -> None:
        self.model = None
        self.device = None

    async def _load_pretrained_model(self) -> Tuple[Any, torch.device]:
        from funasr import AutoModel

        model_path = await self._provision_model(self.config.model)
        device = self._resolve_device(self.config.device)

        model = AutoModel(
            model=model_path,
            hub="hf",
            trust_remote_code=True,
            device=f"{device.type}:{device.index}" if device.index is not None else device.type,
        )

        return model, device

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await FunAsrSpeechToTextTaskAction(action, self.model, self.config.inverse_text_normalization, self.device).run(context)
