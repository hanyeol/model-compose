from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import MediaInspectorComponentConfig, MediaInspectorDriver
from mindor.dsl.schema.action import MediaInspectorActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.variable.time import parse_time
from mindor.core.utils.shell import run_command, run_subprocess
from mindor.core.logger import logging
from ..base import MediaInspectorService, register_media_inspector_service
from ..base import ComponentActionContext
from .common import MediaInspectorAction
import asyncio, json
from mindor.core.component.action.media import MediaInputPathResolver

# ExifTool groups tags under family-1 group names (File, EXIF, XMP, ...). We
# keep these buckets in the normalized output so callers can address
# `metadata.exif` without walking the flat tag list. Everything else falls
# under `metadata.other`.
_KNOWN_GROUPS = {
    "File", "EXIF", "XMP", "IPTC", "ICC_Profile", "MakerNotes", "Composite", "GPS", "QuickTime", "PNG", "JFIF"
}

class ExiftoolMediaInspectorAction(MediaInspectorAction):
    async def _inspect_batch(
        self,
        sources: List[MediaSource],
        return_raw: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        return await asyncio.gather(*[
            self._inspect(source, return_raw) for source in sources
        ])

    async def _inspect(self, source: MediaSource, return_raw: bool) -> Dict[str, Any]:
        input_path, spooled = await MediaInputPathResolver.resolve(source)

        try:
            raw, tags, groups = await self._probe(input_path, source)

            size     = tags.get("FileSize")
            width    = tags.get("ImageWidth") or tags.get("ExifImageWidth")
            height   = tags.get("ImageHeight") or tags.get("ExifImageHeight")
            duration = tags.get("Duration") or tags.get("MediaDuration")

            # QuickTime/MP4 sometimes ship duration as a formatted 'HH:MM:SS'
            # string that exiftool -n doesn't touch; parse_time handles both.
            try:
                duration = parse_time(duration) if duration is not None else None
            except ValueError:
                duration = None

            result: Dict[str, Any] = {
                "path":        input_path,
                "format":      self._pick_format(tags, source.format),
                "mime_type":   tags.get("MIMEType"),
                "size":        int(size)   if size   is not None else None,
                "width":       int(width)  if width  is not None else None,
                "height":      int(height) if height is not None else None,
                "duration":    duration,
                "created_at":  tags.get("CreateDate") or tags.get("DateTimeOriginal"),
                "modified_at": tags.get("ModifyDate") or tags.get("FileModifyDate"),
                "camera":      self._extract_camera(tags),
                "gps":         self._extract_gps(tags),
                "metadata":    self._group_by_family(groups),
            }

            if return_raw:
                result["raw"] = raw

            return result
        finally:
            if spooled and input_path is not None:
                self._remove_file(input_path)

    @staticmethod
    async def _probe(input_path: Optional[str], source: MediaSource) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Dict[str, Any]]]:
        # -j: JSON output, one dict per file.
        # -G1: prefix each tag with its family-1 group (e.g. `EXIF:Model`)
        #      so we can bucket the flat tag list without a second pass.
        # -n: return numeric values instead of human-readable ("PrintConv")
        #     — coordinates come back as signed decimals, dates as strings.
        # exiftool spells stdin as a lone `-` argument.
        command = [
            "exiftool", "-j", "-G1", "-n",
            input_path if input_path is not None else "-",
        ]

        if input_path is not None:
            stdout, stderr, returncode = await run_command(command)
        else:
            process, stdout, stderr = await run_subprocess(
                command,
                source=source.stream,
                stdout_handler=lambda r: r.read(),
                stderr_handler=lambda r: r.read(),
            )
            returncode = process.returncode

        if returncode != 0:
            error_message = stderr.decode("utf-8", errors="replace") if stderr else ""
            raise RuntimeError(f"exiftool failed (exit code {returncode}): {error_message}")

        logging.debug("exiftool completed: %s", f"'{input_path}'" if input_path is not None else "-")

        results = json.loads(stdout.decode("utf-8"))

        if not results:
            raise RuntimeError("exiftool returned no metadata")

        tags: Dict[str, Any] = {}
        groups: Dict[str, Dict[str, Any]] = {}

        for key, value in results[0].items():
            if ":" in key:
                group, tag = key.split(":", 1)
            else:
                group, tag = "", key

            # First occurrence wins so callers get the more specific group
            # (EXIF beats Composite) when the same tag appears twice.
            tags.setdefault(tag, value)

            if group:
                groups.setdefault(group, {})[tag] = value

        return results[0], tags, groups

    @staticmethod
    def _pick_format(tags: Dict[str, Any], hint: Optional[str]) -> Optional[str]:
        # `FileType` is the container/format name (e.g. "JPEG", "PNG", "MP4").
        # Prefer the caller's hint when it matches; otherwise use ExifTool's
        # detection, lowercased for consistency with the ffmpeg driver.
        file_type = str(tags["FileType"]).lower() if tags.get("FileType") else None

        if hint and file_type and hint == file_type:
            return hint

        return file_type if file_type else (hint if hint else None)

    @staticmethod
    def _extract_camera(tags: Dict[str, Any]) -> Dict[str, Any]:
        iso               = tags.get("ISO")
        aperture          = tags.get("FNumber") or tags.get("ApertureValue")
        focal_length      = tags.get("FocalLength")
        focal_length_35mm = tags.get("FocalLengthIn35mmFormat")

        return {
            "make":              tags.get("Make"),
            "model":             tags.get("Model"),
            "lens":              tags.get("LensModel") or tags.get("Lens"),
            "software":          tags.get("Software"),
            "iso":               int(iso)                 if iso               is not None else None,
            "aperture":          float(aperture)          if aperture          is not None else None,
            "shutter_speed":     tags.get("ExposureTime") or tags.get("ShutterSpeedValue"),
            "focal_length":      float(focal_length)      if focal_length      is not None else None,
            "focal_length_35mm": float(focal_length_35mm) if focal_length_35mm is not None else None,
        }

    @staticmethod
    def _extract_gps(tags: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        latitude  = tags.get("GPSLatitude")
        longitude = tags.get("GPSLongitude")
        altitude  = tags.get("GPSAltitude")

        if latitude is None and longitude is None:
            return None

        return {
            "latitude":  float(latitude)  if latitude  is not None else None,
            "longitude": float(longitude) if longitude is not None else None,
            "altitude":  float(altitude)  if altitude  is not None else None,
            "timestamp": tags.get("GPSDateTime") or tags.get("GPSTimeStamp"),
        }

    @staticmethod
    def _group_by_family(groups: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        # Group tags by exiftool's family-1 group name. Returns a lowercase-keyed
        # dict where each known group (EXIF, XMP, ...) is its own sub-dict of
        # `{tag_name: value}`. Anything outside the known set is folded into
        # `other` so callers still get everything without a flat scan.
        result: Dict[str, Dict[str, Any]] = {}

        for group, tags in groups.items():
            key = group.lower() if group in _KNOWN_GROUPS else "other"
            bucket = result.setdefault(key, {})
            for tag, value in tags.items():
                bucket.setdefault(tag, value)

        return result

@register_media_inspector_service(MediaInspectorDriver.EXIFTOOL)
class ExiftoolMediaInspectorService(MediaInspectorService):
    def __init__(self, id: str, config: MediaInspectorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: MediaInspectorActionConfig, context: ComponentActionContext) -> Any:
        return await ExiftoolMediaInspectorAction(action).run(context)
