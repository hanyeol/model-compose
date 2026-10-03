from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import ImageTextScoringModelActionConfig
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.foundation.variable.text import TextArrayValue
from mindor.core.foundation.variable.atomic import AtomicDict
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from .....action.base import ComponentAction
from ...base import ComponentActionContext
from PIL import Image as PILImage

class ImageTextScore(AtomicDict):
    def __log__(self) -> str:
        cosine = self.get("cosine")
        if isinstance(cosine, list):
            return f"<ImageTextScore pairs={len(cosine)}>"
        return f"<ImageTextScore cosine={cosine:.4f}>"

class ImageTextScoringTaskAction(ComponentAction):
    def __init__(self, config: ImageTextScoringModelActionConfig):
        self.config: ImageTextScoringModelActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        image      = await context.render_image_array(self.config.image, single_as_array=True)
        text       = await context.render_text_array(self.config.text, single_as_array=True)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = isinstance(image, ImageArrayValue)
        is_direct_output = not self.config.output or self.config.output == "${result}"

        # Wrap a single (image_array, text_array) pair as one scoring job so the
        # BatchSourceIterator below iterates jobs, not elements within the array.
        image = [ image ] if is_single_input else image
        text  = [ text ] if is_single_input else text

        if isinstance(image, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_images, batch_texts in BatchSourceIterator((image, text), batch_size=batch_size or 1):
                    batch_results = await self._score_batch(batch_images, batch_texts, params, context.cancellation_token)
                    for result in batch_results:
                        context.register_source("result[]", result)
                        yield (await context.render_variable(self.config.output)) if not is_direct_output else result

            return _stream_output_generator()
        else:
            results: List[ImageTextScore] = []
            async for batch_images, batch_texts in BatchSourceIterator((image, text), batch_size=batch_size or 1):
                batch_results = await self._score_batch(batch_images, batch_texts, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _score_batch(
        self,
        batch_images: List[ImageArrayValue],
        batch_texts: List[TextArrayValue],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[ImageTextScore]:
        results: List[ImageTextScore] = []

        for images_array, texts_array in zip(batch_images, batch_texts):
            images = await images_array.collect()
            texts  = await texts_array.collect()
            mode   = self._resolve_scoring_mode(len(images), len(texts))
            score  = await self._score(images, texts, mode, params, cancellation_token)
            results.append(ImageTextScore(score))

        return results

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        return_logit   = await context.render_variable(self.config.params.return_logit)
        return_softmax = await context.render_variable(self.config.params.return_softmax)
        softmax_axis   = await context.render_variable(self.config.params.softmax_axis)

        return {
            "return_logit":   return_logit,
            "return_softmax": return_softmax,
            "softmax_axis":   softmax_axis,
        }

    def _resolve_scoring_mode(self, num_images: int, num_texts: int) -> str:
        if num_images == 0 or num_texts == 0:
            raise ValueError(f"Image-text scoring input cannot be empty: images={num_images}, texts={num_texts}")

        if num_images == num_texts:
            return "pairwise"

        if num_images == 1:
            return "texts_to_image"

        if num_texts == 1:
            return "images_to_text"

        raise ValueError(
            f"Incompatible image/text lengths for scoring: images={num_images}, texts={num_texts}. "
            "Lengths must match, or one side must have length 1."
        )

    @abstractmethod
    async def _score(
        self,
        images: List[PILImage.Image],
        texts: List[str],
        mode: str,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        """Score one scoring job.

        `mode` is one of 'pairwise', 'texts_to_image', 'images_to_text'.
        Returns a dict with 'cosine' (float for pairwise len-1, list otherwise)
        plus optional 'logit' and 'softmax' entries per params.
        """
        pass
