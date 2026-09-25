from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Tuple, Dict, List, Any
from mindor.dsl.schema.component import CameraPoseEstimatorComponentConfig, ColmapMatcherType
from mindor.dsl.schema.action import CameraPoseEstimatorActionConfig
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.logger import logging
from ..base import CameraPoseEstimatorDriver, CameraPoseEstimatorDriverType, register_camera_pose_estimator_driver
from ..base import ComponentActionContext
from .common import CameraPoseEstimatorAction
import os, shutil

if TYPE_CHECKING:
    import pycolmap

class ColmapCameraPoseEstimatorAction(CameraPoseEstimatorAction):
    def __init__(
        self,
        config: CameraPoseEstimatorActionConfig,
        context: ComponentActionContext,
        component_config: CameraPoseEstimatorComponentConfig,
    ):
        super().__init__(config, context)

        self.component_config: CameraPoseEstimatorComponentConfig = component_config

    async def _resolve_params(self) -> Dict[str, Any]:
        params = await super()._resolve_params()

        # COLMAP camera model names are UPPER_SNAKE (e.g. `OPENCV_FISHEYE`);
        # the DSL enum values are lowercase kebab (`opencv-fisheye`).
        params.update({
            "camera_model":  self.component_config.camera_model.value.replace("-", "_").upper(),
            "single_camera": self.component_config.single_camera,
            "matcher":       self.component_config.matcher.value,
            "use_gpu":       self.component_config.use_gpu,
            "num_threads":   self.component_config.num_threads,
        })

        return params

    async def _estimate_batch(
        self,
        inputs: List[Tuple[Optional[ImageArrayValue], str]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        for images, workspace_dir in inputs:
            if images is None:
                if not os.path.isdir(os.path.join(workspace_dir, "images")):
                    raise ValueError(f"no images provided and no 'images/' folder found under {workspace_dir}")
            else:
                await self._save_images(images, os.path.join(workspace_dir, "images"))

            result = await self._run_in_executor(self._run_pipeline, workspace_dir, params)
            results.append(result)

        return results

    async def _save_images(self, images: ImageArrayValue, images_dir: str) -> None:
        # Wipe anything saved by a prior run so pycolmap doesn't pick up
        # stale files mixed in with the current request's images.
        if os.path.isdir(images_dir):
            shutil.rmtree(images_dir)

        os.makedirs(images_dir)

        index = 0
        async for image in images:
            image_path = os.path.join(images_dir, f"image_{index:04d}.png")
            await self._run_in_executor(image.save, image_path, format="PNG")
            index += 1

        if index == 0:
            raise ValueError("images array is empty")

    def _run_pipeline(self, workspace_dir: str, params: Dict[str, Any]) -> Dict[str, Any]:
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

        camera_mode = pycolmap.CameraMode.SINGLE if params["single_camera"] else pycolmap.CameraMode.PER_IMAGE
        device = pycolmap.Device.cuda if params["use_gpu"] else pycolmap.Device.cpu

        reader_options = pycolmap.ImageReaderOptions()
        reader_options.camera_model = params["camera_model"]

        logging.info(
            "COLMAP extract_features (workspace=%s, camera_model=%s, camera_mode=%s, device=%s)",
            workspace_dir, params["camera_model"], camera_mode.name, device.name,
        )

        pycolmap.extract_features(
            database_path,
            image_dir,
            camera_mode=camera_mode,
            reader_options=reader_options,
            device=device,
        )

        matcher_fn = self._resolve_matcher(pycolmap, params["matcher"])

        logging.info("COLMAP %s (device=%s)", matcher_fn.__name__, device.name)

        matcher_fn(database_path, device=device)

        logging.info("COLMAP incremental_mapping (sparse=%s)", sparse_dir)

        reconstructions = pycolmap.incremental_mapping(database_path, image_dir, sparse_dir)

        if not reconstructions:
            raise RuntimeError("COLMAP incremental_mapping produced no reconstruction; check input images and matches.")

        # Pick the reconstruction with the most registered images. Other
        # partial reconstructions remain on disk under sparse/<n>/ for
        # inspection but are not summarised in the returned result.
        best_id = max(reconstructions, key=lambda i: reconstructions[i].num_reg_images())
        reconstruction = reconstructions[best_id]

        return self._build_result(workspace_dir, reconstruction, best_id)

    @staticmethod
    def _resolve_matcher(pycolmap_module: Any, matcher: str):
        matchers = {
            ColmapMatcherType.EXHAUSTIVE.value: pycolmap_module.match_exhaustive,
            ColmapMatcherType.SEQUENTIAL.value: pycolmap_module.match_sequential,
            ColmapMatcherType.SPATIAL.value:    pycolmap_module.match_spatial,
            ColmapMatcherType.VOCAB_TREE.value: pycolmap_module.match_vocabtree,
        }

        return matchers[matcher]

    @staticmethod
    def _build_result(workspace_dir: str, reconstruction: Any, sparse_index: int) -> Dict[str, Any]:
        cameras: List[Dict[str, Any]] = []

        for camera_id, camera in reconstruction.cameras.items():
            cameras.append({
                "id":     int(camera_id),
                "model":  camera.model_name,
                "width":  int(camera.width),
                "height": int(camera.height),
                "params": [ float(v) for v in camera.params ],
            })

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

        return {
            "workspace_dir": os.path.join(workspace_dir, "sparse", str(sparse_index)),
            "images_count":  int(reconstruction.num_reg_images()),
            "points_count":  int(reconstruction.num_points3D()),
            "cameras":       cameras,
            "poses":         poses,
        }

@register_camera_pose_estimator_driver(CameraPoseEstimatorDriverType.COLMAP)
class ColmapCameraPoseEstimatorService(CameraPoseEstimatorDriver):
    def __init__(self, id: str, config: CameraPoseEstimatorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return [ "pycolmap" ]

    async def _run(self, action: CameraPoseEstimatorActionConfig, context: ComponentActionContext) -> Any:
        return await ColmapCameraPoseEstimatorAction(action, context, self.config).run()
