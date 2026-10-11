from __future__ import annotations

from typing import Optional, Tuple, Dict, List, Any, Union
from mindor.dsl.schema.component import MusicScoreLoaderComponentConfig, MusicScoreLoaderDriverType
from mindor.dsl.schema.action import MusicScoreLoaderActionConfig, LocalMusicScoreLoaderActionConfig
from mindor.dsl.schema.action.impl.music_score_loader.impl.common import MusicScoreLoaderFormat
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.streaming.resources import save_stream_to_temporary_file
from mindor.core.foundation.streaming.resolver import resolve_stream_resource
from mindor.core.foundation.cancellation import CancellationToken
from ..base import MusicScoreLoaderDriver, register_music_score_loader_driver
from ..base import ComponentActionContext
from .common import MusicScoreLoaderAction
import asyncio, os, zipfile

# File-content sniffing: MIDI files always start with ``MThd``; MusicXML files
# start with an XML prolog (``<?xml``) or — for the compressed ``.mxl`` ZIP
# container — with ``PK``.
_MIDI_MAGIC = b"MThd"
_XML_MAGIC = b"<?xml"
_ZIP_MAGIC = b"PK\x03\x04"

# Diatonic step → semitone offset within an octave. MusicXML spells notes as
# (step, octave, alter), and MIDI note 0 is C-1 (so middle C = C4 = MIDI 60).
_STEP_TO_SEMITONE = { "C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11 }

class MusicXmlScoreLoader:
    """Parses a MusicXML file (uncompressed ``.xml``/``.musicxml`` or
    compressed ``.mxl``) into the shared score shape.

    Implements the minimum of the spec needed for melodic input: note pitches
    via step/alter/octave, durations via divisions, measure traversal, tempo
    marks via ``<sound tempo>``, basic backup/forward handling, and chord
    recognition. Ties/articulations/dynamics/lyrics are discarded — only pitch
    and timing are kept.

    Score-partwise only; score-timewise raises ``ValueError`` (<5% of
    real-world files use timewise).

    Uses stdlib ``xml.etree`` so no music21 or partitura dependency is needed.
    """

    _DEFAULT_DIVISIONS = 480      # Ticks per quarter note before any <divisions>
    _DEFAULT_TEMPO_BPM = 120.0    # MusicXML default when no <sound tempo> is set
    _DEFAULT_VELOCITY = 0.75      # MusicXML lacks a universal dynamic → fall back to mf

    def load(self, path: str, track_index: Optional[int] = None) -> Dict[str, Any]:
        root = self._load_root(path)

        if root.tag.split("}")[-1] != "score-partwise":
            raise ValueError(f"Unsupported MusicXML layout: {root.tag}; only score-partwise is supported.")

        parts = root.findall("part")

        if not parts:
            raise ValueError("MusicXML file has no <part> elements.")

        selected_parts = self._select_parts(parts, track_index)

        notes: List[Dict[str, Any]] = []
        state = {
            "divisions":      self._DEFAULT_DIVISIONS,
            "tempo":          self._DEFAULT_TEMPO_BPM,
            "time_signature": None,
        }

        for part in selected_parts:
            self._parse_part(part, state, notes)

        notes.sort(key=lambda note: note["start_time"])

        return {
            "notes":          notes,
            "tempo":          state["tempo"],
            "time_signature": list(state["time_signature"]) if state["time_signature"] else None,
            "format":         MusicScoreLoaderFormat.MUSICXML.value,
            "duration":       max((note["end_time"] for note in notes), default=0.0),
        }

    def _load_root(self, path: str) -> Any:
        """Parse the XML tree, transparently unwrapping ``.mxl`` ZIP containers.

        For compressed scores we read the rootfile pointer in
        ``META-INF/container.xml`` and fall back to the first non-meta XML
        entry — mirrors how MuseScore/Finale/Sibelius pack ``.mxl`` files.
        """
        import xml.etree.ElementTree as ElementTree

        if not zipfile.is_zipfile(path):
            return ElementTree.parse(path).getroot()

        with zipfile.ZipFile(path) as archive:
            xml_path = None

            try:
                with archive.open("META-INF/container.xml") as container:
                    container_tree = ElementTree.parse(container)
                    rootfile = container_tree.find(".//{*}rootfile")

                    if rootfile is not None:
                        xml_path = rootfile.get("full-path")
            except KeyError:
                pass

            if xml_path is None:
                for name in archive.namelist():
                    if name.endswith(".xml") and not name.startswith("META-INF/"):
                        xml_path = name
                        break

            if xml_path is None:
                raise ValueError(f"No score file found inside .mxl archive: {path!r}")

            with archive.open(xml_path) as score_file:
                return ElementTree.parse(score_file).getroot()

    def _select_parts(self, parts: List[Any], track_index: Optional[int]) -> List[Any]:
        if track_index is None:
            return parts[:1]

        if track_index < 0 or track_index >= len(parts):
            raise ValueError(f"Track index {track_index} out of range (file has {len(parts)} parts)")

        return [ parts[track_index] ]

    def _parse_part(self, part: Any, state: Dict[str, Any], notes: List[Dict[str, Any]]) -> None:
        """Walk measures in one part, mutating ``state`` (divisions/tempo/time
        signature) and appending to ``notes``. The cursor is a tick count that
        advances with notes and respects ``backup``/``forward`` repositioning.
        """
        cursor_tick = 0

        for measure in part.findall("measure"):
            for element in measure:
                tag = element.tag.split("}")[-1]

                if tag == "attributes":
                    self._apply_attributes(element, state)
                elif tag == "sound":
                    self._apply_sound(element, state)
                elif tag == "note":
                    cursor_tick = self._parse_note(element, cursor_tick, state, notes)
                elif tag == "backup":
                    cursor_tick -= self._read_duration(element)
                elif tag == "forward":
                    cursor_tick += self._read_duration(element)

    def _apply_attributes(self, element: Any, state: Dict[str, Any]) -> None:
        divisions_element = element.find("divisions")

        if divisions_element is not None and divisions_element.text:
            state["divisions"] = int(divisions_element.text)

        time_element = element.find("time")

        if time_element is not None and state["time_signature"] is None:
            beats = time_element.find("beats")
            beat_type = time_element.find("beat-type")

            if beats is not None and beat_type is not None:
                state["time_signature"] = (int(beats.text), int(beat_type.text))

    def _apply_sound(self, element: Any, state: Dict[str, Any]) -> None:
        tempo_attr = element.get("tempo")

        if tempo_attr is not None:
            state["tempo"] = float(tempo_attr)

    def _parse_note(
        self,
        element: Any,
        cursor_tick: int,
        state: Dict[str, Any],
        notes: List[Dict[str, Any]],
    ) -> int:
        """Append one note (if pitched) and return the updated cursor.

        Chord notes share the start time of the previous note, so the cursor
        rewinds before placing them and does **not** advance after.
        """
        duration_ticks = self._read_duration(element)
        is_rest = element.find("rest") is not None
        is_chord = element.find("chord") is not None

        if is_chord:
            note_start_tick = cursor_tick - duration_ticks
            next_cursor = cursor_tick
        else:
            note_start_tick = cursor_tick
            next_cursor = cursor_tick + duration_ticks

        if is_rest:
            return next_cursor

        midi_pitch = self._pitch_to_midi(element.find("pitch"))

        if midi_pitch is None:
            return next_cursor

        start_seconds = note_start_tick / state["divisions"] * 60.0 / state["tempo"]
        end_seconds   = (note_start_tick + duration_ticks) / state["divisions"] * 60.0 / state["tempo"]

        notes.append({
            "start_time": start_seconds,
            "end_time":   end_seconds,
            "pitch":      midi_pitch,
            "velocity":   self._DEFAULT_VELOCITY,
        })

        return next_cursor

    def _read_duration(self, element: Any) -> int:
        duration_element = element.find("duration")

        if duration_element is None or not duration_element.text:
            return 0

        return int(duration_element.text)

    def _pitch_to_midi(self, pitch_element: Optional[Any]) -> Optional[int]:
        if pitch_element is None:
            return None

        step = pitch_element.find("step")
        octave = pitch_element.find("octave")

        if step is None or octave is None:
            return None

        alter_element = pitch_element.find("alter")
        alter = int(alter_element.text) if alter_element is not None and alter_element.text else 0

        return (int(octave.text) + 1) * 12 + _STEP_TO_SEMITONE[step.text.upper()] + alter

class MidiScoreLoader:
    """Parses a Standard MIDI File into the shared score shape.

    One ``note`` per note-on/note-off pair, timed in seconds using the file's
    tempo map and PPQ. When ``track_index`` is None the first non-empty track
    is picked; multi-track selection is left to the caller.
    """

    _DEFAULT_TICKS_PER_BEAT = 480       # MIDI PPQ fallback when the header reports 0
    _DEFAULT_TEMPO_US_PER_BEAT = 500000 # MIDI default when no set_tempo message exists (120 BPM)

    def load(self, path: str, track_index: Optional[int]) -> Dict[str, Any]:
        import mido

        midi = mido.MidiFile(path)
        ticks_per_beat = midi.ticks_per_beat or self._DEFAULT_TICKS_PER_BEAT

        tempo_events, time_signature = self._collect_tempo_and_time_signature(midi)
        track_indices = [ track_index ] if track_index is not None else self._select_track_indices(midi)

        notes: List[Dict[str, Any]] = []

        for index in track_indices:
            notes.extend(self._parse_track(midi.tracks[index], tempo_events, ticks_per_beat))

        notes.sort(key=lambda note: note["start_time"])

        # Tempo report: the first value is the most useful summary; downstream
        # consumers that care about tempo changes should re-parse themselves.
        return {
            "notes":          notes,
            "tempo":          60_000_000 / tempo_events[0][1],
            "time_signature": list(time_signature) if time_signature else None,
            "format":         MusicScoreLoaderFormat.MIDI.value,
            "duration":       max((note["end_time"] for note in notes), default=0.0),
        }

    def _collect_tempo_and_time_signature(self, midi: Any) -> Tuple[List[Tuple[int, int]], Optional[Tuple[int, int]]]:
        """Collect tempo map (tick → µs/beat) across all tracks so per-track
        note times stay consistent even when tempo changes live on a different
        track than the notes.
        """
        tempo_events: List[Tuple[int, int]] = []
        time_signature: Optional[Tuple[int, int]] = None

        for track in midi.tracks:
            absolute_tick = 0

            for message in track:
                absolute_tick += message.time

                if self._is_set_tempo(message):
                    tempo_events.append((absolute_tick, message.tempo))
                    continue

                if self._is_time_signature(message) and time_signature is None:
                    time_signature = (message.numerator, message.denominator)

        if not tempo_events:
            tempo_events.append((0, self._DEFAULT_TEMPO_US_PER_BEAT))

        tempo_events.sort(key=lambda event: event[0])

        return tempo_events, time_signature

    def _select_track_indices(self, midi: Any) -> List[int]:
        """Pick every track that has note_on events (skips tempo-map-only
        track 0 in Type-1 MIDI files).
        """
        indices: List[int] = []

        for index, track in enumerate(midi.tracks):
            for message in track:
                if self._is_note_on(message):
                    indices.append(index)

                    break

        return indices or [ 0 ]

    def _parse_track(
        self,
        track: Any,
        tempo_events: List[Tuple[int, int]],
        ticks_per_beat: int,
    ) -> List[Dict[str, Any]]:
        open_notes: Dict[int, Tuple[int, int]] = {}  # pitch → (start_tick, velocity)
        notes: List[Dict[str, Any]] = []
        absolute_tick = 0

        for message in track:
            absolute_tick += message.time

            if self._is_note_on(message):
                open_notes[message.note] = (absolute_tick, message.velocity)
                continue

            if not self._is_note_off(message):
                continue

            onset = open_notes.pop(message.note, None)

            if onset is None:
                continue

            start_tick, velocity = onset
            notes.append({
                "start_time": self._tick_to_seconds(start_tick, tempo_events, ticks_per_beat),
                "end_time":   self._tick_to_seconds(absolute_tick, tempo_events, ticks_per_beat),
                "pitch":      message.note,
                "velocity":   velocity / 127.0,
            })

        return notes

    @staticmethod
    def _is_set_tempo(message: Any) -> bool:
        return message.type == "set_tempo"

    @staticmethod
    def _is_time_signature(message: Any) -> bool:
        return message.type == "time_signature"

    @staticmethod
    def _is_note_on(message: Any) -> bool:
        return message.type == "note_on" and message.velocity > 0

    @staticmethod
    def _is_note_off(message: Any) -> bool:
        # MIDI convention: a note_on with velocity 0 is a note_off.
        return message.type == "note_off" or (message.type == "note_on" and message.velocity == 0)

    def _tick_to_seconds(self, target_tick: int, tempo_events: List[Tuple[int, int]], ticks_per_beat: int) -> float:
        """Fold the tempo map into seconds up to ``target_tick``."""
        prev_tick, prev_tempo = 0, tempo_events[0][1]
        seconds = 0.0

        for event_tick, event_tempo in tempo_events:
            if event_tick >= target_tick:
                break

            seconds += (event_tick - prev_tick) * prev_tempo / ticks_per_beat / 1_000_000
            prev_tick, prev_tempo = event_tick, event_tempo

        seconds += (target_tick - prev_tick) * prev_tempo / ticks_per_beat / 1_000_000

        return seconds

class LocalMusicScoreLoaderAction(MusicScoreLoaderAction):
    async def _prepare_input(self) -> Any:
        return await self.context.render_variable(self.config.source)

    async def _resolve_params(self) -> Dict[str, Any]:
        params = await super()._resolve_params()

        format = await self.context.render_variable(self.config.format)
        track  = await self.context.render_scalar(self.config.track, int, None) if self.config.track is not None else None

        if isinstance(format, MusicScoreLoaderFormat):
            format = format.value

        params.update({
            "format": format,
            "track":  track,
        })

        return params

    async def _load_batch(
        self,
        sources: List[Any],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        return await asyncio.gather(*[
            self._load(source, params, cancellation_token) for source in sources
        ])

    async def _load(
        self,
        source: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        path, spooled = await self._resolve_source_path(source, params["format"])

        try:
            format = params["format"] or self._sniff_format(path)
            result = await asyncio.to_thread(self._parse_score_file, path, format, params["track"])
        finally:
            if spooled:
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass

        return result

    async def _resolve_source_path(self, source: Any, format: Optional[str]) -> Tuple[str, bool]:
        """Turn any accepted source shape into a filesystem path the parser can read.

        Returns ``(path, spooled)``. When ``spooled`` is True the caller must
        remove ``path`` after use. Mirrors ``MediaInputPathResolver.resolve``.
        """
        if isinstance(source, str) and os.path.exists(source):
            return source, False

        stream = await resolve_stream_resource(source)

        if isinstance(stream, FileStreamResource):
            return stream.path, False

        return await save_stream_to_temporary_file(stream, format), True

    @staticmethod
    def _sniff_format(path: str) -> str:
        with open(path, "rb") as file:
            head = file.read(16)

        if head.startswith(_MIDI_MAGIC):
            return MusicScoreLoaderFormat.MIDI.value
        if head.startswith(_XML_MAGIC) or head.lstrip().startswith(_XML_MAGIC):
            return MusicScoreLoaderFormat.MUSICXML.value
        if head.startswith(_ZIP_MAGIC):
            # Compressed MusicXML (`.mxl`) is a ZIP container with the score XML
            # inside; we still treat it as `musicxml` for parser dispatch.
            return MusicScoreLoaderFormat.MUSICXML.value

        extension = os.path.splitext(path)[1].lower()
        if extension in (".mid", ".midi"):
            return MusicScoreLoaderFormat.MIDI.value
        if extension in (".xml", ".musicxml", ".mxl"):
            return MusicScoreLoaderFormat.MUSICXML.value

        raise ValueError(f"Cannot infer score format for {path!r}; set `format` explicitly.")

    @staticmethod
    def _parse_score_file(path: str, format: str, track_index: Optional[int]) -> Dict[str, Any]:
        if format == MusicScoreLoaderFormat.MIDI.value:
            return MidiScoreLoader().load(path, track_index)
        if format == MusicScoreLoaderFormat.MUSICXML.value:
            return MusicXmlScoreLoader().load(path, track_index)
        raise ValueError(f"Unsupported score format: {format!r}")


@register_music_score_loader_driver(MusicScoreLoaderDriverType.LOCAL)
class LocalMusicScoreLoaderService(MusicScoreLoaderDriver):
    def __init__(self, id: str, config: MusicScoreLoaderComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [ "mido" ]

    async def _run(self, action: MusicScoreLoaderActionConfig, context: ComponentActionContext) -> Any:
        return await LocalMusicScoreLoaderAction(action, context).run()
