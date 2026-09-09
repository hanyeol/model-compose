from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Dict, Optional, List, Tuple, Any
from abc import abstractmethod
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.component import FireRedTextToSpeechPreset
from mindor.dsl.schema.action import ModelActionConfig, TextToSpeechActionMethod
from mindor.dsl.schema.action import FireRedTextToSpeechModelCloneActionConfig
from mindor.dsl.schema.action import FireRedTextToSpeechModelDesignActionConfig
from mindor.dsl.schema.action import FireRedTextToSpeechModelEditActionConfig
from mindor.dsl.schema.action import FireRedTextToSpeechEditMode
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.audio import PcmStreamResource
from mindor.core.foundation.streaming.resources import StreamResource
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.package.installer import install_package_from_github
from mindor.core.utils.audio import encode_waveform_to_pcm
from ......base import ComponentActionContext
from ....base import ModelTaskService
from ..common import TextToSpeechTaskAction
import importlib.util

if TYPE_CHECKING:
    import torch

class FireRedTextToSpeechTaskAction(TextToSpeechTaskAction):
    def __init__(self, config: Any, model: Any, sample_rate: int, device: Optional[torch.device]):
        super().__init__(config, device)

        self.model = model
        self.sample_rate = sample_rate

    async def _generate_batch(
        self,
        texts: List[str],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[StreamResource]:
        def _generate() -> List[StreamResource]:
            results: List[StreamResource] = []

            for text in texts:
                waveform, sample_rate = self._invoke(text, params)

                # generate_voice_design also returns a rewritten voice-plan text
                # as a third element; we discard it here and only emit the audio
                # stream to keep the TTS action's output contract consistent.
                frames, channels = encode_waveform_to_pcm(waveform)

                results.append(PcmStreamResource(frames, {
                    "sample_rate": str(sample_rate),
                    "channels":    str(channels),
                    "bit_depth":   "16",
                }))

            return results

        return await self._run_in_executor(_generate)

    @abstractmethod
    def _invoke(self, text: str, params: Dict[str, Any]) -> Tuple[Any, int]:
        pass

    async def _resolve_reference_audio(self, context: ComponentActionContext, value: Any) -> Tuple[Any, int]:
        """Decode reference audio into a (waveform_tensor, sample_rate) pair.
        FireRedTTS3's Python API takes torch tensors directly (via
        torchaudio.load), so we hand it in-memory buffers rather than a file
        path."""
        import numpy as np
        import torch

        buffer = await context.render_audio_buffer(value)
        waveform = np.asarray(buffer.waveform)

        # torchaudio.load returns shape (channels, samples); align to that.
        if waveform.ndim == 1:
            waveform = waveform[np.newaxis, :]
        elif waveform.ndim == 2 and waveform.shape[0] > waveform.shape[1]:
            waveform = waveform.T

        if np.issubdtype(waveform.dtype, np.integer):
            info = np.iinfo(waveform.dtype)
            waveform = waveform.astype(np.float32) / max(abs(info.min), info.max)
        else:
            waveform = waveform.astype(np.float32)

        return torch.from_numpy(waveform), buffer.sample_rate

class FireRedTextToSpeechCloneTaskAction(FireRedTextToSpeechTaskAction):
    config: FireRedTextToSpeechModelCloneActionConfig

    def __init__(self, config: FireRedTextToSpeechModelCloneActionConfig, model: Any, sample_rate: int, device: Optional[torch.device], preset: FireRedTextToSpeechPreset):
        super().__init__(config, model, sample_rate, device)

        self.preset = preset

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        audio, sample_rate = await self._resolve_reference_audio(context, self.config.reference_audio)
        prompt_text = await context.render_variable(self.config.reference_text)
        language    = await context.render_variable(self.config.language)
        do_tn       = await context.render_scalar(self.config.text_frontend, bool, True)

        params.update({
            "audio":       audio,
            "sample_rate": sample_rate,
            "prompt_text": prompt_text,
            "language":    language,
            "do_tn":       do_tn,
        })

        return params

    def _invoke(self, text: str, params: Dict[str, Any]) -> Tuple[Any, int]:
        # Instruct's generate_tts accepts the ICL cloning args but does not take
        # language / do_tn — those belong to Base.generate. Route accordingly.
        if self.preset == FireRedTextToSpeechPreset.INSTRUCT:
            waveform, sample_rate = self.model.generate_tts(
                prompt_text=params["prompt_text"] or "",
                prompt_audio=params["audio"],
                prompt_audio_sr=params["sample_rate"],
                text=text,
            )
        else:
            waveform, sample_rate = self.model.generate(
                language=params["language"],
                prompt_text=params["prompt_text"] or "",
                prompt_audio=params["audio"],
                prompt_audio_sr=params["sample_rate"],
                text=text,
                do_tn=params["do_tn"],
            )

        return waveform.detach().cpu().squeeze(0), int(sample_rate)

class FireRedTextToSpeechDesignTaskAction(FireRedTextToSpeechTaskAction):
    config: FireRedTextToSpeechModelDesignActionConfig

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        instructions = await context.render_variable(self.config.instructions)
        params["instructions"] = instructions

        return params

    def _invoke(self, text: str, params: Dict[str, Any]) -> Tuple[Any, int]:
        # generate_voice_design returns (audio, sr, gen_text); we drop gen_text
        # because the TTS action output contract is audio-only.
        result = self.model.generate_voice_design(
            instruction=params["instructions"],
            text=text,
        )
        waveform, sample_rate = result[0], result[1]

        return waveform.detach().cpu().squeeze(0), int(sample_rate)

class FireRedTextToSpeechEditTaskAction(FireRedTextToSpeechTaskAction):
    config: FireRedTextToSpeechModelEditActionConfig

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        audio, sample_rate = await self._resolve_reference_audio(context, self.config.reference_audio)
        instructions = await context.render_variable(self.config.instructions)
        mode         = await context.render_variable(self.config.mode)

        try:
            mode = FireRedTextToSpeechEditMode(mode)
        except ValueError:
            raise ValueError(f"Invalid mode: {mode}")

        params.update({
            "audio":        audio,
            "sample_rate":  sample_rate,
            "instructions": instructions,
            "mode":         mode,
        })

        return params

    def _invoke(self, text: str, params: Dict[str, Any]) -> Tuple[Any, int]:
        # Edit methods ignore the batched `text` input — they rewrite the audio
        # from the instruction alone. The `text` loop still runs once per input
        # so callers get one edited clip per batch item.
        if params["mode"] == FireRedTextToSpeechEditMode.ACOUSTIC:
            result = self.model.generate_acoustic_edit(
                instruction=params["instructions"],
                audio_in=params["audio"],
                audio_in_sr=params["sample_rate"],
            )
        else:
            result = self.model.generate_semantic_edit(
                instruction=params["instructions"],
                audio_in=params["audio"],
                audio_in_sr=params["sample_rate"],
            )

        waveform, sample_rate = result[0], result[1]

        return waveform.detach().cpu().squeeze(0), int(sample_rate)

class FireRedTextToSpeechTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[Any] = None
        self.sample_rate: int = 24000
        self.device: Optional[torch.device] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        # fireredtts3 has no pip distribution — clone the repo and add it to the
        # venv's site-packages (e.g. via a .pth file). We only declare the
        # runtime deps its inference paths pull in.
        return [
            *torch_requirements("torch", "torchaudio"),
            "transformers",
            "numpy",
            "soundfile",
            "librosa",
            "wetext",
        ]

    async def _setup(self) -> None:
        if importlib.util.find_spec("fireredtts3") is None:
            await install_package_from_github(
                "fireredtts3",
                "https://github.com/FireRedTeam/FireRedTTS3.git",
                revision="7a1f3a7282ff184cc1c7f070556baaf5f08b5216",
            )

    async def _load_model(self) -> None:
        self.model, self.sample_rate, self.device = await self._load_pretrained_model()

    async def _unload_model(self) -> None:
        self.model = None
        self.device = None

    async def _load_pretrained_model(self) -> Tuple[Any, int, Any]:
        preset = self.config.preset

        if preset == FireRedTextToSpeechPreset.INSTRUCT:
            from fireredtts3.core import FireRedTTS3Instruct as FireRedTTS3Model
        else:
            from fireredtts3.core import FireRedTTS3 as FireRedTTS3Model

        model_dir = await self._provision_model(self.config.model, prefetch=True)
        device = self._resolve_device(self.config.device)

        # LLM TN needs an external API key via .env; keep it off by default.
        # wetext covers zh/en and does basic cleaning for other languages.
        model = FireRedTTS3Model(
            model_dir,
            use_wetext=True,
            use_llm_tn=False,
        )

        # FireRedTTS3 renders at 24 kHz for both Base and Instruct.
        sample_rate = 24000

        return model, sample_rate, device

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        preset = self.config.preset

        if action.method == TextToSpeechActionMethod.CLONE:
            return await FireRedTextToSpeechCloneTaskAction(action, self.model, self.sample_rate, self.device, preset).run(context)

        if action.method == TextToSpeechActionMethod.DESIGN:
            if preset != FireRedTextToSpeechPreset.INSTRUCT:
                raise RuntimeError("The 'design' method requires preset=instruct (FireRedTTS3-Instruct).")
            return await FireRedTextToSpeechDesignTaskAction(action, self.model, self.sample_rate, self.device).run(context)

        if action.method == TextToSpeechActionMethod.EDIT:
            if preset != FireRedTextToSpeechPreset.INSTRUCT:
                raise RuntimeError("The 'edit' method requires preset=instruct (FireRedTTS3-Instruct).")
            return await FireRedTextToSpeechEditTaskAction(action, self.model, self.sample_rate, self.device).run(context)

        raise ValueError(f"Unknown method: {action.method}")
