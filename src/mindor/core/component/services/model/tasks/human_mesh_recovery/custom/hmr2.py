from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple, Optional, Dict, List, Any
from mindor.dsl.schema.component import HMR2HumanMeshRecoveryModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, HMR2HumanMeshRecoveryModelActionConfig
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.package.installer import install_package, install_package_from_github, is_package_installed
from collections.abc import AsyncIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.model_3d import Model3DStreamResource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.utils.files import get_temporary_path
from ....base import ComponentActionContext, ModelTaskDriver
from ..common import HumanMeshRecoveryTaskAction
from PIL import Image as PILImage
from pathlib import Path

if TYPE_CHECKING:
    import numpy as np
    import torch

_VITDET_CHECKPOINT_URL = "https://dl.fbaipublicfiles.com/detectron2/ViTDet/COCO/cascade_mask_rcnn_vitdet_h/f328730692/model_final_f05665.pkl"

class HMR2HumanMeshRecoveryTaskAction(HumanMeshRecoveryTaskAction):
    """Single-image SMPL recovery with HMR2.0 (4D-Humans).

    HMR2 regresses SMPL parameters from a cropped person patch. Each input
    image is first run through ViTDet to detect person bounding boxes, then
    the bundled ``ViTDetDataset`` crops a square patch around each box at
    ``rescale_factor`` times its own size.
    """
    config: HMR2HumanMeshRecoveryModelActionConfig

    def __init__(
        self,
        config: HMR2HumanMeshRecoveryModelActionConfig,
        model: Any,
        model_cfg: Any,
        detector: Any,
        device: torch.device,
    ):
        super().__init__(config)

        self.model: Any = model
        self.model_cfg: Any = model_cfg
        self.detector: Any = detector
        self.device: torch.device = device

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, Any, bool, bool]:
        image = await context.render_image(self.config.image)

        is_single_input    = not isinstance(image, (list, StreamIterator, AsyncIterator))
        is_streaming_input = isinstance(image, (StreamIterator, AsyncIterator))

        return (image,), image, is_single_input, is_streaming_input

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        max_person_count = await context.render_scalar(self.config.max_person_count, int)
        rescale_factor   = await context.render_scalar(self.config.params.rescale_factor, float)

        if max_person_count < 1:
            raise ValueError(f"'max_person_count' must be >= 1, got {max_person_count}")

        if rescale_factor <= 0.0:
            raise ValueError(f"'rescale_factor' must be > 0.0, got {rescale_factor}")

        params.update({
            "max_person_count": max_person_count,
            "rescale_factor":   rescale_factor,
        })

        return params

    async def _recover_batch(
        self,
        inputs: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        def _recover() -> List[Dict[str, Any]]:
            return [ self._recover(image, params) for (image,) in inputs ]

        return await self._run_in_executor(_recover)

    def _recover(self, image: PILImage.Image, params: Dict[str, Any]) -> Dict[str, Any]:
        import numpy as np
        import torch
        from hmr2.datasets.vitdet_dataset import ViTDetDataset

        width, height = image.size
        image = np.array(image.convert("RGB"))[:, :, ::-1].copy()

        boxes, box_scores = self._detect_persons(image, params)

        if boxes.shape[0] == 0:
            return { "people": [], "width": width, "height": height }

        dataset = ViTDetDataset(self.model_cfg, image, boxes, rescale_factor=params["rescale_factor"])
        dataloader = torch.utils.data.DataLoader(dataset, batch_size=boxes.shape[0], shuffle=False, num_workers=0)

        people: List[Dict[str, Any]] = []

        for batch in dataloader:
            batch = { key: value.to(self.device) if isinstance(value, torch.Tensor) else value for key, value in batch.items() }

            with torch.no_grad():
                output = self.model(batch)

            for index in range(batch["img"].shape[0]):
                people.append(self._serialize_person(output, batch, index, float(box_scores[index]), params))

        return { "people": people, "width": width, "height": height }

    def _detect_persons(self, image: np.ndarray, params: Dict[str, Any]) -> Tuple[np.ndarray, np.ndarray]:
        import numpy as np

        instances = self.detector(image)["instances"]

        valid = (instances.pred_classes == 0) & (instances.scores > params["min_confidence"])
        boxes = instances.pred_boxes.tensor[valid].cpu().numpy()
        scores = instances.scores[valid].cpu().numpy()

        if boxes.shape[0] == 0:
            return np.empty((0, 4), dtype=np.float32), np.empty((0,), dtype=np.float32)

        order = np.argsort(-scores)[:params["max_person_count"]]

        return boxes[order], scores[order]

    def _serialize_person(self, output: Dict[str, Any], batch: Dict[str, Any], index: int, score: float, params: Dict[str, Any]) -> Dict[str, Any]:
        person: Dict[str, Any] = { "score": score }

        box_center = batch["box_center"][index].float().cpu().numpy()
        box_size = batch["box_size"][index].float().cpu().numpy()

        person["bounding_box"] = {
            "x":      int(box_center[0] - box_size / 2),
            "y":      int(box_center[1] - box_size / 2),
            "width":  int(box_size),
            "height": int(box_size),
        }

        if params["return_metadata"]:
            smpl_params = output["pred_smpl_params"]
            person["metadata"] = {
                "body_model":    "smpl",
                "global_orient": smpl_params["global_orient"][index].cpu().numpy().tolist(),
                "body_pose":     smpl_params["body_pose"][index].cpu().numpy().tolist(),
                "betas":         smpl_params["betas"][index].cpu().numpy().tolist(),
            }

        if params["return_joints_3d"]:
            person["joints_3d"] = output["pred_keypoints_3d"][index].cpu().numpy().tolist()

        if params["return_joints_2d"]:
            person["joints_2d"] = output["pred_keypoints_2d"][index].cpu().numpy().tolist()

        if params["return_vertices"]:
            person["vertices"] = output["pred_vertices"][index].cpu().numpy().tolist()

        if params["return_mesh"]:
            person["mesh"] = self._export_mesh(output, index)

        if params["return_camera"]:
            # HMR2 regresses a weak-perspective camera as (scale, tx, ty) in the
            # cropped patch frame; expose the translation under ``focal_length``
            # kept at the dataset constant used at training time.
            person["camera"] = {
                "focal_length":    float(self.model_cfg.EXTRA.FOCAL_LENGTH),
                "translation":     output["pred_cam_t"][index].cpu().numpy().tolist(),
                "principal_point": box_center.tolist(),
            }

        return person

    def _export_mesh(self, output: Dict[str, Any], index: int) -> Model3DStreamResource:
        import trimesh

        vertices = output["pred_vertices"][index].cpu().numpy()
        faces = self.model.smpl.faces

        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)

        output_path = get_temporary_path("glb")
        mesh.export(output_path)

        return Model3DStreamResource(
            FileStreamResource(output_path, auto_delete=True),
            format="glb",
            filename="mesh.glb",
        )

