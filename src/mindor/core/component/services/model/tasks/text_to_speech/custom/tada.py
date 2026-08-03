from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Dict, Optional, List, Tuple, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, TextToSpeechActionMethod
from mindor.dsl.schema.action import TadaTextToSpeechModelCloneActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.audio import PcmStreamResource
from mindor.core.foundation.streaming.resources import StreamResource
from mindor.core.utils.audio import encode_waveform_to_pcm
from mindor.core.logger import logging
from ......base import ComponentActionContext
from ....base import ModelTaskService
from ..common import TextToSpeechTaskAction
from ....utils.provision import HuggingfaceModelDownloader

if TYPE_CHECKING:
    import torch

_TADA_CODEC_REPO = "HumeAI/tada-codec"

class TadaTextToSpeechCloneTaskAction(TextToSpeechTaskAction):
    config: TadaTextToSpeechModelCloneActionConfig

    def __init__(
        self,
        config: TadaTextToSpeechModelCloneActionConfig,
        model: Any,
        encoder: Any,
        device: Optional[torch.device],
    ):
        super().__init__(config, device)

        self.model = model
        self.encoder = encoder

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        reference_audio = await context.render_file(self.config.reference_audio)
        reference_text  = await context.render_variable(self.config.reference_text)
        seed            = await context.render_scalar(self.config.seed, int)

        params.update({
            "reference_audio": reference_audio,
            "reference_text":  reference_text,
            "seed":            seed,
        })

        return params

    async def _generate_batch(
        self,
        texts: List[str],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[StreamResource]:
        def _generate() -> List[StreamResource]:
            import numpy as np
            import soundfile as sf
            import torch

            # Encode reference once, reuse for every text in the batch.
            audio_np, sample_rate = sf.read(str(params["reference_audio"]), dtype="float32")
            audio = torch.from_numpy(audio_np).float()
            if audio.ndim == 1:
                audio = audio.unsqueeze(0)  # (samples,) -> (1, samples)
            else:
                audio = audio.T  # (samples, channels) -> (channels, samples)
            audio = audio.to(self.device)

            text_arg = [params["reference_text"]] if params["reference_text"] else None
            prompt = self.encoder(audio, text=text_arg, sample_rate=sample_rate)

            if params["seed"] is not None:
                torch.manual_seed(params["seed"])

            results: List[StreamResource] = []

            for text in texts:
                output = self.model.generate(prompt=prompt, text=text)

                if output.audio and output.audio[0] is not None:
                    samples = output.audio[0].detach().cpu().numpy().squeeze().astype(np.float32)
                else:
                    logging.warning("TADA generation produced no audio")
                    samples = np.zeros(24000, dtype=np.float32)

                frames, channels = encode_waveform_to_pcm(samples)

                results.append(PcmStreamResource(frames, {
                    "sample_rate": str(24000),
                    "channels":    str(channels),
                    "bit_depth":   "16",
                }))

            return results

        return await self._run_in_executor(_generate)

class TadaTextToSpeechTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[Any] = None
        self.encoder: Optional[Any] = None
        self.device: Optional[torch.device] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "tada-tts", "descript-audio-codec", "transformers", "torch", "huggingface_hub", "numpy", "soundfile" ]

    async def _load_model(self) -> None:
        self.model, self.encoder, self.device = await self._load_pretrained_model()

    async def _unload_model(self) -> None:
        self.model = None
        self.encoder = None
        self.device = None

    async def _load_pretrained_model(self) -> Tuple[Any, Any, Any]:
        from tada.modules.aligner import AlignerConfig
        from tada.modules.encoder import Encoder
        from tada.modules.tada import TadaForCausalLM, TadaConfig
        import torch

        # LM weights: for HF sources the schema's default allow_patterns keeps
        # the download to relevant files; local paths are used as-is.
        model_path = await self._provision_model(self.config.model, prefetch=True)
        device = self._resolve_device(self.config.device)
        dtype = self._resolve_model_dtype(device)

        # TADA hardcodes "meta-llama/Llama-3.2-1B" as its tokenizer source,
        # which is gated. Pull the tokenizer from an ungated mirror and
        # inject its local path into the Aligner + Tada configs.
        tokenizer_path = await HuggingfaceModelDownloader().download(
            repo_id=self.config.tokenizer,
            allow_patterns=[ "tokenizer*", "special_tokens*" ],
        )

        AlignerConfig.tokenizer_name = tokenizer_path
        encoder = Encoder.from_pretrained(_TADA_CODEC_REPO, subfolder="encoder").to(device).eval()

        config = TadaConfig.from_pretrained(model_path)
        config.tokenizer_name = tokenizer_path

        model = TadaForCausalLM.from_pretrained(
            model_path,
            config=config,
            torch_dtype=dtype,
        ).to(device).eval()

        return model, encoder, device

    def _resolve_model_dtype(self, device: torch.device) -> torch.dtype:
        import torch

        # MPS is unstable for flow matching; users on Apple Silicon should stick to CPU.
        if device.type == "cuda":
            try:
                use_bf16 = torch.cuda.is_bf16_supported()
            except Exception:
                use_bf16 = False
        elif device.type == "xpu":
            use_bf16 = True
        else:
            use_bf16 = False

        return torch.bfloat16 if use_bf16 else torch.float32

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        if action.method == TextToSpeechActionMethod.CLONE:
            return await TadaTextToSpeechCloneTaskAction(action, self.model, self.encoder, self.device).run(context)

        raise ValueError(f"Unknown method: {action.method}")
