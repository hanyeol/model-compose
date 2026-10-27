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
from .common import MusicScore, MusicScoreLoaderAction
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

# Circle-of-fifths lookup for MIDI ``key_signature`` meta → MusicXML
# ``<fifths>``. mido reports each key as a tonic plus mode suffix (e.g. ``"F#"``,
# ``"Dm"``), already resolving enharmonics; we only need to translate that
# string back into the signed ``fifths`` count MusicXML uses.
_KEY_TONIC_TO_FIFTHS: Dict[Tuple[str, str], int] = {
    ("Cb", "major"): -7, ("Gb", "major"): -6, ("Db", "major"): -5, ("Ab", "major"): -4,
    ("Eb", "major"): -3, ("Bb", "major"): -2, ("F",  "major"): -1, ("C",  "major"):  0,
    ("G",  "major"):  1, ("D",  "major"):  2, ("A",  "major"):  3, ("E",  "major"):  4,
    ("B",  "major"):  5, ("F#", "major"):  6, ("C#", "major"):  7,
    ("Ab", "minor"): -7, ("Eb", "minor"): -6, ("Bb", "minor"): -5, ("F",  "minor"): -4,
    ("C",  "minor"): -3, ("G",  "minor"): -2, ("D",  "minor"): -1, ("A",  "minor"):  0,
    ("E",  "minor"):  1, ("B",  "minor"):  2, ("F#", "minor"):  3, ("C#", "minor"):  4,
    ("G#", "minor"):  5, ("D#", "minor"):  6, ("A#", "minor"):  7,
}

