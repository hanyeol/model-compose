from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, List, Dict, Any, Union, Tuple
import math
from mindor.dsl.schema.component import VideoMotionEstimatorComponentConfig, VideoMotionEstimatorDriverType
from mindor.dsl.schema.action import VideoMotionEstimatorActionConfig, OpenCvVideoMotionEstimatorMode
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.foundation.cancellation import CancellationToken
from ..base import VideoMotionEstimatorDriver, register_video_motion_estimator_driver
from ..base import ComponentActionContext
from .common import VideoMotionEstimatorAction

if TYPE_CHECKING:
    from PIL import Image as PILImage

class OpenCvVideoMotionEstimatorAction(VideoMotionEstimatorAction):
    async def _resolve_params(self, mode: OpenCvVideoMotionEstimatorMode, context: ComponentActionContext) -> Dict[str, Any]:
        if mode == OpenCvVideoMotionEstimatorMode.RIGID:
            analysis_width       = await context.render_scalar(self.config.analysis_width, int)
            max_features         = await context.render_scalar(self.config.max_features, int)
            feature_quality      = await context.render_scalar(self.config.feature_quality, float)
            feature_min_distance = await context.render_scalar(self.config.feature_min_distance, float)
            ransac_threshold     = await context.render_scalar(self.config.ransac_threshold, float)
            min_inliers          = await context.render_scalar(self.config.min_inliers, int)

            if not 64 <= analysis_width <= 4096:
                raise ValueError(f"'analysis_width' must be between 64 and 4096, got {analysis_width}")

            if not 16 <= max_features <= 2000:
                raise ValueError(f"'max_features' must be between 16 and 2000, got {max_features}")

            if not 0.0 < feature_quality <= 1.0:
                raise ValueError(f"'feature_quality' must be in (0.0, 1.0], got {feature_quality}")

            if feature_min_distance <= 0.0:
                raise ValueError(f"'feature_min_distance' must be positive, got {feature_min_distance}")

            if ransac_threshold <= 0.0:
                raise ValueError(f"'ransac_threshold' must be positive, got {ransac_threshold}")

            if not 4 <= min_inliers <= 1000:
                raise ValueError(f"'min_inliers' must be between 4 and 1000, got {min_inliers}")

            return {
                "analysis_width":       analysis_width,
                "max_features":         max_features,
                "feature_quality":      feature_quality,
                "feature_min_distance": feature_min_distance,
                "ransac_threshold":     ransac_threshold,
                "min_inliers":          min_inliers,
            }

        if mode == OpenCvVideoMotionEstimatorMode.KENBURNS:
            analysis_width       = await context.render_scalar(self.config.analysis_width, int)
            max_features         = await context.render_scalar(self.config.max_features, int)
            feature_quality      = await context.render_scalar(self.config.feature_quality, float)
            feature_min_distance = await context.render_scalar(self.config.feature_min_distance, float)
            ransac_threshold     = await context.render_scalar(self.config.ransac_threshold, float)
            stillness_threshold  = await context.render_scalar(self.config.stillness_threshold, float)
            rigid_inlier_floor   = await context.render_scalar(self.config.rigid_inlier_floor, float)

            if not 64 <= analysis_width <= 4096:
                raise ValueError(f"'analysis_width' must be between 64 and 4096, got {analysis_width}")

            if not 16 <= max_features <= 2000:
                raise ValueError(f"'max_features' must be between 16 and 2000, got {max_features}")

            if not 0.0 < feature_quality <= 1.0:
                raise ValueError(f"'feature_quality' must be in (0.0, 1.0], got {feature_quality}")

            if feature_min_distance <= 0.0:
                raise ValueError(f"'feature_min_distance' must be positive, got {feature_min_distance}")

            if ransac_threshold <= 0.0:
                raise ValueError(f"'ransac_threshold' must be positive, got {ransac_threshold}")

            if stillness_threshold < 0.0:
                raise ValueError(f"'stillness_threshold' must be non-negative, got {stillness_threshold}")

            if not 0.0 <= rigid_inlier_floor <= 1.0:
                raise ValueError(f"'rigid_inlier_floor' must be between 0.0 and 1.0, got {rigid_inlier_floor}")

            return {
                "analysis_width":       analysis_width,
                "max_features":         max_features,
                "feature_quality":      feature_quality,
                "feature_min_distance": feature_min_distance,
                "ransac_threshold":     ransac_threshold,
                "stillness_threshold":  stillness_threshold,
                "rigid_inlier_floor":   rigid_inlier_floor,
            }

        raise ValueError(f"Unsupported video motion estimation mode: {mode}")

    async def _estimate(
        self,
        mode: OpenCvVideoMotionEstimatorMode,
        frames: ImageArrayValue,
        frame_rate: Optional[float],
        streaming: bool,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        if mode == OpenCvVideoMotionEstimatorMode.RIGID:
            return await self._estimate_rigid(frames, frame_rate, params, cancellation_token)

        if mode == OpenCvVideoMotionEstimatorMode.KENBURNS:
            return await self._estimate_kenburns(frames, frame_rate, params, cancellation_token)

        raise ValueError(f"Unsupported video motion estimation mode: {mode}")

    async def _estimate_rigid(
        self,
        frames: ImageArrayValue,
        frame_rate: Optional[float],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        frames = await frames.collect()

        def _estimate_rigid() -> Dict[str, Any]:
            import numpy as np

            # Per-pair rigid (similarity) transform fit via LK tracking + RANSAC.
            # The fit yields scale, rotation, translation — from which we derive
            # per-second zoom and pan rates that are directly reproducible with
            # ffmpeg's scale + crop + overlay chain.
            inlier_ratios:  List[float] = []
            residuals:      List[float] = []
            scales:         List[float] = []
            rotations:      List[float] = []
            translations_x: List[float] = []
            translations_y: List[float] = []
            inlier_counts:  List[int]   = []

            previous_luma = None
            previous_source_scale = 1.0

            for frame in frames:
                luma, source_scale = self._luma_thumbnail(frame, params["analysis_width"])

                if previous_luma is not None:
                    # LK needs a consistent analysis resolution; if resolutions
                    # ever disagree between frames the pair is skipped.
                    if luma.shape != previous_luma.shape:
                        previous_luma, previous_source_scale = luma, source_scale

                        continue

                    inlier_ratio, residual, transform = self._fit_rigid_pair(previous_luma, luma, params)

                    if transform is None:
                        inlier_ratios.append(inlier_ratio)
                        residuals.append(residual)
                        inlier_counts.append(0)
                        scales.append(math.nan)
                        rotations.append(math.nan)
                        translations_x.append(math.nan)
                        translations_y.append(math.nan)
                    else:
                        inlier_ratios.append(inlier_ratio)
                        residuals.append(residual)
                        inlier_counts.append(transform["inliers"])
                        scales.append(transform["scale"])
                        rotations.append(transform["rotation"])

                        # Translations are measured in analysis-resolution pixels;
                        # rescale back to source-resolution pixels for ffmpeg use.
                        translations_x.append(transform["translation_x"] * previous_source_scale)
                        translations_y.append(transform["translation_y"] * previous_source_scale)

                previous_luma, previous_source_scale = luma, source_scale

            pair_count = len(inlier_ratios)

            if pair_count == 0:
                return {
                    "rigid_inlier_ratio": 0.0,
                    "rigid_residual":     0.0,
                    "zoom_per_s":         0.0,
                    "pan_px_per_s":       0.0,
                    "pair_count":         0,
                    "frame_count":        len(frames),
                    "frame_rate":         frame_rate,
                    "analysis_width":     params["analysis_width"],
                    "min_inliers":        params["min_inliers"],
                }

            inlier_ratios = np.asarray(inlier_ratios, dtype=np.float32)
            residuals     = np.asarray(residuals, dtype=np.float32)
            inlier_counts = np.asarray(inlier_counts, dtype=np.int32)

            # Aggregate scale & translation only over pairs with enough inliers;
            # noisy pairs would otherwise skew the per-second rates.
            valid_mask  = inlier_counts >= params["min_inliers"]
            valid_count = int(valid_mask.sum())

            if valid_count > 0 and frame_rate:
                scales         = np.asarray(scales, dtype=np.float32)[valid_mask]
                translations_x = np.asarray(translations_x, dtype=np.float32)[valid_mask]
                translations_y = np.asarray(translations_y, dtype=np.float32)[valid_mask]

                # Per-pair zoom factor is the scale; convert the geometric mean
                # over valid pairs into a per-second zoom rate.
                log_zoom_mean   = float(np.log(np.maximum(scales, 1e-6)).mean())
                zoom_per_s      = math.exp(log_zoom_mean * frame_rate) - 1.0 if math.isfinite(log_zoom_mean) else 0.0
                pan_px_per_pair = float(np.hypot(translations_x, translations_y).mean())
                pan_px_per_s    = pan_px_per_pair * frame_rate
            else:
                zoom_per_s   = 0.0
                pan_px_per_s = 0.0

            return {
                "rigid_inlier_ratio": float(inlier_ratios.mean()),
                "rigid_residual":     float(residuals.mean()),
                "zoom_per_s":         zoom_per_s,
                "pan_px_per_s":       pan_px_per_s,
                "pair_count":         pair_count,
                "valid_pair_count":   valid_count,
                "frame_count":        len(frames),
                "frame_rate":         frame_rate,
                "analysis_width":     params["analysis_width"],
                "min_inliers":        params["min_inliers"],
            }

        return await self._run_in_executor(_estimate_rigid)

    async def _estimate_kenburns(
        self,
        frames: ImageArrayValue,
        frame_rate: Optional[float],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        frames = await frames.collect()

        def _estimate_kenburns() -> Dict[str, Any]:
            import numpy as np

            # Ken Burns detection: the content itself is still, but the frame
            # moves as a plane. We combine two signals per pair:
            #   - median feature displacement below stillness_threshold ->
            #     tracked points barely move in the scene coordinates, i.e.
            #     no object motion;
            #   - rigid inlier ratio above rigid_inlier_floor -> whatever
            #     motion does exist fits a single plane (pure camera move).
            inlier_ratios:        List[float] = []
            median_displacements: List[float] = []
            kenburns_mask:        List[int]   = []

            previous_luma = None

            for frame in frames:
                luma, _ = self._luma_thumbnail(frame, params["analysis_width"])

                if previous_luma is not None:
                    if luma.shape != previous_luma.shape:
                        previous_luma = luma
                        continue

                    inlier_ratio, _residual, transform = self._fit_rigid_pair(previous_luma, luma, params)
                    median_displacement = self._median_feature_displacement(previous_luma, luma, params)

                    inlier_ratios.append(inlier_ratio)
                    median_displacements.append(median_displacement if median_displacement is not None else math.nan)

                    is_still = median_displacement is not None and median_displacement < params["stillness_threshold"]
                    is_plane = transform is not None and inlier_ratio >= params["rigid_inlier_floor"]
                    kenburns_mask.append(int(is_still and is_plane))

                previous_luma = luma

            pair_count = len(kenburns_mask)

            if pair_count == 0:
                return {
                    "kenburns_score":      0.0,
                    "kenburns_pair_count": 0,
                    "median_displacement": 0.0,
                    "rigid_inlier_ratio":  0.0,
                    "pair_count":          0,
                    "frame_count":         len(frames),
                    "frame_rate":          frame_rate,
                    "analysis_width":      params["analysis_width"],
                    "stillness_threshold": params["stillness_threshold"],
                    "rigid_inlier_floor":  params["rigid_inlier_floor"],
                }

            kenburns_mask        = np.asarray(kenburns_mask, dtype=np.float32)
            inlier_ratios        = np.asarray(inlier_ratios, dtype=np.float32)
            median_displacements = np.asarray(median_displacements, dtype=np.float32)
            kenburns_pair_count  = int(kenburns_mask.sum())

            finite_displacements = median_displacements[np.isfinite(median_displacements)]

            return {
                "kenburns_score":      kenburns_pair_count / pair_count,
                "kenburns_pair_count": kenburns_pair_count,
                "median_displacement": float(finite_displacements.mean()) if finite_displacements.size else 0.0,
                "rigid_inlier_ratio":  float(inlier_ratios.mean()),
                "pair_count":          pair_count,
                "frame_count":         len(frames),
                "frame_rate":          frame_rate,
                "analysis_width":      params["analysis_width"],
                "stillness_threshold": params["stillness_threshold"],
                "rigid_inlier_floor":  params["rigid_inlier_floor"],
            }

        return await self._run_in_executor(_estimate_kenburns)

    def _luma_thumbnail(self, frame: "PILImage.Image", analysis_width: int) -> Tuple[Any, float]:
        """PIL frame -> (BT.601 luma uint8 thumbnail, source_scale_factor).

        Returns the scale factor used to convert translations measured at the
        analysis resolution back to source-resolution pixels (1.0 when no
        downscale was applied). Uint8 is required because LK tracking and
        goodFeaturesToTrack both expect 8-bit single-channel input.
        """
        import numpy as np
        import cv2

        luma = np.asarray(frame.convert("L"), dtype=np.uint8)
        height, width = luma.shape

        if width == 0 or height == 0:
            return np.zeros((1, 1), dtype=np.uint8), 1.0

        if width > analysis_width:
            height = max(1, int(round(height * analysis_width / width)))
            luma = cv2.resize(luma, (analysis_width, height), interpolation=cv2.INTER_AREA)

            return luma, width / analysis_width

        return luma, 1.0

    def _fit_rigid_pair(self, previous_luma, current_luma, params: Dict[str, Any]) -> Tuple[float, float, Optional[Dict[str, Any]]]:
        """Track features from previous -> current with LK, fit a similarity
        transform with RANSAC, and return (inlier_ratio, mean inlier residual,
        transform dict or None). The transform dict is None when there aren't
        enough tracked points or the RANSAC fit fails."""
        import numpy as np
        import cv2

        previous_points = cv2.goodFeaturesToTrack(
            previous_luma,
            maxCorners=params["max_features"],
            qualityLevel=params["feature_quality"],
            minDistance=params["feature_min_distance"],
        )

        if previous_points is None or len(previous_points) < 4:
            return 0.0, 0.0, None

        current_points, status, _ = cv2.calcOpticalFlowPyrLK(previous_luma, current_luma, previous_points, None)

        if current_points is None:
            return 0.0, 0.0, None

        tracked_mask    = status.reshape(-1).astype(bool)
        previous_points = previous_points.reshape(-1, 2)[tracked_mask]
        current_points  = current_points.reshape(-1, 2)[tracked_mask]

        if len(previous_points) < 4:
            return 0.0, 0.0, None

        matrix, inlier_mask = cv2.estimateAffinePartial2D(
            previous_points,
            current_points,
            method=cv2.RANSAC,
            ransacReprojThreshold=params["ransac_threshold"],
            maxIters=2000,
            confidence=0.99,
            refineIters=10,
        )

        if matrix is None or inlier_mask is None:
            return 0.0, 0.0, None

        inlier_mask  = inlier_mask.reshape(-1).astype(bool)
        inlier_count = int(inlier_mask.sum())
        inlier_ratio = inlier_count / len(previous_points)

        if inlier_count == 0:
            return inlier_ratio, 0.0, None

        # estimateAffinePartial2D returns [[a, -b, tx], [b, a, ty]] where
        # a = scale * cos(theta), b = scale * sin(theta).
        a = float(matrix[0, 0])
        b = float(matrix[1, 0])

        scale         = math.hypot(a, b)
        rotation      = math.atan2(b, a)
        translation_x = float(matrix[0, 2])
        translation_y = float(matrix[1, 2])

        projected       = (matrix[:, :2] @ previous_points.T).T + matrix[:, 2]
        residuals       = np.linalg.norm(projected - current_points, axis=1)
        inlier_residual = float(residuals[inlier_mask].mean())

        return inlier_ratio, inlier_residual, {
            "scale":         scale,
            "rotation":      rotation,
            "translation_x": translation_x,
            "translation_y": translation_y,
            "inliers":       inlier_count,
        }

    def _median_feature_displacement(self, previous_luma, current_luma, params: Dict[str, Any]) -> Optional[float]:
        """Median LK displacement in analysis-resolution pixels across all
        successfully tracked features. Returns None when too few features
        could be tracked to form a stable median."""
        import numpy as np
        import cv2

        previous_points = cv2.goodFeaturesToTrack(
            previous_luma,
            maxCorners=params["max_features"],
            qualityLevel=params["feature_quality"],
            minDistance=params["feature_min_distance"],
        )

        if previous_points is None or len(previous_points) < 4:
            return None

        current_points, status, _ = cv2.calcOpticalFlowPyrLK(previous_luma, current_luma, previous_points, None)

        if current_points is None:
            return None

        tracked_mask    = status.reshape(-1).astype(bool)
        previous_points = previous_points.reshape(-1, 2)[tracked_mask]
        current_points  = current_points.reshape(-1, 2)[tracked_mask]

        if len(previous_points) < 4:
            return None

        displacements = np.linalg.norm(current_points - previous_points, axis=1)

        return float(np.median(displacements))

@register_video_motion_estimator_driver(VideoMotionEstimatorDriverType.OPENCV)
class OpenCvVideoMotionEstimatorService(VideoMotionEstimatorDriver):
    def __init__(self, id: str, config: VideoMotionEstimatorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [ "opencv-python", "numpy" ]

    async def _run(
        self,
        action: VideoMotionEstimatorActionConfig,
        context: ComponentActionContext,
    ) -> Any:
        return await OpenCvVideoMotionEstimatorAction(action).run(context)
