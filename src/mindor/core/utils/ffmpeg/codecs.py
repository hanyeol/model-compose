from __future__ import annotations

from typing import Dict, Optional, Set, Tuple

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

# Codec → containers where alpha is preserved (measured). Codecs not listed
# either surface a hard error on mismatch (prores_ks + mp4) or don't support
# alpha at all, so no extra check is needed there. Only pairings whose failure
# is silent belong here.
_CODEC_ALPHA_CONTAINERS_MAP: Dict[str, Set[str]] = {
    "libvpx-vp9": { "webm", "mkv" },
}

# Pixel formats each encoder accepts. Encoders not listed here are treated as
# "unknown" and callers skip pix-fmt validation for them; this leaves hardware
# encoders (h264_videotoolbox, *_nvenc, ...) and custom builds unblocked at
# the cost of no early error on an unsupported format. Verified against
# `ffmpeg -h encoder=<name>` on ffmpeg 7.x for the common software encoders.
_SUPPORTED_PIXEL_FORMATS: Dict[str, Set[str]] = {
    "libx264": {
        "yuv420p", "yuvj420p", "yuv422p", "yuvj422p", "yuv444p", "yuvj444p",
        "nv12", "nv16", "nv21",
        "yuv420p10le", "yuv422p10le", "yuv444p10le", "nv20le",
        "gray", "gray10le",
    },
    "libx265": {
        "yuv420p", "yuvj420p", "yuv422p", "yuvj422p", "yuv444p", "yuvj444p",
        "gbrp",
        "yuv420p10le", "yuv422p10le", "yuv444p10le", "gbrp10le",
        "yuv420p12le", "yuv422p12le", "yuv444p12le", "gbrp12le",
        "gray", "gray10le", "gray12le",
    },
    "libvpx": {
        "yuv420p", "yuva420p",
    },
    "libvpx-vp9": {
        "yuv420p", "yuva420p", "yuv422p", "yuv440p", "yuv444p",
        "yuv420p10le", "yuv422p10le", "yuv440p10le", "yuv444p10le",
        "yuv420p12le", "yuv422p12le", "yuv440p12le", "yuv444p12le",
        "gbrp", "gbrp10le", "gbrp12le",
    },
    "libaom-av1": {
        "yuv420p", "yuv422p", "yuv444p", "gbrp",
        "yuv420p10le", "yuv422p10le", "yuv444p10le", "gbrp10le",
        "yuv420p12le", "yuv422p12le", "yuv444p12le", "gbrp12le",
        "gray", "gray10le", "gray12le",
    },
    "prores_ks": {
        "yuv422p10le", "yuv444p10le", "yuva444p10le",
    },
    "mpeg4": {
        "yuv420p",
    },
    "libtheora": {
        "yuv420p", "yuv422p", "yuv444p",
    },
    "gif": {
        "rgb8", "bgr8", "rgb4_byte", "bgr4_byte", "gray", "pal8",
    },
}

# Pixel formats that carry an alpha channel. Derived from `ffmpeg -pix_fmts`
# (component count 2 or 4 in a 4-component color model), captured explicitly
# rather than sniffed at runtime. Add new entries as ffmpeg introduces them.
_ALPHA_PIXEL_FORMATS: Set[str] = {
    # YUV+A (planar)
    "yuva420p", "yuva422p", "yuva444p",
    "yuva420p9be", "yuva420p9le", "yuva422p9be", "yuva422p9le", "yuva444p9be", "yuva444p9le",
    "yuva420p10be", "yuva420p10le", "yuva422p10be", "yuva422p10le", "yuva444p10be", "yuva444p10le",
    "yuva422p12be", "yuva422p12le", "yuva444p12be", "yuva444p12le",
    "yuva420p16be", "yuva420p16le", "yuva422p16be", "yuva422p16le", "yuva444p16be", "yuva444p16le",

    # YUV+A (packed)
    "ayuv64be", "ayuv64le", "vuya",

    # RGB+A (packed 8-bit)
    "rgba", "argb", "bgra", "abgr",

    # RGB+A (packed high-bit)
    "rgba64be", "rgba64le", "bgra64be", "bgra64le",
    "rgbaf16be", "rgbaf16le", "rgbaf32be", "rgbaf32le",

    # Grayscale+A
    "ya8", "ya16be", "ya16le",

    # Planar GBR+A
    "gbrap", "gbrap10be", "gbrap10le", "gbrap12be", "gbrap12le",
    "gbrap14be", "gbrap14le", "gbrap16be", "gbrap16le",
    "gbrapf32be", "gbrapf32le",
}

def get_video_codecs_for_format(format: str) -> Tuple[Optional[str], Optional[str]]:
    return _VIDEO_FORMAT_CODEC_MAP.get(format, (None, None))

def get_audio_codec_for_format(format: str) -> Optional[str]:
    return _AUDIO_FORMAT_CODEC_MAP.get(format)

def get_alpha_containers_for_codec(codec: str) -> Optional[Set[str]]:
    return _CODEC_ALPHA_CONTAINERS_MAP.get(codec)

def get_supported_pixel_formats(encoder: str) -> Optional[Set[str]]:
    return _SUPPORTED_PIXEL_FORMATS.get(encoder)

def has_alpha_channel(pixel_format: str) -> bool:
    return pixel_format in _ALPHA_PIXEL_FORMATS