class MusicXmlScoreLoader:
    """Parses a MusicXML file (uncompressed ``.xml``/``.musicxml`` or
    compressed ``.mxl``) into a ``MusicScore``.

    Covers the elements documented in the ``MusicScore`` shape: notes
    (step/alter/octave, chord sharing, backup/forward), ``<part-list>`` metadata
    (part-name, score-instrument, midi-instrument), tempos (``<sound tempo>``,
    ``<direction><metronome>``), time/key signatures and clefs via
    ``<attributes>``, chord symbols via ``<harmony>``, and lyrics via
    ``<note><lyric>``. Ties/slurs/dynamics/articulations are discarded.

    Score-partwise only; score-timewise raises ``ValueError`` (<5% of
    real-world files use timewise).

    Uses stdlib ``xml.etree`` so no music21 or partitura dependency is needed.
    """

    _DEFAULT_DIVISIONS = 480      # Ticks per quarter note before any <divisions>
    _DEFAULT_TEMPO_BPM = 120.0    # MusicXML default when no <sound tempo> is set
    _DEFAULT_VELOCITY = 0.75      # MusicXML lacks a universal dynamic → fall back to mf

    def load(self, path: str, part_index: Optional[int] = None) -> MusicScore:
        root = self._load_root(path)

        if root.tag.split("}")[-1] != "score-partwise":
            raise ValueError(f"Unsupported MusicXML layout: {root.tag}; only score-partwise is supported.")

        part_elements = root.findall("part")

        if not part_elements:
            raise ValueError("MusicXML file has no <part> elements.")

        part_metadata = self._collect_part_metadata(root)
        selected_parts = self._select_parts(part_elements, part_index)

        parts: List[Dict[str, Any]] = []
        tempos: List[Dict[str, Any]] = []
        time_signatures: List[Dict[str, Any]] = []
        key_signatures: List[Dict[str, Any]] = []
        harmonies: List[Dict[str, Any]] = []

        for part_element in selected_parts:
            part_id = part_element.get("id") or f"P{len(parts) + 1}"
            metadata = part_metadata.get(part_id, {})
            state = {
                "divisions": self._DEFAULT_DIVISIONS,
                "tempo":     self._DEFAULT_TEMPO_BPM,
            }

            part = {
                "id":                part_id,
                "part_name":         metadata.get("part_name", part_id),
                "part_abbreviation": metadata.get("part_abbreviation"),
                "midi_channel":      metadata.get("midi_channel"),
                "midi_program":      metadata.get("midi_program"),
                "notes":             [],
                "lyrics":            [],
                "clefs":             [],
            }

            self._parse_part(part_element, state, part, tempos, time_signatures, key_signatures, harmonies)

            part["notes"].sort(key=lambda note: note["start_time"])
            parts.append(part)

        if not tempos:
            tempos.append({ "time": 0.0, "beats_per_minute": self._DEFAULT_TEMPO_BPM })

        duration = max(
            (note["end_time"] for part in parts for note in part["notes"]),
            default=0.0,
        )

        return MusicScore({
            "format":          MusicScoreLoaderFormat.MUSICXML.value,
            "duration":        duration,
            "parts":           parts,
            "tempos":          tempos,
            "time_signatures": time_signatures,
            "key_signatures":  key_signatures,
            "harmonies":       harmonies,
        })

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

    def _collect_part_metadata(self, root: Any) -> Dict[str, Dict[str, Any]]:
        """Index ``<score-part>`` declarations by id. One entry per score-part,
        carrying the fields the ``MusicScore`` ``Part`` shape surfaces.
        """
        metadata: Dict[str, Dict[str, Any]] = {}
        part_list = root.find("part-list")

        if part_list is None:
            return metadata

        for score_part in part_list.findall("score-part"):
            part_id = score_part.get("id")

            if not part_id:
                continue

            part_name = score_part.find("part-name")
            part_abbreviation = score_part.find("part-abbreviation")
            midi_instrument = score_part.find("midi-instrument")
            midi_channel = midi_instrument.find("midi-channel") if midi_instrument is not None else None
            midi_program = midi_instrument.find("midi-program") if midi_instrument is not None else None

            metadata[part_id] = {
                "part_name":         part_name.text if part_name is not None and part_name.text else part_id,
                "part_abbreviation": part_abbreviation.text if part_abbreviation is not None and part_abbreviation.text else None,
                "midi_channel":      int(midi_channel.text) if midi_channel is not None and midi_channel.text else None,
                "midi_program":      int(midi_program.text) if midi_program is not None and midi_program.text else None,
            }

        return metadata

    def _select_parts(self, parts: List[Any], part_index: Optional[int]) -> List[Any]:
        if part_index is None:
            return parts

        if part_index < 0 or part_index >= len(parts):
            raise ValueError(f"Part index {part_index} out of range (file has {len(parts)} parts)")

        return [ parts[part_index] ]

    def _parse_part(
        self,
        part_element: Any,
        state: Dict[str, Any],
        part: Dict[str, Any],
        tempos: List[Dict[str, Any]],
        time_signatures: List[Dict[str, Any]],
        key_signatures: List[Dict[str, Any]],
        harmonies: List[Dict[str, Any]],
    ) -> None:
        """Walk measures in one part, mutating ``state`` (divisions/tempo) and
        appending to ``part`` (notes/lyrics/clefs) and the score-level lists
        (tempos/time_signatures/key_signatures/harmonies). The cursor is a tick
        count that advances with notes and respects ``backup``/``forward``.
        """
        cursor_tick = 0

        for measure in part_element.findall("measure"):
            for element in measure:
                tag = element.tag.split("}")[-1]

                if tag == "attributes":
                    self._apply_attributes(element, cursor_tick, state, part, time_signatures, key_signatures)
                elif tag == "sound":
                    self._apply_sound(element, cursor_tick, state, tempos)
                elif tag == "direction":
                    self._apply_direction(element, cursor_tick, state, tempos)
                elif tag == "harmony":
                    self._apply_harmony(element, cursor_tick, state, part["id"], harmonies)
                elif tag == "note":
                    cursor_tick = self._parse_note(element, cursor_tick, state, part)
                elif tag == "backup":
                    cursor_tick -= self._read_duration(element)
                elif tag == "forward":
                    cursor_tick += self._read_duration(element)

    def _apply_attributes(
        self,
        element: Any,
        cursor_tick: int,
        state: Dict[str, Any],
        part: Dict[str, Any],
        time_signatures: List[Dict[str, Any]],
        key_signatures: List[Dict[str, Any]],
    ) -> None:
        divisions_element = element.find("divisions")

        if divisions_element is not None and divisions_element.text:
            state["divisions"] = int(divisions_element.text)

        time_element = element.find("time")

        if time_element is not None:
            beats = time_element.find("beats")
            beat_type = time_element.find("beat-type")

            if beats is not None and beat_type is not None:
                time_signatures.append({
                    "time":      self._ticks_to_seconds(cursor_tick, state),
                    "beats":     int(beats.text),
                    "beat_type": int(beat_type.text),
                })

        key_element = element.find("key")

        if key_element is not None:
            fifths = key_element.find("fifths")
            mode = key_element.find("mode")

            if fifths is not None and fifths.text:
                key_signatures.append({
                    "time":   self._ticks_to_seconds(cursor_tick, state),
                    "fifths": int(fifths.text),
                    "mode":   mode.text if mode is not None and mode.text else "major",
                })

        for clef_element in element.findall("clef"):
            sign = clef_element.find("sign")
            line = clef_element.find("line")

            if sign is None or not sign.text:
                continue

            part["clefs"].append({
                "time":  self._ticks_to_seconds(cursor_tick, state),
                "sign":  sign.text,
                "line":  int(line.text) if line is not None and line.text else 0,
                "staff": int(clef_element.get("number") or 1),
            })

    def _apply_sound(
        self,
        element: Any,
        cursor_tick: int,
        state: Dict[str, Any],
        tempos: List[Dict[str, Any]],
    ) -> None:
        tempo_attr = element.get("tempo")

        if tempo_attr is not None:
            bpm = float(tempo_attr)
            tempos.append({
                "time":             self._ticks_to_seconds(cursor_tick, state),
                "beats_per_minute": bpm,
            })
            state["tempo"] = bpm

    def _apply_direction(
        self,
        element: Any,
        cursor_tick: int,
        state: Dict[str, Any],
        tempos: List[Dict[str, Any]],
    ) -> None:
        """Pick up tempos from ``<direction>``: nested ``<sound tempo>`` for the
        playback value, or ``<direction-type><metronome>`` as the notated mark.
        """
        sound = element.find("sound")

        if sound is not None:
            self._apply_sound(sound, cursor_tick, state, tempos)

        metronome = element.find("direction-type/metronome")

        if metronome is not None:
            per_minute = metronome.find("per-minute")

            if per_minute is not None and per_minute.text:
                bpm = float(per_minute.text)
                tempos.append({
                    "time":             self._ticks_to_seconds(cursor_tick, state),
                    "beats_per_minute": bpm,
                })
                state["tempo"] = bpm

    def _apply_harmony(
        self,
        element: Any,
        cursor_tick: int,
        state: Dict[str, Any],
        part_id: str,
        harmonies: List[Dict[str, Any]],
    ) -> None:
        root = element.find("root")
        kind = element.find("kind")

        if root is None or kind is None or not (kind.text or ""):
            return

        root_step = root.find("root-step")
        root_alter = root.find("root-alter")

        if root_step is None or not root_step.text:
            return

        bass = element.find("bass")
        bass_step = bass.find("bass-step") if bass is not None else None
        bass_alter = bass.find("bass-alter") if bass is not None else None

        harmonies.append({
            "time":       self._ticks_to_seconds(cursor_tick, state),
            "part_id":    part_id,
            "root_step":  root_step.text,
            "root_alter": int(root_alter.text) if root_alter is not None and root_alter.text else 0,
            "kind":       kind.text,
            "bass_step":  bass_step.text if bass_step is not None and bass_step.text else None,
            "bass_alter": int(bass_alter.text) if bass_alter is not None and bass_alter.text else None,
        })

    def _parse_note(
        self,
        element: Any,
        cursor_tick: int,
        state: Dict[str, Any],
        part: Dict[str, Any],
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

        part["notes"].append({
            "start_time": self._ticks_to_seconds(note_start_tick, state),
            "end_time":   self._ticks_to_seconds(note_start_tick + duration_ticks, state),
            "pitch":      midi_pitch,
            "velocity":   self._DEFAULT_VELOCITY,
        })

        note_index = len(part["notes"]) - 1

        for lyric_element in element.findall("lyric"):
            text = lyric_element.find("text")

            if text is None or not text.text:
                continue

            syllabic = lyric_element.find("syllabic")
            number = lyric_element.get("number")

            part["lyrics"].append({
                "note_index": note_index,
                "text":       text.text,
                "syllabic":   syllabic.text if syllabic is not None and syllabic.text else None,
                "number":     int(number) if number is not None and number.isdigit() else None,
            })

        return next_cursor

    def _read_duration(self, element: Any) -> int:
        duration_element = element.find("duration")

        if duration_element is None or not duration_element.text:
            return 0

        return int(duration_element.text)

    def _ticks_to_seconds(self, tick: int, state: Dict[str, Any]) -> float:
        return tick / state["divisions"] * 60.0 / state["tempo"]

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
    """Parses a Standard MIDI File into a ``MusicScore``.

    Each ``(track, channel)`` combination with note activity becomes one
    ``Part``; this keeps Format-0 files (one track, many channels) and
    Format-1 files (one track per instrument) parsing the same way, and
    preserves the GM convention that channel 10 is drums. The tempo and
    time-signature maps are collected across all tracks so per-channel
    note times remain consistent when the tempo lives on a dedicated meta
    track. MusicXML-only fields (``harmonies``, ``clefs``, lyric
    ``syllabic``/``number``) are left empty / ``None``.

    When ``part_index`` is set, only the part at that index in the sorted
    ``(track, channel)`` list is returned.
    """

    _DEFAULT_TICKS_PER_BEAT = 480       # MIDI PPQ fallback when the header reports 0
    _DEFAULT_TEMPO_US_PER_BEAT = 500000 # MIDI default when no set_tempo message exists (120 BPM)

    def load(self, path: str, part_index: Optional[int]) -> MusicScore:
        import mido

        midi = mido.MidiFile(path)
        ticks_per_beat = midi.ticks_per_beat or self._DEFAULT_TICKS_PER_BEAT

        tempo_events, time_signatures, key_signatures = self._collect_meta_events(midi, ticks_per_beat)
        part_keys, track_names, part_lyrics = self._collect_part_keys(midi)
        selected_keys = self._select_part_keys(part_keys, part_index)

        parts: List[Dict[str, Any]] = []

        for track_index, channel in selected_keys:
            notes, programs = self._parse_track(
                midi.tracks[track_index],
                channel,
                tempo_events,
                ticks_per_beat,
            )
            notes.sort(key=lambda note: note["start_time"])

            parts.append({
                "id":                f"T{track_index}_C{channel}",
                "part_name":         track_names.get(track_index) or f"Track {track_index} Channel {channel}",
                "part_abbreviation": None,
                "midi_channel":      channel,
                "midi_program":      programs[0] if programs else None,
                "notes":             notes,
                "lyrics":            part_lyrics.get(track_index, []),
                "clefs":             [],
            })

        tempos = [
            { "time": self._tick_to_seconds(tick, tempo_events, ticks_per_beat),
              "beats_per_minute": 60_000_000 / tempo }
            for tick, tempo in tempo_events
        ]

        duration = max(
            (note["end_time"] for part in parts for note in part["notes"]),
            default=0.0,
        )

        return MusicScore({
            "format":          MusicScoreLoaderFormat.MIDI.value,
            "duration":        duration,
            "parts":           parts,
            "tempos":          tempos,
            "time_signatures": time_signatures,
            "key_signatures":  key_signatures,
            "harmonies":       [],
        })

    def _collect_meta_events(
        self,
        midi: Any,
        ticks_per_beat: int,
    ) -> Tuple[List[Tuple[int, int]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Collect tempo map (tick → µs/beat), time signatures, and key
        signatures across all tracks so per-track note times stay consistent
        even when tempo changes live on a different track than the notes.
        """
        tempo_events: List[Tuple[int, int]] = []
        time_signature_events: List[Tuple[int, int, int]] = []
        key_signature_events: List[Tuple[int, int, str]] = []

        for track in midi.tracks:
            absolute_tick = 0

            for message in track:
                absolute_tick += message.time

                if self._is_set_tempo(message):
                    tempo_events.append((absolute_tick, message.tempo))
                elif self._is_time_signature(message):
                    time_signature_events.append((absolute_tick, message.numerator, message.denominator))
                elif self._is_key_signature(message):
                    key_signature_events.append((absolute_tick, message.key, ""))

        if not tempo_events:
            tempo_events.append((0, self._DEFAULT_TEMPO_US_PER_BEAT))

        tempo_events.sort(key=lambda event: event[0])
        time_signature_events.sort(key=lambda event: event[0])
        key_signature_events.sort(key=lambda event: event[0])

        time_signatures = [
            { "time":      self._tick_to_seconds(tick, tempo_events, ticks_per_beat),
              "beats":     numerator,
              "beat_type": denominator }
            for tick, numerator, denominator in time_signature_events
        ]
        key_signatures = [
            { "time":   self._tick_to_seconds(tick, tempo_events, ticks_per_beat),
              **self._parse_midi_key(key) }
            for tick, key, _ in key_signature_events
        ]

        return tempo_events, time_signatures, key_signatures

    def _collect_part_keys(
        self,
        midi: Any,
    ) -> Tuple[List[Tuple[int, int]], Dict[int, str], Dict[int, List[Dict[str, Any]]]]:
        """Scan every track for note-emitting ``(track, channel)`` pairs and
        pick up ``track_name``/``lyrics`` meta. Lyrics are reported at the
        track level because MIDI meta ``lyrics`` carry no channel.
        """
        part_keys: List[Tuple[int, int]] = []
        track_names: Dict[int, str] = {}
        track_lyrics: Dict[int, List[Dict[str, Any]]] = {}

        for track_index, track in enumerate(midi.tracks):
            seen_channels: set = set()

            for message in track:
                if self._is_note_on(message) and message.channel not in seen_channels:
                    seen_channels.add(message.channel)
                    part_keys.append((track_index, message.channel))
                elif self._is_track_name(message):
                    track_names[track_index] = message.name
                elif self._is_lyrics(message):
                    track_lyrics.setdefault(track_index, []).append({
                        "note_index": -1,
                        "text":       message.text,
                        "syllabic":   None,
                        "number":     None,
                    })

        if not part_keys:
            part_keys.append((0, 0))

        return part_keys, track_names, track_lyrics

    def _select_part_keys(
        self,
        part_keys: List[Tuple[int, int]],
        part_index: Optional[int],
    ) -> List[Tuple[int, int]]:
        if part_index is None:
            return part_keys

        if part_index < 0 or part_index >= len(part_keys):
            raise ValueError(f"Part index {part_index} out of range (file has {len(part_keys)} parts)")

        return [ part_keys[part_index] ]

    def _parse_track(
        self,
        track: Any,
        channel: int,
        tempo_events: List[Tuple[int, int]],
        ticks_per_beat: int,
    ) -> Tuple[List[Dict[str, Any]], List[int]]:
        open_notes: Dict[int, Tuple[int, int]] = {}  # pitch → (start_tick, velocity)
        notes: List[Dict[str, Any]] = []
        programs: List[int] = []
        absolute_tick = 0

        for message in track:
            absolute_tick += message.time

            if self._is_program_change(message) and message.channel == channel:
                programs.append(message.program)
                continue

            if self._is_note_on(message) and message.channel == channel:
                open_notes[message.note] = (absolute_tick, message.velocity)
                continue

            if not (self._is_note_off(message) and message.channel == channel):
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

        return notes, programs

    @staticmethod
    def _is_set_tempo(message: Any) -> bool:
        return message.type == "set_tempo"

    @staticmethod
    def _is_time_signature(message: Any) -> bool:
        return message.type == "time_signature"

    @staticmethod
    def _is_key_signature(message: Any) -> bool:
        return message.type == "key_signature"

    @staticmethod
    def _is_track_name(message: Any) -> bool:
        return message.type == "track_name"

    @staticmethod
    def _is_lyrics(message: Any) -> bool:
        return message.type == "lyrics"

    @staticmethod
    def _is_program_change(message: Any) -> bool:
        return message.type == "program_change"

    @staticmethod
    def _is_note_on(message: Any) -> bool:
        return message.type == "note_on" and message.velocity > 0

    @staticmethod
    def _is_note_off(message: Any) -> bool:
        # MIDI convention: a note_on with velocity 0 is a note_off.
        return message.type == "note_off" or (message.type == "note_on" and message.velocity == 0)

    @staticmethod
    def _parse_midi_key(key: str) -> Dict[str, Any]:
        """Translate mido's ``key_signature`` string (e.g. ``"C"``, ``"Am"``,
        ``"F#m"``) into the ``MusicScore`` ``KeySignature`` ``fifths``/``mode``
        pair. mido already resolves the enharmonic choice, so we recover
        ``fifths`` by looking up the tonic in the circle-of-fifths table.
        """
        mode = "minor" if key.endswith("m") else "major"
        tonic = key[:-1] if mode == "minor" else key
        fifths = _KEY_TONIC_TO_FIFTHS.get((tonic, mode), 0)

        return { "fifths": fifths, "mode": mode }

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
    async def _prepare_input(self, context: ComponentActionContext) -> Any:
        return await context.render_variable(self.config.source)

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        format = await context.render_variable(self.config.format)
        part   = await context.render_scalar(self.config.part, int, None) if self.config.part is not None else None

        if isinstance(format, MusicScoreLoaderFormat):
            format = format.value

        params.update({
            "format": format,
            "part":   part,
        })

        return params

    async def _load_batch(
        self,
        sources: List[Any],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[MusicScore]:
        return await asyncio.gather(*[
            self._load(source, params, cancellation_token) for source in sources
        ])

    async def _load(
        self,
        source: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> MusicScore:
        path, spooled = await self._resolve_source_path(source, params["format"])

        try:
            format = params["format"] or self._sniff_format(path)
            result = await asyncio.to_thread(self._parse_score_file, path, format, params["part"])
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
    def _parse_score_file(path: str, format: str, part_index: Optional[int]) -> MusicScore:
        if format == MusicScoreLoaderFormat.MIDI.value:
            return MidiScoreLoader().load(path, part_index)
        if format == MusicScoreLoaderFormat.MUSICXML.value:
            return MusicXmlScoreLoader().load(path, part_index)
        raise ValueError(f"Unsupported score format: {format!r}")


@register_music_score_loader_driver(MusicScoreLoaderDriverType.LOCAL)
class LocalMusicScoreLoaderService(MusicScoreLoaderDriver):
    def __init__(self, id: str, config: MusicScoreLoaderComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [ "mido" ]

    async def _run(self, action: MusicScoreLoaderActionConfig, context: ComponentActionContext) -> Any:
        return await LocalMusicScoreLoaderAction(action).run(context)
