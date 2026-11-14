from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, List, Dict, Any, Union, Tuple
from mindor.dsl.schema.component import ImageAnalyzerComponentConfig, ImageAnalyzerDriverType
from mindor.dsl.schema.action import ImageAnalyzerActionConfig, NativeImageAnalyzerMetric
from mindor.core.foundation.cancellation import CancellationToken
from ..base import ImageAnalyzerDriver, register_image_analyzer_driver
from ..base import ComponentActionContext
from .common import ImageAnalyzerAction

if TYPE_CHECKING:
    from PIL import Image as PILImage

class NativeImageAnalyzerAction(ImageAnalyzerAction):
    async def _resolve_params(self, metric: NativeImageAnalyzerMetric, context: ComponentActionContext) -> Dict[str, Any]:
        if metric == NativeImageAnalyzerMetric.BRIGHTNESS:
            return {}

        if metric == NativeImageAnalyzerMetric.CONTRAST:
            return {}

        if metric == NativeImageAnalyzerMetric.EXPOSURE:
            shadow_threshold    = await context.render_scalar(self.config.shadow_threshold, int)
            highlight_threshold = await context.render_scalar(self.config.highlight_threshold, int)

            return {
                "shadow_threshold":    shadow_threshold,
                "highlight_threshold": highlight_threshold,
            }

        if metric == NativeImageAnalyzerMetric.DARKNESS:
            dark_threshold     = await context.render_scalar(self.config.dark_threshold, int)
            block_size         = await context.render_scalar(self.config.block_size, int)
            flat_std_threshold = await context.render_scalar(self.config.flat_std_threshold, float)

            if not 0 <= dark_threshold <= 255:
                raise ValueError(f"'dark_threshold' must be between 0 and 255, got {dark_threshold}")

            if not 2 <= block_size <= 64:
                raise ValueError(f"'block_size' must be between 2 and 64, got {block_size}")

            if flat_std_threshold < 0.0:
                raise ValueError(f"'flat_std_threshold' must be non-negative, got {flat_std_threshold}")

            return {
                "dark_threshold":     dark_threshold,
                "block_size":         block_size,
                "flat_std_threshold": flat_std_threshold,
            }

        if metric == NativeImageAnalyzerMetric.SHARPNESS:
            blur_threshold = await context.render_scalar(self.config.blur_threshold, float)

            return {
                "blur_threshold": blur_threshold,
            }

        if metric == NativeImageAnalyzerMetric.NOISE:
            edge_quantile = await context.render_scalar(self.config.edge_quantile, float)

            if not 0.0 <= edge_quantile <= 1.0:
                raise ValueError(f"'edge_quantile' must be between 0.0 and 1.0, got {edge_quantile}")

            return {
                "edge_quantile": edge_quantile,
            }

        if metric == NativeImageAnalyzerMetric.FLAT_REGIONS:
            block_size    = await context.render_scalar(self.config.block_size, int)
            std_threshold = await context.render_scalar(self.config.std_threshold, float)

            if not 2 <= block_size <= 64:
                raise ValueError(f"'block_size' must be between 2 and 64, got {block_size}")

            if std_threshold < 0.0:
                raise ValueError(f"'std_threshold' must be non-negative, got {std_threshold}")

            return {
                "block_size":    block_size,
                "std_threshold": std_threshold,
            }

        if metric == NativeImageAnalyzerMetric.PALETTE:
            bits_per_channel = await context.render_scalar(self.config.bits_per_channel, int)
            coverage         = await context.render_scalar(self.config.coverage, float)
            top_k            = await context.render_scalar(self.config.top_k, int)

            if not 1 <= bits_per_channel <= 8:
                raise ValueError(f"'bits_per_channel' must be between 1 and 8, got {bits_per_channel}")

            if not 0.0 < coverage <= 1.0:
                raise ValueError(f"'coverage' must be in (0.0, 1.0], got {coverage}")

            if top_k < 0:
                raise ValueError(f"'top_k' must be non-negative, got {top_k}")

            return {
                "bits_per_channel": bits_per_channel,
                "coverage":         coverage,
                "top_k":            top_k,
            }

        if metric == NativeImageAnalyzerMetric.COLOR_VARIETY:
            vivid_saturation  = await context.render_scalar(self.config.vivid_saturation, float)
            vivid_value       = await context.render_scalar(self.config.vivid_value, float)
            hue_bins          = await context.render_scalar(self.config.hue_bins, int)
            hue_bin_min_share = await context.render_scalar(self.config.hue_bin_min_share, float)

            if not 0.0 <= vivid_saturation <= 1.0:
                raise ValueError(f"'vivid_saturation' must be between 0.0 and 1.0, got {vivid_saturation}")

            if not 0.0 <= vivid_value <= 1.0:
                raise ValueError(f"'vivid_value' must be between 0.0 and 1.0, got {vivid_value}")

            if not 1 <= hue_bins <= 36:
                raise ValueError(f"'hue_bins' must be between 1 and 36, got {hue_bins}")

            if not 0.0 <= hue_bin_min_share <= 1.0:
                raise ValueError(f"'hue_bin_min_share' must be between 0.0 and 1.0, got {hue_bin_min_share}")

            return {
                "vivid_saturation":  vivid_saturation,
                "vivid_value":       vivid_value,
                "hue_bins":          hue_bins,
                "hue_bin_min_share": hue_bin_min_share,
            }

        raise ValueError(f"Unsupported image metric: {metric}")

    async def _analyze(
        self,
        metric: NativeImageAnalyzerMetric,
        image: PILImage.Image,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        if metric == NativeImageAnalyzerMetric.BRIGHTNESS:
            return await self._analyze_brightness(image, params, cancellation_token)

        if metric == NativeImageAnalyzerMetric.CONTRAST:
            return await self._analyze_contrast(image, params, cancellation_token)

        if metric == NativeImageAnalyzerMetric.EXPOSURE:
            return await self._analyze_exposure(image, params, cancellation_token)

        if metric == NativeImageAnalyzerMetric.DARKNESS:
            return await self._analyze_darkness(image, params, cancellation_token)

        if metric == NativeImageAnalyzerMetric.SHARPNESS:
            return await self._analyze_sharpness(image, params, cancellation_token)

        if metric == NativeImageAnalyzerMetric.NOISE:
            return await self._analyze_noise(image, params, cancellation_token)

        if metric == NativeImageAnalyzerMetric.FLAT_REGIONS:
            return await self._analyze_flat_regions(image, params, cancellation_token)

        if metric == NativeImageAnalyzerMetric.PALETTE:
            return await self._analyze_palette(image, params, cancellation_token)

        if metric == NativeImageAnalyzerMetric.COLOR_VARIETY:
            return await self._analyze_color_variety(image, params, cancellation_token)

        raise ValueError(f"Unsupported image metric: {metric}")

    async def _analyze_brightness(
        self,
        image: PILImage.Image,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        def _analyze_brightness() -> Dict[str, Any]:
            import numpy as np

            # Pillow's `convert("L")` applies ITU-R BT.601 luma coefficients
            # (0.299 R + 0.587 G + 0.114 B), which every metric below assumes.
            luma = np.asarray(image.convert("L"), dtype=np.float32)

            return {
                "mean_brightness": float(luma.mean()),
                "min_brightness":  float(luma.min()),
                "max_brightness":  float(luma.max()),
                "std_brightness":  float(luma.std()),
                "width":           image.width,
                "height":          image.height,
            }

        return await self._run_in_executor(_analyze_brightness)

    async def _analyze_contrast(
        self,
        image: PILImage.Image,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        def _analyze_contrast() -> Dict[str, Any]:
            import numpy as np

            luma = np.asarray(image.convert("L"), dtype=np.float32)

            # RMS contrast: standard deviation of pixel luma — a scale-invariant
            # measure that beats naive (max-min) for photographic images where a
            # few outlier pixels would otherwise dominate.
            rms_contrast = float(luma.std())

            # Michelson contrast on percentile-clipped extremes, so a single hot
            # pixel doesn't push the number to its ceiling.
            low = float(np.percentile(luma, 1))
            high = float(np.percentile(luma, 99))
            denominator = high + low
            michelson_contrast = (high - low) / denominator if denominator else 0.0

            return {
                "rms_contrast":       rms_contrast,
                "michelson_contrast": michelson_contrast,
                "luma_percentile_1":  low,
                "luma_percentile_99": high,
                "width":              image.width,
                "height":             image.height,
            }

        return await self._run_in_executor(_analyze_contrast)

    async def _analyze_exposure(
        self,
        image: PILImage.Image,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        def _analyze_exposure() -> Dict[str, Any]:
            import numpy as np

            shadow_threshold    = params["shadow_threshold"]
            highlight_threshold = params["highlight_threshold"]

            luma = np.asarray(image.convert("L"), dtype=np.float32)
            total_pixels = luma.size

            shadow_clipped = int((luma <= shadow_threshold).sum())
            highlight_clipped = int((luma >= highlight_threshold).sum())

            return {
                "shadow_threshold":         shadow_threshold,
                "highlight_threshold":      highlight_threshold,
                "shadow_clipped_pixels":    shadow_clipped,
                "highlight_clipped_pixels": highlight_clipped,
                "shadow_clipped_ratio":     shadow_clipped / total_pixels if total_pixels else 0.0,
                "highlight_clipped_ratio":  highlight_clipped / total_pixels if total_pixels else 0.0,
                "mean_brightness":          float(luma.mean()),
                "width":                    image.width,
                "height":                   image.height,
            }

        return await self._run_in_executor(_analyze_exposure)

    async def _analyze_darkness(
        self,
        image: PILImage.Image,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        def _analyze_darkness() -> Dict[str, Any]:
            import numpy as np

            luma = np.asarray(image.convert("L"), dtype=np.float32)
            dark_mask = luma <= params["dark_threshold"]
            dark_pixels = int(dark_mask.sum())
            total_pixels = luma.size

            # Block-level flatness restricted to mostly-dark blocks: a rendered
            # dark background holds zero std inside each block, while night
            # footage keeps sensor grain and reports a lower dark_flat ratio.
            height, width = luma.shape
            trimmed_height = (height // params["block_size"]) * params["block_size"]
            trimmed_width = (width // params["block_size"]) * params["block_size"]
            dark_flat = 0.0
            dark_blocks = 0

            if trimmed_height and trimmed_width:
                blocks = luma[:trimmed_height, :trimmed_width].reshape(
                    trimmed_height // params["block_size"], params["block_size"],
                    trimmed_width // params["block_size"], params["block_size"],
                ).transpose(0, 2, 1, 3)
                dark_mask_blocks = dark_mask[:trimmed_height, :trimmed_width].reshape(
                    trimmed_height // params["block_size"], params["block_size"],
                    trimmed_width // params["block_size"], params["block_size"],
                ).transpose(0, 2, 1, 3)

                block_dark_share = dark_mask_blocks.reshape(blocks.shape[0], blocks.shape[1], -1).mean(axis=-1)
                block_std = blocks.reshape(blocks.shape[0], blocks.shape[1], -1).std(axis=-1)

                mostly_dark = block_dark_share >= 0.5
                dark_blocks = int(mostly_dark.sum())

                if dark_blocks:
                    dark_flat = float(((block_std < params["flat_std_threshold"]) & mostly_dark).sum() / dark_blocks)

            return {
                "dark_ratio":         dark_pixels / total_pixels if total_pixels else 0.0,
                "dark_std":           float(luma[dark_mask].std()) if dark_pixels else 0.0,
                "dark_flat":          dark_flat,
                "dark_pixels":        dark_pixels,
                "dark_blocks":        dark_blocks,
                "dark_threshold":     params["dark_threshold"],
                "block_size":         params["block_size"],
                "flat_std_threshold": params["flat_std_threshold"],
                "width":              image.width,
                "height":             image.height,
            }

        return await self._run_in_executor(_analyze_darkness)

    async def _analyze_sharpness(
        self,
        image: PILImage.Image,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        def _analyze_sharpness() -> Dict[str, Any]:
            import numpy as np

            luma = np.asarray(image.convert("L"), dtype=np.float32)

            # Laplacian variance is the standard cheap blur detector: apply a 3x3
            # Laplacian kernel, take the variance of the response. Low variance
            # means the image has little high-frequency detail, i.e. it's blurred
            # or out of focus. The classic threshold is ~100 for 8-bit imagery,
            # but the "right" value depends on content.
            laplacian = np.zeros_like(luma, dtype=np.float32)
            laplacian[1:-1, 1:-1] = (
                -4.0 * luma[1:-1, 1:-1]
                + luma[:-2, 1:-1]
                + luma[2:, 1:-1]
                + luma[1:-1, :-2]
                + luma[1:-1, 2:]
            )
            variance = float(laplacian.var())

            return {
                "laplacian_variance": variance,
                "blur_threshold":     params["blur_threshold"],
                "is_blurry":          variance < params["blur_threshold"],
                "width":              image.width,
                "height":             image.height,
            }

        return await self._run_in_executor(_analyze_sharpness)

    async def _analyze_noise(
        self,
        image: PILImage.Image,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        def _analyze_noise() -> Dict[str, Any]:
            import numpy as np

            luma = np.asarray(image.convert("L"), dtype=np.float32)

            # Immerkær (1996) fast noise estimate: the 3x3 mask
            # [[1,-2,1],[-2,4,-2],[1,-2,1]] annihilates smooth regions and
            # quadratic ramps, so the convolution response is dominated by
            # noise. Edges also survive the mask, so pixels above a
            # gradient-magnitude quantile are excluded from the mean.
            laplacian_response = np.abs(
                4.0 * luma[1:-1, 1:-1]
                - 2.0 * (luma[:-2, 1:-1] + luma[2:, 1:-1] + luma[1:-1, :-2] + luma[1:-1, 2:])
                + luma[:-2, :-2] + luma[:-2, 2:] + luma[2:, :-2] + luma[2:, 2:]
            )

            dx = luma[1:-1, 2:] - luma[1:-1, :-2]
            dy = luma[2:, 1:-1] - luma[:-2, 1:-1]
            gradient_magnitude = np.sqrt(dx * dx + dy * dy)

            if gradient_magnitude.size:
                edge_cutoff = float(np.quantile(gradient_magnitude, params["edge_quantile"]))
                non_edge = gradient_magnitude <= edge_cutoff
                non_edge_pixels = int(non_edge.sum())
                mean_response = float(laplacian_response[non_edge].mean()) if non_edge_pixels else float(laplacian_response.mean())
            else:
                edge_cutoff = 0.0
                non_edge_pixels = 0
                mean_response = 0.0

            noise_sigma = (np.sqrt(np.pi / 2.0) / 6.0) * mean_response
            interior_pixels = laplacian_response.size

            return {
                "noise_sigma":     float(noise_sigma),
                "edge_quantile":   params["edge_quantile"],
                "edge_cutoff":     edge_cutoff,
                "non_edge_pixels": non_edge_pixels,
                "non_edge_ratio":  non_edge_pixels / interior_pixels if interior_pixels else 0.0,
                "width":           image.width,
                "height":          image.height,
            }

        return await self._run_in_executor(_analyze_noise)

    async def _analyze_flat_regions(
        self,
        image: PILImage.Image,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        def _analyze_flat_regions() -> Dict[str, Any]:
            import numpy as np

            luma = np.asarray(image.convert("L"), dtype=np.float32)
            height, width = luma.shape

            # Trim to a block-aligned crop; padding would create artificial flat
            # regions at the edges and inflate the ratio.
            trimmed_height = (height // params["block_size"]) * params["block_size"]
            trimmed_width = (width // params["block_size"]) * params["block_size"]

            if trimmed_height == 0 or trimmed_width == 0:
                return {
                    "flat_ratio":    0.0,
                    "flat_blocks":   0,
                    "total_blocks":  0,
                    "block_size":    params["block_size"],
                    "std_threshold": params["std_threshold"],
                    "width":         image.width,
                    "height":        image.height,
                }

            blocks = luma[:trimmed_height, :trimmed_width].reshape(
                trimmed_height // params["block_size"], params["block_size"],
                trimmed_width // params["block_size"], params["block_size"],
            ).transpose(0, 2, 1, 3)

            block_std = blocks.reshape(blocks.shape[0], blocks.shape[1], -1).std(axis=-1)

            total_blocks = int(block_std.size)
            flat_blocks = int((block_std < params["std_threshold"]).sum())

            return {
                "flat_ratio":     flat_blocks / total_blocks if total_blocks else 0.0,
                "flat_blocks":    flat_blocks,
                "total_blocks":   total_blocks,
                "block_size":     params["block_size"],
                "std_threshold":  params["std_threshold"],
                "mean_block_std": float(block_std.mean()) if total_blocks else 0.0,
                "width":          image.width,
                "height":         image.height,
            }

        return await self._run_in_executor(_analyze_flat_regions)

    async def _analyze_palette(
        self,
        image: PILImage.Image,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        def _analyze_palette() -> Dict[str, Any]:
            import numpy as np

            shift = 8 - params["bits_per_channel"]
            channel_mask = (1 << params["bits_per_channel"]) - 1
            # Centre of the quantization bucket, added back so a reported RGB sits
            # mid-bucket rather than at the floor (matters at coarse bit depths).
            bucket_centre = 1 << (shift - 1) if shift > 0 else 0

            quantized = np.asarray(image.convert("RGB"), dtype=np.uint8).reshape(-1, 3) >> shift
            keys = (quantized[:, 0].astype(np.int64) << (params["bits_per_channel"] * 2)) \
                 | (quantized[:, 1].astype(np.int64) << params["bits_per_channel"]) \
                 |  quantized[:, 2].astype(np.int64)

            total_pixels = keys.size
            unique_keys, counts = np.unique(keys, return_counts=True)

            order = np.argsort(-counts)
            counts = counts[order]
            unique_keys = unique_keys[order]

            cumulative = np.cumsum(counts)
            palette_size = int(min(np.searchsorted(cumulative, params["coverage"] * total_pixels) + 1, counts.size)) if total_pixels else 0

            probabilities = counts / total_pixels if total_pixels else counts

            with np.errstate(divide="ignore", invalid="ignore"):
                palette_entropy = float(-np.sum(np.where(probabilities > 0, probabilities * np.log2(probabilities), 0.0)))

            dominant_colors: List[Dict[str, Any]] = []

            for index in range(min(params["top_k"], unique_keys.size)):
                key = int(unique_keys[index])
                r = ((key >> (params["bits_per_channel"] * 2)) & channel_mask) << shift
                g = ((key >> params["bits_per_channel"]) & channel_mask) << shift
                b = (key & channel_mask) << shift

                dominant_colors.append({
                    "rgb":   [r + bucket_centre, g + bucket_centre, b + bucket_centre],
                    "share": float(counts[index] / total_pixels) if total_pixels else 0.0,
                })

            return {
                "bits_per_channel": params["bits_per_channel"],
                "coverage":         params["coverage"],
                "palette_size":     palette_size,
                "unique_colors":    int(unique_keys.size),
                "palette_entropy":  palette_entropy,
                "dominant_colors":  dominant_colors,
                "width":            image.width,
                "height":           image.height,
            }

        return await self._run_in_executor(_analyze_palette)

    async def _analyze_color_variety(
        self,
        image: PILImage.Image,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        def _analyze_color_variety() -> Dict[str, Any]:
            import numpy as np

            rgb = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
            red, green, blue = rgb[..., 0], rgb[..., 1], rgb[..., 2]

            value = np.maximum(np.maximum(red, green), blue)
            chroma = value - np.minimum(np.minimum(red, green), blue)

            with np.errstate(divide="ignore", invalid="ignore"):
                hue = np.zeros_like(value)
                red_dominant   = (value == red)   & (chroma > 0)
                green_dominant = (value == green) & (chroma > 0) & ~red_dominant
                blue_dominant  = (value == blue)  & (chroma > 0) & ~red_dominant & ~green_dominant
                hue[red_dominant]   = ((green[red_dominant]   - blue[red_dominant])   / chroma[red_dominant])   % 6.0
                hue[green_dominant] = ((blue[green_dominant]  - red[green_dominant])  / chroma[green_dominant]) + 2.0
                hue[blue_dominant]  = ((red[blue_dominant]    - green[blue_dominant]) / chroma[blue_dominant])  + 4.0
            hue = hue / 6.0

            saturation = np.where(value > 0, chroma / np.where(value == 0, 1.0, value), 0.0)

            vivid_mask = (saturation >= params["vivid_saturation"]) & (value >= params["vivid_value"])
            vivid_pixels = int(vivid_mask.sum())
            total_pixels = value.size

            hue_histogram, _ = np.histogram(hue[vivid_mask], bins=params["hue_bins"], range=(0.0, 1.0))
            hue_shares = (hue_histogram / vivid_pixels) if vivid_pixels else hue_histogram.astype(np.float32)

            return {
                "vivid_ratio":      vivid_pixels / total_pixels if total_pixels else 0.0,
                "vivid_pixels":     vivid_pixels,
                "sat_p90":          float(np.quantile(saturation, 0.9)) if total_pixels else 0.0,
                "hue_bands":        int((hue_shares >= params["hue_bin_min_share"]).sum()),
                "hue_histogram":    [float(x) for x in hue_shares.tolist()],
                "vivid_saturation": params["vivid_saturation"],
                "vivid_value":      params["vivid_value"],
                "width":            image.width,
                "height":           image.height,
            }

        return await self._run_in_executor(_analyze_color_variety)

@register_image_analyzer_driver(ImageAnalyzerDriverType.NATIVE)
class NativeImageAnalyzerService(ImageAnalyzerDriver):
    def __init__(self, id: str, config: ImageAnalyzerComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [ "numpy" ]

    async def _run(
        self,
        action: ImageAnalyzerActionConfig,
        context: ComponentActionContext,
    ) -> Any:
        return await NativeImageAnalyzerAction(action).run(context)
