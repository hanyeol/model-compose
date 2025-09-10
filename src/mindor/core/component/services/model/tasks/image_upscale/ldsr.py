from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, TypeAlias, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, LdsrImageUpscaleModelActionConfig
from mindor.core.logger import logging
from ...base import ComponentActionContext
from .common import ImageUpscaleTaskService, ImageUpscaleTaskAction
from PIL import Image as PILImage
import asyncio

if TYPE_CHECKING:
    from transformers import PreTrainedModel
    import torch

class LdsrImageUpscaleTaskAction(ImageUpscaleTaskAction):
    def __init__(self, config: LdsrImageUpscaleModelActionConfig, model: PreTrainedModel, device: torch.device):
        super().__init__(config, device)

        self.model: PreTrainedModel = model

    async def _upscale(self, images: List[PILImage.Image], params: Dict[str, Any]) -> List[PILImage.Image]:
        import torch
        import numpy as np
        from torchvision import transforms
        
        upscaled_images = []
        
        # Extract parameters
        steps = params.get("steps", 50)
        eta = params.get("eta", 1.0)
        downsample_method = params.get("downsample_method", "Lanczos")
        half_precision = params.get("half_precision", False)
        
        # Setup transforms
        to_tensor = transforms.ToTensor()
        to_pil    = transforms.ToPILImage()
        
        for image in images:
            # Apply downsampling method if needed for preprocessing
            if downsample_method is not None:
                image = self._downsample_image(image, downsample_method)

            # Convert to tensor
            if half_precision:
                tensor_image = to_tensor(image).unsqueeze(0).to(self.device).half()
            else:
                tensor_image = to_tensor(image).unsqueeze(0).to(self.device)

            # Run LDSR inference with diffusion steps
            with torch.no_grad():
                # LDSR uses diffusion process with specified steps and eta
                upscaled_tensor = self._run_ldsr_diffusion(tensor_image, steps, eta)

            # Convert back to PIL image
            upscaled_tensor = upscaled_tensor.squeeze(0).cpu().float()
            upscaled_image  = to_pil(upscaled_tensor)
            
            upscaled_images.append(upscaled_image)

        return upscaled_images
    
    def _run_ldsr_diffusion(self, input: torch.Tensor, steps: int, eta: float) -> torch.Tensor:
        pass

    async def _resolve_upscale_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        
        params["steps"            ] = await context.render_variable(self.config.params.steps)
        params["eta"              ] = await context.render_variable(self.config.params.eta)
        params["downsample_method"] = await context.render_variable(self.config.params.downsample_method)
        params["half_precision"   ] = await context.render_variable(self.config.params.half_precision)
        
        return params

class LdsrImageUpscaleTaskService(ImageUpscaleTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[PreTrainedModel] = None
        self.device: Optional[torch.device] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def _serve(self) -> None:
        try:
            self.model, self.device = self._load_pretrained_model()
            logging.info(f"Model loaded successfully on device '{self.device}': {self.config.model}")
        except Exception as e:
            logging.error(f"Failed to load model '{self.config.model}': {e}")
            raise

    async def _shutdown(self) -> None:
        self.model  = None
        self.device = None

    def _load_pretrained_model(self) -> Tuple[PreTrainedModel, torch.device]:
        pass

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return LdsrImageUpscaleTaskAction(action, self.model).run(context)
