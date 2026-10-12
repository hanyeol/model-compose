"""PiDiNet (Pixel Difference Network) edge detection driver.

Architecture ported from hellozhuo/pidinet (ICCV 2021, Table 5 config)
with the ControlNet-adapted post-processing. Weights are the public
`table5_pidinet.pth` checkpoint from the `lllyasviel/Annotators`
HuggingFace repo.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple, Optional, Dict, List, Any
from mindor.dsl.schema.component import ModelComponentConfig, ModelProvider
from mindor.dsl.schema.action import ModelActionConfig, PidinetImageEdgeDetectionModelActionConfig
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.cancellation import CancellationToken
from ....base import ComponentActionContext, ModelTaskDriver
from ..common import ImageEdgeDetectionTaskAction
from PIL import Image as PILImage

if TYPE_CHECKING:
    import torch

_PIDINET_WEIGHT_FILENAME = "table5_pidinet.pth"

class PidinetImageEdgeDetectionTaskAction(ImageEdgeDetectionTaskAction):
    config: PidinetImageEdgeDetectionModelActionConfig

    def __init__(
        self,
        config: PidinetImageEdgeDetectionModelActionConfig,
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
                    output = self.model(tensor)
                    edge = output[-1] if isinstance(output, (list, tuple)) else output

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

        # PiDiNet expects normalized [0, 1] RGB (standard torchvision convention).
        resized = image.resize((image_size, image_size), PILImage.Resampling.BILINEAR)
        array = np.array(resized, dtype=np.float32) / 255.0

        tensor = torch.from_numpy(array).permute(2, 0, 1).unsqueeze(0)
        return tensor

    def _apply_safe_mode(self, edge_u8: Any) -> Any:
        import numpy as np

        edge = edge_u8.astype(np.float32) / 255.0
        threshold = edge.mean() + edge.std()
        edge = np.where(edge >= threshold, edge, edge * (edge / max(threshold, 1e-6)) ** 2)

        return (edge.clip(0, 1) * 255.0).astype(np.uint8)

class PidinetImageEdgeDetectionTaskDriver(ModelTaskDriver):
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
            model.filename = _PIDINET_WEIGHT_FILENAME

    def _build_network(self) -> Any:
        import torch
        import torch.nn as nn
        import torch.nn.functional as F

        class CSAM(nn.Module):
            """Compact Spatial Attention Module."""

            def __init__(self, channels: int):
                super().__init__()
                self.relu = nn.ReLU()
                self.conv1 = nn.Conv2d(channels, 1, kernel_size=1)
                self.conv2 = nn.Conv2d(1, 1, kernel_size=3, padding=1, bias=False)
                self.sigmoid = nn.Sigmoid()
                nn.init.constant_(self.conv1.bias, 0)

            def forward(self, x):
                y = self.relu(x)
                y = self.conv1(y)
                y = self.conv2(y)
                y = self.sigmoid(y)
                return x * y

        class CDCM(nn.Module):
            """Compact Dilation Convolution-based Module."""

            def __init__(self, in_channels: int, out_channels: int):
                super().__init__()
                self.relu = nn.ReLU()
                self.conv1 = nn.Conv2d(in_channels, out_channels, kernel_size=1, padding=0)
                self.conv2_1 = nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=5, dilation=5, bias=False)
                self.conv2_2 = nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=7, dilation=7, bias=False)
                self.conv2_3 = nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=9, dilation=9, bias=False)
                self.conv2_4 = nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=11, dilation=11, bias=False)
                nn.init.constant_(self.conv1.bias, 0)

            def forward(self, x):
                x = self.relu(x)
                x = self.conv1(x)
                x1 = self.conv2_1(x)
                x2 = self.conv2_2(x)
                x3 = self.conv2_3(x)
                x4 = self.conv2_4(x)
                return x1 + x2 + x3 + x4

        class MapReduce(nn.Module):
            """1x1 convolution reducing a feature stack to a single-channel edge map."""

            def __init__(self, channels: int):
                super().__init__()
                self.conv = nn.Conv2d(channels, 1, kernel_size=1, padding=0)
                nn.init.constant_(self.conv.bias, 0)

            def forward(self, x):
                return self.conv(x)

        class PDCBlock(nn.Module):
            """Pixel Difference Convolution block (Table 5 variant: plain CNN).

            The published PiDiNet replaces conv weights with pixel-difference
            operators at train time; at inference the checkpoint stores the
            equivalent plain convolution weights, so no custom op is needed.
            """

            def __init__(self, in_channels: int, out_channels: int, stride: int = 1):
                super().__init__()
                if stride > 1:
                    self.shortcut = nn.Sequential(
                        nn.AvgPool2d(stride, stride=stride),
                        nn.Conv2d(in_channels, out_channels, kernel_size=1, padding=0, bias=False),
                    )
                    self.conv1 = nn.Conv2d(in_channels, out_channels, kernel_size=3, stride=stride, padding=1, groups=1, bias=False)
                else:
                    self.shortcut = nn.Identity()
                    self.conv1 = nn.Conv2d(in_channels, in_channels, kernel_size=3, padding=1, groups=in_channels, bias=False)
                self.relu2 = nn.ReLU()
                self.conv2 = nn.Conv2d(in_channels if stride == 1 else out_channels, out_channels, kernel_size=1, padding=0, bias=False)

            def forward(self, x):
                y = self.conv1(x)
                y = self.relu2(y)
                y = self.conv2(y)
                return y + self.shortcut(x)

        class PiDiNet(nn.Module):
            def __init__(self):
                super().__init__()
                inplane = 60

                self.init_block = nn.Conv2d(3, inplane, kernel_size=3, padding=1, bias=False)

                self.block1_1 = PDCBlock(inplane, inplane)
                self.block1_2 = PDCBlock(inplane, inplane)
                self.block1_3 = PDCBlock(inplane, inplane)

                inplane2 = 120
                self.block2_1 = PDCBlock(inplane,  inplane2, stride=2)
                self.block2_2 = PDCBlock(inplane2, inplane2)
                self.block2_3 = PDCBlock(inplane2, inplane2)
                self.block2_4 = PDCBlock(inplane2, inplane2)

                inplane3 = 240
                self.block3_1 = PDCBlock(inplane2, inplane3, stride=2)
                self.block3_2 = PDCBlock(inplane3, inplane3)
                self.block3_3 = PDCBlock(inplane3, inplane3)
                self.block3_4 = PDCBlock(inplane3, inplane3)

                self.block4_1 = PDCBlock(inplane3, inplane3, stride=2)
                self.block4_2 = PDCBlock(inplane3, inplane3)
                self.block4_3 = PDCBlock(inplane3, inplane3)
                self.block4_4 = PDCBlock(inplane3, inplane3)

                self.conv_reduces = nn.ModuleList([
                    MapReduce(inplane),
                    MapReduce(inplane2),
                    MapReduce(inplane3),
                    MapReduce(inplane3),
                ])

                self.attentions = nn.ModuleList([
                    CSAM(inplane),
                    CSAM(inplane2),
                    CSAM(inplane3),
                    CSAM(inplane3),
                ])

                self.dilations = nn.ModuleList([
                    CDCM(inplane,  24),
                    CDCM(inplane2, 24),
                    CDCM(inplane3, 24),
                    CDCM(inplane3, 24),
                ])

                self.conv_reduces_dilated = nn.ModuleList([
                    MapReduce(24),
                    MapReduce(24),
                    MapReduce(24),
                    MapReduce(24),
                ])

                self.classifier = nn.Conv2d(4, 1, kernel_size=1)
                nn.init.constant_(self.classifier.weight, 0.25)
                nn.init.constant_(self.classifier.bias, 0)

            def forward(self, x: torch.Tensor):
                height, width = x.shape[-2:]

                x = self.init_block(x)

                x1 = self.block1_1(x);  x1 = self.block1_2(x1); x1 = self.block1_3(x1)
                x2 = self.block2_1(x1); x2 = self.block2_2(x2); x2 = self.block2_3(x2); x2 = self.block2_4(x2)
                x3 = self.block3_1(x2); x3 = self.block3_2(x3); x3 = self.block3_3(x3); x3 = self.block3_4(x3)
                x4 = self.block4_1(x3); x4 = self.block4_2(x4); x4 = self.block4_3(x4); x4 = self.block4_4(x4)

                features = [x1, x2, x3, x4]
                edges = []

                for feature, attention, dilation, reduce_dilated in zip(features, self.attentions, self.dilations, self.conv_reduces_dilated):
                    attended = attention(feature)
                    dilated = dilation(attended)
                    reduced = reduce_dilated(dilated)
                    edges.append(F.interpolate(reduced, size=(height, width), mode="bilinear", align_corners=False))

                fused = self.classifier(torch.cat(edges, dim=1))
                return torch.sigmoid(fused)

        return PiDiNet()

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await PidinetImageEdgeDetectionTaskAction(action, self.model, self.device).run(context)
