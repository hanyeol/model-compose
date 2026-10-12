"""Lineart (anime-style line extraction) driver.

Architecture ported from Mukosame/Anime2Sketch via `controlnet_aux` —
the ControlNet 1.1 lineart preprocessor. The network is a ResNet-style
Generator (3 residual blocks) partitioned into five Sequential stages
to match the checkpoint layout.

Two public checkpoints on `lllyasviel/Annotators`:
- `sk_model.pth`  — realistic / detailed lines
- `sk_model2.pth` — coarse / simpler lines
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple, Optional, Dict, List, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, LineartImageEdgeDetectionModelActionConfig
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.cancellation import CancellationToken
from ....base import ComponentActionContext, ModelTaskDriver
from ..common import ImageEdgeDetectionTaskAction
from PIL import Image as PILImage

if TYPE_CHECKING:
    import torch

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
                # Generator emits a bright-background / dark-line image in
                # [0, 1]; ControlNet convention is the inverse (dark
                # background, bright line). Flip once so the default output
                # matches, matching upstream `detected_map = 255 - detected_map`.
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

        # Lineart expects RGB in [0, 1] (upstream converts a uint8 image to
        # float and divides by 255).
        resized = image.resize((image_size, image_size), PILImage.Resampling.BILINEAR)
        array = np.array(resized, dtype=np.float32) / 255.0

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

    def _build_network(self) -> Any:
        import torch
        import torch.nn as nn

        norm_layer = nn.InstanceNorm2d

        class ResidualBlock(nn.Module):
            def __init__(self, in_features: int):
                super().__init__()

                self.conv_block = nn.Sequential(
                    nn.ReflectionPad2d(1),
                    nn.Conv2d(in_features, in_features, 3),
                    norm_layer(in_features),
                    nn.ReLU(inplace=True),
                    nn.ReflectionPad2d(1),
                    nn.Conv2d(in_features, in_features, 3),
                    norm_layer(in_features),
                )

            def forward(self, x: torch.Tensor) -> torch.Tensor:
                return x + self.conv_block(x)

        class Generator(nn.Module):
            """Anime2Sketch Generator (3 residual blocks, sigmoid output).

            Split into five named Sequential submodules (model0..model4)
            to match the checkpoint keys.
            """

            def __init__(self, input_nc: int = 3, output_nc: int = 1, n_residual_blocks: int = 3):
                super().__init__()

                self.model0 = nn.Sequential(
                    nn.ReflectionPad2d(3),
                    nn.Conv2d(input_nc, 64, 7),
                    norm_layer(64),
                    nn.ReLU(inplace=True),
                )

                downsampling: List[nn.Module] = []
                in_features = 64
                out_features = in_features * 2

                for _ in range(2):
                    downsampling += [
                        nn.Conv2d(in_features, out_features, 3, stride=2, padding=1),
                        norm_layer(out_features),
                        nn.ReLU(inplace=True),
                    ]
                    in_features = out_features
                    out_features = in_features * 2

                self.model1 = nn.Sequential(*downsampling)
                self.model2 = nn.Sequential(*[ ResidualBlock(in_features) for _ in range(n_residual_blocks) ])

                upsampling: List[nn.Module] = []
                out_features = in_features // 2

                for _ in range(2):
                    upsampling += [
                        nn.ConvTranspose2d(in_features, out_features, 3, stride=2, padding=1, output_padding=1),
                        norm_layer(out_features),
                        nn.ReLU(inplace=True),
                    ]
                    in_features = out_features
                    out_features = in_features // 2

                self.model3 = nn.Sequential(*upsampling)
                self.model4 = nn.Sequential(
                    nn.ReflectionPad2d(3),
                    nn.Conv2d(64, output_nc, 7),
                    nn.Sigmoid(),
                )

            def forward(self, x: torch.Tensor) -> torch.Tensor:
                x = self.model0(x)
                x = self.model1(x)
                x = self.model2(x)
                x = self.model3(x)

                return self.model4(x)

        return Generator()

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await LineartImageEdgeDetectionTaskAction(action, self.model, self.device).run(context)
