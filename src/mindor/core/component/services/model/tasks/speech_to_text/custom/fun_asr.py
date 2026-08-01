from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Dict, Optional, List, Tuple, Union, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import ModelComponentConfig, FunAsrSpeechToTextModelComponentConfig, HuggingfaceModelConfig
from mindor.dsl.schema.action import ModelActionConfig, SpeechToTextModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.audio import AudioBufferStreamer
from mindor.core.foundation.streaming.media import MediaSource
from ......base import ComponentActionContext
from ..common import SpeechToTextTaskService, SpeechToTextTaskAction

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

_DEFAULT_FUN_ASR_REPO = "FunAudioLLM/Fun-ASR-MLT-Nano-2512"

class FunAsrSpeechToTextTaskAction(SpeechToTextTaskAction):
    def __init__(
        self,
        config: SpeechToTextModelActionConfig,
        model: Any,
        itn: bool,
        device: Optional[torch.device],
    ):
        super().__init__(config, device)

        self.model: Any = model
        self.itn: bool = itn

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        return_timestamps = bool(await context.render_variable(self.config.params.return_timestamps))

        generation_params: Dict[str, Any] = { "itn": self.itn }

        language = self._resolve_language(params["language"])
        if language is not None:
            generation_params["language"] = language

        params["generation"] = generation_params
        params["return_timestamps"] = return_timestamps

        return params

    async def _transcribe_batch(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Union[List[str], List[List[Dict[str, Any]]]]:
        if streaming:
            raise NotImplementedError("Fun-ASR streaming inference is not supported yet; set streaming: false.")

        waveforms = await self._preprocess_audio(audios)

        generation_params = params["generation"]
        return_timestamps = params["return_timestamps"]

        # Fun-ASR-Nano rejects batch decoding (see model.inference_prepare); feed
        # samples one at a time and concatenate the results.
        def _transcribe() -> Union[List[str], List[List[Dict[str, Any]]]]:
            outputs: List[Any] = []

            for waveform in waveforms:
                result = self.model.generate(
                    input=[ waveform ],
                    cache={},
                    batch_size=1,
                    **generation_params,
                )[0]
                outputs.append(self._to_segments(result) if return_timestamps else result.get("text", ""))

            return outputs

        return await self._run_in_executor(_transcribe)

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

class FunAsrSpeechToTextTaskService(SpeechToTextTaskService):
    config: FunAsrSpeechToTextModelComponentConfig

    def __init__(self, id: str, config: FunAsrSpeechToTextModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[Any] = None
        self.device: Optional[torch.device] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "funasr>=1.3.26", "torch", "torchaudio", "numpy", "soxr" ]

    async def _load_model(self) -> None:
        self.model, self.device = self._load_pretrained_model()

    async def _unload_model(self) -> None:
        self.model = None
        self.device = None

    def _load_pretrained_model(self) -> Tuple[Any, torch.device]:
        from funasr import AutoModel

        device = self._resolve_device(self.config.device)
        source, hub = self._resolve_source_and_hub()

        model = AutoModel(
            model=source,
            hub=hub,
            trust_remote_code=True,
            device=f"{device.type}:{device.index}" if device.index is not None else device.type,
        )

        return model, device

    def _resolve_source_and_hub(self) -> Tuple[str, str]:
        model = self.config.model

        if isinstance(model, HuggingfaceModelConfig):
            return model.repository, "hf"

        if isinstance(model, str):
            return model, "hf"

        return _DEFAULT_FUN_ASR_REPO, "hf"

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await FunAsrSpeechToTextTaskAction(action, self.model, self.config.itn, self.device).run(context)
