from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, TypeAlias, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, EsrganImageUpscaleModelActionConfig
from mindor.core.logger import logging
from ...base import ComponentActionContext
from .common import ImageUpscaleTaskService, ImageUpscaleTaskAction
from PIL import Image as PILImage
import asyncio

if TYPE_CHECKING:
    from basicsr.archs.rrdbnet_arch import RRDBNet
    import torch

class EsrganImageUpscaleTaskAction(ImageUpscaleTaskAction):
    def __init__(self, config: EsrganImageUpscaleModelActionConfig, model: RRDBNet, device: torch.device):
        super().__init__(config, device)

        self.model: RRDBNet = model

    async def _upscale(self, images: List[PILImage.Image], params: Dict[str, Any]) -> List[PILImage.Image]:
        pass

    async def _resolve_upscale_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        pass

class EsrganImageUpscaleTaskService(ImageUpscaleTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[RRDBNet] = None
        self.device: Optional[torch.device] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "basicsr", "torchvision" ]

    async def _serve(self) -> None:
        try:
            self.model, self.device = self._load_pretrained_model()
            logging.info(f"Model loaded successfully on device '{self.device}': {self.config.model}")
        except Exception as e:
            logging.error(f"Failed to load model '{self.config.model}': {e}")
            raise

    async def _shutdown(self) -> None:
        self.model = None
        self.device = None

    def _load_pretrained_model(self) -> Tuple[RRDBNet, torch.device]:
        from basicsr.archs.rrdbnet_arch import RRDBNet
            
        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=self.config.scale)
        model.load_state_dict(torch.load(self.config.model, map_location=("cpu"), strict=True))
        
        return model, None

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return EsrganImageUpscaleTaskAction(action, self.model).run(context)
