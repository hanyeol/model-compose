from __future__ import annotations
from typing import TYPE_CHECKING, Union, Tuple

from typing import Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import ModelComponentConfig, KimodoCfgType
from mindor.dsl.schema.action import (
    ModelActionConfig,
    MotionGenerationActionMethod,
    CommonKimodoMotionGenerationModelActionConfig,
    KimodoMotionGenerationModelGenerateActionConfig,
)
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.cancellation import CancellationToken
from ....base import ComponentActionContext, ModelTaskDriver
from ..common import MotionGenerationTaskAction, MotionClip
import os

# Kimodo-SOMA presets emit the 77-joint SOMA skeleton; G1/SMPL-X presets would
# resolve differently and are not yet exposed.
_KIMODO_SKELETON = "soma"

if TYPE_CHECKING:
    from kimodo.model.kimodo_model import Kimodo

class KimodoMotionGenerationTaskAction(MotionGenerationTaskAction):
    config: CommonKimodoMotionGenerationModelActionConfig

    def __init__(self, config: CommonKimodoMotionGenerationModelActionConfig, model: Kimodo, cfg_type: KimodoCfgType):
        super().__init__(config)

        self.model: Kimodo = model
        self.cfg_type: KimodoCfgType = cfg_type

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        duration        = await context.render_scalar(self.config.params.duration, float)
        num_samples     = await context.render_scalar(self.config.params.num_samples, int)
        diffusion_steps = await context.render_scalar(self.config.params.diffusion_steps, int)
        cfg_weight      = await context.render_variable(self.config.params.cfg_weight)
        post_processing = await context.render_scalar(self.config.params.post_processing, bool)

        if isinstance(cfg_weight, list):
            cfg_weight = [ float(value) for value in cfg_weight ]
        elif cfg_weight is not None:
            cfg_weight = float(cfg_weight)

        params.update({
            "duration":        duration,
            "num_samples":     num_samples,
            "diffusion_steps": diffusion_steps,
            "cfg_weight":      cfg_weight,
            "post_processing": post_processing,
        })

        return params

class KimodoMotionGenerationModelGenerateAction(KimodoMotionGenerationTaskAction):
    config: KimodoMotionGenerationModelGenerateActionConfig

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, bool, bool]:
        prompt = await context.render_text(self.config.prompt)

        is_single_input    = not isinstance(prompt, (list, StreamIterator, AsyncIterator))
        is_streaming_input = isinstance(prompt, (StreamIterator, AsyncIterator))

        return (prompt,), is_single_input, is_streaming_input

    async def _generate_batch(
        self,
        inputs: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        fps = int(self.model.fps)
        num_frames = max(1, int(round(float(params["duration"]) * fps)))

        def _generate() -> List[MotionClip]:
            import torch

            results: List[MotionClip] = []

            for (prompt,) in inputs:
                if cancellation_token is not None and cancellation_token.is_cancelled():
                    break

                if params.get("seed") is not None:
                    torch.manual_seed(int(params["seed"]))

                motion = self.model(
                    prompts=prompt,
                    num_frames=num_frames,
                    num_denoising_steps=int(params["diffusion_steps"]),
                    cfg_weight=params["cfg_weight"],
                    cfg_type=self.cfg_type.value,
                    num_samples=int(params["num_samples"]),
                    post_processing=bool(params["post_processing"]),
                    return_numpy=True,
                    progress_bar=lambda iterator, **_: iterator,
                )

                results.append(MotionClip({
                    "frame_rate":       fps,
                    "skeleton":         _KIMODO_SKELETON,
                    "joint_positions":  motion["posed_joints"],
                    "joint_rotations":  motion["global_rot_mats"],
                    "rotation_format":  "matrix",
                    "root_position":    motion["root_positions"],
                    "extras": {
                        "local_rot_mats":      motion["local_rot_mats"],
                        "smooth_root_pos":     motion["smooth_root_pos"],
                        "global_root_heading": motion["global_root_heading"],
                        "foot_contacts":       motion["foot_contacts"],
                    },
                }))

            return results

        return await self._run_in_executor(_generate)

class KimodoMotionGenerationTaskDriver(ModelTaskDriver):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[Kimodo] = None

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        # Kimodo pins torch via its own extras; install torch ahead of the package
        # so pip doesn't resolve a drifted version while building the environment.
        return [
            *torch_requirements("torch", "torchvision"),
            "kimodo@git+https://github.com/nv-tlabs/kimodo.git",
        ]

    async def _load_model(self) -> None:
        from kimodo.model.load_model import load_model

        preset             = self.config.preset
        device             = str(self._resolve_device(self.config.device))
        text_encoder_fp32  = bool(self.config.text_encoder_fp32)

        # Kimodo reads TEXT_ENCODER_DEVICE from the process environment at import
        # time; set it before touching the loader so the preset picks it up.
        text_encoder_device = self.config.text_encoder_device
        if text_encoder_device:
            os.environ["TEXT_ENCODER_DEVICE"] = text_encoder_device

        def _load() -> Kimodo:
            return load_model(
                modelname=preset,
                device=device,
                text_encoder_fp32=text_encoder_fp32,
            )

        self.model = await self._run_in_executor(_load)

    async def _unload_model(self) -> None:
        self.model = None

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        if action.method == MotionGenerationActionMethod.GENERATE:
            return await KimodoMotionGenerationModelGenerateAction(action, self.model, self.config.cfg_type).run(context)

        raise ValueError(f"Unknown method: {action.method}")
