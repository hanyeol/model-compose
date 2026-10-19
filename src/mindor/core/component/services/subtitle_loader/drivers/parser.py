from __future__ import annotations

from typing import Optional, Dict, List, Any
import html, re


class SubtitleParser:
    """Base for subtitle parsers. Owns the shared text-normalization helpers."""

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", html.unescape(text)).strip()

class WebVttSubtitleParser(SubtitleParser):
    """Parse WebVTT via webvtt-py so inline timestamp tags survive.

    pysubs2's WebVTT reader inherits SubRip's cue-header detection
    (`len(TIMESTAMP.findall(line)) == 2`) and misreads any cue whose text
    line itself holds two inline timestamps, which is the normal shape for
    YouTube auto-generated captions.
    """

    _INLINE_TS_PATTERN = re.compile(r"<(\d{2}):(\d{2}):(\d{2})\.(\d{3})>")
    _CUE_TAG_PATTERN   = re.compile(r"</?c[^>]*>", re.IGNORECASE)

    # webvtt-py's `start_in_seconds` truncates to whole seconds; parse ms ourselves.
    _VTT_TS_PATTERN    = re.compile(r"(?:(\d+):)?(\d{2}):(\d{2})\.(\d{3})")

    def parse(self, path: str, encoding: Optional[str]) -> Dict[str, Any]:
        import webvtt

        captions = list(webvtt.read(path, encoding=encoding))
        is_asr = any(self._INLINE_TS_PATTERN.search(caption.raw_text or "") for caption in captions)

        segments = self._build_asr_segments(captions) if is_asr else self._build_plain_segments(captions)
        full_text = " ".join(segment["text"] for segment in segments)

        return {
            "segments":  segments,
            "full_text": full_text,
            "format":    "vtt",
        }

    def _build_plain_segments(self, captions: List[Any]) -> List[Dict[str, Any]]:
        segments: List[Dict[str, Any]] = []

        for caption in captions:
            text = self._normalize_text(caption.text)

            if not text:
                continue

            start_time = self._vtt_ts_to_seconds(caption.start)
            end_time   = self._vtt_ts_to_seconds(caption.end)

            segments.append({
                "text":       text,
                "start_time": start_time,
                "end_time":   end_time,
                "duration":   end_time - start_time,
            })

        return segments

    def _build_asr_segments(self, captions: List[Any]) -> List[Dict[str, Any]]:
        """Collapse YouTube ASR vtt into one segment per spoken line.

        YouTube ASR cues are rolling: each cue repeats the previous line
        above the new line, and a ~10 ms "flash" cue sits between every
        pair of content cues. We treat only the *last* line of each cue as
        new text, drop a segment whose text equals the previous one (that
        absorbs the flash cue), and set each segment's `end_time` to the
        next segment's `start_time` so adjacent segments abut.
        """
        segments: List[Dict[str, Any]] = []

        for caption in captions:
            lines = (caption.raw_text or "").split("\n")

            if not lines:
                continue

            last_line = lines[-1]
            text = self._normalize_text(self._strip_cue_markup(last_line))

            if not text:
                continue

            if segments and segments[-1]["text"] == text:
                continue

            cue_start = self._vtt_ts_to_seconds(caption.start)
            cue_end   = self._vtt_ts_to_seconds(caption.end)

            segment: Dict[str, Any] = {
                "text":       text,
                "start_time": cue_start,
                "end_time":   cue_end,
                "duration":   cue_end - cue_start,
            }

            words = self._parse_word_timestamps(last_line, cue_start, cue_end)

            if words:
                segment["words"] = words

            segments.append(segment)

        for index in range(len(segments) - 1):
            next_start = segments[index + 1]["start_time"]
            segments[index]["end_time"] = next_start
            segments[index]["duration"] = next_start - segments[index]["start_time"]

        return segments

    def _parse_word_timestamps(self, line: str, cue_start: float, cue_end: float) -> List[Dict[str, Any]]:
        """Split a cue line into word-level timed chunks.

        Line shape:  `word0<ts1><c> word1</c><ts2><c> word2</c>`.
        Chunk N starts at the preceding `<ts>` (or `cue_start` for the
        leading chunk) and ends at the following `<ts>` (or `cue_end` for
        the trailing chunk). Returns an empty list when the line has no
        inline timestamps.
        """
        line = self._CUE_TAG_PATTERN.sub("", line)
        timestamps = list(self._INLINE_TS_PATTERN.finditer(line))

        if not timestamps:
            return []

        chunks: List[Dict[str, Any]] = []
        current_start = cue_start
        pos = 0

        for match in timestamps:
            chunks.append({
                "text":  line[pos:match.start()],
                "start": current_start,
                "end":   None,
            })

            current_start = self._inline_ts_to_seconds(*match.groups())
            pos = match.end()

        chunks.append({
            "text":  line[pos:],
            "start": current_start,
            "end":   cue_end,
        })

        for index in range(len(chunks) - 1):
            chunks[index]["end"] = chunks[index + 1]["start"]

        words: List[Dict[str, Any]] = []

        for chunk in chunks:
            text = self._normalize_text(chunk["text"])

            if not text:
                continue

            words.append({
                "text":       text,
                "start_time": chunk["start"],
                "end_time":   chunk["end"],
            })

        return words

    def _strip_cue_markup(self, raw: str) -> str:
        return self._INLINE_TS_PATTERN.sub("", self._CUE_TAG_PATTERN.sub("", raw))

    def _vtt_ts_to_seconds(self, ts: str) -> float:
        match = self._VTT_TS_PATTERN.search(ts)

        if not match:
            raise ValueError(f"Invalid WebVTT timestamp: {ts!r}")

        h, m, s, ms = match.groups()

        return int(h or 0) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0

    def _inline_ts_to_seconds(self, h: str, m: str, s: str, ms: str) -> float:
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0

class Pysubs2SubtitleParser(SubtitleParser):
    """Parse SRT/ASS/SSA/etc. via pysubs2."""

    def parse(self, path: str, format: Optional[str], encoding: Optional[str]) -> Dict[str, Any]:
        import pysubs2

        load_params: Dict[str, Any] = {}

        if encoding is not None:
            load_params["encoding"] = encoding

        if format:
            load_params["format_"] = format

        subtitles = pysubs2.load(path, **load_params)
        segments: List[Dict[str, Any]] = []

        for event in subtitles.events:
            if event.type != "Dialogue":
                continue

            start_time = event.start / 1000.0
            end_time   = event.end / 1000.0

            segments.append({
                "text":       event.plaintext,
                "start_time": start_time,
                "end_time":   end_time,
                "duration":   end_time - start_time,
            })

        full_text = " ".join(segment["text"] for segment in segments)

        return {
            "segments":  segments,
            "full_text": full_text,
            "format":    subtitles.format,
        }

def parse_subtitle_file(path: str, format: Optional[str], encoding: Optional[str]) -> Dict[str, Any]:
    """Parse a subtitle file into the subtitle-loader result shape.

    VTT files go through `WebVttSubtitleParser`; everything else through
    `Pysubs2SubtitleParser`.
    """
    format = (format or _sniff_format(path, encoding)) or ""

    if format.lower() == "vtt":
        return WebVttSubtitleParser().parse(path, encoding)

    return Pysubs2SubtitleParser().parse(path, format, encoding)

def _sniff_format(path: str, encoding: Optional[str]) -> Optional[str]:
    try:
        with open(path, "r", encoding=encoding or "utf-8-sig") as fp:
            head = fp.read(128)
    except OSError:
        return None

    return "vtt" if head.lstrip().startswith("WEBVTT") else None
