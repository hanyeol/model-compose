from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple, Optional, Dict, List, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import GVHMRHumanMeshRecoveryModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, GVHMRHumanMeshRecoveryModelActionConfig
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.package.installer import install_package_from_github, is_package_installed
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.model_3d import Model3DStreamResource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.utils.files import get_temporary_path
from ....base import ComponentActionContext, ModelTaskDriver
from ..common import HumanMeshRecoveryTaskAction

if TYPE_CHECKING:
    import torch

class GVHMRHumanMeshRecoveryTaskAction(HumanMeshRecoveryTaskAction):
    """Temporal SMPL-X recovery with GVHMR.

    GVHMR consumes a full frame sequence and regresses per-frame SMPL-X
    parameters together with a global-space camera trajectory. The input
    slots follow the ``pose-tracking`` contract: each request is one video's
    ordered frames, with either per-frame timestamps or a shared ``frame_rate``
    plus per-batch ``time_offset``.
    """
    config: GVHMRHumanMeshRecoveryModelActionConfig

    def __init__(
        self,
        config: GVHMRHumanMeshRecoveryModelActionConfig,
        model: Any,
        device: torch.device,
    ):
        super().__init__(config)

        self.model: Any = model
        self.device: torch.device = device

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, Any, bool, bool]:
        frames      = await context.render_image_array(self.config.frames)
        timestamps  = await context.render_array(self.config.timestamps) if self.config.timestamps is not None else None
        time_offset = await context.render_time(self.config.time_offset, 0.0)
        frame_rate  = await context.render_scalar(self.config.frame_rate, float)

        # `timestamps` overrides both `frame_rate` and `time_offset`; `frame_rate`
        # is required only when `timestamps` is unset (extrapolation needs it).
        if timestamps is None and (not frame_rate or frame_rate <= 0):
            raise ValueError(f"'frame_rate' must be > 0 when 'timestamps' is unset, got {frame_rate}")

        is_single_input    = isinstance(frames, ImageArrayValue)
        is_streaming_input = isinstance(frames, (StreamIterator, AsyncIterator))

        return (frames, timestamps, time_offset), frames, is_single_input, is_streaming_input

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        static_camera = await context.render_scalar(self.config.params.static_camera, bool)
        frame_rate    = await context.render_scalar(self.config.frame_rate, float)

        params.update({
            "static_camera": static_camera,
            "frame_rate":    frame_rate,
        })

        return params

    async def _recover_batch(
        self,
        inputs: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        def _recover() -> List[Dict[str, Any]]:
            return [ self._recover(frames, timestamps, offset, params) for (frames, timestamps, offset) in inputs ]

        return await self._run_in_executor(_recover)

    def _recover(
        self,
        frames: ImageArrayValue,
        timestamps: Optional[Any],
        offset: float,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        import numpy as np
        import torch

        frames = [ frame.convert("RGB") for frame in frames ]
        frame_size = frames[0].size
        frames = np.stack([ np.array(frame) for frame in frames ], axis=0)

        if timestamps is not None:
            timestamps = [ float(ts) for ts in timestamps ]
        else:
            timestamps = [ offset + index / params["frame_rate"] for index in range(frames.shape[0]) ]

        with torch.no_grad():
            prediction = self.model.predict({
                "frames":        torch.from_numpy(frames).to(self.device),
                "frame_rate":    params["frame_rate"],
                "static_camera": params["static_camera"],
            })

        return self._serialize(prediction, timestamps, frame_size, params)

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

        for index in range(frame_count):
            pose: Dict[str, Any] = { "timestamp": timestamps[index] }

            if params["return_metadata"]:
                smpl_params = prediction["smpl_params_global"]
                pose["metadata"] = {
                    "body_model":    "smpl-x",
                    "global_orient": smpl_params["global_orient"][index].cpu().numpy().tolist(),
                    "body_pose":     smpl_params["body_pose"][index].cpu().numpy().tolist(),
                    "betas":         smpl_params["betas"][index].cpu().numpy().tolist(),
                    "transl":        smpl_params["transl"][index].cpu().numpy().tolist(),
                }

            if params["return_joints_3d"]:
                pose["joints_3d"] = prediction["pred_joints_global"][index].cpu().numpy().tolist()

            if params["return_joints_2d"]:
                pose["joints_2d"] = prediction["pred_joints_2d"][index].cpu().numpy().tolist()

            if params["return_vertices"]:
                pose["vertices"] = prediction["pred_vertices_global"][index].cpu().numpy().tolist()

            if params["return_mesh"]:
                pose["mesh"] = self._export_mesh(prediction, index)

            poses.append(pose)

        result: Dict[str, Any] = {
            "poses":       poses,
            "frame_count": frame_count,
            "width":       width,
            "height":      height,
        }

        if params["return_camera"]:
            result["camera"] = {
                "intrinsics":  prediction["K_fullimg"].cpu().numpy().tolist(),
                "extrinsics":  prediction["cam_pose"].cpu().numpy().tolist(),
                "static":      params["static_camera"],
            }

        return result

    def _export_mesh(self, prediction: Dict[str, Any], index: int) -> Model3DStreamResource:
        import trimesh

        vertices = prediction["pred_vertices_global"][index].cpu().numpy()
        faces = self.model.smplx.faces

        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)

        output_path = get_temporary_path("glb")
        mesh.export(output_path)

        return Model3DStreamResource(
            FileStreamResource(output_path, auto_delete=True),
            format="glb",
            filename=f"mesh_{index:04d}.glb",
        )

class GVHMRHumanMeshRecoveryTaskDriver(ModelTaskDriver):
    config: GVHMRHumanMeshRecoveryModelComponentConfig

    def __init__(self, id: str, config: GVHMRHumanMeshRecoveryModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        # GVHMR pins torch==2.3.0 and bundles its own copy of DPVO + DROID-SLAM
        # with CUDA kernels; isolate the model worker so those pins don't leak
        # into the controller's stack.
        self._require_isolated_runtime()

        self.model: Optional[Any] = None
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [
            *torch_requirements("torch==2.3.0", "torchvision==0.18.0"),
            "transformers>=4.30",
            "huggingface_hub>=0.34.0,<1.0",
            "pytorch-lightning>=2.0",
            "hydra-core>=1.3",
            "omegaconf>=2.3",
            "smplx>=0.1.28",
            "trimesh>=4.0",
            "numpy>=1.23,<2",
            "opencv-python",
            "einops",
            "chumpy",
        ]

    async def _setup(self) -> None:
        if not is_package_installed("hmr4d"):
            # GVHMR's inference code lives in the `hmr4d` package shipped inside
            # the upstream repo; install directly from the git tree.
            await install_package_from_github(
                module_name="hmr4d",
                repo_url="https://github.com/zju3dv/GVHMR.git",
                source_path=".",
                pip_options=[ "--no-build-isolation" ],
            )

    async def _load_model(self) -> None:
        self.model, self.device = await self._load_pipeline()

    async def _unload_model(self) -> None:
        self.model = None
        self.device = None

    async def _load_pipeline(self) -> Tuple[Any, torch.device]:
        # GVHMR's ViT backbone and DPVO CUDA kernels run on CUDA only.
        device = self._resolve_device(self.config.device)

        if device.type != "cuda":
            raise RuntimeError(
                f"Component '{self.id}': GVHMR requires a CUDA device, "
                f"but resolved device is '{device.type}'. Set component.device to "
                "'cuda' or a specific 'cuda:N' index."
            )

        model_path = await self._provision_model(self.config.model, prefetch=True)
        smplx_path = await self._provision_model(self.config.smplx.model, prefetch=True)

        def _load() -> Any:
            import hydra
            from hydra import compose, initialize_config_dir
            from hmr4d.utils.pylogger import Log
            from hmr4d.utils.net_utils import load_pretrained_model
            import os

            config_dir = os.path.join(os.path.dirname(hydra.__file__), "..", "hmr4d", "configs")
            with initialize_config_dir(config_dir=config_dir, version_base="1.3"):
                cfg = compose(config_name="demo")

            # Rebind the SMPL-X body-model path to honor the user-provided
            # ``smplx`` submodule rather than GVHMR's hard-coded
            # ``inputs/checkpoints/body_models/smplx/`` default.
            cfg.model.smplx.model_path = smplx_path

            model = hydra.utils.instantiate(cfg.model, _recursive_=False)
            load_pretrained_model(model, os.path.join(model_path, "gvhmr/mixed/mixed.ckpt"))
            model.to(str(device)).eval()

            Log.info(f"GVHMR loaded: {model_path}")

            return model

        model = await self._run_in_executor(_load)

        return model, device

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await GVHMRHumanMeshRecoveryTaskAction(
            action,
            self.model,
            self.device,
        ).run(context)
