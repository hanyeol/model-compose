"""HED (Holistically-Nested Edge Detection) driver.

Architecture ported from the ControlNetHED preprocessor used by the
`controlnet_aux` project — originally lllyasviel/ControlNet-v1-1-nightly.
Weights are the public `ControlNetHED.pth` checkpoint published to the
`lllyasviel/Annotators` HuggingFace repo (Apache-2.0 attribution).
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple, Optional, Dict, List, Any
from mindor.dsl.schema.component import ModelComponentConfig, ModelProvider
from mindor.dsl.schema.action import ModelActionConfig, HedImageEdgeDetectionModelActionConfig
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.cancellation import CancellationToken
from ....base import ComponentActionContext, ModelTaskDriver
from ..common import ImageEdgeDetectionTaskAction
from PIL import Image as PILImage

if TYPE_CHECKING:
    import torch

_HED_WEIGHT_FILENAME = "ControlNetHED.pth"

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
        array -= np.array([104.00698793, 116.66876762, 122.67891434], dtype=np.float32)

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
            model.filename = _HED_WEIGHT_FILENAME

    def _build_network(self) -> Any:
        import torch
        import torch.nn as nn

        class DoubleConv(nn.Module):
            def __init__(self, in_channels: int, out_channels: int, mid_channels: Optional[int] = None):
                super().__init__()

                mid_channels = mid_channels or out_channels
                self.block = nn.Sequential(
                    nn.Conv2d(in_channels, mid_channels, kernel_size=3, padding=1),
                    nn.ReLU(inplace=True),
                    nn.Conv2d(mid_channels, out_channels, kernel_size=3, padding=1),
                    nn.ReLU(inplace=True),
                )

            def forward(self, x):
                return self.block(x)

        class TripleConv(nn.Module):
            def __init__(self, in_channels: int, out_channels: int):
                super().__init__()

                self.block = nn.Sequential(
                    nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1),
                    nn.ReLU(inplace=True),
                    nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1),
                    nn.ReLU(inplace=True),
                    nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1),
                    nn.ReLU(inplace=True),
                )

            def forward(self, x):
                return self.block(x)

        class ControlNetHED(nn.Module):
            """ControlNet 1.1's HED preprocessor.

            VGG16-style five-stage encoder. Each stage produces a side output
            upsampled to the input resolution; a 1x1 conv fuses them into the
            final edge map.
            """

            def __init__(self):
                super().__init__()

                self.conv1 = DoubleConv(3, 64, 64)
                self.conv2 = DoubleConv(64, 128)
                self.conv3 = TripleConv(128, 256)
                self.conv4 = TripleConv(256, 512)
                self.conv5 = TripleConv(512, 512)

                self.score1 = nn.Conv2d(64,  1, kernel_size=1)
                self.score2 = nn.Conv2d(128, 1, kernel_size=1)
                self.score3 = nn.Conv2d(256, 1, kernel_size=1)
                self.score4 = nn.Conv2d(512, 1, kernel_size=1)
                self.score5 = nn.Conv2d(512, 1, kernel_size=1)

                self.fuse = nn.Conv2d(5, 1, kernel_size=1)
                self.pool = nn.MaxPool2d(kernel_size=2, stride=2)

            def forward(self, x: torch.Tensor) -> torch.Tensor:
                height, width = x.shape[-2:]

                c1 = self.conv1(x)
                c2 = self.conv2(self.pool(c1))
                c3 = self.conv3(self.pool(c2))
                c4 = self.conv4(self.pool(c3))
                c5 = self.conv5(self.pool(c4))

                s1 = torch.nn.functional.interpolate(self.score1(c1), size=(height, width), mode="bilinear", align_corners=False)
                s2 = torch.nn.functional.interpolate(self.score2(c2), size=(height, width), mode="bilinear", align_corners=False)
                s3 = torch.nn.functional.interpolate(self.score3(c3), size=(height, width), mode="bilinear", align_corners=False)
                s4 = torch.nn.functional.interpolate(self.score4(c4), size=(height, width), mode="bilinear", align_corners=False)
                s5 = torch.nn.functional.interpolate(self.score5(c5), size=(height, width), mode="bilinear", align_corners=False)

                fused = torch.sigmoid(self.fuse(torch.cat([s1, s2, s3, s4, s5], dim=1)))

                return fused

        return ControlNetHED()

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await HedImageEdgeDetectionTaskAction(action, self.model, self.device).run(context)