class HMR2HumanMeshRecoveryTaskDriver(ModelTaskDriver):
    config: HMR2HumanMeshRecoveryModelComponentConfig

    def __init__(self, id: str, config: HMR2HumanMeshRecoveryModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        # 4D-Humans pulls in Detectron2, which has to compile its CUDA extension
        # against the installed torch. Isolate the model worker so the build
        # products and torch pins do not leak into the controller's stack.
        self._require_isolated_runtime()

        self.model: Optional[Any] = None
        self.model_cfg: Optional[Any] = None
        self.detector: Optional[Any] = None
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [
            # 4D-Humans leaves torch unpinned upstream; cap below 2.6 because
            # its `torch.load(weights_only=True)` default breaks hmr2 and
            # detectron2 checkpoint loading. 2.4/2.5 are confirmed working
            # (upstream issue #179).
            *torch_requirements("torch>=2.4,<2.6", "torchvision>=0.19,<0.21"),
            "transformers>=4.30,<5",
            "huggingface_hub>=0.34.0,<1.0",
            "trimesh>=4.0",
            "numpy>=1.26",
            "opencv-python",
            "einops",
            "yacs",
            "pyrender",
            "smplx>=0.1.28",
            "scikit-image",
        ]

    async def _setup(self) -> None:
        if not is_package_installed("chumpy"):
            # Needed on sys.path to unpickle SMPL .pkl objects. `--no-build-isolation`
            # because chumpy's setup.py imports pip, which PEP 517's isolated env hides.
            await install_package("chumpy", pip_options=[ "--no-build-isolation" ])

        if not is_package_installed("hmr2"):
            # 4D-Humans ships `hmr2` as a git package without a PyPI release;
            # install it directly from the upstream tree.
            await install_package_from_github(
                module_name="hmr2",
                repo_url="https://github.com/shubham-goel/4D-Humans.git",
                source_path=".",
                pip_options=[ "--no-build-isolation" ],
            )

        if not is_package_installed("detectron2"):
            # Detectron2 is HMR2's upstream choice for ViTDet person detection.
            await install_package_from_github(
                module_name="detectron2",
                repo_url="https://github.com/facebookresearch/detectron2.git",
                source_path=".",
                pip_options=[ "--no-build-isolation" ],
            )

    async def _load_model(self) -> None:
        self.model, self.model_cfg, self.detector, self.device = await self._load_pipeline()

    async def _unload_model(self) -> None:
        self.model = None
        self.model_cfg = None
        self.detector = None
        self.device = None

    async def _load_pipeline(self) -> Tuple[Any, Any, Any, torch.device]:
        # HMR2's ViTPose backbone and Detectron2 kernels run on CUDA only — fail
        # loudly here rather than crash mid-run.
        device = self._resolve_device(self.config.device)

        if device.type != "cuda":
            raise RuntimeError(
                f"Component '{self.id}': HMR2 requires a CUDA device, "
                f"but resolved device is '{device.type}'. Set component.device to "
                "'cuda' or a specific 'cuda:N' index."
            )

        model_path = await self._provision_model(self.config.model, prefetch=True)
        smpl_path = await self._provision_model(self.config.smpl_model, prefetch=True)

        def _load_hmr2(checkpoint_path: str) -> Tuple[Any, Any]:
            """Drop-in replacement for ``hmr2.models.load_hmr2`` that honors
            the user-provided ``smpl_model`` path and the local extraction
            root for `data/*` assets.

            Upstream's ``load_hmr2`` calls ``check_smpl_exists`` against a
            hard-coded ``~/.cache/4DHumans/data/smpl/SMPL_NEUTRAL.pkl``
            before constructing the model, and ``update_cachedir=True``
            prefixes relative paths with the same hard-coded cache dir —
            neither honors our provisioned model path or the user's SMPL
            path. We repoint ``CACHE_DIR_4DHUMANS`` and override the SMPL
            path before ``HMR2.load_from_checkpoint`` builds its SMPLLayer.
            """
            from hmr2.models import HMR2
            from hmr2.configs import get_config
            import hmr2.configs

            hmr2.configs.CACHE_DIR_4DHUMANS = model_path

            model_cfg = get_config(
                str(Path(checkpoint_path).parent.parent / "model_config.yaml"),
                update_cachedir=True,
            )

            model_cfg.defrost()

            if model_cfg.MODEL.BACKBONE.TYPE == "vit" and "BBOX_SHAPE" not in model_cfg.MODEL:
                model_cfg.MODEL.BBOX_SHAPE = [ 192, 256 ]

            model_cfg.SMPL.MODEL_PATH = smpl_path
            model_cfg.freeze()

            model = HMR2.load_from_checkpoint(checkpoint_path, strict=False, cfg=model_cfg)

            return model, model_cfg

        def _load() -> Tuple[Any, Any, Any]:
            from hmr2.utils.utils_detectron2 import DefaultPredictor_Lazy
            from detectron2.config import LazyConfig
            import hmr2

            # The upstream tarball expands to `logs/train/multiruns/hmr2/0/
            # checkpoints/epoch=35-step=1000000.ckpt` plus a sibling
            # `model_config.yaml`.
            checkpoint_path = str(
                Path(model_path)
                / "logs" / "train" / "multiruns" / "hmr2" / "0"
                / "checkpoints" / "epoch=35-step=1000000.ckpt"
            )
            model, model_cfg = _load_hmr2(checkpoint_path)
            model.to(str(device)).eval()

            # ViTDet detector — config ships inside the hmr2 package, weights
            # are pulled on demand from fbaipublicfiles. Mirrors the upstream
            # `demo.py --detector vitdet` branch.
            detectron_cfg_path = Path(hmr2.__file__).parent / "configs" / "cascade_mask_rcnn_vitdet_h_75ep.py"
            detectron_cfg = LazyConfig.load(str(detectron_cfg_path))
            detectron_cfg.train.init_checkpoint = _VITDET_CHECKPOINT_URL

            for index in range(3):
                detectron_cfg.model.roi_heads.box_predictors[index].test_score_thresh = 0.25

            detector = DefaultPredictor_Lazy(detectron_cfg)

            return model, model_cfg, detector

        model, model_cfg, detector = await self._run_in_executor(_load)

        return model, model_cfg, detector, device

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await HMR2HumanMeshRecoveryTaskAction(
            action,
            self.model,
            self.model_cfg,
            self.detector,
            self.device,
        ).run(context)
