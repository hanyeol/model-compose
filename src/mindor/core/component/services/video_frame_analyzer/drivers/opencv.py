from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, List, Dict, Any, Union, Tuple
from mindor.dsl.schema.component import VideoFrameAnalyzerComponentConfig, VideoFrameAnalyzerDriverType
from mindor.dsl.schema.action import VideoFrameAnalyzerActionConfig, OpenCvVideoFrameAnalyzerMetric
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.foundation.cancellation import CancellationToken
from ..base import VideoFrameAnalyzerDriver, register_video_frame_analyzer_driver
from ..base import ComponentActionContext
from .common import VideoFrameAnalyzerAction

if TYPE_CHECKING:
    from PIL import Image as PILImage

# 24 / 25 fps content transcoded to 30 fps leaves a 4- or 5-frame duplicate
# pattern; 24 -> 60 leaves a 1- or 2-frame pattern. Anything outside this
# table is reported as "irregular" rather than a known pulldown.
_PULLDOWN_TABLE = (
    ("24->30", range(4, 6)),
    ("25->30", range(5, 7)),
    ("24->60", range(1, 3)),
)

class OpenCvVideoFrameAnalyzerAction(VideoFrameAnalyzerAction):
    async def _resolve_params(self, metric: OpenCvVideoFrameAnalyzerMetric, context: ComponentActionContext) -> Dict[str, Any]:
        if metric == OpenCvVideoFrameAnalyzerMetric.MOVING_PAIRS:
            downsample_width       = await context.render_scalar(self.config.downsample_width, int)
            change_threshold       = await context.render_scalar(self.config.change_threshold, float)
            moving_share_threshold = await context.render_scalar(self.config.moving_share_threshold, float)

            if not 16 <= downsample_width <= 4096:
                raise ValueError(f"'downsample_width' must be between 16 and 4096, got {downsample_width}")

            if change_threshold < 0.0:
                raise ValueError(f"'change_threshold' must be non-negative, got {change_threshold}")

            if not 0.0 <= moving_share_threshold <= 1.0:
                raise ValueError(f"'moving_share_threshold' must be between 0.0 and 1.0, got {moving_share_threshold}")

            return {
                "downsample_width":       downsample_width,
                "change_threshold":       change_threshold,
                "moving_share_threshold": moving_share_threshold,
            }

        if metric == OpenCvVideoFrameAnalyzerMetric.DUPLICATE:
            downsample_width    = await context.render_scalar(self.config.downsample_width, int)
            duplicate_threshold = await context.render_scalar(self.config.duplicate_threshold, float)
            max_period          = await context.render_scalar(self.config.max_period, int)

            if not 16 <= downsample_width <= 4096:
                raise ValueError(f"'downsample_width' must be between 16 and 4096, got {downsample_width}")

            if duplicate_threshold < 0.0:
                raise ValueError(f"'duplicate_threshold' must be non-negative, got {duplicate_threshold}")

            if not 2 <= max_period <= 32:
                raise ValueError(f"'max_period' must be between 2 and 32, got {max_period}")

            return {
                "downsample_width":    downsample_width,
                "duplicate_threshold": duplicate_threshold,
                "max_period":          max_period,
            }

        if metric == OpenCvVideoFrameAnalyzerMetric.SHARPNESS:
            downsample_width = await context.render_scalar(self.config.downsample_width, int)
            max_period       = await context.render_scalar(self.config.max_period, int)

            if not 16 <= downsample_width <= 4096:
                raise ValueError(f"'downsample_width' must be between 16 and 4096, got {downsample_width}")

            if not 2 <= max_period <= 32:
                raise ValueError(f"'max_period' must be between 2 and 32, got {max_period}")

            return {
                "downsample_width": downsample_width,
                "max_period":       max_period,
            }

        if metric == OpenCvVideoFrameAnalyzerMetric.PICTURE_BOX:
            downsample_width       = await context.render_scalar(self.config.downsample_width, int)
            sample_count           = await context.render_scalar(self.config.sample_count, int)
            lit_threshold          = await context.render_scalar(self.config.lit_threshold, float)
            picture_lit_share      = await context.render_scalar(self.config.picture_lit_share, float)
            bar_dark_share         = await context.render_scalar(self.config.bar_dark_share, float)
            bar_min_share          = await context.render_scalar(self.config.bar_min_share, float)
            picture_edge_lit_share = await context.render_scalar(self.config.picture_edge_lit_share, float)
            min_picture_fraction   = await context.render_scalar(self.config.min_picture_fraction, float)

            if not 64 <= downsample_width <= 4096:
                raise ValueError(f"'downsample_width' must be between 64 and 4096, got {downsample_width}")

            if not 4 <= sample_count <= 256:
                raise ValueError(f"'sample_count' must be between 4 and 256, got {sample_count}")

            if not 0.0 <= lit_threshold <= 255.0:
                raise ValueError(f"'lit_threshold' must be between 0.0 and 255.0, got {lit_threshold}")

            if not 0.0 <= picture_lit_share <= 1.0:
                raise ValueError(f"'picture_lit_share' must be between 0.0 and 1.0, got {picture_lit_share}")

            if not 0.0 <= bar_dark_share <= 1.0:
                raise ValueError(f"'bar_dark_share' must be between 0.0 and 1.0, got {bar_dark_share}")

            if not 0.0 <= bar_min_share <= 1.0:
                raise ValueError(f"'bar_min_share' must be between 0.0 and 1.0, got {bar_min_share}")

            if not 0.0 <= picture_edge_lit_share <= 1.0:
                raise ValueError(f"'picture_edge_lit_share' must be between 0.0 and 1.0, got {picture_edge_lit_share}")

            if not 0.0 < min_picture_fraction <= 1.0:
                raise ValueError(f"'min_picture_fraction' must be in (0.0, 1.0], got {min_picture_fraction}")

            return {
                "downsample_width":       downsample_width,
                "sample_count":           sample_count,
                "lit_threshold":          lit_threshold,
                "picture_lit_share":      picture_lit_share,
                "bar_dark_share":         bar_dark_share,
                "bar_min_share":          bar_min_share,
                "picture_edge_lit_share": picture_edge_lit_share,
                "min_picture_fraction":   min_picture_fraction,
            }

        if metric == OpenCvVideoFrameAnalyzerMetric.PALETTE:
            downsample_width = await context.render_scalar(self.config.downsample_width, int)
            sample_count     = await context.render_scalar(self.config.sample_count, int)
            max_colors      = await context.render_scalar(self.config.max_colors, int)
            min_share        = await context.render_scalar(self.config.min_share, float)

            if not 16 <= downsample_width <= 4096:
                raise ValueError(f"'downsample_width' must be between 16 and 4096, got {downsample_width}")

            if not 1 <= sample_count <= 256:
                raise ValueError(f"'sample_count' must be between 1 and 256, got {sample_count}")

            if not 1 <= max_colors <= 32:
                raise ValueError(f"'max_colors' must be between 1 and 32, got {max_colors}")

            if not 0.0 <= min_share <= 1.0:
                raise ValueError(f"'min_share' must be between 0.0 and 1.0, got {min_share}")

            return {
                "downsample_width": downsample_width,
                "sample_count":     sample_count,
                "max_colors":      max_colors,
                "min_share":        min_share,
            }

        raise ValueError(f"Unsupported video frame metric: {metric}")

    async def _analyze(
        self,
        metric: OpenCvVideoFrameAnalyzerMetric,
        frames: ImageArrayValue,
        frame_rate: Optional[float],
        streaming: bool,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        if metric == OpenCvVideoFrameAnalyzerMetric.MOVING_PAIRS:
            return await self._analyze_moving_pairs(frames, frame_rate, params, cancellation_token)

        if metric == OpenCvVideoFrameAnalyzerMetric.DUPLICATE:
            return await self._analyze_duplicate(frames, frame_rate, params, cancellation_token)

        if metric == OpenCvVideoFrameAnalyzerMetric.SHARPNESS:
            return await self._analyze_sharpness(frames, frame_rate, params, cancellation_token)

        if metric == OpenCvVideoFrameAnalyzerMetric.PICTURE_BOX:
            return await self._analyze_picture_box(frames, frame_rate, params, cancellation_token)

        if metric == OpenCvVideoFrameAnalyzerMetric.PALETTE:
            return await self._analyze_palette(frames, frame_rate, params, cancellation_token)

        raise ValueError(f"Unsupported video frame metric: {metric}")

    async def _analyze_moving_pairs(
        self,
        frames: ImageArrayValue,
        frame_rate: Optional[float],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        collected = await frames.collect()

        def _analyze_moving_pairs() -> Dict[str, Any]:
            import numpy as np
            import cv2

            moving_pixel_shares: List[float] = []
            previous_luma = None

            for frame in collected:
                luma = self._luma_thumbnail(frame, params["downsample_width"])

                if previous_luma is not None:
                    changed_pixels = cv2.absdiff(luma, previous_luma) >= params["change_threshold"]
                    moving_pixel_shares.append(float(changed_pixels.mean()))

                previous_luma = luma

            pair_count = len(moving_pixel_shares)

            if pair_count == 0:
                return {
                    "moving_pair_ratio":        0.0,
                    "moving_pair_count":        0,
                    "pair_count":               0,
                    "mean_changed_pixel_share": 0.0,
                    "max_changed_pixel_share":  0.0,
                    "change_threshold":         params["change_threshold"],
                    "moving_share_threshold":   params["moving_share_threshold"],
                    "frame_count":              len(collected),
                    "frame_rate":               frame_rate,
                    "downsample_width":         params["downsample_width"],
                }

            moving_pixel_shares = np.asarray(moving_pixel_shares, dtype=np.float32)
            moving_pair_count = int((moving_pixel_shares >= params["moving_share_threshold"]).sum())

            return {
                "moving_pair_ratio":        moving_pair_count / pair_count,
                "moving_pair_count":        moving_pair_count,
                "pair_count":               pair_count,
                "mean_changed_pixel_share": float(moving_pixel_shares.mean()),
                "max_changed_pixel_share":  float(moving_pixel_shares.max()),
                "change_threshold":         params["change_threshold"],
                "moving_share_threshold":   params["moving_share_threshold"],
                "frame_count":              len(collected),
                "frame_rate":               frame_rate,
                "downsample_width":         params["downsample_width"],
            }

        return await self._run_in_executor(_analyze_moving_pairs)

    async def _analyze_duplicate(
        self,
        frames: ImageArrayValue,
        frame_rate: Optional[float],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        collected = await frames.collect()

        def _analyze_duplicate() -> Dict[str, Any]:
            import numpy as np
            import cv2

            # For each adjacent pair, 1 = duplicate / 0 = different. Autocorrelation
            # of this binary signal reveals pulldown cadence (e.g. 24 -> 30 fps
            # repeats every 5th frame, so the duplicate mask has a period-5 peak).
            duplicate_mask: List[int] = []
            previous_luma = None

            for frame in collected:
                luma = self._luma_thumbnail(frame, params["downsample_width"])

                if previous_luma is not None:
                    duplicate_mask.append(int(float(cv2.absdiff(luma, previous_luma).mean()) < params["duplicate_threshold"]))

                previous_luma = luma

            pair_count = len(duplicate_mask)
            if pair_count == 0:
                return {
                    "dup_ratio":           0.0,
                    "dup_count":           0,
                    "pair_count":          0,
                    "dup_period":          None,
                    "dup_regularity":      0.0,
                    "pulldown":            None,
                    "duplicate_threshold": params["duplicate_threshold"],
                    "max_period":          params["max_period"],
                    "frame_count":         len(collected),
                    "frame_rate":          frame_rate,
                    "downsample_width":    params["downsample_width"],
                }

            duplicate_mask = np.asarray(duplicate_mask, dtype=np.float32)
            dup_count = int(duplicate_mask.sum())

            # Autocorrelation of the zero-mean duplicate mask. Lag k = how many
            # frames apart two duplicates sit. The best lag with the strongest
            # peak is the pulldown period.
            if dup_count >= 2:
                dup_period, dup_regularity = self._strongest_period(duplicate_mask, params["max_period"])
            else:
                dup_period, dup_regularity = None, 0.0

            pulldown = self._classify_pulldown(dup_period, dup_count / pair_count) if dup_period else None

            return {
                "dup_ratio":           dup_count / pair_count,
                "dup_count":           dup_count,
                "pair_count":          pair_count,
                "dup_period":          dup_period,
                "dup_regularity":      dup_regularity,
                "pulldown":            pulldown,
                "duplicate_threshold": params["duplicate_threshold"],
                "max_period":          params["max_period"],
                "frame_count":         len(collected),
                "frame_rate":          frame_rate,
                "downsample_width":    params["downsample_width"],
            }

        return await self._run_in_executor(_analyze_duplicate)

    async def _analyze_sharpness(
        self,
        frames: ImageArrayValue,
        frame_rate: Optional[float],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        collected = await frames.collect()

        def _analyze_sharpness() -> Dict[str, Any]:
            import numpy as np
            import cv2

            # Laplacian variance per frame as a sharpness proxy. Frame
            # interpolation introduces a periodic sharpness dip (the synthetic
            # frames are softer than the originals), which autocorrelation
            # exposes as a short-lag peak.
            sharpness_series: List[float] = []

            for frame in collected:
                luma = self._luma_thumbnail(frame, params["downsample_width"])
                laplacian = cv2.Laplacian(luma, cv2.CV_32F)
                sharpness_series.append(float(laplacian.var()))

            frame_count = len(sharpness_series)

            if frame_count < 2:
                return {
                    "sharpness_mean":   0.0,
                    "sharpness_std":    0.0,
                    "sharp_alt":        0.0,
                    "sharp_period":     None,
                    "sharp_period_ac":  0.0,
                    "frame_count":      frame_count,
                    "frame_rate":       frame_rate,
                    "max_period":       params["max_period"],
                    "downsample_width": params["downsample_width"],
                }

            sharpness_series = np.asarray(sharpness_series, dtype=np.float32)
            sharpness_mean = float(sharpness_series.mean())

            # `sharp_alt` is the share of adjacent sharpness pairs that dip or
            # peak — a proxy for "sharpness oscillates between frames".
            sharpness_diff = np.diff(sharpness_series)
            sign_flips = int(((sharpness_diff[:-1] * sharpness_diff[1:]) < 0).sum()) if len(sharpness_diff) >= 2 else 0
            sharp_alt = sign_flips / (len(sharpness_diff) - 1) if len(sharpness_diff) >= 2 else 0.0

            sharp_period, sharp_period_ac = self._strongest_period(sharpness_series, params["max_period"])

            return {
                "sharpness_mean":   sharpness_mean,
                "sharpness_std":    float(sharpness_series.std()),
                "sharp_alt":        sharp_alt,
                "sharp_period":     sharp_period,
                "sharp_period_ac":  sharp_period_ac,
                "frame_count":      frame_count,
                "frame_rate":       frame_rate,
                "max_period":       params["max_period"],
                "downsample_width": params["downsample_width"],
            }

        return await self._run_in_executor(_analyze_sharpness)

    async def _analyze_picture_box(
        self,
        frames: ImageArrayValue,
        frame_rate: Optional[float],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        collected = await frames.collect()

        def _analyze_picture_box() -> Dict[str, Any]:
            import numpy as np
            import cv2

            # Evenly sampled frames stacked as a (N, H, W) "lit" mask;
            # a pixel lit in any sample makes its row / column count as
            # inside the picture. Dark bars that stay dark across every
            # sample remain dark here and get cropped away.
            if not collected:
                return {
                    "detected":         False,
                    "box":              None,
                    "aspect":           None,
                    "bar_share":        None,
                    "frame_count":      0,
                    "sample_count":     0,
                    "frame_rate":       frame_rate,
                    "downsample_width": params["downsample_width"],
                }

            sample_indices = np.unique(np.linspace(0, len(collected) - 1, num=min(len(collected), params["sample_count"])).astype(int))
            samples = [ self._grayscale_thumbnail(collected[int(index)], params["downsample_width"]) for index in sample_indices ]
            stack   = np.stack(samples)
            height, width = stack.shape[1:]

            if height < 4 or width < 4:
                return {
                    "detected":         False,
                    "box":              None,
                    "aspect":           None,
                    "bar_share":        None,
                    "frame_count":      len(collected),
                    "sample_count":     len(samples),
                    "frame_rate":       frame_rate,
                    "downsample_width": params["downsample_width"],
                }

            lit = stack > params["lit_threshold"]

            # Alternate row / column reductions twice so a picture that
            # fills only part of the height picks up a tighter column
            # box (and vice versa) — one pass would miss a vertical
            # column of bars when the picture also has horizontal bars.
            y0, y1, x0, x1 = 0, height, 0, width

            for _ in range(2):
                row_span = self._picture_run(
                    lit[:, :, x0:x1].mean(axis=2).max(axis=0) > params["picture_lit_share"],
                    max(1, height // 50),
                )

                if row_span is None:
                    return self._empty_picture_box_result(collected, samples, frame_rate, params)

                y0, y1 = row_span
                col_span = self._picture_run(
                    lit[:, y0:y1, :].mean(axis=1).max(axis=0) > params["picture_lit_share"],
                    max(1, width // 50),
                )

                if col_span is None:
                    return self._empty_picture_box_result(collected, samples, frame_rate, params)

                x0, x1 = col_span

            row_lit_share         = lit[:, :, x0:x1].mean(axis=2).max(axis=0)
            col_lit_share         = lit[:, y0:y1, :].mean(axis=1).max(axis=0)
            outside_row_lit_share = np.concatenate([row_lit_share[:y0], row_lit_share[y1:]])
            outside_col_lit_share = np.concatenate([col_lit_share[:x0], col_lit_share[x1:]])
            bar_share_rows        = (y0 + height - y1) / height
            bar_share_cols        = (x0 + width  - x1) / width

            row_bars_ok = (
                bar_share_rows >= params["bar_min_share"]
                and (not len(outside_row_lit_share) or float(np.median(outside_row_lit_share)) < params["bar_dark_share"])
                and min(row_lit_share[y0], row_lit_share[y1 - 1]) > params["picture_edge_lit_share"]
            )
            col_bars_ok = (
                bar_share_cols >= params["bar_min_share"]
                and (not len(outside_col_lit_share) or float(np.median(outside_col_lit_share)) < params["bar_dark_share"])
                and min(col_lit_share[x0], col_lit_share[x1 - 1]) > params["picture_edge_lit_share"]
            )

            if not (row_bars_ok or col_bars_ok):
                return self._empty_picture_box_result(collected, samples, frame_rate, params)

            if not row_bars_ok:
                y0, y1 = 0, height

            if not col_bars_ok:
                x0, x1 = 0, width

            if (y1 - y0) < params["min_picture_fraction"] * height or (x1 - x0) < params["min_picture_fraction"] * width:
                return self._empty_picture_box_result(collected, samples, frame_rate, params)

            box = [
                float(x0) / float(width),
                float(y0) / float(height),
                float(x1 - x0) / float(width),
                float(y1 - y0) / float(height),
            ]
            aspect    = float(x1 - x0) / float(max(1, y1 - y0))
            bar_share = 1.0 - float(x1 - x0) * float(y1 - y0) / float(height * width)

            return {
                "detected":         True,
                "box":              box,
                "aspect":           aspect,
                "bar_share":        bar_share,
                "frame_count":      len(collected),
                "sample_count":     len(samples),
                "frame_rate":       frame_rate,
                "downsample_width": params["downsample_width"],
            }

        return await self._run_in_executor(_analyze_picture_box)

    async def _analyze_palette(
        self,
        frames: ImageArrayValue,
        frame_rate: Optional[float],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        collected = await frames.collect()

        def _analyze_palette() -> Dict[str, Any]:
            import numpy as np
            import cv2

            if not collected:
                return {
                    "background":       None,
                    "colors":           [],
                    "frame_count":      0,
                    "sample_count":     0,
                    "frame_rate":       frame_rate,
                    "downsample_width": params["downsample_width"],
                }

            sample_indices = np.unique(np.linspace(0, len(collected) - 1, num=min(len(collected), params["sample_count"])).astype(int))
            samples: List[Any] = []

            for index in sample_indices:
                frame = collected[int(index)].convert("RGB")
                width  = params["downsample_width"]
                height = max(1, int(round(frame.size[1] * width / max(1, frame.size[0]))))
                frame  = frame.resize((width, height))
                samples.append(cv2.cvtColor(np.asarray(frame, dtype=np.uint8), cv2.COLOR_RGB2BGR))

            stacked_samples = np.vstack(samples)  # (sum_H, W, 3)
            lab_pixels      = cv2.cvtColor(stacked_samples, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)
            color_count     = min(params["max_colors"], len(np.unique(lab_pixels, axis=0)))

            if color_count < 1:
                return {
                    "background":       None,
                    "colors":           [],
                    "frame_count":      len(collected),
                    "sample_count":     len(samples),
                    "frame_rate":       frame_rate,
                    "downsample_width": params["downsample_width"],
                }

            # Seed k-means++ with a fixed RNG so repeated runs on the
            # same shot return the same hexes.
            kmeans_criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
            cv2.setRNGSeed(0)
            _, pixel_clusters, cluster_centers = cv2.kmeans(lab_pixels, color_count, None, kmeans_criteria, 2, cv2.KMEANS_PP_CENTERS)
            pixel_clusters = pixel_clusters.ravel()
            cluster_shares = np.bincount(pixel_clusters, minlength=color_count) / float(len(pixel_clusters))
            cluster_colors = [ self._lab_to_hex(center) for center in cluster_centers ]

            # Border pixels of the stacked image vote for the background:
            # a per-sample border would mix dominant subjects when samples
            # are visually different, so the stacked border captures the
            # color most often sitting at the frame edges.
            cluster_grid     = pixel_clusters.reshape(stacked_samples.shape[:2])
            border_clusters  = np.concatenate([cluster_grid[0], cluster_grid[-1], cluster_grid[:, 0], cluster_grid[:, -1]])
            background_index = int(np.bincount(border_clusters, minlength=color_count).argmax())
            background       = cluster_colors[background_index]

            sorted_cluster_indices = [ int(index) for index in np.argsort(-cluster_shares) if float(cluster_shares[index]) >= params["min_share"] ]
            colors                 = [ { "hex": cluster_colors[index], "share": round(float(cluster_shares[index]), 4) } for index in sorted_cluster_indices ]

            return {
                "background":       background,
                "colors":           colors,
                "frame_count":      len(collected),
                "sample_count":     len(samples),
                "frame_rate":       frame_rate,
                "downsample_width": params["downsample_width"],
            }

        return await self._run_in_executor(_analyze_palette)

    def _luma_thumbnail(self, frame: PILImage.Image, downsample_width: int):
        """PIL frame -> BT.601 luma float32 thumbnail, resized with OpenCV's INTER_AREA
        (faster than Pillow for the sizes this analyzer works with)."""
        import numpy as np
        import cv2

        luma = np.asarray(frame.convert("L"), dtype=np.float32)
        height, width = luma.shape

        if width == 0 or height == 0:
            return np.zeros((1, 1), dtype=np.float32)

        if width > downsample_width:
            height = max(1, int(round(height * downsample_width / width)))
            luma = cv2.resize(luma, (downsample_width, height), interpolation=cv2.INTER_AREA)

        return luma

    def _grayscale_thumbnail(self, frame: PILImage.Image, downsample_width: int) -> Any:
        """PIL frame -> uint8 grayscale thumbnail, resized with OpenCV's
        INTER_AREA so the picture-box gate sees the same edge sharpness the
        algorithm expects (nearest-neighbour would smear a narrow bar)."""
        import numpy as np
        import cv2

        grayscale = np.asarray(frame.convert("L"), dtype=np.uint8)
        height, width = grayscale.shape

        if width == 0 or height == 0:
            return np.zeros((1, 1), dtype=np.uint8)

        if width > downsample_width:
            height = max(1, int(round(height * downsample_width / width)))
            grayscale = cv2.resize(grayscale, (downsample_width, height), interpolation=cv2.INTER_AREA)

        return grayscale

    def _strongest_period(self, series, max_period: int) -> Tuple[Optional[int], float]:
        """Scan lags 2..max_period for the strongest autocorrelation peak of a
        zero-mean series, returning (period, normalized autocorrelation at that
        lag). Returns (None, 0.0) when the series has no variance or no lag
        produces a positive correlation."""
        import numpy as np

        length = len(series)
        if length < 3:
            return None, 0.0

        centered = series - series.mean()
        variance = float((centered * centered).mean())

        if variance == 0.0:
            return None, 0.0

        best_lag, best_corr = 0, 0.0

        for lag in range(2, min(max_period, length) + 1):
            corr = float((centered[:-lag] * centered[lag:]).mean()) / variance

            if corr > best_corr:
                best_lag, best_corr = lag, corr

        if not best_lag:
            return None, 0.0

        return best_lag, max(0.0, best_corr)

    def _classify_pulldown(self, period: Optional[int], ratio: float) -> Optional[str]:
        """Match a measured duplicate period / ratio against known pulldown cadences.
        Returns the label when the period falls into one of the known bands and the
        duplicate ratio is above a minimal plausibility floor, else None (irregular)."""
        if period is None or ratio < 0.05:
            return None

        for label, periods in _PULLDOWN_TABLE:
            if period in periods:
                return label

        return None

    def _picture_run(self, lit_axis: Any, gap_tolerance: int) -> Optional[Tuple[int, int]]:
        """Longest run of lit entries along an axis, allowing short dark gaps.
        Returns (start, end) as half-open indices, or None when nothing clears
        the gap-tolerance threshold."""
        import numpy as np

        length = len(lit_axis)

        if length == 0:
            return None

        start = end = -1
        best_start = best_end = -1
        gap = 0

        for index in range(length):
            if lit_axis[index]:
                if start < 0:
                    start = index

                end = index
                gap = 0

                continue

            if start < 0:
                continue

            gap += 1

            if gap > gap_tolerance:
                if end - start > best_end - best_start:
                    best_start, best_end = start, end

                start = end = -1
                gap = 0

        if start >= 0 and end - start > best_end - best_start:
            best_start, best_end = start, end

        if best_start < 0:
            return None

        return best_start, best_end + 1

    def _empty_picture_box_result(
        self,
        collected: List[Any],
        samples: List[Any],
        frame_rate: Optional[float],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Shared `detected=False` payload for every early-return branch of
        the picture-box analyzer; keeps the result shape stable so downstream
        code can rely on the same keys whether bars were found or not."""
        return {
            "detected":         False,
            "box":              None,
            "aspect":           None,
            "bar_share":        None,
            "frame_count":      len(collected),
            "sample_count":     len(samples),
            "frame_rate":       frame_rate,
            "downsample_width": params["downsample_width"],
        }

    def _lab_to_hex(self, lab_center: Any) -> str:
        """Convert a single LAB triplet (k-means center) back to a #RRGGBB
        string so the palette output is UI-ready without the caller touching
        OpenCV."""
        import numpy as np
        import cv2

        lab_pixel = np.uint8([[ lab_center ]])
        bgr_pixel = cv2.cvtColor(lab_pixel, cv2.COLOR_LAB2BGR)[0, 0]

        return "#{:02x}{:02x}{:02x}".format(int(bgr_pixel[2]), int(bgr_pixel[1]), int(bgr_pixel[0]))

@register_video_frame_analyzer_driver(VideoFrameAnalyzerDriverType.OPENCV)
class OpenCvVideoFrameAnalyzerService(VideoFrameAnalyzerDriver):
    def __init__(self, id: str, config: VideoFrameAnalyzerComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [ "opencv-python", "numpy" ]

    async def _run(
        self,
        action: VideoFrameAnalyzerActionConfig,
        context: ComponentActionContext,
    ) -> Any:
        return await OpenCvVideoFrameAnalyzerAction(action).run(context)
