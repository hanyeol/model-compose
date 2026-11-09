from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple, Optional, Dict, List, Any
from mindor.dsl.schema.component import GVHMRHumanMeshRecoveryModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, GVHMRHumanMeshRecoveryModelActionConfig
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.model_3d import Model3DStreamResource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.utils.files import get_temporary_path
from ....base import ComponentActionContext, ModelTaskDriver
from ..common import HumanMeshRecoveryTaskAction
import os

if TYPE_CHECKING:
    import torch

# COCO 17 keypoints in the order pose-tracking's `return_keypoints` emits them
# (natural layout) — upstream VitPose outputs the same order, so passing the
# flattened kp2d through to GVHMR.predict needs no reindexing.
_COCO17_KEYPOINT_COUNT = 17

class GVHMRHumanMeshRecoveryTaskAction(HumanMeshRecoveryTaskAction):
    """Temporal SMPL-X recovery with GVHMR (ryanrudes/gvhmr package).

    Replaces upstream's video-centric demo pipeline (YOLO + VitPose + HMR2 ViT
    + SimpleVO on an on-disk mp4) with an in-memory contract:

    - ``frames``: the ordered PIL frames for one video.
    - ``tracks``: the paired pose-tracking `return_detections: true` output,
      which already carries bounding boxes and COCO-17 keypoints. The driver
      reuses them and skips YOLO / VitPose entirely.

    The driver still runs the HMR2 ViT feature extractor and SimpleVO's
    SIFT + two-view camera estimator itself — neither has a model-compose
    equivalent to delegate to.
    """
    config: GVHMRHumanMeshRecoveryModelActionConfig

    def __init__(
        self,
        config: GVHMRHumanMeshRecoveryModelActionConfig,
        pipeline: Dict[str, Any],
        device: torch.device,
    ):
        super().__init__(config)

        self.pipeline: Dict[str, Any] = pipeline
        self.device: torch.device = device

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, Any, bool, bool]:
        frames     = await context.render_image_array(self.config.frames)
        tracks     = await context.render_array(self.config.tracks)
        timestamps = await context.render_array(self.config.timestamps) if self.config.timestamps is not None else None
        frame_rate = await context.render_scalar(self.config.frame_rate, float)

        if timestamps is None and (not frame_rate or frame_rate <= 0):
            raise ValueError(f"'frame_rate' must be > 0 when 'timestamps' is unset, got {frame_rate}")

        # One request == one video. Wrap the inputs in a single-item slot tuple
        # so the base action's batch loop dispatches a single `_recover`.
        return ((frames,), (tracks,), (timestamps,), (frame_rate,)), frames, True, False

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        static_camera = await context.render_scalar(self.config.params.static_camera, bool)
        focal_length  = await context.render_scalar(self.config.params.focal_length, float)
        track_id      = await context.render_scalar(self.config.params.track_id, int)

        params.update({
            "static_camera": static_camera,
            "focal_length":  focal_length,
            "track_id":      track_id,
        })

        return params

    async def _recover_batch(
        self,
        inputs: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        for frames, tracks, timestamps, frame_rate in inputs:
            results.append(await self._recover(frames, tracks, timestamps, frame_rate, params))

        return results

    async def _recover(
        self,
        frames: ImageArrayValue,
        tracks: Any,
        timestamps: Optional[List[float]],
        frame_rate: Optional[float],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        from gvhmr.utils.geo.hmr_cam import get_bbx_xys_from_xyxy, estimate_K, create_camera_sensor
        from gvhmr.utils.geo_transform import compute_cam_angvel
        from gvhmr.network.hmr2.utils.preproc import crop_and_resize, IMAGE_MEAN, IMAGE_STD
        import numpy as np
        import torch

        # GVHMR's network consumes the whole clip at once, so collect any
        # streaming sources up front before entering the sync executor path.
        # `frames`/`tracks` may arrive as ImageArrayValue/ArrayValue (with
        # `.collect()`) or as a raw StreamChunkIterator (no `.collect()`), so
        # iterate uniformly instead.
        frames = [ frame async for frame in frames ]
        tracks = [ track async for track in tracks ]

        frames_np = np.stack([ np.array(frame.convert("RGB")) for frame in frames ], axis=0)
        frame_count, height, width, _ = frames_np.shape

        if timestamps is None:
            timestamps = [ index / frame_rate for index in range(frame_count) ]
        else:
            timestamps = [ float(ts) for ts in timestamps ]

        bbx_xyxy, kp2d = self._tracks_to_arrays(tracks, frame_count, params["track_id"])
        bbx_xys = get_bbx_xys_from_xyxy(torch.from_numpy(bbx_xyxy).float(), base_enlarge=1.2)

        def _recover() -> Dict[str, Any]:
            imgs_tensor = self._crop_frames_for_vit(frames_np, bbx_xys, crop_and_resize, IMAGE_MEAN, IMAGE_STD)

            with torch.no_grad():
                f_imgseq = self.pipeline["extractor"].extract_video_features(imgs_tensor, bbx_xys).float()

            if params["static_camera"]:
                R_w2c = torch.eye(3).repeat(frame_count, 1, 1)
            else:
                R_w2c = self._run_simple_vo(frames_np, params["focal_length"])

            if params["focal_length"] is not None:
                _, _, K_intrinsics = create_camera_sensor(width, height, params["focal_length"])
                K_fullimg = K_intrinsics.repeat(frame_count, 1, 1)
            else:
                K_fullimg = estimate_K(width, height).repeat(frame_count, 1, 1)

            data = {
                "length":     torch.tensor(frame_count),
                "bbx_xys":    bbx_xys,
                "kp2d":       torch.from_numpy(kp2d).float(),
                "K_fullimg":  K_fullimg,
                "cam_angvel": compute_cam_angvel(R_w2c),
                "f_imgseq":   f_imgseq,
            }

            with torch.no_grad():
                return self.pipeline["model"].predict(data, static_cam=params["static_camera"])

        prediction = await self._run_in_executor(_recover)

        return self._serialize(prediction, timestamps, (width, height), params)

    @staticmethod
    def _tracks_to_arrays(
        tracks: Any,
        frame_count: int,
        track_id: Optional[int],
    ) -> Tuple[Any, Any]:
        """Collapse pose-tracking detections into per-frame bbx_xyxy + kp2d.

        Picks the chosen track (or the longest one when ``track_id`` is None),
        then fills missing frames by holding the last seen pose — GVHMR expects
        a dense per-frame tensor.
        """
        import numpy as np

        if not isinstance(tracks, list):
            raise TypeError(f"'tracks' must be a list of per-frame detections, got {type(tracks).__name__}")

        poses_by_track: Dict[int, Dict[int, Dict[str, Any]]] = {}

        for frame in tracks:
            frame_number = frame.get("number")

            if frame_number is None or frame_number >= frame_count:
                continue

            for pose in frame.get("poses", []):
                if "keypoints" not in pose:
                    raise ValueError("Pose-tracking detections must include 'keypoints' (COCO 17); set 'return_keypoints: true' on the tracker.")

                poses_by_track.setdefault(pose["track_id"], {})[frame_number] = pose

        if not poses_by_track:
            raise ValueError("Pose-tracking detections are empty; GVHMR needs at least one tracked person.")

        if track_id is not None:
            if track_id not in poses_by_track:
                raise ValueError(f"'track_id' {track_id} not found in tracks; available: {sorted(poses_by_track.keys())}")

            selected = poses_by_track[track_id]
        else:
            selected = max(poses_by_track.values(), key=len)

        bbx_xyxy = np.zeros((frame_count, 4), dtype=np.float32)
        kp2d     = np.zeros((frame_count, _COCO17_KEYPOINT_COUNT, 3), dtype=np.float32)
        last_pose: Optional[Dict[str, Any]] = None

        for frame_number in range(frame_count):
            pose = selected.get(frame_number, last_pose)

            if pose is None:
                continue

            last_pose = pose

            box = pose["bounding_box"]
            bbx_xyxy[frame_number] = [ box["x"], box["y"], box["x"] + box["width"], box["y"] + box["height"] ]

            for keypoint_index, keypoint in enumerate(pose["keypoints"][:_COCO17_KEYPOINT_COUNT]):
                kp2d[frame_number, keypoint_index] = [ keypoint["x"], keypoint["y"], keypoint.get("visibility", 1.0) ]

        return bbx_xyxy, kp2d

    @staticmethod
    def _crop_frames_for_vit(
        frames_np: Any,
        bbx_xys: Any,
        crop_and_resize: Any,
        image_mean: Any,
        image_std: Any,
        img_ds: float = 0.5,
        img_dst_size: int = 256,
    ) -> Any:
        """Mirror `gvhmr.utils.imgcrop.get_batch` on an in-memory frame stack so
        we avoid round-tripping frames through a tempfile mp4."""
        import numpy as np
        import torch, cv2

        gt_bbx_size_ds = bbx_xys[:, 2].numpy() * img_ds
        ds_factors = (gt_bbx_size_ds / img_dst_size / 2.0)
        frames_ds = np.stack([ cv2.resize(frame, (0, 0), fx=img_ds, fy=img_ds) for frame in frames_np ])
        frames_ds = np.stack([
            cv2.GaussianBlur(frame, (5, 5), (factor - 1) / 2) if factor > 1.1 else frame
            for frame, factor in zip(frames_ds, ds_factors)
        ])

        cropped: List[Any] = []
        for frame_ds, bbx in zip(frames_ds, bbx_xys.numpy()):
            crop, _ = crop_and_resize(frame_ds, bbx[:2] * img_ds, bbx[2] * img_ds, img_dst_size, enlarge_ratio=1.0)
            cropped.append(crop)

        imgs = torch.from_numpy(np.stack(cropped))
        imgs = ((imgs / 255.0 - image_mean) / image_std).permute(0, 3, 1, 2)

        return imgs

    def _run_simple_vo(self, frames_np: Any, focal_length: Optional[float]) -> Any:
        """Drive SimpleVO's two-view SIFT solver on in-memory frames — the
        public `SimpleVO.compute()` wrapper only accepts video paths, but the
        underlying `Matcher` + `TwoPairSolver` happily take numpy frames."""
        from gvhmr.utils.preproc.relpose.simple_vo import focal_length_from_mm, interpolate_missing_frames
        from gvhmr.utils.preproc.relpose.matcher_wrapper import Matcher
        from gvhmr.utils.preproc.relpose.solver_two_view import TwoPairSolver, CameraParams
        import numpy as np
        import torch, cv2

        scale = 0.5
        step = 8
        frame_count = frames_np.shape[0]

        sample_idxs = np.arange(0, frame_count, step)

        if sample_idxs[-1] != frame_count - 1:
            sample_idxs = np.concatenate([ sample_idxs, [ frame_count - 1 ] ])

        sampled = np.stack([
            cv2.resize(frames_np[idx], (0, 0), fx=scale, fy=scale)
            for idx in sample_idxs
        ])

        _, height, width, _ = sampled.shape
        focal_length_mm = focal_length if focal_length is not None else 24
        focal_length_px = focal_length_from_mm(width, height, focal_length_mm)

        solver = TwoPairSolver(
            CameraParams(width, height, focal_length=focal_length_px),
            solver="pycolmap",
        )

        matcher = Matcher("sift")

        T_w2c_list = [ np.eye(4) ]
        prev_frame = sampled[0]

        for current_frame in sampled[1:]:
            pts0, pts1 = matcher.match_np(prev_frame, current_frame)
            T_delta = solver.solve(pts0, pts1)

            # A degenerate two-view geometry (fast motion / low texture) hands
            # back None; fall back to the identity so the carry-forward chain
            # still advances.
            if T_delta is None:
                T_delta = np.eye(4, dtype=np.float32)

            T_w2c_list.append(T_delta @ T_w2c_list[-1])
            prev_frame = current_frame

        T_w2c_list = interpolate_missing_frames(T_w2c_list, sample_idxs)

        return torch.from_numpy(np.stack([ T[:3, :3] for T in T_w2c_list ])).float()

    def _serialize(
        self,
        prediction: Dict[str, Any],
        timestamps: List[float],
        frame_size: Tuple[int, int],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        width, height = frame_size
        frame_count = len(timestamps)

        poses: List[Dict[str, Any]] = []

        smpl_params = prediction["smpl_params_global"]

        for index in range(frame_count):
            pose: Dict[str, Any] = { "timestamp": timestamps[index] }

            if params["return_metadata"]:
                pose["metadata"] = {
                    "body_model":    "smpl-x",
                    "global_orient": smpl_params["global_orient"][index].cpu().numpy().tolist(),
                    "body_pose":     smpl_params["body_pose"][index].cpu().numpy().tolist(),
                    "betas":         smpl_params["betas"][index].cpu().numpy().tolist(),
                    "transl":        smpl_params["transl"][index].cpu().numpy().tolist(),
                }

            if params["return_vertices"] or params["return_mesh"] or params["return_joints_3d"]:
                vertices, joints, faces = self._decode_smplx(prediction["smpl_params_global"], index)

                if params["return_joints_3d"]:
                    pose["joints_3d"] = joints.cpu().numpy().tolist()

                if params["return_vertices"]:
                    pose["vertices"] = vertices.cpu().numpy().tolist()

                if params["return_mesh"]:
                    pose["mesh"] = self._export_mesh(vertices, faces, index)

            poses.append(pose)

        result: Dict[str, Any] = {
            "poses":       poses,
            "frame_count": frame_count,
            "width":       width,
            "height":      height,
        }

        if params["return_camera"]:
            result["camera"] = {
                "intrinsics": prediction["K_fullimg"].cpu().numpy().tolist(),
                "static":     params["static_camera"],
            }

        return result

    def _decode_smplx(self, smpl_params_global: Dict[str, Any], index: int) -> Tuple[Any, Any, Any]:
        """Run the shared SMPL-X body model on one frame's params.

        The GVHMR `predict` dict carries SMPL-X *parameters*, not the decoded
        mesh — joints/vertices are reconstructed on demand so the recovery
        stays fast when the caller only wants metadata. `pipeline["smplx"]`
        is `gvhmr.utils.smplx_utils.make_smplx("supermotion")`, already on the
        pipeline's device.
        """
        import torch

        params: Dict[str, Any] = {}

        for key in ("global_orient", "body_pose", "betas", "transl"):
            params[key] = smpl_params_global[key][index].unsqueeze(0).to(self.device)

        with torch.no_grad():
            output = self.pipeline["smplx"](**params)

        return output.vertices[0], output.joints[0], self.pipeline["smplx"].faces

    def _export_mesh(self, vertices: Any, faces: Any, index: int) -> Model3DStreamResource:
        import numpy as np
        import trimesh

        mesh = trimesh.Trimesh(vertices=vertices.cpu().numpy(), faces=faces, process=False)

        # GVHMR predicts vertices in a gravity-aligned world frame (+Y down,
        # +Z forward); rotate 180° around X to match glTF's +Y-up convention so
        # viewers show the subject upright.
        mesh.apply_transform(trimesh.transformations.rotation_matrix(np.radians(180), [1, 0, 0]))

        output_path = get_temporary_path("glb")
        mesh.export(output_path, file_type="glb")

        return Model3DStreamResource(
            FileStreamResource(output_path, auto_delete=True),
            format="glb",
            filename=f"mesh_{index:04d}.glb",
        )

class GVHMRHumanMeshRecoveryTaskDriver(ModelTaskDriver):
    config: GVHMRHumanMeshRecoveryModelComponentConfig

    def __init__(self, id: str, config: GVHMRHumanMeshRecoveryModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        # GVHMR vendors its own pytorch3d + a frozen HMR2 ViT backbone; pin the
        # worker to an isolated runtime so those don't leak into the controller.
        self._require_isolated_runtime()

        self.pipeline: Optional[Dict[str, Any]] = None
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [
            *torch_requirements("torch>=2.5,<2.6", "torchvision>=0.20,<0.21"),
            "gvhmr",
            "yacs",
            "pycolmap",
        ]

    async def _load_model(self) -> None:
        self.pipeline, self.device = await self._load_pipeline()

    async def _unload_model(self) -> None:
        self.pipeline = None
        self.device = None

    async def _load_pipeline(self) -> Tuple[Dict[str, Any], torch.device]:
        device = self._resolve_device(self.config.device)

        if device.type != "cuda":
            raise RuntimeError(
                f"Component '{self.id}': GVHMR requires a CUDA device, "
                f"but resolved device is '{device.type}'. Set component.device to "
                "'cuda' or a specific 'cuda:N' index."
            )

        model_path       = await self._provision_model(self.config.model, prefetch=True)
        smplx_model_path = await self._provision_model(self.config.smplx_model, prefetch=True)

        if os.path.isfile(smplx_model_path):
            smplx_model_path = os.path.dirname(smplx_model_path)

        def _load() -> Dict[str, Any]:
            # `gvhmr.utils.assets` captures these at import time, so set them
            # before the gvhmr import below. Absolute paths, since gvhmr reads
            # the env vars from an unknown cwd.
            os.environ["GVHMR_CHECKPOINTS"] = os.path.abspath(model_path)
            os.environ["GVHMR_BODY_MODELS"] = os.path.dirname(os.path.abspath(smplx_model_path))

            from gvhmr import GVHMR
            from gvhmr.utils.preproc.vitfeat_extractor import Extractor
            from gvhmr.utils.smplx_utils import make_smplx

            model = GVHMR.from_pretrained(
                ckpt_path=os.path.join(model_path, "gvhmr/gvhmr_siga24_release.ckpt"),
                device=str(device),
            )
            model = model.to(str(device)).eval()

            smplx_model = make_smplx("supermotion").to(str(device)).eval()
            extractor = Extractor(tqdm_leave=False)

            return {
                "model":     model,
                "extractor": extractor,
                "smplx":     smplx_model,
            }

        pipeline = await self._run_in_executor(_load)

        return pipeline, device

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await GVHMRHumanMeshRecoveryTaskAction(
            action,
            self.pipeline,
            self.device,
        ).run(context)
