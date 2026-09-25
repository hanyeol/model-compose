from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Tuple, Dict, List, Any
from mindor.dsl.schema.component import CameraPoseEstimatorComponentConfig, ColmapMatcherType
from mindor.dsl.schema.action import CameraPoseEstimatorActionConfig, ColmapCameraPoseEstimatorActionConfig
from mindor.core.foundation.variable.file import FileArrayValue
from mindor.core.foundation.streaming.model_3d import Model3DStreamResource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.files import get_temporary_path
from mindor.core.logger import logging
from ..base import CameraPoseEstimatorDriver, CameraPoseEstimatorDriverType, register_camera_pose_estimator_driver
from ..base import ComponentActionContext
from .common import CameraPoseEstimatorAction
import os, shutil, asyncio

if TYPE_CHECKING:
    import pycolmap

class ColmapCameraPoseEstimatorAction(CameraPoseEstimatorAction):
    config: ColmapCameraPoseEstimatorActionConfig

    def __init__(
        self,
        config: ColmapCameraPoseEstimatorActionConfig,
        context: ComponentActionContext,
        component_config: CameraPoseEstimatorComponentConfig,
    ):
        super().__init__(config, context)

        self.component_config: CameraPoseEstimatorComponentConfig = component_config

    async def _resolve_params(self) -> Dict[str, Any]:
        params = await super()._resolve_params()

        return_cameras = await self.context.render_scalar(self.config.return_cameras, bool)
        return_poses   = await self.context.render_scalar(self.config.return_poses, bool)
        return_points  = await self.context.render_scalar(self.config.return_points, bool)

        # COLMAP camera model names are UPPER_SNAKE (e.g. `OPENCV_FISHEYE`);
        # the DSL enum values are lowercase kebab (`opencv-fisheye`).
        params.update({
            "camera_model":   self.component_config.camera_model.value.replace("-", "_").upper(),
            "single_camera":  self.component_config.single_camera,
            "matcher":        self.component_config.matcher.value,
            "use_gpu":        self.component_config.use_gpu,
            "thread_count":   self.component_config.thread_count,
            "return_cameras": return_cameras,
            "return_poses":   return_poses,
            "return_points":  return_points,
        })

        return params

    async def _estimate_batch(
        self,
        inputs: List[Tuple[Optional[FileArrayValue], str]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        import pycolmap

        results: List[Dict[str, Any]] = []

        for images, workspace_dir in inputs:
            if images is None:
                if not os.path.isdir(os.path.join(workspace_dir, "images")):
                    raise ValueError(f"no images provided and no 'images/' folder found under {workspace_dir}")
            else:
                await self._save_images(images, os.path.join(workspace_dir, "images"))

            # `_run_in_executor` only reacts to asyncio cancellation, but our
            # CancellationToken is a threading.Event that has to be polled.
            # pycolmap exposes its own `CancellationToken` that the C++
            # backend polls between iterations, so we forward mindor's token
            # into it from an asyncio watcher; pycolmap then aborts extraction,
            # matching, and mapping mid-flight.
            pycolmap_cancellation_token = pycolmap.CancellationToken()
            pipeline_task = asyncio.create_task(self._run_in_executor(self._run_pipeline, workspace_dir, params, pycolmap_cancellation_token))

            watcher_task: Optional[asyncio.Task] = None

            if cancellation_token is not None:
                async def _watch_cancellation() -> None:
                    while not cancellation_token.is_cancelled():
                        if pipeline_task.done():
                            return
                        await asyncio.sleep(0.2)
                    pycolmap_cancellation_token.cancel()

                watcher_task = asyncio.create_task(_watch_cancellation())

            try:
                results.append(await pipeline_task)
            finally:
                if not pipeline_task.done():
                    pycolmap_cancellation_token.cancel()

                if watcher_task is not None and not watcher_task.done():
                    watcher_task.cancel()

        return results

    def _run_pipeline(self, workspace_dir: str, params: Dict[str, Any], cancellation_token: Any) -> Dict[str, Any]:
        import pycolmap

        image_dir     = os.path.join(workspace_dir, "images")
        database_path = os.path.join(workspace_dir, "database.db")
        sparse_dir    = os.path.join(workspace_dir, "sparse")

        os.makedirs(workspace_dir, exist_ok=True)

        if os.path.exists(database_path):
            os.remove(database_path)

        if os.path.isdir(sparse_dir):
            shutil.rmtree(sparse_dir)

        os.makedirs(sparse_dir)

        camera_mode  = pycolmap.CameraMode.SINGLE if params["single_camera"] else pycolmap.CameraMode.PER_IMAGE
        device       = pycolmap.Device.cuda if params["use_gpu"] else pycolmap.Device.cpu
        thread_count = params["thread_count"]

        reader_options = pycolmap.ImageReaderOptions()
        reader_options.camera_model = params["camera_model"]

        extraction_options = pycolmap.FeatureExtractionOptions()
        matching_options   = pycolmap.FeatureMatchingOptions()
        mapping_options    = pycolmap.IncrementalPipelineOptions()

        # `thread_count = None` leaves pycolmap's own defaults (auto). Setting
        # `num_threads` on each options object routes the requested worker
        # count through feature extraction, matching, and bundle adjustment.
        if thread_count is not None:
            extraction_options.num_threads = thread_count
            matching_options.num_threads   = thread_count
            mapping_options.num_threads    = thread_count

        logging.info(
            "COLMAP extract_features (workspace=%s, camera_model=%s, camera_mode=%s, device=%s)",
            workspace_dir, params["camera_model"], camera_mode.name, device.name,
        )

        pycolmap.extract_features(
            database_path,
            image_dir,
            camera_mode=camera_mode,
            reader_options=reader_options,
            extraction_options=extraction_options,
            device=device,
            cancellation_token=cancellation_token,
        )

        matcher_fn = self._resolve_matcher(pycolmap, params["matcher"])

        logging.info("COLMAP %s (device=%s)", matcher_fn.__name__, device.name)

        matcher_fn(
            database_path,
            matching_options=matching_options,
            device=device,
            cancellation_token=cancellation_token
        )

        logging.info("COLMAP incremental_mapping (sparse=%s)", sparse_dir)

        reconstructions = pycolmap.incremental_mapping(
            database_path,
            image_dir,
            sparse_dir,
            options=mapping_options,
            cancellation_token=cancellation_token
        )

        if not reconstructions:
            raise RuntimeError("COLMAP incremental_mapping produced no reconstruction; check input images and matches.")

        # Pick the reconstruction with the most registered images. Other
        # partial reconstructions remain on disk under sparse/<n>/ for
        # inspection but are not summarised in the returned result.
        best_id = max(reconstructions, key=lambda i: reconstructions[i].num_reg_images())
        reconstruction = reconstructions[best_id]

        return self._build_result(workspace_dir, reconstruction, best_id, params)

    @staticmethod
    def _resolve_matcher(pycolmap_module: Any, matcher: str):
        matchers = {
            ColmapMatcherType.EXHAUSTIVE.value: pycolmap_module.match_exhaustive,
            ColmapMatcherType.SEQUENTIAL.value: pycolmap_module.match_sequential,
            ColmapMatcherType.SPATIAL.value:    pycolmap_module.match_spatial,
        }

        return matchers[matcher]

    def _build_result(self, workspace_dir: str, reconstruction: Any, sparse_index: int, params: Dict[str, Any]) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "workspace_dir": os.path.join(workspace_dir, "sparse", str(sparse_index)),
            "images_count":  int(reconstruction.num_reg_images()),
            "points_count":  int(reconstruction.num_points3D()),
        }

        if params["return_cameras"]:
            cameras: List[Dict[str, Any]] = []

            for camera_id, camera in reconstruction.cameras.items():
                cameras.append({
                    "id":     int(camera_id),
                    "model":  camera.model_name,
                    "width":  int(camera.width),
                    "height": int(camera.height),
                    "params": [ float(v) for v in camera.params ],
                })

            result["cameras"] = cameras

        if params["return_poses"]:
            poses: List[Dict[str, Any]] = []

            for _, image in reconstruction.images.items():
                if not image.has_pose:
                    continue

                cam_from_world = image.cam_from_world()

                # pycolmap stores rotations as `Rotation3d`, whose `.quat` is
                # `[x, y, z, w]` (Eigen convention). COLMAP's on-disk / textual
                # convention is `[qw, qx, qy, qz]`, so swap the scalar to the
                # front for downstream consumers.
                qx, qy, qz, qw = cam_from_world.rotation.quat
                poses.append({
                    "image":       image.name,
                    "camera_id":   int(image.camera_id),
                    "quaternion":  [ float(qw), float(qx), float(qy), float(qz) ],
                    "translation": [ float(v) for v in cam_from_world.translation ],
                })

            result["poses"] = poses

        if params["return_points"]:
            scene = self._build_points_scene(reconstruction)
            points_path = get_temporary_path("glb")

            scene.export(points_path, file_type="glb")

            result["points"] = Model3DStreamResource(
                FileStreamResource(points_path, auto_delete=True),
                format="glb",
                filename="points.glb",
            )

        return result

    def _build_points_scene(self, reconstruction: Any) -> Any:
        # Bundle the sparse point cloud and per-image camera frustums into
        # one scene so a Gradio Model3D viewer shows both geometry and poses
        # without additional client-side glue.
        import numpy as np
        import trimesh

        # COLMAP uses a right-handed frame with +y down / +z forward; glTF
        # viewers use +y up / +z back. Flipping y and z on every world-space
        # point brings the reconstruction upright in the Model3D viewer
        # without needing a scene-graph transform (trimesh's `Scene`
        # `apply_transform` requires geometry to already be attached).
        world_axes_to_gltf = np.diag([ 1.0, -1.0, -1.0 ])

        points_xyz: List[List[float]] = []
        points_rgb: List[List[int]] = []

        for _, point in reconstruction.points3D.items():
            points_xyz.append([ float(v) for v in point.xyz ])
            points_rgb.append([ int(v) for v in point.color ] + [ 255 ])

        # Gather world-space camera centers first so we can pick a frustum size
        # that scales with the scene — SfM reconstructions come out at an
        # arbitrary unit, so a fixed constant would render as either a dot or
        # a giant occluder depending on the scene.
        camera_centers: List[Any] = []
        camera_poses: List[Tuple[Any, Any]] = []

        for _, image in reconstruction.images.items():
            if not image.has_pose:
                continue

            camera         = reconstruction.cameras[image.camera_id]
            cam_from_world = image.cam_from_world()
            rotation       = np.asarray(cam_from_world.rotation.matrix())
            translation    = np.asarray(cam_from_world.translation)
            # center_world: X_cam = R·X_world + t  ⇒  X_world = R^T·(X_cam - t)
            center_world   = -rotation.T @ translation

            camera_centers.append(center_world)
            camera_poses.append((camera, cam_from_world))

        camera_center_array = np.asarray(camera_centers) if camera_centers else None
        frustum_scale = self._resolve_frustum_scale(camera_center_array)
        scene = trimesh.Scene()

        if points_xyz:
            point_vertices = np.asarray(points_xyz) @ world_axes_to_gltf.T
            scene.add_geometry(trimesh.PointCloud(vertices=point_vertices, colors=np.asarray(points_rgb, dtype=np.uint8)))

        for camera, cam_from_world in camera_poses:
            frustum = self._build_camera_frustum(
                camera,
                cam_from_world,
                scale=frustum_scale,
                world_transform=world_axes_to_gltf
            )

            if frustum is not None:
                scene.add_geometry(frustum)

        return scene

    @staticmethod
    def _resolve_frustum_scale(camera_centers: Optional[Any]) -> float:
        # Median pairwise camera distance gives a scene-relative unit that's
        # robust to a couple of outlier cameras; take a fraction of it so
        # each frustum sits comfortably between neighboring viewpoints.
        import numpy as np

        if camera_centers is None or len(camera_centers) < 2:
            return 0.2

        deltas    = camera_centers[:, None, :] - camera_centers[None, :, :]
        distances = np.linalg.norm(deltas, axis=-1)
        # Only look at the upper triangle (i<j) — the diagonal is zero and the
        # lower triangle just mirrors the upper.
        upper     = distances[np.triu_indices(len(camera_centers), k=1)]
        median    = float(np.median(upper))

        return max(median * 0.25, 1e-6)

    @staticmethod
    def _build_camera_frustum(camera: Any, cam_from_world: Any, scale: float, world_transform: Optional[Any] = None) -> Optional[Any]:
        """Build a wireframe frustum for one camera in world coordinates.

        Uses the camera's calibration matrix to back-project the four image
        corners onto a plane at depth `scale` in the camera frame, then
        transforms everything to world space via the inverse of `cam_from_world`.
        When `world_transform` is provided (3×3), it is applied to the final
        world-space vertices — used to reorient from COLMAP into glTF axes.
        """
        import numpy as np
        import trimesh

        width, height = float(camera.width), float(camera.height)

        # `calibration_matrix()` handles the per-model params → (fx, fy, cx, cy)
        # mapping internally, so a SIMPLE_RADIAL camera with `params=[f,cx,cy,k]`
        # doesn't get its `cx` mistakenly read as `fy`.
        calibration = np.asarray(camera.calibration_matrix())
        fx, fy      = calibration[0, 0], calibration[1, 1]
        cx, cy      = calibration[0, 2], calibration[1, 2]

        if fx <= 0 or fy <= 0:
            return None

        # Back-project the image corners (0..width, 0..height) through K^-1 to
        # a plane at depth `scale` in camera space; using cx/cy keeps the
        # frustum accurate for cameras whose principal point isn't centered.
        corners_pixel = np.array([
            [ 0.0,    0.0    ],
            [ width,  0.0    ],
            [ width,  height ],
            [ 0.0,    height ],
        ])
        corners_cam = np.column_stack([
            (corners_pixel[:, 0] - cx) / fx,
            (corners_pixel[:, 1] - cy) / fy,
            np.ones(4),
        ]) * scale

        rotation    = np.asarray(cam_from_world.rotation.matrix())
        translation = np.asarray(cam_from_world.translation)

        # cam_from_world: X_cam = R * X_world + t  ⇒  X_world = R^T * (X_cam - t)
        world_from_cam_rot = rotation.T
        origin_world       = -world_from_cam_rot @ translation
        corners_world      = (world_from_cam_rot @ corners_cam.T).T + origin_world

        vertices = np.vstack([ origin_world[None, :], corners_world ])

        if world_transform is not None:
            vertices = vertices @ np.asarray(world_transform).T

        # 4 rays from optical center to the corners, plus a 4-segment loop around
        # the image plane — enough to read the camera's pose at a glance.
        edges = np.array([
            [ 0, 1 ], [ 0, 2 ], [ 0, 3 ], [ 0, 4 ],
            [ 1, 2 ], [ 2, 3 ], [ 3, 4 ], [ 4, 1 ],
        ])

        return trimesh.load_path(vertices[edges])

@register_camera_pose_estimator_driver(CameraPoseEstimatorDriverType.COLMAP)
class ColmapCameraPoseEstimatorService(CameraPoseEstimatorDriver):
    def __init__(self, id: str, config: CameraPoseEstimatorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return [
            *(super()._get_setup_requirements() or []),
            "pycolmap>=4.0",
            "trimesh>=4.0",
            "numpy"
        ]

    async def _run(self, action: CameraPoseEstimatorActionConfig, context: ComponentActionContext) -> Any:
        return await ColmapCameraPoseEstimatorAction(action, context, self.config).run()
