from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Dict, Optional, List, Tuple, Any
from abc import abstractmethod
from mindor.dsl.schema.component import ModelComponentConfig, HuggingfaceModelConfig
from mindor.dsl.schema.action import ModelActionConfig, TextToSpeechActionMethod
from mindor.dsl.schema.action import CommonTextToSpeechModelActionConfig
from mindor.dsl.schema.action import CosyvoiceTextToSpeechModelGenerateActionConfig
from mindor.dsl.schema.action import CosyvoiceTextToSpeechModelCloneActionConfig
from mindor.dsl.schema.action import CosyvoiceTextToSpeechModelDesignActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.audio import PcmStreamResource
from mindor.core.foundation.streaming.resources import StreamResource
from mindor.core.utils.audio import encode_waveform_to_pcm
from ......base import ComponentActionContext
from ..common import TextToSpeechTaskService, TextToSpeechTaskAction

if TYPE_CHECKING:
    import torch

class CosyvoiceTextToSpeechTaskAction(TextToSpeechTaskAction):
    config: CommonTextToSpeechModelActionConfig

    def __init__(self, config: CommonTextToSpeechModelActionConfig, model: Any, sample_rate: int, device: Optional[torch.device]):
        super().__init__(config, device)

        self.model = model
        self.sample_rate = sample_rate

    async def _generate(
        self,
        texts: List[str],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[StreamResource]:
        def _generate() -> List[StreamResource]:
            import numpy as np

            results: List[StreamResource] = []

            for text in texts:
                # inference_* returns a generator of {'tts_speech': tensor} dicts.
                # With stream=False the LLM produces one chunk per normalized
                # sentence; concatenate them so a single input text produces a
                # single output audio.
                chunks: List[Any] = []
                for output in self._invoke(text, params):
                    speech = output["tts_speech"]  # shape (1, samples)
                    chunks.append(speech.detach().cpu().numpy().squeeze(0))

                samples = np.concatenate(chunks, axis=0) if len(chunks) > 1 else chunks[0]
                samples = samples.astype(np.float32)
                frames, channels = encode_waveform_to_pcm(samples)

                results.append(PcmStreamResource(frames, {
                    "sample_rate": str(self.sample_rate),
                    "channels":    str(channels),
                    "bit_depth":   "16",
                }))

            return results

        return await self._run_in_executor(_generate)

    @abstractmethod
    def _invoke(self, text: str, params: Dict[str, Any]) -> Any:
        pass

class CosyvoiceTextToSpeechGenerateTaskAction(CosyvoiceTextToSpeechTaskAction):
    config: CosyvoiceTextToSpeechModelGenerateActionConfig

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        voice         = await context.render_variable(self.config.voice)
        speed         = await context.render_variable(self.config.speed)
        text_frontend = await context.render_variable(self.config.text_frontend)

        params.update({
            "voice":         voice,
            "speed":         float(speed) if speed is not None else 1.0,
            "text_frontend": bool(text_frontend) if text_frontend is not None else True,
        })

        return params

    def _invoke(self, text: str, params: Dict[str, Any]) -> Any:
        # inference_sft is defined on the base CosyVoice class. CosyVoice2/3
        # inherit the method but only reach real preset speakers when the
        # loaded model_dir includes an spk2info.pt (typically CosyVoice-300M-SFT
        # or a v2/v3 checkpoint with pre-registered zero-shot speakers).
        if not hasattr(self.model, "inference_sft"):
            raise RuntimeError(
                "The loaded CosyVoice model does not support the 'generate' method. "
                "Use family=cosyvoice with a *-SFT checkpoint, or switch to method=clone."
            )

        available = getattr(self.model, "list_available_spks", lambda: [])()
        if available and params["voice"] not in available:
            raise ValueError(
                f"Unknown voice '{params['voice']}'. Available speakers: {available}"
            )

        return self.model.inference_sft(
            tts_text=text,
            spk_id=params["voice"],
            stream=False,
            speed=params["speed"],
            text_frontend=params["text_frontend"],
        )

class CosyvoiceTextToSpeechCloneTaskAction(CosyvoiceTextToSpeechTaskAction):
    config: CosyvoiceTextToSpeechModelCloneActionConfig

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        reference_audio = await context.render_file(self.config.reference_audio)
        reference_text  = await context.render_variable(self.config.reference_text)
        speed           = await context.render_variable(self.config.speed)
        text_frontend   = await context.render_variable(self.config.text_frontend)

        params.update({
            "reference_audio": reference_audio,
            "reference_text":  reference_text,
            "speed":           float(speed) if speed is not None else 1.0,
            "text_frontend":   bool(text_frontend) if text_frontend is not None else True,
        })

        return params

    def _invoke(self, text: str, params: Dict[str, Any]) -> Any:
        from cosyvoice.utils.file_utils import load_wav

        # CosyVoice's frontend expects a 16kHz mono tensor for the prompt wav.
        prompt_wav = load_wav(str(params["reference_audio"]), 16000)

        # With a transcript, use zero_shot (better speaker similarity). Without
        # one, fall back to cross_lingual — which accepts any language and does
        # not require reference text.
        if params["reference_text"]:
            return self.model.inference_zero_shot(
                tts_text=text,
                prompt_text=params["reference_text"],
                prompt_wav=prompt_wav,
                stream=False,
                speed=params["speed"],
                text_frontend=params["text_frontend"],
            )

        return self.model.inference_cross_lingual(
            tts_text=text,
            prompt_wav=prompt_wav,
            stream=False,
            speed=params["speed"],
            text_frontend=params["text_frontend"],
        )

class CosyvoiceTextToSpeechDesignTaskAction(CosyvoiceTextToSpeechTaskAction):
    config: CosyvoiceTextToSpeechModelDesignActionConfig

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        instructions    = await context.render_variable(self.config.instructions)
        reference_audio = await context.render_file(self.config.reference_audio)
        speed           = await context.render_variable(self.config.speed)
        text_frontend   = await context.render_variable(self.config.text_frontend)

        params.update({
            "instructions":    instructions,
            "reference_audio": reference_audio,
            "speed":           float(speed) if speed is not None else 1.0,
            "text_frontend":   bool(text_frontend) if text_frontend is not None else True,
        })

        return params

    def _invoke(self, text: str, params: Dict[str, Any]) -> Any:
        # inference_instruct2 only exists on CosyVoice2/3. The original
        # CosyVoice-Instruct model exposes inference_instruct with a different
        # signature (spk_id-based, no prompt wav) — refuse rather than silently
        # loading the wrong path.
        if not hasattr(self.model, "inference_instruct2"):
            raise RuntimeError(
                "The loaded CosyVoice model does not support the 'design' method. "
                "Use family=cosyvoice with a CosyVoice2/3 checkpoint (e.g. FunAudioLLM/CosyVoice2-0.5B)."
            )

        from cosyvoice.utils.file_utils import load_wav

        prompt_wav = load_wav(str(params["reference_audio"]), 16000)

        return self.model.inference_instruct2(
            tts_text=text,
            instruct_text=params["instructions"],
            prompt_wav=prompt_wav,
            stream=False,
            speed=params["speed"],
            text_frontend=params["text_frontend"],
        )

class CosyvoiceTextToSpeechTaskService(TextToSpeechTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[Any] = None
        self.sample_rate: int = 24000
        self.device: Optional[torch.device] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        # cosyvoice has no pip distribution — clone it from source and add both the
        # repo root and its Matcha-TTS submodule to sys.path (or a venv .pth file).
        # We still declare the runtime deps so the environment matches what the
        # inference paths expect.
        return [
            "torch",
            "torchaudio",
            "modelscope",
            "hyperpyyaml",
            "numpy",
            "soundfile",
            "librosa",
            "transformers",
            "diffusers",
            "accelerate",
            "onnxruntime-gpu",
            "conformer",
            "openai-whisper",
            "wetext",
        ]

    async def _load_model(self) -> None:
        self.model, self.sample_rate, self.device = self._load_pretrained_model()

    async def _unload_model(self) -> None:
        self.model = None
        self.device = None

    def _load_pretrained_model(self) -> Tuple[Any, int, Any]:
        # CosyVoice ships an AutoModel factory that picks CosyVoice / CosyVoice2 /
        # CosyVoice3 by looking for cosyvoice{,2,3}.yaml inside model_dir, and
        # calls snapshot_download() itself if model_dir isn't a local path.
        try:
            from cosyvoice.cli.cosyvoice import AutoModel
        except ImportError as e:
            raise RuntimeError(
                f"Failed to import cosyvoice.cli.cosyvoice: {e}\n"
                "If the cosyvoice package itself is missing, clone the repo and add it to the venv:\n"
                "  git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git\n"
                "then add both the repo root and its third_party/Matcha-TTS to the venv "
                "(e.g. via a .pth file in the venv's site-packages).\n"
                "If cosyvoice is present but a dependency is missing, install it into the venv."
            ) from e

        if isinstance(self.config.model, HuggingfaceModelConfig):
            model_dir = self.config.model.repository
        else:
            model_dir = self._get_model_path()

        device = self._resolve_device(self.config.device)

        # jit/trt/vllm/fp16 are CUDA-only; AutoModel warns and silently disables
        # them on CPU, but we filter here so the intent is visible in logs.
        load_jit  = bool(getattr(self.config, "load_jit",  False)) and device.type == "cuda"
        load_trt  = bool(getattr(self.config, "load_trt",  False)) and device.type == "cuda"
        load_vllm = bool(getattr(self.config, "load_vllm", False)) and device.type == "cuda"
        fp16      = bool(getattr(self.config, "fp16",      False)) and device.type == "cuda"

        # AutoModel returns CosyVoice / CosyVoice2 / CosyVoice3. Only v2/v3
        # accept load_vllm, so pass it conditionally by peeking at the yaml.
        import os
        kwargs: Dict[str, Any] = {
            "model_dir": model_dir,
            "load_jit":  load_jit,
            "load_trt":  load_trt,
            "fp16":      fp16,
        }
        resolved_dir = model_dir if os.path.exists(model_dir) else None
        if resolved_dir and (
            os.path.exists(os.path.join(resolved_dir, "cosyvoice2.yaml")) or
            os.path.exists(os.path.join(resolved_dir, "cosyvoice3.yaml"))
        ):
            kwargs["load_vllm"] = load_vllm
        elif load_vllm:
            # We don't yet know the version (AutoModel will download); attempt
            # anyway and let AutoModel raise a clear TypeError if unsupported.
            kwargs["load_vllm"] = load_vllm

        model = AutoModel(**kwargs)
        sample_rate = int(getattr(model, "sample_rate", 24000))

        return model, sample_rate, device

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        if action.method == TextToSpeechActionMethod.GENERATE:
            return await CosyvoiceTextToSpeechGenerateTaskAction(action, self.model, self.sample_rate, self.device).run(context)

        if action.method == TextToSpeechActionMethod.CLONE:
            return await CosyvoiceTextToSpeechCloneTaskAction(action, self.model, self.sample_rate, self.device).run(context)

        if action.method == TextToSpeechActionMethod.DESIGN:
            return await CosyvoiceTextToSpeechDesignTaskAction(action, self.model, self.sample_rate, self.device).run(context)

        raise ValueError(f"Unknown method: {action.method}")
