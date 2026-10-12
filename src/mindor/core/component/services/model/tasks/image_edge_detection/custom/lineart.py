"""Lineart (anime-style line extraction) driver.

Architecture ported from Mukosame/Anime2Sketch (which lllyasviel adopted
for ControlNet 1.1 lineart). The network is a U-Net style generator with
residual blocks in the bottleneck.

Two public checkpoints on `lllyasviel/Annotators`:
- `sk_model.pth`  — realistic / detailed lines
- `sk_model2.pth` — coarse / simpler lines
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple, Optional, Dict, List, Any
from mindor.dsl.schema.component import ModelComponentConfig, ModelProvider
from mindor.dsl.schema.action import ModelActionConfig, LineartImageEdgeDetectionModelActionConfig
from mindor.dsl.schema.component.impl.model.tasks.image_edge_detection.impl.custom.lineart import LineartVariant
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.cancellation import CancellationToken
from ....base import ComponentActionContext, ModelTaskDriver
from ..common import ImageEdgeDetectionTaskAction
from PIL import Image as PILImage

if TYPE_CHECKING:
    import torch

_LINEART_WEIGHT_FILENAMES: Dict[LineartVariant, str] = {
    LineartVariant.REALISTIC: "sk_model.pth",
    LineartVariant.COARSE:    "sk_model2.pth",
}

class LineartImageEdgeDetectionTaskAction(ImageEdgeDetectionTaskAction):
    config: LineartImageEdgeDetectionModelActionConfig

    def __init__(
        self,
        config: LineartImageEdgeDetectionModelActionConfig,
        model: Any,
        device: torch.device,
    ):
        super().__init__(config, device)

        self.model: Any = model

    async def _detect_batch(
        self,
        images: List[PILImage.Image],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[PILImage.Image]:
        def _detect() -> List[PILImage.Image]:
            import torch
            import torch.nn.functional as F

            edges: List[PILImage.Image] = []

            for image in images:
                image = image.convert("RGB")
                tensor = self._image_to_tensor(image, params["image_size"] or 512).to(self.device)

                with torch.inference_mode():
                    out = self.model(tensor)

                out = F.interpolate(out, size=(image.height, image.width), mode="bilinear", align_corners=False)
                # Lineart Generator emits a bright-background / dark-line image in
                # [0, 1]; ControlNet convention is the inverse (dark background,
                # bright line). Flip once so the default output matches.
                edge = 1.0 - out
                edge_u8 = (edge.squeeze().clamp(0, 1) * 255.0).to(torch.uint8).cpu().numpy()

                if params["invert"]:
                    edge_u8 = 255 - edge_u8

                edges.append(PILImage.fromarray(edge_u8, mode="L"))

            return edges

        return await self._run_in_executor(_detect)

    def _image_to_tensor(self, image: PILImage.Image, image_size: int) -> Any:
        import torch
        import numpy as np

        # Lineart expects RGB in [-1, 1] (standard GAN normalization).
        resized = image.resize((image_size, image_size), PILImage.Resampling.BILINEAR)
        array = np.array(resized, dtype=np.float32) / 255.0
        array = (array - 0.5) * 2.0

        tensor = torch.from_numpy(array).permute(2, 0, 1).unsqueeze(0)
        return tensor

class LineartImageEdgeDetectionTaskDriver(ModelTaskDriver):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[Any] = None
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [
            *torch_requirements("torch"),
            "numpy",
        ]

    async def _load_model(self) -> None:
        self._inflate_default_filename()
        model_path = await self._provision_model(self.config.model, prefetch=True)

        def _load() -> Any:
            model = self._build_network()
            self._load_model_checkpoint(model, model_path)
            return model

        self.device = self._resolve_device(self.config.device)
        self.model = await self._run_in_executor(_load)
        self.model.to(self.device).eval()

    async def _unload_model(self) -> None:
        self.model = None
        self.device = None

    def _inflate_default_filename(self) -> None:
        model = self.config.model
        if model.provider == ModelProvider.HUGGINGFACE and model.filename is None:
            model.filename = _LINEART_WEIGHT_FILENAMES[self.config.variant]

    def _build_network(self) -> Any:
        import torch
        import torch.nn as nn

        class ResnetBlock(nn.Module):
            """Residual block with reflection-padded 3x3 convs — Anime2Sketch Generator bottleneck unit."""

            def __init__(self, channels: int):
                super().__init__()
                self.block = nn.Sequential(
                    nn.ReflectionPad2d(1),
                    nn.Conv2d(channels, channels, kernel_size=3, padding=0, bias=True),
                    nn.InstanceNorm2d(channels),
                    nn.ReLU(inplace=True),
                    nn.ReflectionPad2d(1),
                    nn.Conv2d(channels, channels, kernel_size=3, padding=0, bias=True),
                    nn.InstanceNorm2d(channels),
                )

            def forward(self, x):
                return x + self.block(x)

        class UNetGenerator(nn.Module):
            """Anime2Sketch Generator (resnet_9blocks variant)."""

            def __init__(self, in_channels: int = 3, out_channels: int = 1, ngf: int = 64, n_blocks: int = 9):
                super().__init__()

                layers: List[nn.Module] = [
                    nn.ReflectionPad2d(3),
                    nn.Conv2d(in_channels, ngf, kernel_size=7, padding=0, bias=True),
                    nn.InstanceNorm2d(ngf),
                    nn.ReLU(inplace=True),
                ]

                n_downsampling = 2
                for i in range(n_downsampling):
                    mult = 2 ** i
                    layers += [
                        nn.Conv2d(ngf * mult, ngf * mult * 2, kernel_size=3, stride=2, padding=1, bias=True),
                        nn.InstanceNorm2d(ngf * mult * 2),
                        nn.ReLU(inplace=True),
                    ]

                mult = 2 ** n_downsampling
                for _ in range(n_blocks):
                    layers.append(ResnetBlock(ngf * mult))

                for i in range(n_downsampling):
                    mult = 2 ** (n_downsampling - i)
                    layers += [
                        nn.ConvTranspose2d(ngf * mult, int(ngf * mult / 2), kernel_size=3, stride=2, padding=1, output_padding=1, bias=True),
                        nn.InstanceNorm2d(int(ngf * mult / 2)),
                        nn.ReLU(inplace=True),
                    ]

                layers += [
                    nn.ReflectionPad2d(3),
                    nn.Conv2d(ngf, out_channels, kernel_size=7, padding=0),
                    nn.Sigmoid(),
                ]

                self.model = nn.Sequential(*layers)

            def forward(self, x: torch.Tensor) -> torch.Tensor:
                return self.model(x)

        return UNetGenerator()

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await LineartImageEdgeDetectionTaskAction(action, self.model, self.device).run(context)
