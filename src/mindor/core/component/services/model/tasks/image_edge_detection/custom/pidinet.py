"""PiDiNet (Pixel Difference Network) edge detection driver.

Architecture ported from hellozhuo/pidinet (ICCV 2021) via the
`controlnet_aux` wrapper that pairs it with the `carv4` configuration
(dil=24, spatial-attention). Weights are the public `table5_pidinet.pth`
checkpoint from the `lllyasviel/Annotators` HuggingFace repo.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple, Optional, Dict, List, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, PidinetImageEdgeDetectionModelActionConfig
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.cancellation import CancellationToken
from ....base import ComponentActionContext, ModelTaskDriver
from ..common import ImageEdgeDetectionTaskAction
from PIL import Image as PILImage

if TYPE_CHECKING:
    import torch

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
            import torch.nn.functional as F
            import torch

            edges: List[PILImage.Image] = []

            for image in images:
                image = image.convert("RGB")
                tensor = self._image_to_tensor(image, params["image_size"] or 512).to(self.device)

                with torch.inference_mode():
                    outputs = self.model(tensor)

                # `pidinet()` returns [e1, e2, e3, e4, classifier] already
                # sigmoid-activated; the final fused edge is at index -1.
                edge = outputs[-1] if isinstance(outputs, (list, tuple)) else outputs
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

        # PiDiNet expects BGR in [0, 1] (OpenCV convention — upstream
        # `PidiNetDetector` reverses the last channel of a numpy image).
        resized = image.resize((image_size, image_size), PILImage.Resampling.BILINEAR)
        array = np.array(resized, dtype=np.float32)[:, :, ::-1] / 255.0

        tensor = torch.from_numpy(array.copy()).permute(2, 0, 1).unsqueeze(0)
        return tensor

    def _apply_safe_mode(self, edge_u8: Any) -> Any:
        """Suppress weak edges by applying a soft threshold (ControlNet 1.1 'safe' option)."""
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
        model_path = await self._provision_model(self.config.model, prefetch=True)

        def _load() -> Any:
            import torch

            model = self._build_network()
            checkpoint = torch.load(model_path, map_location="cpu", weights_only=False)

            # Upstream checkpoint was saved via DataParallel so every key is
            # prefixed with ``module.``; strip it to match our flat module.
            state_dict = { key.replace("module.", "", 1): value for key, value in checkpoint["state_dict"].items() }
            model.load_state_dict(state_dict, strict=True)

            return model

        self.device = self._resolve_device(self.config.device)
        self.model = await self._run_in_executor(_load)
        self.model.to(self.device).eval()

    async def _unload_model(self) -> None:
        self.model = None
        self.device = None

    def _build_network(self) -> Any:
        import math
        import torch
        import torch.nn as nn
        import torch.nn.functional as F

        class PdcConv2d(nn.Module):
            """3x3 convolution driven by a pixel-difference operator."""

            def __init__(
                self,
                pdc_fn,
                in_channels: int,
                out_channels: int,
                kernel_size: int = 3,
                stride: int = 1,
                padding: int = 0,
                dilation: int = 1,
                groups: int = 1,
                bias: bool = False
            ):
                super().__init__()

                self.stride = stride
                self.padding = padding
                self.dilation = dilation
                self.groups = groups
                self.weight = nn.Parameter(torch.empty(out_channels, in_channels // groups, kernel_size, kernel_size))

                if bias:
                    self.bias = nn.Parameter(torch.empty(out_channels))
                else:
                    self.register_parameter("bias", None)

                nn.init.kaiming_uniform_(self.weight, a=math.sqrt(5))

                if self.bias is not None:
                    bound = 1 / math.sqrt(in_channels * kernel_size * kernel_size)
                    nn.init.uniform_(self.bias, -bound, bound)

                self.pdc_fn = pdc_fn

            def forward(self, x: torch.Tensor) -> torch.Tensor:
                return self.pdc_fn(x, self.weight, self.bias, self.stride, self.padding, self.dilation, self.groups)

        class PDCBlock(nn.Module):
            """PiDiNet residual block.

            Downsamples through MaxPool2d(2) when stride=2; the shortcut
            then re-projects channels with a 1x1 conv to match the main
            path's output channel count.
            """

            def __init__(self, pdc_fn, in_channels: int, out_channels: int, stride: int = 1):
                super().__init__()

                self.stride = stride

                if stride > 1:
                    self.pool = nn.MaxPool2d(kernel_size=2, stride=2)
                    self.shortcut = nn.Conv2d(in_channels, out_channels, kernel_size=1, padding=0)

                self.conv1 = PdcConv2d(pdc_fn, in_channels, in_channels, kernel_size=3, padding=1, groups=in_channels, bias=False)
                self.relu2 = nn.ReLU()
                self.conv2 = nn.Conv2d(in_channels, out_channels, kernel_size=1, padding=0, bias=False)

            def forward(self, x: torch.Tensor) -> torch.Tensor:
                if self.stride > 1:
                    x = self.pool(x)

                y = self.conv1(x)
                y = self.relu2(y)
                y = self.conv2(y)

                if self.stride > 1:
                    x = self.shortcut(x)

                return y + x

        class CSAM(nn.Module):
            """Compact Spatial Attention Module."""

            def __init__(self, channels: int):
                super().__init__()

                self.relu1 = nn.ReLU()
                self.conv1 = nn.Conv2d(channels, 4, kernel_size=1, padding=0)
                self.conv2 = nn.Conv2d(4, 1, kernel_size=3, padding=1, bias=False)
                self.sigmoid = nn.Sigmoid()
                nn.init.constant_(self.conv1.bias, 0)

            def forward(self, x: torch.Tensor) -> torch.Tensor:
                y = self.relu1(x)
                y = self.conv1(y)
                y = self.conv2(y)
                y = self.sigmoid(y)

                return x * y

        class CDCM(nn.Module):
            """Compact Dilation Convolution-based Module."""

            def __init__(self, in_channels: int, out_channels: int):
                super().__init__()

                self.relu1 = nn.ReLU()
                self.conv1 = nn.Conv2d(in_channels, out_channels, kernel_size=1, padding=0)
                self.conv2_1 = nn.Conv2d(out_channels, out_channels, kernel_size=3, dilation=5,  padding=5,  bias=False)
                self.conv2_2 = nn.Conv2d(out_channels, out_channels, kernel_size=3, dilation=7,  padding=7,  bias=False)
                self.conv2_3 = nn.Conv2d(out_channels, out_channels, kernel_size=3, dilation=9,  padding=9,  bias=False)
                self.conv2_4 = nn.Conv2d(out_channels, out_channels, kernel_size=3, dilation=11, padding=11, bias=False)
                nn.init.constant_(self.conv1.bias, 0)

            def forward(self, x: torch.Tensor) -> torch.Tensor:
                x = self.relu1(x)
                x = self.conv1(x)

                return self.conv2_1(x) + self.conv2_2(x) + self.conv2_3(x) + self.conv2_4(x)

        class MapReduce(nn.Module):
            """1x1 convolution reducing a feature stack to a single-channel edge map."""

            def __init__(self, channels: int):
                super().__init__()

                self.conv = nn.Conv2d(channels, 1, kernel_size=1, padding=0)
                nn.init.constant_(self.conv.bias, 0)

            def forward(self, x: torch.Tensor) -> torch.Tensor:
                return self.conv(x)

        class PiDiNet(nn.Module):
            # carv4 PDC pattern used by `pidinet()` in the upstream repo:
            # a mix of central-difference (cd), angular-difference (ad),
            # radial-difference (rd) and vanilla (cv) convolutions.
            _CARV4_PDCS: List[str] = [
                "cd", "ad", "rd", "cv",
                "cd", "ad", "rd", "cv",
                "cd", "ad", "rd", "cv",
                "cd", "ad", "rd", "cv",
            ]

            def __init__(self):
                super().__init__()

                pdcs = [ self._make_pdc_func(op) for op in self._CARV4_PDCS ]
                inplane = 60
                dil = 24

                self.init_block = PdcConv2d(pdcs[0], 3, inplane, kernel_size=3, padding=1, bias=False)

                self.block1_1 = PDCBlock(pdcs[1], inplane, inplane)
                self.block1_2 = PDCBlock(pdcs[2], inplane, inplane)
                self.block1_3 = PDCBlock(pdcs[3], inplane, inplane)

                self.block2_1 = PDCBlock(pdcs[4], inplane,     inplane * 2, stride=2)
                self.block2_2 = PDCBlock(pdcs[5], inplane * 2, inplane * 2)
                self.block2_3 = PDCBlock(pdcs[6], inplane * 2, inplane * 2)
                self.block2_4 = PDCBlock(pdcs[7], inplane * 2, inplane * 2)

                self.block3_1 = PDCBlock(pdcs[8],  inplane * 2, inplane * 4, stride=2)
                self.block3_2 = PDCBlock(pdcs[9],  inplane * 4, inplane * 4)
                self.block3_3 = PDCBlock(pdcs[10], inplane * 4, inplane * 4)
                self.block3_4 = PDCBlock(pdcs[11], inplane * 4, inplane * 4)

                self.block4_1 = PDCBlock(pdcs[12], inplane * 4, inplane * 4, stride=2)
                self.block4_2 = PDCBlock(pdcs[13], inplane * 4, inplane * 4)
                self.block4_3 = PDCBlock(pdcs[14], inplane * 4, inplane * 4)
                self.block4_4 = PDCBlock(pdcs[15], inplane * 4, inplane * 4)

                fuseplanes = [ inplane, inplane * 2, inplane * 4, inplane * 4 ]
                self.dilations = nn.ModuleList([ CDCM(channels, dil) for channels in fuseplanes ])
                self.attentions = nn.ModuleList([ CSAM(dil) for _ in fuseplanes ])
                self.conv_reduces = nn.ModuleList([ MapReduce(dil) for _ in fuseplanes ])

                self.classifier = nn.Conv2d(4, 1, kernel_size=1)
                nn.init.constant_(self.classifier.weight, 0.25)
                nn.init.constant_(self.classifier.bias, 0)

            def forward(self, x: torch.Tensor) -> List[torch.Tensor]:
                height, width = x.shape[-2:]

                x = self.init_block(x)

                x1 = self.block1_1(x);  x1 = self.block1_2(x1); x1 = self.block1_3(x1)
                x2 = self.block2_1(x1); x2 = self.block2_2(x2); x2 = self.block2_3(x2); x2 = self.block2_4(x2)
                x3 = self.block3_1(x2); x3 = self.block3_2(x3); x3 = self.block3_3(x3); x3 = self.block3_4(x3)
                x4 = self.block4_1(x3); x4 = self.block4_2(x4); x4 = self.block4_3(x4); x4 = self.block4_4(x4)

                fused = [
                    attention(dilation(feature))
                    for feature, dilation, attention in zip([ x1, x2, x3, x4 ], self.dilations, self.attentions)
                ]

                edges = [
                    F.interpolate(reduce(feature), size=(height, width), mode="bilinear", align_corners=False)
                    for feature, reduce in zip(fused, self.conv_reduces)
                ]

                final = self.classifier(torch.cat(edges, dim=1))

                return [torch.sigmoid(e) for e in edges] + [torch.sigmoid(final)]

            @staticmethod
            def _make_pdc_func(op_type: str):
                """Pixel-difference convolution kernels from hellozhuo/pidinet.

                Each variant rewrites the convolution to encode the explicit
                pixel-difference operation. `cv` is a plain conv.
                """
                if op_type == "cv":
                    return F.conv2d

                if op_type == "cd":
                    def func(x, weights, bias=None, stride=1, padding=0, dilation=1, groups=1):
                        weights_c = weights.sum(dim=[2, 3], keepdim=True)
                        yc = F.conv2d(x, weights_c, stride=stride, padding=0, groups=groups)
                        y  = F.conv2d(x, weights, bias, stride=stride, padding=padding, dilation=dilation, groups=groups)
                        return y - yc
                    return func

                if op_type == "ad":
                    def func(x, weights, bias=None, stride=1, padding=0, dilation=1, groups=1):
                        shape = weights.shape
                        flat = weights.view(shape[0], shape[1], -1)
                        rotated = flat[:, :, [3, 0, 1, 6, 4, 2, 7, 8, 5]]
                        conv_weights = (flat - rotated).view(shape)
                        return F.conv2d(x, conv_weights, bias, stride=stride, padding=padding, dilation=dilation, groups=groups)
                    return func

                if op_type == "rd":
                    def func(x, weights, bias=None, stride=1, padding=0, dilation=1, groups=1):
                        padding = 2 * dilation
                        shape = weights.shape
                        buffer = torch.zeros(shape[0], shape[1], 25, device=weights.device, dtype=weights.dtype)
                        flat = weights.view(shape[0], shape[1], -1)
                        buffer[:, :, [0, 2, 4, 10, 14, 20, 22, 24]] =  flat[:, :, 1:]
                        buffer[:, :, [6, 7, 8, 11, 13, 16, 17, 18]] = -flat[:, :, 1:]
                        buffer = buffer.view(shape[0], shape[1], 5, 5)
                        return F.conv2d(x, buffer, bias, stride=stride, padding=padding, dilation=dilation, groups=groups)
                    return func

                raise ValueError(f"Unknown PDC op type: {op_type}")

        return PiDiNet()

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await PidinetImageEdgeDetectionTaskAction(action, self.model, self.device).run(context)
