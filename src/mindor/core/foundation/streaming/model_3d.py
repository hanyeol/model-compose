from __future__ import annotations

from typing import Union, Optional, Dict, Any, List
from collections.abc import AsyncIterator
from mindor.core.utils.files import get_file_extension
from .resources import StreamResource, TeeStreamResource
from .bytes import BytesStreamResource
from .file import UploadFileStreamResource
from .media import MediaSource
from starlette.datastructures import UploadFile

# glTF variants and USDZ are the only 3D formats with IANA-registered `model/*`
# MIME types (Khronos + Apple registrations); PLY, splat, and FBX fall back to
# `application/octet-stream` because no registration exists.
_MODEL_3D_CONTENT_TYPE_MAP: Dict[str, str] = {
    "glb":   "model/gltf-binary",
    "gltf":  "model/gltf+json",
    "obj":   "model/obj",
    "stl":   "model/stl",
    "ply":   "application/octet-stream",
    "splat": "application/octet-stream",
    "usdz":  "model/vnd.usdz+zip",
    "fbx":   "application/octet-stream",
}

def resolve_model_3d_content_type(format: Optional[str]) -> str:
    """Return the MIME content type for a 3D asset format (e.g. `glb`, `gltf`)."""
    if format:
        return _MODEL_3D_CONTENT_TYPE_MAP.get(format.lower(), "application/octet-stream")

    return "application/octet-stream"

def get_model_3d_file_extensions() -> List[str]:
    """Return the file extensions (with leading dot) accepted for 3D assets."""
    return [ f".{format}" for format in _MODEL_3D_CONTENT_TYPE_MAP ]

class Model3DStreamResource(StreamResource):
    def __init__(
        self,
        source: Union[StreamResource, bytes],
        format: Optional[str] = None,
        attrs: Optional[Dict[str, Any]] = None,
        filename: Optional[str] = None,
    ):
        super().__init__(resolve_model_3d_content_type(format), filename, size=self._resolve_size(source))

        self.source: StreamResource = source if isinstance(source, StreamResource) else BytesStreamResource(source)
        self.format: Optional[str] = format
        self.attrs: Dict[str, Any] = attrs or {}

    def copyable(self) -> bool:
        return self.source.copyable()

    def copy(self, count: int) -> List[Model3DStreamResource]:
        return [
            Model3DStreamResource(source, self.format, self.attrs, self.filename)
            for source in self.source.copy(count)
        ]

    def tee(self, sources: List[AsyncIterator[bytes]]) -> List[Model3DStreamResource]:
        return [
            Model3DStreamResource(
                source=TeeStreamResource(source),
                format=self.format,
                attrs=self.attrs,
                filename=self.filename,
            )
            for source in sources
        ]

    async def close(self) -> None:
        await self.source.close()

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        async for chunk in self.source:
            yield chunk

    @staticmethod
    def _resolve_size(source: Union[StreamResource, bytes]) -> Optional[int]:
        return source.size if isinstance(source, StreamResource) else len(source)

def create_model_3d_source(value: Any) -> MediaSource:
    if isinstance(value, Model3DStreamResource):
        return MediaSource(value.source, value.format, value.attrs)

    if isinstance(value, StreamResource):
        if getattr(value, "filename", None):
            return MediaSource(value, format=get_file_extension(getattr(value, "filename")))
        else:
            return MediaSource(value)

    if isinstance(value, UploadFile):
        if value.filename:
            return MediaSource(UploadFileStreamResource(value), format=get_file_extension(value.filename))
        else:
            return MediaSource(UploadFileStreamResource(value))

    if isinstance(value, (bytes, bytearray)):
        return MediaSource(BytesStreamResource(bytes(value)))

    raise TypeError(f"Unsupported 3D model source: {value.__class__.__name__}")
