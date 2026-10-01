from __future__ import annotations
from typing import TYPE_CHECKING, Optional, List, Dict, Union, Tuple, Any
import math

from mindor.dsl.schema.action import ModelActionConfig, MinimaxH3TextToVideoModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.logger import logging
from ......base import ComponentActionContext
from ..base import MinimaxH3TextToVideoTaskAction, MinimaxH3TextToVideoTaskDriverBase

if TYPE_CHECKING:
    import torch

_MINIMAX_H3_SM120_CAPABILITY = (12, 0)
_SOL_ATTN_HEAD_DIM = 128

class SolAttnMinimaxH3Processor:
    """Diffusers attention processor that routes MiniMax-H3 self-attention through Sol-Attn.

    Mirrors :class:`diffusers.models.transformers.transformer_minimax_h3.MiniMaxH3AttnProcessor`
    but replaces :func:`dispatch_attention_fn` with Sol-Attn's compiled
    ``flex_attention`` kernel when the call is a long packed sequence of
    bfloat16 128-dim heads. Short sequences (the two token-refiner blocks),
    non-bf16 or non-128 cases, and the trailing dense window all delegate to
    the inherited dense path from the upstream processor.
    """
    _attention_backend = None
    _parallel_config = None

    def __init__(
        self,
        tau: float,
        thresh_type: str,
        dense_steps: Optional[int],
        step_off: Optional[float],
    ):
        self.tau: float = float(tau)
        self.thresh_type: str = str(thresh_type)
        self.dense_steps: int = int(dense_steps) if dense_steps is not None else 0
        self.step_off: float = float(step_off) if step_off is not None else 0.0
        # Updated from the pipeline's `callback_on_step_end` so the processor
        # can honor the trailing-dense window on the last denoising steps.
        self.current_step: int = 0
        self.total_steps: int = 0
        # Threshold below which a packed sequence is treated as the short
        # token-refiner stream and routed to dense attention. MiniMax-H3's
        # text-refiner stream is capped around a few hundred tokens; the real
        # packed video sequence is in the millions.
        self._min_sparse_seq_len: int = 4096

    def _is_trailing_dense(self) -> bool:
        if self.total_steps <= 0:
            return False

        remaining = max(0, self.total_steps - self.current_step)

        if self.dense_steps > 0:
            dense_from_count = remaining <= self.dense_steps
        else:
            dense_from_count = False

        if self.step_off > 0.0:
            fraction = min(max(self.step_off, 0.0), 1.0)
            dense_from_fraction = remaining <= int(math.ceil(self.total_steps * fraction))
        else:
            dense_from_fraction = False

        return dense_from_count or dense_from_fraction

    def __call__(
        self,
        attn: Any,
        hidden_states: torch.Tensor,
        rotary_emb: Optional[tuple[torch.Tensor, torch.Tensor]] = None,
        attention_mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        import torch
        from diffusers.models.transformers.transformer_minimax_h3 import (
            MiniMaxH3AttnProcessor,
            _apply_rotary_emb,
        )

        # Fall back to the upstream dense processor whenever Sol-Attn is a
        # structural mismatch (short refiner stream, non-bf16, head_dim != 128,
        # mask present) or when the trailing-dense window is active.
        seq_len = hidden_states.shape[1]
        dense_fallback = any((
            seq_len < self._min_sparse_seq_len,
            hidden_states.dtype != torch.bfloat16,
            attention_mask is not None,
            self._is_trailing_dense(),
        ))

        if dense_fallback:
            return self._fallback(attn, hidden_states, rotary_emb, attention_mask)

        if attn.fused_projections:
            query, key, value = attn.to_qkv(hidden_states).chunk(3, dim=-1)
        else:
            query = attn.to_q(hidden_states)
            key = attn.to_k(hidden_states)
            value = attn.to_v(hidden_states)

        query = query.unflatten(-1, (attn.heads, -1))
        key = key.unflatten(-1, (attn.heads, -1))
        value = value.unflatten(-1, (attn.heads, -1))

        query = attn.norm_q(query)
        key = attn.norm_k(key)

        if rotary_emb is not None:
            query = _apply_rotary_emb(query, *rotary_emb)
            key = _apply_rotary_emb(key, *rotary_emb)

        if query.shape[-1] != _SOL_ATTN_HEAD_DIM:
            # head_dim is fixed by the checkpoint, but guard anyway so a
            # misconfigured block won't hit the SM120 kernel's shape asserts.
            return self._fallback_from_qkv(attn, query, key, value, attention_mask)

        try:
            from sol_attn_blackwell import sol_attn_flex
            hidden_states = sol_attn_flex(query, key, value, tau=self.tau, thresh_type=self.thresh_type)
        except Exception as exc:
            logging.warning(f"Sol-Attn flex path failed ({type(exc).__name__}: {exc}); falling back to dense SDPA.")
            return self._fallback_from_qkv(attn, query, key, value, attention_mask)

        hidden_states = hidden_states.flatten(2, 3).type_as(query)
        hidden_states = attn.to_out[0](hidden_states)
        hidden_states = attn.to_out[1](hidden_states)

        return hidden_states

    @staticmethod
    def _fallback(
        attn: Any,
        hidden_states: torch.Tensor,
        rotary_emb: Optional[tuple[torch.Tensor, torch.Tensor]],
        attention_mask: Optional[torch.Tensor],
    ) -> torch.Tensor:
        from diffusers.models.transformers.transformer_minimax_h3 import MiniMaxH3AttnProcessor

        return MiniMaxH3AttnProcessor().__call__(attn, hidden_states, rotary_emb, attention_mask)

    @staticmethod
    def _fallback_from_qkv(
        attn: Any,
        query: torch.Tensor,
        key: torch.Tensor,
        value: torch.Tensor,
        attention_mask: Optional[torch.Tensor],
    ) -> torch.Tensor:
        from diffusers.models.attention_dispatch import dispatch_attention_fn

        hidden_states = dispatch_attention_fn(
            query, key, value,
            attn_mask=attention_mask,
            dropout_p=0.0,
            is_causal=False,
        )

        hidden_states = hidden_states.flatten(2, 3).type_as(query)
        hidden_states = attn.to_out[0](hidden_states)
        hidden_states = attn.to_out[1](hidden_states)

        return hidden_states


class MinimaxH3SolTextToVideoTaskDriver(MinimaxH3TextToVideoTaskDriverBase):
    """MiniMax-H3 driver that routes main-block self-attention through Sol-Attn on SM120."""

    def __init__(self, id: str, config: Any, daemon: bool):
        super().__init__(id, config, daemon)

        self.sol_attn_processor: Optional[SolAttnMinimaxH3Processor] = None

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [
            *super()._get_setup_requirements(),
            "mindor-sol-attn-blackwell@git+https://github.com/hanyeol/mindor-sol-attn-blackwell.git@v2.0",
        ]

    async def _load_model(self) -> None:
        await super()._load_model()

        self.sol_attn_processor = self._install_sol_attn_processor()

    async def _unload_model(self) -> None:
        await super()._unload_model()

        self.sol_attn_processor = None

    def _install_sol_attn_processor(self) -> SolAttnMinimaxH3Processor:
        import torch

        if torch.cuda.is_available():
            capability = torch.cuda.get_device_capability(self.device if self.device is not None else 0)

            if capability != _MINIMAX_H3_SM120_CAPABILITY:
                logging.info(
                    f"Sol-Attn kernels are validated only for SM{_MINIMAX_H3_SM120_CAPABILITY[0] * 10 + _MINIMAX_H3_SM120_CAPABILITY[1]} "
                    f"Blackwell consumer GPUs; detected SM{capability[0] * 10 + capability[1]} — "
                    f"attempting the flex_attention path anyway (falls back to dense attention on failure)."
                )
        else:
            logging.info("CUDA is not available; Sol-Attn requested but the flex_attention path cannot run — dense fallback will be used.")

        try:
            from sol_attn_blackwell import apply_inductor_fix_if_needed

            apply_inductor_fix_if_needed()
        except Exception as exc:
            logging.warning(f"Sol-Attn inductor fix skipped: {exc}")

        sol_cfg = self._first_action_sol_attn_config()
        tau = 1.0
        thresh_type = "diag"
        dense_steps: Optional[int] = None
        step_off: Optional[float] = None

        if sol_cfg is not None:
            tau         = float(sol_cfg.tau) if not isinstance(sol_cfg.tau, str) else tau
            thresh_type = str(sol_cfg.thresh_type)
            dense_steps = int(sol_cfg.dense_steps) if isinstance(sol_cfg.dense_steps, int) else None
            step_off    = float(sol_cfg.step_off) if isinstance(sol_cfg.step_off, (int, float)) else None

        processor = SolAttnMinimaxH3Processor(
            tau=tau,
            thresh_type=thresh_type,
            dense_steps=dense_steps,
            step_off=step_off,
        )

        # The two token-refiner blocks are left on the upstream dense processor;
        # sparse routing has no measurable benefit on their short text-only
        # stream and the processor already shortcuts to dense if invoked there.
        for block in self.pipeline.transformer.transformer_blocks:
            block.attn.set_processor(processor)

        return processor

    def _first_action_sol_attn_config(self) -> Optional[Any]:
        # The processor is installed per transformer stack, so every action on
        # a sol-backend component shares the same Sol-Attn tuning. Pick the
        # first action that provides overrides; warn when actions disagree.
        chosen = None

        for action in getattr(self.config, "actions", []) or []:
            sol_attn = getattr(getattr(action, "params", None), "sol_attn", None)

            if sol_attn is None:
                continue

            if chosen is None:
                chosen = sol_attn
                continue

            if sol_attn.model_dump() != chosen.model_dump():
                logging.warning(
                    "Multiple MiniMax-H3 actions on this component declare different sol_attn overrides; "
                    "using the first action's configuration for the shared transformer."
                )
                break

        return chosen

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await MinimaxH3SolTextToVideoTaskAction(action, self.pipeline, self.sol_attn_processor).run(context)


class MinimaxH3SolTextToVideoTaskAction(MinimaxH3TextToVideoTaskAction):
    """Sol-backend action that resets the processor's step counter per batch item
    and streams the current denoising step into it via ``callback_on_step_end``."""

    def __init__(
        self,
        config: MinimaxH3TextToVideoModelActionConfig,
        pipeline: Any,
        sol_attn_processor: SolAttnMinimaxH3Processor,
    ):
        super().__init__(config, pipeline)

        self.sol_attn_processor: SolAttnMinimaxH3Processor = sol_attn_processor

    async def _generate_batch(
        self,
        prompts: List[str],
        negative_prompts: Optional[List[Optional[str]]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[VideoStreamResource]:
        def _generate() -> List[VideoStreamResource]:
            import torch

            negatives = negative_prompts if negative_prompts is not None else [ None ] * len(prompts)
            fps = int(params["fps"])
            seed = params["seed"]
            total_steps = int(params["inference_steps"])
            processor = self.sol_attn_processor
            results: List[VideoStreamResource] = []

            def _on_step_end(pipeline: Any, step: int, timestep: Any, callback_kwargs: Dict[str, Any]):
                processor.current_step = int(step) + 1
                processor.total_steps = int(getattr(pipeline, "num_timesteps", total_steps) or total_steps)
                return callback_kwargs

            for prompt, negative in zip(prompts, negatives):
                generator = torch.Generator(device=self.pipeline.device).manual_seed(int(seed)) if seed is not None else None

                processor.current_step = 0
                processor.total_steps = total_steps

                output = self.pipeline(
                    prompt=prompt,
                    negative_prompt=negative,
                    height=int(params["height"]),
                    width=int(params["width"]),
                    num_frames=int(params["num_frames"]),
                    num_inference_steps=total_steps,
                    guidance_scale=float(params["guidance_scale"]),
                    generator=generator,
                    callback_on_step_end=_on_step_end,
                )

                results.append(self._encode_video_audio_to_mp4(output, fps))

            return results

        return await self._run_in_executor(_generate)
