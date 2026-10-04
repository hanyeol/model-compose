from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Union, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import VideoTextScoringModelActionConfig
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.foundation.variable.text import TextArrayValue
from mindor.core.foundation.variable.array import ArrayValue
from mindor.core.foundation.variable.atomic import AtomicDict
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from .....action.base import ComponentAction
from ...base import ComponentActionContext
from PIL import Image as PILImage

class VideoTextScore(AtomicDict):
    def __log__(self) -> str:
        cosine = self.get("cosine")
        if isinstance(cosine, list):
            return f"<VideoTextScore pairs={len(cosine)}>"
        return f"<VideoTextScore cosine={cosine:.4f}>"

class VideoTextScoringTaskAction(ComponentAction):
    def __init__(self, config: VideoTextScoringModelActionConfig):
        self.config: VideoTextScoringModelActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        frames     = await context.render_image_array(self.config.frames, single_as_array=True)
        text       = await context.render_text_array(self.config.text, single_as_array=True)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = isinstance(frames, ImageArrayValue)
        is_direct_output = not self.config.output or self.config.output == "${result}"

        # Wrap collect-mode input in an ArrayValue so BatchSourceIterator sees it
        # as a scalar — N videos × K texts stay bundled in one X-CLIP forward.
        if not isinstance(frames, (StreamIterator, AsyncIterator)):
            frames = ArrayValue([ frames ] if is_single_input else frames)

        if isinstance(frames, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_videos, batch_texts in BatchSourceIterator((frames, text), batch_size=batch_size or 1):
                    batch_results = await self._score_batch(batch_videos, batch_texts, params, context.cancellation_token)
                    for result in batch_results:
                        context.register_source("result[]", result)
                        yield (await context.render_variable(self.config.output)) if not is_direct_output else result

            return _stream_output_generator()
        else:
            results: List[VideoTextScore] = []
            async for batch_videos, batch_texts in BatchSourceIterator((frames, text), batch_size=batch_size or 1):
                batch_results = await self._score_batch(batch_videos, batch_texts, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0]  # collect-mode packs every video into one job
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _score_batch(
        self,
        frames_arrays: List[Union[ArrayValue, ImageArrayValue]],
        texts_arrays: List[TextArrayValue],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[VideoTextScore]:
        results: List[VideoTextScore] = []

        for frames_array, texts_array in zip(frames_arrays, texts_arrays):
            # `frames_array` is either an ArrayValue (collect-mode: N videos
            # packed into one job) or a single ImageArrayValue (stream-mode:
            # one video per tick).
            if isinstance(frames_array, ArrayValue):
                videos = await frames_array.collect()
            else:
                videos = [ frames_array ]

            videos = [ await video.collect() for video in videos ]
            texts  = await texts_array.collect()

            mode = self._resolve_scoring_mode(len(videos), len(texts))
            score = await self._score(videos, texts, mode, params, cancellation_token)

            results.append(VideoTextScore(score))

        return results

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        return_logit   = await context.render_variable(self.config.params.return_logit)
        return_softmax = await context.render_variable(self.config.params.return_softmax)

        return {
            "return_logit":   return_logit,
            "return_softmax": return_softmax,
        }

    def _resolve_scoring_mode(self, num_videos: int, num_texts: int) -> str:
        if num_videos == 0 or num_texts == 0:
            raise ValueError(f"Video-text scoring input cannot be empty: videos={num_videos}, texts={num_texts}")

        if num_videos == num_texts:
            return "pairwise"

        if num_videos == 1:
            return "texts_to_video"

        if num_texts == 1:
            return "videos_to_text"

        raise ValueError(
            f"Incompatible video/text lengths for scoring: videos={num_videos}, texts={num_texts}. "
            "Lengths must match, or one side must have length 1."
        )

    @abstractmethod
    async def _score(
        self,
        videos: List[List[PILImage.Image]],
        texts: List[str],
        mode: str,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        """Score one job.

        `videos` is a list of per-video frame sequences; the driver samples each
        to the architecture's expected frame count before forwarding.
        `mode` is one of 'pairwise', 'texts_to_video', 'videos_to_text'.
        Returns a dict with 'cosine' (float for single-pair pairwise, list
        otherwise) plus optional 'logit' and 'softmax' entries per params.
        """
        pass
