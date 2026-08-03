from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Dict, Optional, List, Tuple, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, TextToSpeechActionMethod
from mindor.dsl.schema.action import LuxttsTextToSpeechModelCloneActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.audio import PcmStreamResource
from mindor.core.foundation.streaming.resources import StreamResource
from mindor.core.utils.audio import encode_waveform_to_pcm
from ......base import ComponentActionContext
from ....base import ModelTaskService
from ..common import TextToSpeechTaskAction
import os

if TYPE_CHECKING:
    import torch

class LuxttsTextToSpeechCloneTaskAction(TextToSpeechTaskAction):
    config: LuxttsTextToSpeechModelCloneActionConfig

    def __init__(self, config: LuxttsTextToSpeechModelCloneActionConfig, model: Any, device: Optional[torch.device]):
        super().__init__(config, device)

        self.model = model

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        reference_audio    = await context.render_file(self.config.reference_audio)
        reference_duration = await context.render_scalar(self.config.reference_duration, int, 5)
        reference_rms      = await context.render_scalar(self.config.reference_rms, float, 0.01)
        num_steps          = await context.render_scalar(self.config.num_steps, int, 4)
        guidance_scale     = await context.render_scalar(self.config.guidance_scale, float, 3.0)
        t_shift            = await context.render_scalar(self.config.t_shift, float, 0.5)
        speed              = await context.render_scalar(self.config.speed, float, 1.0)
        seed               = await context.render_scalar(self.config.seed, int)

        params.update({
            "reference_audio":    reference_audio,
            "reference_duration": reference_duration,
            "reference_rms":      reference_rms,
            "num_steps":          num_steps,
            "guidance_scale":     guidance_scale,
            "t_shift":            t_shift,
            "speed":              speed,
            "seed":               seed,
        })

        return params

    async def _generate_batch(
        self,
        texts: List[str],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[StreamResource]:
        def _generate() -> List[StreamResource]:
            import torch

            encode_dict = self.model.encode_prompt(
                prompt_audio=str(params["reference_audio"]),
                duration=params["reference_duration"],
                rms=params["reference_rms"],
            )

            if params["seed"] is not None:
                torch.manual_seed(params["seed"])

            results: List[StreamResource] = []

            for text in texts:
                wav = self.model.generate_speech(
                    text=text,
                    encode_dict=encode_dict,
                    num_steps=params["num_steps"],
                    guidance_scale=params["guidance_scale"],
                    t_shift=params["t_shift"],
                    speed=params["speed"],
                    return_smooth=False,
                )
                samples = wav.detach().cpu().numpy().squeeze()
                frames, channels = encode_waveform_to_pcm(samples)

                results.append(PcmStreamResource(frames, {
                    "sample_rate": str(48000),
                    "channels":    str(channels),
                    "bit_depth":   "16",
                }))

            return results

        return await self._run_in_executor(_generate)

class LuxttsTextToSpeechTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[Any] = None
        self.device: Optional[torch.device] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "zipvoice", "torch", "numpy", "soundfile" ]

    async def _load_model(self) -> None:
        self.model, self.device = await self._load_pretrained_model()

    async def _unload_model(self) -> None:
        self.model = None
        self.device = None

    async def _load_pretrained_model(self) -> Tuple[Any, Any]:
        from zipvoice.luxvoice import LuxTTS

        # zipvoice's LuxTTS takes an HF repo id directly for `model_path` and
        # handles the download itself.
        model_path = await self._provision_model(self.config.model)
        device = self._resolve_device(self.config.device)

        if device.type == "cpu":
            threads = min(os.cpu_count() or 4, 8)
            model = LuxTTS(model_path=model_path, device=str(device), threads=threads)
        else:
            model = LuxTTS(model_path=model_path, device=str(device))

        return model, device

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        if action.method == TextToSpeechActionMethod.CLONE:
            return await LuxttsTextToSpeechCloneTaskAction(action, self.model, self.device).run(context)

        raise ValueError(f"Unknown method: {action.method}")
