from __future__ import annotations

from typing import Dict

# ffmpeg picks the output muxer from a filename's extension, but ffprobe
# reports containers by muxer name — some of those (e.g. `matroska`) aren't
# valid filename extensions. Map muxer-only names (or muxer names whose
# canonical file extension differs) to an extension ffmpeg autodetects.
# Muxers whose name already matches the extension (mp4, webm, avi, mp3, ...)
# do not need an entry.
_MUXER_EXTENSION_MAP: Dict[str, str] = {
    # video / mixed containers
    "matroska":       "mkv",
    "mpegts":         "ts",
    "mpeg":           "mpg",
    "mpeg1video":     "mpg",
    "mpeg2video":     "mpg",
    "asf":            "wmv",
    "asf_stream":     "wmv",
    "svcd":           "vob",
    "vcd":            "mpg",
    "dvd":            "vob",

    # streaming manifests
    "hls":            "m3u8",
    "dash":           "mpd",

    # audio containers
    "adts":           "aac",
    "ac3":            "ac3",
    "eac3":           "eac3",
    "dts":            "dts",
    "spdif":          "spdif",
    "oga":            "oga",
    "spx":            "spx",
    "opus":           "opus",
    "mlp":            "mlp",
    "truehd":         "thd",

    # raw video / bitstream muxers whose extension differs
    "h264":           "h264",
    "hevc":           "h265",
    "rawvideo":       "yuv",
    "data":           "bin",

    # image sequences (single-frame outputs)
    "image2":         "jpg",
    "singlejpeg":     "jpg",

    # subtitle muxers
    "srt":            "srt",
    "webvtt":         "vtt",
    "ass":            "ass",
    "microdvd":       "sub",
    "jacosub":        "jss",
}

def get_extension_for_muxer(muxer: str) -> str:
    """Convert an ffmpeg muxer name to a filename extension ffmpeg autodetects."""
    return _MUXER_EXTENSION_MAP.get(muxer, muxer)
