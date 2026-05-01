from typing import Optional, Dict
import wave, io

def pcm_to_wav(data: bytes, attrs: Optional[Dict[str, str]] = None) -> bytes:
    attrs = attrs or {}
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(int(attrs.get("channels", 1)))
        wav.setsampwidth(int(attrs.get("bit_depth", 16)) // 8)
        wav.setframerate(int(attrs.get("sample_rate", 44100)))
        wav.writeframes(data)
    return buffer.getvalue()
