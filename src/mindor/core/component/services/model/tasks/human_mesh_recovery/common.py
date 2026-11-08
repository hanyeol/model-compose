from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any
from abc import abstractmethod
from mindor.dsl.schema.action import HumanMeshRecoveryModelActionConfig
from mindor.core.foundation.streaming.iterators import StreamChunkIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from ...base import ComponentActionContext, ModelTaskComponentAction

class HumanMeshRecoveryTaskAction(ModelTaskComponentAction):
    def __init__(self, config: HumanMeshRecoveryModelActionConfig):
        self.config: HumanMeshRecoveryModelActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        input, primary_input, is_single_input, is_streaming_input = await self._prepare_input(context)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_direct_output = not self.config.output or self.config.output == "${result}"

        if is_streaming_input:
            async def _stream_output_generator():
                async for batch_inputs in BatchSourceIterator(input, batch_size=batch_size or 1):
                    batch_inputs = tuple(zip(*batch_inputs))  # Transpose per-slot batches into per-request tuples.
                    batch_results = await self._recover_batch(batch_inputs, params, context.cancellation_token)
                    for result in batch_results:
                        context.register_source("result", result)
                        yield (await context.render_variable(self.config.output)) if not is_direct_output else result

            if isinstance(primary_input, StreamChunkIterator) and primary_input.is_fragmented:
                return StreamChunkIterator(_stream_output_generator(), is_fragmented=True)

            return _stream_output_generator()
        else:
            results: List[Any] = []
            async for batch_inputs in BatchSourceIterator(input, batch_size=batch_size or 1):
                batch_inputs = tuple(zip(*batch_inputs))  # Transpose per-slot batches into per-request tuples.
                batch_results = await self._recover_batch(batch_inputs, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    @abstractmethod
    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, Any, bool, bool]:
        """Return ``(slots, primary_input, is_single_input, is_streaming_input)``.

        ``slots`` is a tuple of per-request input streams that the base ``run``
        zips into per-request tuples before dispatching to ``_recover_batch``.
        Drivers differ in input shape (single image for HMR2, frame sequence
        for GVHMR), so each concrete subclass owns this entirely.
        """
        pass

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        return_joints_3d = await context.render_scalar(self.config.return_joints_3d, bool)
        return_joints_2d = await context.render_scalar(self.config.return_joints_2d, bool)
        return_vertices  = await context.render_scalar(self.config.return_vertices, bool)
        return_mesh      = await context.render_scalar(self.config.return_mesh, bool)
        return_camera    = await context.render_scalar(self.config.return_camera, bool)
        return_metadata  = await context.render_scalar(self.config.return_metadata, bool)
        min_confidence   = await context.render_scalar(self.config.params.min_confidence, float)

        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError(f"'min_confidence' must be between 0.0 and 1.0, got {min_confidence}")

        return {
            "return_joints_3d": return_joints_3d,
            "return_joints_2d": return_joints_2d,
            "return_vertices":  return_vertices,
            "return_mesh":      return_mesh,
            "return_camera":    return_camera,
            "return_metadata":  return_metadata,
            "min_confidence":   min_confidence,
        }

    @abstractmethod
    async def _recover_batch(
        self,
        inputs: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        pass
