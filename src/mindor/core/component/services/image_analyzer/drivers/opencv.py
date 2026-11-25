from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, List, Dict, Any, Union, Tuple
from mindor.dsl.schema.component import ImageAnalyzerComponentConfig, ImageAnalyzerDriverType
from mindor.dsl.schema.action import ImageAnalyzerActionConfig, OpenCvImageAnalyzerMetric
from mindor.core.foundation.cancellation import CancellationToken
from ..base import ImageAnalyzerDriver, register_image_analyzer_driver
from ..base import ComponentActionContext
from .common import ImageAnalyzerAction

if TYPE_CHECKING:
    from PIL import Image as PILImage

class OpenCvImageAnalyzerAction(ImageAnalyzerAction):
    async def _resolve_params(self, metric: OpenCvImageAnalyzerMetric, context: ComponentActionContext) -> Dict[str, Any]:
        if metric == OpenCvImageAnalyzerMetric.GRADIENT:
            gradient_min        = await context.render_scalar(self.config.gradient_min, float)
            gradient_max        = await context.render_scalar(self.config.gradient_max, float)
            curvature_threshold = await context.render_scalar(self.config.curvature_threshold, float)

            if gradient_min < 0.0:
                raise ValueError(f"'gradient_min' must be non-negative, got {gradient_min}")

            if gradient_max <= gradient_min:
                raise ValueError(f"'gradient_max' ({gradient_max}) must be greater than 'gradient_min' ({gradient_min})")

            if curvature_threshold < 0.0:
                raise ValueError(f"'curvature_threshold' must be non-negative, got {curvature_threshold}")

            return {
                "gradient_min":        gradient_min,
                "gradient_max":        gradient_max,
                "curvature_threshold": curvature_threshold,
            }

        if metric == OpenCvImageAnalyzerMetric.EDGE_STRUCTURE:
            edge_threshold         = await context.render_scalar(self.config.edge_threshold, float)
            axis_tolerance_degrees = await context.render_scalar(self.config.axis_tolerance_degrees, float)
            orientation_bins       = await context.render_scalar(self.config.orientation_bins, int)

            if edge_threshold < 0.0:
                raise ValueError(f"'edge_threshold' must be non-negative, got {edge_threshold}")

            if not 0.0 <= axis_tolerance_degrees <= 45.0:
                raise ValueError(f"'axis_tolerance_degrees' must be between 0.0 and 45.0, got {axis_tolerance_degrees}")

            if not 2 <= orientation_bins <= 180:
                raise ValueError(f"'orientation_bins' must be between 2 and 180, got {orientation_bins}")

            return {
                "edge_threshold":         edge_threshold,
                "axis_tolerance_degrees": axis_tolerance_degrees,
                "orientation_bins":       orientation_bins,
            }

        if metric == OpenCvImageAnalyzerMetric.TEXTURE:
            fine_kernel      = await context.render_scalar(self.config.fine_kernel, int)
            mid_kernel       = await context.render_scalar(self.config.mid_kernel, int)
            coarse_kernel    = await context.render_scalar(self.config.coarse_kernel, int)
            detail_threshold = await context.render_scalar(self.config.detail_threshold, float)

            for name, kernel in (("fine_kernel", fine_kernel), ("mid_kernel", mid_kernel), ("coarse_kernel", coarse_kernel)):
                if kernel < 3 or kernel % 2 == 0:
                    raise ValueError(f"'{name}' must be an odd integer >= 3, got {kernel}")

            if not (fine_kernel < mid_kernel < coarse_kernel):
                raise ValueError(f"kernels must be strictly increasing: fine={fine_kernel} < mid={mid_kernel} < coarse={coarse_kernel}")

            if detail_threshold < 0.0:
                raise ValueError(f"'detail_threshold' must be non-negative, got {detail_threshold}")

            return {
                "fine_kernel":      fine_kernel,
                "mid_kernel":       mid_kernel,
                "coarse_kernel":    coarse_kernel,
                "detail_threshold": detail_threshold,
            }

        if metric == OpenCvImageAnalyzerMetric.LIT_STRUCTURE:
            lit_threshold    = await context.render_scalar(self.config.lit_threshold, int)
            ink_threshold    = await context.render_scalar(self.config.ink_threshold, int)
            peak_window      = await context.render_scalar(self.config.peak_window, int)
            smooth_tolerance = await context.render_scalar(self.config.smooth_tolerance, float)

            if not 0 <= lit_threshold <= 255:
                raise ValueError(f"'lit_threshold' must be between 0 and 255, got {lit_threshold}")

            if not 0 <= ink_threshold <= 255:
                raise ValueError(f"'ink_threshold' must be between 0 and 255, got {ink_threshold}")

            if peak_window < 3 or peak_window % 2 == 0:
                raise ValueError(f"'peak_window' must be an odd integer >= 3, got {peak_window}")

            if smooth_tolerance < 0.0:
                raise ValueError(f"'smooth_tolerance' must be non-negative, got {smooth_tolerance}")

            return {
                "lit_threshold":    lit_threshold,
                "ink_threshold":    ink_threshold,
                "peak_window":      peak_window,
                "smooth_tolerance": smooth_tolerance,
            }

        raise ValueError(f"Unsupported image metric: {metric}")

    async def _analyze(
        self,
        metric: OpenCvImageAnalyzerMetric,
        image: PILImage.Image,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        if metric == OpenCvImageAnalyzerMetric.GRADIENT:
            return await self._analyze_gradient(image, params, cancellation_token)

        if metric == OpenCvImageAnalyzerMetric.EDGE_STRUCTURE:
            return await self._analyze_edge_structure(image, params, cancellation_token)

        if metric == OpenCvImageAnalyzerMetric.TEXTURE:
            return await self._analyze_texture(image, params, cancellation_token)

        if metric == OpenCvImageAnalyzerMetric.LIT_STRUCTURE:
            return await self._analyze_lit_structure(image, params, cancellation_token)

        raise ValueError(f"Unsupported image metric: {metric}")

    async def _analyze_gradient(
        self,
        image: PILImage.Image,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        def _analyze_gradient() -> Dict[str, Any]:
            import numpy as np
            import cv2

            luma = np.asarray(image.convert("L"), dtype=np.float32)
            dx = cv2.Sobel(luma, cv2.CV_32F, 1, 0, ksize=3)
            dy = cv2.Sobel(luma, cv2.CV_32F, 0, 1, ksize=3)
            gradient_magnitude = cv2.magnitude(dx, dy)

            # Gentle-gradient band: pixels brighter than flat (above gradient_min)
            # but below an edge (below gradient_max). Code-rendered gradients
            # occupy wide bands here; photographic skin tones occupy them too but
            # with fine-scale curvature from grain.
            gentle_mask = (gradient_magnitude >= params["gradient_min"]) & (gradient_magnitude <= params["gradient_max"])
            total_pixels = luma.size
            gentle_pixels = int(gentle_mask.sum())

            # Second-derivative magnitude as a curvature proxy. A perfectly linear
            # ramp has zero curvature; procedural gradients stay close to zero;
            # photographic shading has higher curvature from texture.
            dxx = cv2.Sobel(dx, cv2.CV_32F, 1, 0, ksize=3)
            dyy = cv2.Sobel(dy, cv2.CV_32F, 0, 1, ksize=3)
            curvature_magnitude = np.sqrt(dxx * dxx + dyy * dyy)

            mean_curvature = float(curvature_magnitude[gentle_mask].mean()) if gentle_pixels else 0.0
            clean_pixels = int((curvature_magnitude[gentle_mask] < params["curvature_threshold"]).sum()) if gentle_pixels else 0

            return {
                "grad_share":          gentle_pixels / total_pixels if total_pixels else 0.0,
                "grad_pixels":         gentle_pixels,
                "grad_clean":          clean_pixels / gentle_pixels if gentle_pixels else 0.0,
                "grad_mean_curvature": mean_curvature,
                "gradient_min":        params["gradient_min"],
                "gradient_max":        params["gradient_max"],
                "curvature_threshold": params["curvature_threshold"],
                "width":               image.width,
                "height":              image.height,
            }

        return await self._run_in_executor(_analyze_gradient)

    async def _analyze_edge_structure(
        self,
        image: PILImage.Image,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        def _analyze_edge_structure() -> Dict[str, Any]:
            import numpy as np
            import cv2

            luma = np.asarray(image.convert("L"), dtype=np.float32)
            dx = cv2.Sobel(luma, cv2.CV_32F, 1, 0, ksize=3)
            dy = cv2.Sobel(luma, cv2.CV_32F, 0, 1, ksize=3)
            gradient_magnitude = cv2.magnitude(dx, dy)

            edge_mask = gradient_magnitude >= params["edge_threshold"]
            edge_pixels = int(edge_mask.sum())
            total_pixels = luma.size

            # Orientation of each edge pixel in degrees, folded to [0, 180) so
            # vertical and horizontal strokes get a single bin regardless of
            # which side of the gradient points inward.
            orientation_degrees = np.degrees(np.arctan2(dy[edge_mask], dx[edge_mask])) % 180.0

            axis_aligned_pixels = 0
            orientation_entropy = 0.0

            if edge_pixels:
                near_horizontal = orientation_degrees <= params["axis_tolerance_degrees"]
                near_vertical = np.abs(orientation_degrees - 90.0) <= params["axis_tolerance_degrees"]
                near_horizontal_wrap = orientation_degrees >= 180.0 - params["axis_tolerance_degrees"]
                axis_aligned_pixels = int((near_horizontal | near_vertical | near_horizontal_wrap).sum())

                orientation_histogram, _ = np.histogram(orientation_degrees, bins=params["orientation_bins"], range=(0.0, 180.0))
                orientation_shares = orientation_histogram / edge_pixels

                with np.errstate(divide="ignore", invalid="ignore"):
                    orientation_entropy = float(-np.sum(np.where(orientation_shares > 0, orientation_shares * np.log2(orientation_shares), 0.0)))

            return {
                "edge_density":             edge_pixels / total_pixels if total_pixels else 0.0,
                "edge_pixels":              edge_pixels,
                "axis_edge_ratio":          axis_aligned_pixels / edge_pixels if edge_pixels else 0.0,
                "axis_aligned_pixels":      axis_aligned_pixels,
                "edge_orientation_entropy": orientation_entropy,
                "edge_threshold":           params["edge_threshold"],
                "axis_tolerance_degrees":   params["axis_tolerance_degrees"],
                "orientation_bins":         params["orientation_bins"],
                "width":                    image.width,
                "height":                   image.height,
            }

        return await self._run_in_executor(_analyze_edge_structure)

    async def _analyze_texture(
        self,
        image: PILImage.Image,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        def _analyze_texture() -> Dict[str, Any]:
            import numpy as np
            import cv2

            # medianBlur requires uint8 input; converting afterwards to float32 so
            # the high-pass residuals can go negative without wrapping.
            luma_uint8 = np.asarray(image.convert("L"), dtype=np.uint8)
            fine_blur   = cv2.medianBlur(luma_uint8, params["fine_kernel"]).astype(np.float32)
            mid_blur    = cv2.medianBlur(luma_uint8, params["mid_kernel"]).astype(np.float32)
            coarse_blur = cv2.medianBlur(luma_uint8, params["coarse_kernel"]).astype(np.float32)
            luma = luma_uint8.astype(np.float32)

            # Band-pass residuals at three scales. A rendered gradient keeps all
            # three near zero; photographic grain survives the fine blur; fabric
            # weave survives the mid blur; surface markings survive the coarse one.
            tex_fine   = np.abs(luma - fine_blur)
            tex_mid    = np.abs(fine_blur - mid_blur)
            tex_coarse = np.abs(mid_blur - coarse_blur)

            total_pixels = luma.size

            return {
                "tex_fine":         float(tex_fine.mean()) / 255.0 if total_pixels else 0.0,
                "tex_mid":          float(tex_mid.mean()) / 255.0 if total_pixels else 0.0,
                "tex_coarse":       float(tex_coarse.mean()) / 255.0 if total_pixels else 0.0,
                "detail_ratio":     float((tex_fine >= params["detail_threshold"]).mean()) if total_pixels else 0.0,
                "detail_threshold": params["detail_threshold"],
                "fine_kernel":      params["fine_kernel"],
                "mid_kernel":       params["mid_kernel"],
                "coarse_kernel":    params["coarse_kernel"],
                "width":            image.width,
                "height":           image.height,
            }

        return await self._run_in_executor(_analyze_texture)

    async def _analyze_lit_structure(
        self,
        image: PILImage.Image,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        def _analyze_lit_structure() -> Dict[str, Any]:
            import numpy as np
            import cv2

            luma_uint8 = np.asarray(image.convert("L"), dtype=np.uint8)
            luma = luma_uint8.astype(np.float32)
            total_pixels = luma_uint8.size

            peak_kernel = np.ones((params["peak_window"], params["peak_window"]), dtype=np.uint8)

            # A local maximum is a pixel whose value equals the maximum over the
            # peak_window neighbourhood; dilation gives that max for free.
            dilated = cv2.dilate(luma_uint8, peak_kernel)
            eroded  = cv2.erode(luma_uint8, peak_kernel)

            # Smoothness is a per-pixel comparison against a lightly blurred
            # version. The blur reads from a 3x3 neighbourhood so it has to run
            # on the full frame, but the |luma - blurred| residual is only
            # needed where lit_mask / ink_mask are true — extract those
            # positions before the subtraction to avoid a full-frame temporary.
            blurred = cv2.GaussianBlur(luma, (0, 0), sigmaX=1.0)

            lit_mask = luma_uint8 >= params["lit_threshold"]
            lit_pixels = int(lit_mask.sum())
            lit_peaks_pixels = int(((luma_uint8 == dilated) & lit_mask).sum())
            lit_smooth_pixels = int((np.abs(luma[lit_mask] - blurred[lit_mask]) <= params["smooth_tolerance"]).sum()) if lit_pixels else 0

            ink_mask = luma_uint8 <= params["ink_threshold"]
            ink_pixels = int(ink_mask.sum())
            ink_peaks_pixels = int(((luma_uint8 == eroded) & ink_mask).sum())
            ink_smooth_pixels = int((np.abs(luma[ink_mask] - blurred[ink_mask]) <= params["smooth_tolerance"]).sum()) if ink_pixels else 0

            return {
                "lit_ratio":        lit_pixels / total_pixels if total_pixels else 0.0,
                "lit_pixels":       lit_pixels,
                "lit_smooth":       lit_smooth_pixels / lit_pixels if lit_pixels else 0.0,
                "lit_peaks":        lit_peaks_pixels / lit_pixels if lit_pixels else 0.0,
                "ink_ratio":        ink_pixels / total_pixels if total_pixels else 0.0,
                "ink_pixels":       ink_pixels,
                "ink_smooth":       ink_smooth_pixels / ink_pixels if ink_pixels else 0.0,
                "ink_peaks":        ink_peaks_pixels / ink_pixels if ink_pixels else 0.0,
                "lit_threshold":    params["lit_threshold"],
                "ink_threshold":    params["ink_threshold"],
                "peak_window":      params["peak_window"],
                "smooth_tolerance": params["smooth_tolerance"],
                "width":            image.width,
                "height":           image.height,
            }

        return await self._run_in_executor(_analyze_lit_structure)

@register_image_analyzer_driver(ImageAnalyzerDriverType.OPENCV)
class OpenCvImageAnalyzerDriver(ImageAnalyzerDriver):
    def __init__(self, id: str, config: ImageAnalyzerComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [ "opencv-python", "numpy" ]

    async def _run(
        self,
        action: ImageAnalyzerActionConfig,
        context: ComponentActionContext,
    ) -> Any:
        return await OpenCvImageAnalyzerAction(action).run(context)
