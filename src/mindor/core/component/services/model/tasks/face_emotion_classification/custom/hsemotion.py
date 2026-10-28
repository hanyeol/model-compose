from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple, Optional, Dict, List, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, HSEmotionFaceEmotionClassificationModelActionConfig
from mindor.core.foundation.package.onnxruntime import get_onnxruntime_distributions
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.logger import logging
from ..common import FaceEmotionClassificationTaskAction
from ....base import ComponentActionContext, ModelTaskDriver
from ....utils.onnxruntime import resolve_onnx_providers
from PIL import Image as PILImage

if TYPE_CHECKING:
    import numpy as np
    import onnxruntime as ort

# AffectNet 8-class label order used by HSEmotion's `enet_b0_8_best_afew` checkpoint.
# The ONNX graph outputs logits in this exact index order.
_HSEMOTION_AFFECTNET8_LABELS: List[str] = [
    "Anger",
    "Contempt",
    "Disgust",
    "Fear",
    "Happiness",
    "Neutral",
    "Sadness",
    "Surprise",
]

_INPUT_IMAGE_SIZE: Tuple[int, int] = (224, 224)
_IMAGENET_MEAN: Tuple[float, float, float] = (0.485, 0.456, 0.406)
_IMAGENET_STD: Tuple[float, float, float]  = (0.229, 0.224, 0.225)

class HSEmotionFaceEmotionClassificationTaskAction(FaceEmotionClassificationTaskAction):
    config: HSEmotionFaceEmotionClassificationModelActionConfig

    def __init__(
        self,
        config: HSEmotionFaceEmotionClassificationModelActionConfig,
        session: ort.InferenceSession,
        input_name: str,
        labels: List[str],
    ):
        super().__init__(config, labels)

        self.session: ort.InferenceSession = session
        self.input_name: str = input_name

    async def _classify_batch(
        self,
        images: List[PILImage.Image],
        params: Dict[str, Any],
        labels: List[str],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        def _classify() -> List[Dict[str, Any]]:
            import numpy as np

            batch = np.stack([ self._preprocess_image(image) for image in images ], axis=0)
            logits = self.session.run(None, { self.input_name: batch })[0]

            # Softmax per row.
            shifted = logits - logits.max(axis=1, keepdims=True)
            exps = np.exp(shifted)
            probs = exps / exps.sum(axis=1, keepdims=True)

            predictions: List[Dict[str, Any]] = []

            for prob in probs:
                predicted_index = int(np.argmax(prob))
                prediction: Dict[str, Any] = {
                    "label":    labels[predicted_index],
                    "label_id": predicted_index,
                }

                if params["return_probabilities"]:
                    prediction["probabilities"] = prob.tolist()

                predictions.append(prediction)

            return predictions

        return await self._run_in_executor(_classify)

    @staticmethod
    def _preprocess_image(image: PILImage.Image) -> np.ndarray:
        import numpy as np

        image = image.convert("RGB").resize(_INPUT_IMAGE_SIZE, PILImage.BILINEAR)
        array = np.asarray(image, dtype=np.float32) / 255.0
        array = (array - np.array(_IMAGENET_MEAN, dtype=np.float32)) / np.array(_IMAGENET_STD, dtype=np.float32)

        return np.transpose(array, (2, 0, 1))

class HSEmotionFaceEmotionClassificationTaskDriver(ModelTaskDriver):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.session: Optional[ort.InferenceSession] = None
        self.input_name: str = ""
        self.labels: List[str] = _HSEMOTION_AFFECTNET8_LABELS

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [
            ("onnxruntime", get_onnxruntime_distributions()),
            "numpy",
        ]

    async def _load_model(self) -> None:
        self.session, self.input_name = await self._load_onnx_session()

    async def _unload_model(self) -> None:
        self.session = None
        self.input_name = ""

    async def _load_onnx_session(self) -> Tuple[ort.InferenceSession, str]:
        import onnxruntime as ort

        model_path = await self._provision_model(self.config.model, prefetch=True)
        providers = resolve_onnx_providers()

        logging.debug(f"HSEmotion providers: {providers}")

        def _load() -> Tuple[ort.InferenceSession, str]:
            session = ort.InferenceSession(model_path, providers=providers)
            input_name = session.get_inputs()[0].name

            return session, input_name

        return await self._run_in_executor(_load)

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await HSEmotionFaceEmotionClassificationTaskAction(
            action,
            self.session,
            self.input_name,
            self.labels,
        ).run(context)
