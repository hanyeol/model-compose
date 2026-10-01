from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any
from abc import abstractmethod
from mindor.dsl.schema.action import CommonMotionGenerationModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.variable.atomic import AtomicDict
from mindor.core.utils.iterators import BatchSourceIterator
from .....action.base import ComponentAction
from ...base import ComponentActionContext

class MotionClip(AtomicDict):
    # Generator-agnostic skeletal-motion container shared across motion-generation
    # drivers and (future) motion-converter. Required keys: fps, skeleton,
    # joint_positions [T,J,3], joint_rotations [T,J,...], rotation_format,
    # root_position [T,3]. Driver-specific signals (foot contacts, heading
    # vectors, smoothed root, alternate rotation reps, ...) live under `extras`.
    def __log__(self) -> str:
        joint_positions = self.get("joint_positions")
        frames = int(joint_positions.shape[0]) if joint_positions is not None else 0
        joint_count = int(joint_positions.shape[1]) if joint_positions is not None else 0

        return (
            f"<MotionClip skeleton={self.get('skeleton')!r} "
            f"frames={frames} joints={joint_count} fps={self.get('fps')}>"
        )

class MotionGenerationTaskAction(ComponentAction):
    def __init__(self, config: CommonMotionGenerationModelActionConfig):
        self.config: CommonMotionGenerationModelActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        input, is_single_input, is_streaming_input = await self._prepare_input(context)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_direct_output = not self.config.output or self.config.output == "${result}"

        if is_streaming_input:
            async def _stream_output_generator():
                async for batch_inputs in BatchSourceIterator(input, batch_size=batch_size or 1):
                    batch_inputs = tuple(zip(*batch_inputs))  # Transpose per-slot batches into per-request tuples.
                    batch_results = await self._generate_batch(batch_inputs, params, context.cancellation_token)
                    for result in batch_results:
                        context.register_source("result[]", result)
                        yield (await context.render_variable(self.config.output)) if not is_direct_output else result

            return _stream_output_generator()
        else:
            results: List[Any] = []
            async for batch_inputs in BatchSourceIterator(input, batch_size=batch_size or 1):
                batch_inputs = tuple(zip(*batch_inputs))  # Transpose per-slot batches into per-request tuples.
                batch_results = await self._generate_batch(batch_inputs, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        seed = await context.render_scalar(self.config.seed, int)

        return {
            "seed": seed,
        }

    @abstractmethod
    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, bool, bool]:
        pass

    @abstractmethod
    async def _generate_batch(
        self,
        inputs: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        pass
