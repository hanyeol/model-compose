"""End-to-end tests for the local music-score-loader parsers.

Each test builds a tiny score file (MIDI or MusicXML) on disk, runs it through
the parser, and checks the emitted notes/tempo/duration are what we expect.
"""

import os
import tempfile
import pytest

from mindor.core.component.services.music_score_loader.drivers.local import (
    LocalMusicScoreLoaderAction,
)

pytest.importorskip("mido")


_MINIMAL_MUSICXML = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="4.0">
  <part-list><score-part id="P1"><part-name>Melody</part-name></score-part></part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>480</divisions>
        <time><beats>4</beats><beat-type>4</beat-type></time>
      </attributes>
      <sound tempo="120"/>
      <note><pitch><step>C</step><octave>4</octave></pitch><duration>480</duration></note>
      <note><pitch><step>E</step><octave>4</octave></pitch><duration>480</duration></note>
      <note><pitch><step>F</step><alter>1</alter><octave>4</octave></pitch><duration>480</duration></note>
      <note><rest/><duration>480</duration></note>
    </measure>
  </part>
</score-partwise>
"""


def _write_midi(path: str) -> None:
    """Write a two-note MIDI file (C4 then E4, quarter notes at 120 BPM)."""
    import mido

    midi = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    midi.tracks.append(track)
    track.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
    track.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
    track.append(mido.Message("note_on",  note=60, velocity=100, time=0))
    track.append(mido.Message("note_off", note=60, velocity=0,   time=480))
    track.append(mido.Message("note_on",  note=64, velocity=90,  time=0))
    track.append(mido.Message("note_off", note=64, velocity=0,   time=480))
    midi.save(path)


class TestMidiParser:
    def test_simple_two_note_file(self, tmp_path):
        midi_path = str(tmp_path / "test.mid")
        _write_midi(midi_path)

        result = LocalMusicScoreLoaderAction._parse_score_file(midi_path, "midi", None)

        assert result["format"] == "midi"
        assert result["tempo"] == pytest.approx(120.0)
        assert result["time_signature"] == [4, 4]
        assert result["duration"] == pytest.approx(1.0)
        assert len(result["notes"]) == 2

        first, second = result["notes"]
        assert first["pitch"] == 60
        assert first["start_time"] == pytest.approx(0.0)
        assert first["end_time"] == pytest.approx(0.5)
        assert second["pitch"] == 64
        assert second["start_time"] == pytest.approx(0.5)
        assert second["end_time"] == pytest.approx(1.0)

    def test_format_sniffed_from_header(self, tmp_path):
        midi_path = str(tmp_path / "noext")
        _write_midi(midi_path)

        format = LocalMusicScoreLoaderAction._sniff_format(midi_path)
        assert format == "midi"


class TestMusicXmlParser:
    def test_minimal_file(self, tmp_path):
        xml_path = tmp_path / "test.xml"
        xml_path.write_text(_MINIMAL_MUSICXML, encoding="utf-8")

        result = LocalMusicScoreLoaderAction._parse_score_file(str(xml_path), "musicxml", None)

        assert result["format"] == "musicxml"
        assert result["tempo"] == pytest.approx(120.0)
        assert result["time_signature"] == [4, 4]
        assert len(result["notes"]) == 3  # Rest is skipped

        # Pitches: C4=60, E4=64, F#4=66 (alter=+1)
        assert [note["pitch"] for note in result["notes"]] == [60, 64, 66]
        # Rest preserves the cursor, so duration is 1.5s not 1.0s
        assert result["duration"] == pytest.approx(1.5)

    def test_format_sniffed_from_xml_prolog(self, tmp_path):
        xml_path = tmp_path / "noext"
        xml_path.write_text(_MINIMAL_MUSICXML, encoding="utf-8")

        format = LocalMusicScoreLoaderAction._sniff_format(str(xml_path))
        assert format == "musicxml"

    def test_rejects_timewise_layout(self, tmp_path):
        xml_path = tmp_path / "timewise.xml"
        xml_path.write_text(
            '<?xml version="1.0"?><score-timewise><measure/></score-timewise>',
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="score-partwise"):
            LocalMusicScoreLoaderAction._parse_score_file(str(xml_path), "musicxml", None)


class TestSniffer:
    def test_unknown_extension_errors(self, tmp_path):
        path = tmp_path / "nope.txt"
        path.write_bytes(b"random stuff")

        with pytest.raises(ValueError, match="Cannot infer"):
            LocalMusicScoreLoaderAction._sniff_format(str(path))
