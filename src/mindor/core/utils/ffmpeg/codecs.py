from __future__ import annotations

from typing import Dict, Optional, Tuple

# Fallback (video_codec, audio_codec) per container when the encoding config leaves them unset.
_VIDEO_FORMAT_CODEC_MAP: Dict[str, Tuple[str, str]] = {
    "mp4":  ("libx264",    "aac"),
    "m4v":  ("libx264",    "aac"),
    "mov":  ("libx264",    "aac"),
    "mkv":  ("libx264",    "aac"),
    "webm": ("libvpx-vp9", "libopus"),
    "avi":  ("mpeg4",      "libmp3lame"),
    "ogv":  ("libtheora",  "libvorbis"),
    "gif":  ("gif",        None),
}

# Fallback audio codec per container when the encoding config leaves it unset.
_AUDIO_FORMAT_CODEC_MAP: Dict[str, str] = {
    "mp3":  "libmp3lame",
    "wav":  "pcm_s16le",
    "flac": "flac",
    "aac":  "aac",
    "m4a":  "aac",
    "opus": "libopus",
    "ogg":  "libvorbis",
}

def get_video_codecs_for_format(format: str) -> Tuple[Optional[str], Optional[str]]:
    return _VIDEO_FORMAT_CODEC_MAP.get(format, (None, None))

def get_audio_codec_for_format(format: str) -> Optional[str]:
    return _AUDIO_FORMAT_CODEC_MAP.get(format)
