from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple, Optional, Dict, List, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, HiDiffImageDeblurringModelActionConfig
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.cancellation import CancellationToken
from ..common import ImageDeblurringTaskAction
from ....base import ComponentActionContext, ModelTaskDriver
from .utils.predict import predict_tile
from .utils.tiling import blend_tiles
from PIL import Image as PILImage
import os

if TYPE_CHECKING:
    from torch import Tensor
    import torch

_HI_DIFF_FILES = ( "net_g.pth", "net_le_dm.pth", "net_d.pth" )

class HiDiffImageDeblurringTaskAction(ImageDeblurringTaskAction):
    config: HiDiffImageDeblurringModelActionConfig

    def __init__(
        self,
        config: HiDiffImageDeblurringModelActionConfig,
        model: "torch.nn.Module",
        device: Optional["torch.device"],
    ):
        super().__init__(config, device)

        self.model: "torch.nn.Module" = model

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        seed = await context.render_scalar(self.config.params.seed, int) if self.config.params.seed is not None else None

        params.update({
            "seed": seed,
        })

        return params

    async def _deblur_batch(
        self,
        images: List[PILImage.Image],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[PILImage.Image]:
        def _deblur() -> List[PILImage.Image]:
            import numpy as np
            import torch

            def interrupt() -> None:
                if cancellation_token is not None and cancellation_token.is_cancelled():
                    raise RuntimeError("HI-Diff deblurring cancelled")

            def predict(patch: "Tensor") -> "Tensor":
                with torch.inference_mode():
                    return predict_tile(
                        model=self.model,
                        image=patch,
                        device=self.device,
                        augmented=params["augmented_inference"],
                        seed=params["seed"],
                        interrupt=interrupt,
                    )

            results: List[PILImage.Image] = []

            for image in images:
                pixels = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
                tensor = torch.from_numpy(pixels).permute(2, 0, 1).unsqueeze(0)

                if params["tile_size"] and params["tile_size"] > 0:
                    output = blend_tiles(
                        image=tensor,
                        predict=predict,
                        tile=params["tile_size"],
                        overlap=params["tile_overlap"],
                        method=params["blend"],
                    )
                else:
                    output = predict(tensor)

                output = output.squeeze(0).clamp(0, 1).permute(1, 2, 0).numpy()
                results.append(PILImage.fromarray((output * 255.0).round().astype(np.uint8)))

            return results

        return await self._run_in_executor(_deblur)

class HiDiffImageDeblurringTaskDriver(ModelTaskDriver):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional["torch.nn.Module"] = None
        self.device: Optional["torch.device"] = None

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [
            *torch_requirements("torch", "torchvision"),
            "mindor-hi-diff@git+https://github.com/hanyeol/mindor-hi-diff.git@1caf3ed01dc8",
        ]

    async def _load_model(self) -> None:
        self.model, self.device = await self._load_pretrained_model()

    async def _unload_model(self) -> None:
        self.model = None
        self.device = None

    async def _load_pretrained_model(self) -> Tuple["torch.nn.Module", "torch.device"]:
        model_dir = await self._provision_model(self.config.model, prefetch=True)
        device = self._resolve_device(self.config.device)
        variant = self.config.variant

        def _load() -> "torch.nn.Module":
            from mindor_hi_diff import build_hi_diff_model
            import torch

            if os.path.isfile(model_dir):
                raise ValueError(
                    f"HI-Diff expects a directory containing {', '.join(_HI_DIFF_FILES)}, "
                    f"got a single file: {model_dir}"
                )

            checkpoints: Dict[str, Any] = {}

            for key, filename in zip(( "g", "le_dm", "d" ), _HI_DIFF_FILES):
                path = os.path.join(model_dir, filename)

                if not os.path.isfile(path):
                    raise FileNotFoundError(f"HI-Diff weight missing: {path}")

                checkpoints[key] = torch.load(path, map_location="cpu")

            return build_hi_diff_model(variant, checkpoints).to(device)

        model = await self._run_in_executor(_load)

        return model, device

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await HiDiffImageDeblurringTaskAction(action, self.model, self.device).run(context)
