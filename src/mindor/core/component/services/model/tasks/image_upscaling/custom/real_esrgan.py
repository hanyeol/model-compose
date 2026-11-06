from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple, Optional, Dict, List, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, RealEsrganImageUpscalingModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.package.installer import install_package_from_github, is_package_installed
from mindor.core.logger import logging
from ..common import ImageUpscalingTaskAction
from ....base import ComponentActionContext, ModelTaskDriver
from PIL import Image as PILImage

if TYPE_CHECKING:
    from RealESRGAN import RealESRGAN
    import torch

class RealEsrganImageUpscalingTaskAction(ImageUpscalingTaskAction):
    config: RealEsrganImageUpscalingModelActionConfig

    def __init__(
        self,
        config: RealEsrganImageUpscalingModelActionConfig,
        model: RealESRGAN,
        device: Optional[torch.device]
    ):
        super().__init__(config, device)

        self.model: RealESRGAN = model

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        tile_batch_size = await context.render_variable(self.config.params.tile_batch_size)
        tile_size       = await context.render_variable(self.config.params.tile_size)
        tile_pad_size   = await context.render_variable(self.config.params.tile_pad_size)
        pre_pad_size    = await context.render_variable(self.config.params.pre_pad_size)

        params.update({
            "batch_size":   tile_batch_size,
            "patches_size": tile_size,
            "padding":      tile_pad_size,
            "pad_size":     pre_pad_size,
        })

        return params

    async def _upscale_batch(
        self,
        images: List[PILImage.Image],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[PILImage.Image]:
        def _upscale() -> List[PILImage.Image]:
            import numpy as np

            results: List[PILImage.Image] = []

            for image in images:
                results.append(self.model.predict(
                    np.array(image),
                    batch_size=params["batch_size"],
                    patches_size=params["patches_size"],
                    padding=params["padding"],
                    pad_size=params["pad_size"],
                ))

            return results

        return await self._run_in_executor(_upscale)

class RealEsrganImageUpscalingTaskDriver(ModelTaskDriver):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[RealESRGAN] = None
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [
            *torch_requirements("torch", "torchvision"),
            "numpy",
            "opencv-python",
            "Pillow",
            "tqdm",
            "huggingface_hub>=0.20,<0.26",
        ]

    async def _setup(self) -> None:
        if not is_package_installed("RealESRGAN"):
            await install_package_from_github(
                "RealESRGAN",
                "https://github.com/ai-forever/Real-ESRGAN.git",
                revision="362a0316878f41dbdfbb23657b450c3353de5acf",
                subdirs=[ "RealESRGAN" ],
            )

    async def _load_model(self) -> None:
        self.model, self.device = await self._load_pretrained_model()

    async def _unload_model(self) -> None:
        self.model = None
        self.device = None

    async def _load_pretrained_model(self) -> Tuple[RealESRGAN, torch.device]:
        from RealESRGAN import RealESRGAN

        model_path = await self._provision_model(self.config.model, prefetch=True)
        device = self._resolve_device(self.config.device)

        def _load() -> RealESRGAN:
            model = RealESRGAN(device=device, scale=self.config.scale)
            model.load_weights(model_path)

            return model

        model = await self._run_in_executor(_load)

        return model, device

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await RealEsrganImageUpscalingTaskAction(action, self.model, self.device).run(context)
