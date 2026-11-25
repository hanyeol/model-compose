from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, List, Dict, Any, Union, Tuple
from mindor.dsl.schema.component import VideoSceneTransitionClassifierComponentConfig, VideoSceneTransitionClassifierDriverType
from mindor.dsl.schema.action import VideoSceneTransitionClassifierActionConfig
from ..base import VideoSceneTransitionClassifierDriver, register_video_scene_transition_classifier_driver
from ..base import ComponentActionContext
from .native import NativeVideoSceneTransitionClassifierAction

if TYPE_CHECKING:
    pass

class OpenCvVideoSceneTransitionClassifierAction(NativeVideoSceneTransitionClassifierAction):
    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        motion_max_features         = await context.render_scalar(self.config.motion_max_features, int)
        motion_feature_quality      = await context.render_scalar(self.config.motion_feature_quality, float)
        motion_feature_min_distance = await context.render_scalar(self.config.motion_feature_min_distance, float)
        motion_ransac_threshold     = await context.render_scalar(self.config.motion_ransac_threshold, float)
        motion_min_inlier_ratio     = await context.render_scalar(self.config.motion_min_inlier_ratio, float)
        motion_calm_path_limit      = await context.render_scalar(self.config.motion_calm_path_limit, float)
        motion_calm_zoom_limit      = await context.render_scalar(self.config.motion_calm_zoom_limit, float)
        motion_calm_rotation_limit  = await context.render_scalar(self.config.motion_calm_rotation_limit, float)
        spin_min_rotation_degrees   = await context.render_scalar(self.config.spin_min_rotation_degrees, float)
        spin_turn_share             = await context.render_scalar(self.config.spin_turn_share, float)
        zoom_min_scale_change       = await context.render_scalar(self.config.zoom_min_scale_change, float)
        whip_min_net_share          = await context.render_scalar(self.config.whip_min_net_share, float)
        whip_max_path_ratio         = await context.render_scalar(self.config.whip_max_path_ratio, float)
        whip_max_detail_ratio       = await context.render_scalar(self.config.whip_max_detail_ratio, float)
        shake_min_path_share        = await context.render_scalar(self.config.shake_min_path_share, float)
        shake_min_path_net_ratio    = await context.render_scalar(self.config.shake_min_path_net_ratio, float)
        shake_min_tracked_pairs     = await context.render_scalar(self.config.shake_min_tracked_pairs, int)
        glitch_min_back_swings      = await context.render_scalar(self.config.glitch_min_back_swings, int)
        glitch_min_hard_switches    = await context.render_scalar(self.config.glitch_min_hard_switches, int)

        if not 16 <= motion_max_features <= 2000:
            raise ValueError(f"'motion_max_features' must be between 16 and 2000, got {motion_max_features}")

        if not 0.0 < motion_feature_quality <= 1.0:
            raise ValueError(f"'motion_feature_quality' must be in (0.0, 1.0], got {motion_feature_quality}")

        if motion_feature_min_distance <= 0.0:
            raise ValueError(f"'motion_feature_min_distance' must be positive, got {motion_feature_min_distance}")

        if motion_ransac_threshold <= 0.0:
            raise ValueError(f"'motion_ransac_threshold' must be positive, got {motion_ransac_threshold}")

        if not 0.0 <= motion_min_inlier_ratio <= 1.0:
            raise ValueError(f"'motion_min_inlier_ratio' must be between 0.0 and 1.0, got {motion_min_inlier_ratio}")

        if motion_calm_path_limit < 0.0:
            raise ValueError(f"'motion_calm_path_limit' must be non-negative, got {motion_calm_path_limit}")

        if motion_calm_zoom_limit < 0.0:
            raise ValueError(f"'motion_calm_zoom_limit' must be non-negative, got {motion_calm_zoom_limit}")

        if motion_calm_rotation_limit < 0.0:
            raise ValueError(f"'motion_calm_rotation_limit' must be non-negative, got {motion_calm_rotation_limit}")

        if spin_min_rotation_degrees <= 0.0:
            raise ValueError(f"'spin_min_rotation_degrees' must be positive, got {spin_min_rotation_degrees}")

        if not 0.0 < spin_turn_share <= 1.0:
            raise ValueError(f"'spin_turn_share' must be in (0.0, 1.0], got {spin_turn_share}")

        if zoom_min_scale_change <= 0.0:
            raise ValueError(f"'zoom_min_scale_change' must be positive, got {zoom_min_scale_change}")

        if not 0.0 < whip_min_net_share <= 1.0:
            raise ValueError(f"'whip_min_net_share' must be in (0.0, 1.0], got {whip_min_net_share}")

        if whip_max_path_ratio <= 0.0:
            raise ValueError(f"'whip_max_path_ratio' must be positive, got {whip_max_path_ratio}")

        if not 0.0 < whip_max_detail_ratio <= 1.0:
            raise ValueError(f"'whip_max_detail_ratio' must be in (0.0, 1.0], got {whip_max_detail_ratio}")

        if not 0.0 < shake_min_path_share <= 1.0:
            raise ValueError(f"'shake_min_path_share' must be in (0.0, 1.0], got {shake_min_path_share}")

        if shake_min_path_net_ratio <= 0.0:
            raise ValueError(f"'shake_min_path_net_ratio' must be positive, got {shake_min_path_net_ratio}")

        if not 1 <= shake_min_tracked_pairs <= 64:
            raise ValueError(f"'shake_min_tracked_pairs' must be between 1 and 64, got {shake_min_tracked_pairs}")

        if not 1 <= glitch_min_back_swings <= 64:
            raise ValueError(f"'glitch_min_back_swings' must be between 1 and 64, got {glitch_min_back_swings}")

        if not 1 <= glitch_min_hard_switches <= 64:
            raise ValueError(f"'glitch_min_hard_switches' must be between 1 and 64, got {glitch_min_hard_switches}")

        params.update({
            "motion_max_features":         motion_max_features,
            "motion_feature_quality":      motion_feature_quality,
            "motion_feature_min_distance": motion_feature_min_distance,
            "motion_ransac_threshold":     motion_ransac_threshold,
            "motion_min_inlier_ratio":     motion_min_inlier_ratio,
            "motion_calm_path_limit":      motion_calm_path_limit,
            "motion_calm_zoom_limit":      motion_calm_zoom_limit,
            "motion_calm_rotation_limit":  motion_calm_rotation_limit,
            "spin_min_rotation_degrees":   spin_min_rotation_degrees,
            "spin_turn_share":             spin_turn_share,
            "zoom_min_scale_change":       zoom_min_scale_change,
            "whip_min_net_share":          whip_min_net_share,
            "whip_max_path_ratio":         whip_max_path_ratio,
            "whip_max_detail_ratio":       whip_max_detail_ratio,
            "shake_min_path_share":        shake_min_path_share,
            "shake_min_path_net_ratio":    shake_min_path_net_ratio,
            "shake_min_tracked_pairs":     shake_min_tracked_pairs,
            "glitch_min_back_swings":      glitch_min_back_swings,
            "glitch_min_hard_switches":    glitch_min_hard_switches,
        })

        return params

    def _measure_signals(self, boundary: int, thumb_lumas: Dict[int, Any], frame_rate: Optional[float], params: Dict[str, Any]) -> Dict[str, Any]:
        """Extend the native signal dict with motion signals measured over
        the full `[boundary - window_size, boundary + window_size)` frame
        window: per-pair camera similarity (log-scale, rotation, dx, dy)
        summed into zoom / rot / turn / path / net, plus back-swings and
        hard switches in the first-to-last progress curve. Motion uses the
        full window rather than the span `_measure_span` narrows to, because
        whip / zoom / spin need the surrounding context the fade/dissolve
        signal avoided."""
        import numpy as np

        signals = super()._measure_signals(boundary, thumb_lumas, frame_rate, params)

        window: List[Any] = []

        for index in range(boundary - params["window_size"], boundary + params["window_size"]):
            if index in thumb_lumas:
                window.append(thumb_lumas[index])

        if len(window) < 3:
            signals.update({
                "motion_zoom":     0.0,
                "motion_rotation": 0.0,
                "motion_turn":     0.0,
                "motion_path":     0.0,
                "motion_net":      0.0,
                "motion_heading":  None,
                "motion_tracked":  0,
                "motion_back":     0,
                "motion_jumps":    0,
            })

            return signals

        zoom_sum = 0.0
        rot_sum  = 0.0
        turn_sum = 0.0
        path_sum = 0.0
        tracked  = 0
        net      = np.zeros(2, dtype=np.float32)

        for index in range(len(window) - 1):
            camera_motion = self._estimate_camera_motion(window[index], window[index + 1], params)

            if camera_motion is None:
                continue

            log_scale, rotation_degrees, dx, dy = camera_motion
            tracked  += 1
            zoom_sum += abs(log_scale)
            rot_sum  += abs(rotation_degrees)
            turn_sum += rotation_degrees
            path_sum += float(np.hypot(dx, dy))
            net      += (dx, dy)

        net_magnitude = float(np.hypot(*net))

        if abs(net[0]) > abs(net[1]):
            heading = "left" if net[0] < 0 else "right"
        else:
            heading = "up" if net[1] < 0 else "down"

        # Back-swings: progress curve from the window's `before` to its
        # `after` endpoint reverses by more than 0.25 between adjacent
        # frames. Glitch stacks multiple back-swings; two cuts in a row
        # never reverse.
        before_frame = window[0]
        after_frame  = window[-1]
        progress_curve = []

        for frame in window:
            before_diff = float(np.abs(frame - before_frame).mean())
            after_diff  = float(np.abs(frame - after_frame).mean())
            progress_curve.append(before_diff / (before_diff + after_diff + 1e-6))

        progress_diffs = np.diff(np.asarray(progress_curve, dtype=np.float32)) if len(progress_curve) >= 2 else np.zeros(0, dtype=np.float32)
        back_count     = int((progress_diffs < -0.25).sum())

        # Hard switches: adjacent frames differ by more than half the
        # whole before-to-after change — several of these inside a short
        # span read as glitch rather than a clean transition.
        whole_change = float(np.abs(before_frame - after_frame).mean()) + 1e-6
        hard_switches = 0

        for index in range(1, len(window)):
            if float(np.abs(window[index] - window[index - 1]).mean()) > 0.5 * whole_change:
                hard_switches += 1

        signals.update({
            "motion_zoom":     zoom_sum,
            "motion_rotation": rot_sum,
            "motion_turn":     turn_sum,
            "motion_path":     path_sum,
            "motion_net":      net_magnitude,
            "motion_heading":  heading,
            "motion_tracked":  tracked,
            "motion_back":     back_count,
            "motion_jumps":    hard_switches,
        })

        return signals

    def _decide_label(self, signals: Dict[str, Any], params: Dict[str, Any]) -> Tuple[str, float]:
        """Check motion labels (whip / zoom / spin / shake / glitch) before
        falling back to native's luma-based cascade. A motion effect would
        otherwise register as `cut` or `blur` once native's chain reaches
        its pair-MAD fallback, so motion runs first."""
        motion_label = self._decide_motion_label(signals, params)

        if motion_label is not None:
            return motion_label

        return super()._decide_label(signals, params)

    def _decide_motion_label(self, signals: Dict[str, Any], params: Dict[str, Any]) -> Optional[Tuple[str, float]]:
        """Motion-effect gates checked in order glitch → spin → zoom → whip
        → shake; the first matching gate wins. Returns None when no motion
        effect is detected."""
        motion_zoom     = signals["motion_zoom"]
        motion_rotation = signals["motion_rotation"]
        motion_turn     = signals["motion_turn"]
        motion_path     = signals["motion_path"]
        motion_net      = signals["motion_net"]
        motion_tracked  = signals["motion_tracked"]
        motion_back     = signals["motion_back"]
        motion_jumps    = signals["motion_jumps"]
        blur_rx         = signals["blur_rx"]
        blur_ry         = signals["blur_ry"]

        is_calm = all([
            motion_path < params["motion_calm_path_limit"],
            motion_zoom < params["motion_calm_zoom_limit"],
            motion_rotation < params["motion_calm_rotation_limit"],
        ])

        # Glitch: picture reverses direction inside the span (two cuts in
        # a row never go back). A single reversal plus several hard
        # switches also reads as glitch.
        if is_calm and any([
            motion_back >= params["glitch_min_back_swings"],
            motion_back >= 1 and motion_jumps >= params["glitch_min_hard_switches"],
        ]):
            return "glitch", min(1.0, motion_back / (params["glitch_min_back_swings"] * 2.0))

        # Spin: rotation adds up AND most of it is signed (same direction).
        if all([
            motion_rotation >= params["spin_min_rotation_degrees"],
            abs(motion_turn) >= params["spin_turn_share"] * motion_rotation,
        ]):
            return "spin", min(1.0, motion_rotation / (params["spin_min_rotation_degrees"] * 2.0))

        # Zoom: accumulated |log scale| crosses threshold.
        if motion_zoom >= params["zoom_min_scale_change"]:
            return "zoom", min(1.0, motion_zoom / (params["zoom_min_scale_change"] * 2.0))

        # Whip: net displacement crosses threshold AND path stays close
        # to net (motion goes one way) AND inside detail falls (motion
        # blur hides the cut).
        if all([
            motion_net >= params["whip_min_net_share"],
            motion_path < params["whip_max_path_ratio"] * motion_net,
            min(blur_rx, blur_ry) < params["whip_max_detail_ratio"],
        ]):
            return "whip", min(1.0, motion_net / (params["whip_min_net_share"] * 2.0))

        # Shake: path accumulates but net stays small (oscillation).
        if all([
            motion_path >= params["shake_min_path_share"],
            motion_path > params["shake_min_path_net_ratio"] * motion_net,
            motion_tracked >= params["shake_min_tracked_pairs"],
        ]):
            return "shake", min(1.0, motion_path / (params["shake_min_path_share"] * 2.0))

        return None

    def _estimate_camera_motion(self, before: Any, after: Any, params: Dict[str, Any]) -> Optional[Tuple[float, float, float, float]]:
        """Affine camera motion between two luma frames as (log scale,
        rotation degrees, dx, dy) where dx / dy are fractions of the
        frame width / height. Returns None when too few features track
        well enough to fit the transform."""
        import numpy as np
        import cv2

        before_uint8 = np.clip(before, 0, 255).astype(np.uint8)
        after_uint8  = np.clip(after,  0, 255).astype(np.uint8)

        feature_points = cv2.goodFeaturesToTrack(
            before_uint8,
            maxCorners=params["motion_max_features"],
            qualityLevel=params["motion_feature_quality"],
            minDistance=params["motion_feature_min_distance"],
        )

        if feature_points is None or len(feature_points) < 10:
            return None

        tracked_points, status, _ = cv2.calcOpticalFlowPyrLK(
            before_uint8, after_uint8, feature_points, None,
            winSize=(15, 15), maxLevel=2,
        )
        tracked_mask = status.ravel() == 1

        if int(tracked_mask.sum()) < 10:
            return None

        affine, inliers = cv2.estimateAffinePartial2D(
            feature_points[tracked_mask],
            tracked_points[tracked_mask],
            ransacReprojThreshold=params["motion_ransac_threshold"],
        )

        if affine is None or inliers is None or float(inliers.mean()) < params["motion_min_inlier_ratio"]:
            return None

        height, width = before_uint8.shape
        center_before = np.array([ width / 2.0, height / 2.0, 1.0 ], dtype=np.float32)
        center_after  = affine @ center_before

        log_scale        = float(np.log(np.hypot(affine[0, 0], affine[1, 0]) + 1e-9))
        rotation_degrees = float(np.degrees(np.arctan2(affine[1, 0], affine[0, 0])))
        dx               = float((center_after[0] - center_before[0]) / width)
        dy               = float((center_after[1] - center_before[1]) / height)

        return log_scale, rotation_degrees, dx, dy

@register_video_scene_transition_classifier_driver(VideoSceneTransitionClassifierDriverType.OPENCV)
class OpenCvVideoSceneTransitionClassifierDriver(VideoSceneTransitionClassifierDriver):
    def __init__(self, id: str, config: VideoSceneTransitionClassifierComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [ "opencv-python-headless", "numpy" ]

    async def _run(
        self,
        action: VideoSceneTransitionClassifierActionConfig,
        context: ComponentActionContext,
    ) -> Any:
        return await OpenCvVideoSceneTransitionClassifierAction(action).run(context)
