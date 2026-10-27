from __future__ import annotations

from typing import Union, Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import MusicScoreLoaderActionConfig
from mindor.core.foundation.streaming.iterators import StreamIterator, StreamChunkIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.variable.atomic import AtomicDict
from mindor.core.utils.iterators import BatchSourceIterator
from ....action.base import ComponentAction
from ..base import ComponentActionContext

class MusicScore(AtomicDict):
    """A parsed music score, modeled on MusicXML ``<score-partwise>``. MIDI
    loads populate the subset of fields MIDI can carry (notes, tempos,
    time_signatures, key_signatures, part/program/channel); MusicXML-only
    fields (harmonies, lyric syllabic/number, clefs) are left as ``[]``
    or ``None`` so consumers can treat both formats uniformly.

    Shape::

        {
            "format":           "midi" | "musicxml",
            "duration":         float,                # seconds; end_time of the last note
            "parts":            [Part, ...],
            "tempos":           [{"time": float, "beats_per_minute": float}, ...],
            "time_signatures":  [{"time": float, "beats": int, "beat_type": int}, ...],
            "key_signatures":   [{"time": float, "fifths": int, "mode": str}, ...],
            "harmonies":        [Harmony, ...],       # [] for MIDI loads
        }

    Part shape::

        {
            "id":                str,                 # MusicXML <score-part id> or synthesized "T{track}_C{channel}"
            "part_name":         str,                 # <part-name> or MIDI track name
            "part_abbreviation": Optional[str],
            "midi_channel":      Optional[int],
            "midi_program":      Optional[int],
            "notes":             [Note, ...],
            "lyrics":            [Lyric, ...],
            "clefs":             [Clef, ...],         # [] for MIDI loads
        }

    Note shape (shared with MusicTranscriptNotes elements)::

        {"start_time": float, "end_time": float, "pitch": int, "velocity": float}

    Lyric shape (``syllabic`` and ``number`` are MusicXML-only; ``None`` for MIDI)::

        {"note_index": int, "text": str,
         "syllabic": Optional[str], "number": Optional[int]}

    Clef shape (MusicXML <clef>)::

        {"time": float, "sign": str, "line": int, "staff": int}

    Harmony shape (MusicXML <harmony>)::

        {"time": float, "part_id": str,
         "root_step": str, "root_alter": int, "kind": str,
         "bass_step": Optional[str], "bass_alter": Optional[int]}
    """

    def __log__(self) -> str:
        return (
            f"<MusicScore format={self.get('format')} "
            f"duration={self.get('duration', 0.0):.2f}s "
            f"parts={len(self.get('parts', []))} "
            f"tempos={len(self.get('tempos', []))} "
            f"harmonies={len(self.get('harmonies', []))}>"
        )

class MusicScoreLoaderAction(ComponentAction):
    def __init__(self, config: MusicScoreLoaderActionConfig):
        self.config: MusicScoreLoaderActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        source     = await self._prepare_input(context)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(source, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(source, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_sources in BatchSourceIterator(source, batch_size=batch_size or 1):
                    batch_results = await self._load_batch(batch_sources, params, context.cancellation_token)
                    for result in batch_results:
                        context.register_source("result", result)
                        yield (await context.render_variable(self.config.output)) if not is_direct_output else result

            if isinstance(source, StreamChunkIterator) and source.is_fragmented:
                return StreamChunkIterator(_stream_output_generator(), is_fragmented=True)

            return _stream_output_generator()
        else:
            results: List[Dict[str, Any]] = []
            async for batch_sources in BatchSourceIterator(source, batch_size=batch_size or 1):
                batch_results = await self._load_batch(batch_sources, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    @abstractmethod
    async def _prepare_input(self, context: ComponentActionContext) -> Any:
        pass

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        return {}

    @abstractmethod
    async def _load_batch(
        self,
        sources: List[Any],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[MusicScore]:
        """Load one batch of sources and return one ``MusicScore`` per source."""
        pass
