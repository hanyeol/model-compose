"""HED (Holistically-Nested Edge Detection) driver.

Architecture ported from the ControlNetHED preprocessor used by the
`controlnet_aux` project — originally lllyasviel/ControlNet-v1-1-nightly.
Weights are the public `ControlNetHED.pth` checkpoint published to the
`lllyasviel/Annotators` HuggingFace repo (Apache-2.0 attribution).
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple, Optional, Dict, List, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, HedImageEdgeDetectionModelActionConfig
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.cancellation import CancellationToken
from ....base import ComponentActionContext, ModelTaskDriver
from ..common import ImageEdgeDetectionTaskAction
from PIL import Image as PILImage

if TYPE_CHECKING:
    import torch

class HedImageEdgeDetectionTaskAction(ImageEdgeDetectionTaskAction):
    config: HedImageEdgeDetectionModelActionConfig

    def __init__(
        self,
        config: HedImageEdgeDetectionModelActionConfig,
        model: Any,
        device: torch.device,
    ):
        super().__init__(config, device)

        self.model: Any = model

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        use_safe_mode = await context.render_variable(self.config.params.use_safe_mode)

        params.update({
            "use_safe_mode": bool(use_safe_mode),
        })

        return params

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
                    edge = self.model(tensor)  # [1, 1, H, W] in [0, 1]

                edge = F.interpolate(edge, size=(image.height, image.width), mode="bilinear", align_corners=False)
                edge_u8 = (edge.squeeze().clamp(0, 1) * 255.0).to(torch.uint8).cpu().numpy()

                if params["use_safe_mode"]:
                    edge_u8 = self._apply_safe_mode(edge_u8)

                if params["invert"]:
                    edge_u8 = 255 - edge_u8

                edges.append(PILImage.fromarray(edge_u8, mode="L"))

            return edges

        return await self._run_in_executor(_detect)

    def _image_to_tensor(self, image: PILImage.Image, image_size: int) -> Any:
        import torch
        import numpy as np

        # HED expects BGR, mean-subtracted, [0, 255] input (OpenCV convention).
        resized = image.resize((image_size, image_size), PILImage.Resampling.BILINEAR)
        array = np.array(resized, dtype=np.float32)
        array = array[:, :, ::-1]  # RGB -> BGR
        array -= np.array([ 104.00698793, 116.66876762, 122.67891434 ], dtype=np.float32)

        tensor = torch.from_numpy(array.copy()).permute(2, 0, 1).unsqueeze(0)
        return tensor

    def _apply_safe_mode(self, edge_u8: Any) -> Any:
        """Suppress weak edges by applying a soft threshold.

        Mirrors the ControlNet 1.1 'safe' option: pixels below the dynamic
        threshold are driven to zero, strong edges are preserved. Reduces
        stray background texture that often confuses ControlNet.
        """
        import numpy as np

        edge = edge_u8.astype(np.float32) / 255.0
        threshold = edge.mean() + edge.std()
        edge = np.where(edge >= threshold, edge, edge * (edge / max(threshold, 1e-6)) ** 2)

        return (edge.clip(0, 1) * 255.0).astype(np.uint8)

class HedImageEdgeDetectionTaskDriver(ModelTaskDriver):
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
        import torch.nn.functional as F

        class DoubleConvBlock(nn.Module):
            """VGG stage with two or three 3x3 convs plus a per-stage 1x1 projection to a single-channel edge map."""

            def __init__(self, in_channels: int, out_channels: int, num_convs: int):
                super().__init__()

                channels = [ in_channels ] + [ out_channels ] * num_convs
                self.convs = nn.ModuleList([
                    nn.Conv2d(channels[i], channels[i + 1], kernel_size=3, padding=1)
                    for i in range(num_convs)
                ])
                self.projection = nn.Conv2d(out_channels, 1, kernel_size=1)

            def forward(self, x: torch.Tensor, down_sample: Optional[nn.Module] = None) -> tuple:
                h = down_sample(x) if down_sample is not None else x
                for conv in self.convs:
                    h = F.relu(conv(h), inplace=True)
                edge = self.projection(h)
                return h, edge

        class ControlNetHED(nn.Module):
            """ControlNet 1.1's HED preprocessor (lllyasviel/Annotators/ControlNetHED.pth).

            VGG16-style five-stage encoder where each stage produces its own
            single-channel edge map via a 1x1 projection. The outputs are
            upsampled to the input resolution and averaged — no fuse conv.
            """

            def __init__(self):
                super().__init__()

                # Per-channel BGR mean subtracted from the input (ImageNet BGR
                # convention, stored in the checkpoint as a broadcastable tensor).
                self.norm = nn.Parameter(torch.zeros(1, 3, 1, 1))

                self.block1 = DoubleConvBlock(3,   64,  num_convs=2)
                self.block2 = DoubleConvBlock(64,  128, num_convs=2)
                self.block3 = DoubleConvBlock(128, 256, num_convs=3)
                self.block4 = DoubleConvBlock(256, 512, num_convs=3)
                self.block5 = DoubleConvBlock(512, 512, num_convs=3)

                self.pool = nn.MaxPool2d(kernel_size=2, stride=2)

            def forward(self, x: torch.Tensor) -> torch.Tensor:
                height, width = x.shape[-2:]

                x = x - self.norm

                h1, e1 = self.block1(x)
                h2, e2 = self.block2(h1, down_sample=self.pool)
                h3, e3 = self.block3(h2, down_sample=self.pool)
                h4, e4 = self.block4(h3, down_sample=self.pool)
                _,  e5 = self.block5(h4, down_sample=self.pool)

                edges = [
                    F.interpolate(edge, size=(height, width), mode="bilinear", align_corners=False)
                    for edge in (e1, e2, e3, e4, e5)
                ]

                return torch.sigmoid(torch.stack(edges, dim=0).mean(dim=0))

        return ControlNetHED()

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await HedImageEdgeDetectionTaskAction(action, self.model, self.device).run(context)
