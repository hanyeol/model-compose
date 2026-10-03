from __future__ import annotations
from typing import TYPE_CHECKING

from typing import List, Optional, Dict, Any, Union, Tuple
from mindor.dsl.schema.component import Model3DRendererComponentConfig
from mindor.dsl.schema.action import Model3DRendererActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.image import ImageStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.utils.files import get_file_extension
from mindor.core.logger import logging
from .....action.media import MediaInputPathResolver
from ...base import Model3DRendererDriver, Model3DRendererDriverType, register_model_3d_renderer_driver
from ...base import ComponentActionContext
from ..common import Model3DRendererAction
from .shaders import get_vertex_shader, get_fragment_shader
from PIL import Image as PILImage
import asyncio, os, math

if TYPE_CHECKING:
    import numpy as np
    import moderngl
    import trimesh

_DEFAULT_CAMERA: Dict[str, Any] = {
    "yaw": 30.0,
    "pitch": 20.0,
    "roll": 0.0,
    "distance": None,
    "fov": 45.0,
    "up": "y",
}

_DEFAULT_LIGHTING: Dict[str, Any] = {
    "preset": "studio",
    "ambient": 0.3,
    "directional": 1.0,
    "exposure": 1.0,
    # True: the rig moves with the camera, so every view is lit the same way.
    # False: the rig is pinned to where it sits for the default camera, so the
    # lighting stays fixed in world space across views (turntables, multi-view sets).
    "follow_camera": True,
}

# Light rigs are authored in CAMERA space (+x right, +y up, +z toward the viewer)
# as (direction from the surface toward the light, linear RGB, relative intensity).
# Intensities are calibrated so a white Lambert surface facing a light receives
# exactly that light's color. `sky` / `ground` form a hemisphere ambient around
# world +Y that also serves as a cheap reflection environment; both are scaled
# by `lighting.ambient`, the direct lights by `lighting.directional`.
_LIGHT_RIGS: Dict[str, Dict[str, Any]] = {
    "studio": {
        "lights": [
            ((-0.6, 0.7,  0.8), (1.00, 0.97, 0.93), 1.00),  # key: upper left, in front of the subject
            (( 0.8, 0.1,  0.6), (0.93, 0.96, 1.00), 0.35),  # fill: right, near eye level
            (( 0.2, 0.6, -0.8), (1.00, 1.00, 1.00), 0.70),  # rim: behind and above, separates the silhouette
        ],
        "sky":    (1.00, 1.00, 1.00),
        "ground": (0.45, 0.43, 0.40),
    },
    "flat": {
        "lights": [
            (( 0.0, 0.25, 1.0), (1.00, 1.00, 1.00), 0.80),  # headlight
        ],
        "sky":    (1.00, 1.00, 1.00),
        "ground": (1.00, 1.00, 1.00),
    },
    "outdoor": {
        "lights": [
            (( 0.5, 0.9,  0.4), (1.00, 0.94, 0.85), 1.40),  # sun: high, front right
        ],
        "sky":    (0.70, 0.80, 1.00),
        "ground": (0.42, 0.38, 0.32),
    },
}

_CREASE_ANGLE_DEG = 45.0  # edges sharper than this stay hard when normals are generated
_MSAA_SAMPLES = 8
_FALLBACK_BASE_COLOR_SRGB = (0.8, 0.8, 0.82)
_ALPHA_MODES = { "OPAQUE": 0, "MASK": 1, "BLEND": 2 }
_TEXTURE_SLOTS = ("base_color", "metallic_roughness", "normal", "occlusion", "emissive")  # = texture units 0..4


class ModelMatrixHelper:
    """Build model-space matrices applied to loaded meshes."""

    @staticmethod
    def translation(offset: np.ndarray) -> np.ndarray:
        import numpy as np

        matrix = np.eye(4, dtype="f4")
        matrix[:3, 3] = offset

        return matrix

class CameraMatrixHelper:
    """Build view / projection matrices for a yaw-pitch-roll camera orbiting the origin."""

    @staticmethod
    def view(distance: float, yaw_deg: float, pitch_deg: float, roll_deg: float) -> np.ndarray:
        import numpy as np

        yaw = math.radians(yaw_deg)
        pitch = math.radians(pitch_deg)
        roll = math.radians(roll_deg)

        rot_y = np.array([
            [ math.cos(yaw), 0.0, math.sin(yaw), 0.0],
            [          0.0, 1.0,          0.0, 0.0],
            [-math.sin(yaw), 0.0, math.cos(yaw), 0.0],
            [          0.0, 0.0,          0.0, 1.0],
        ])
        rot_x = np.array([
            [1.0,              0.0,              0.0, 0.0],
            [0.0, math.cos(pitch), -math.sin(pitch), 0.0],
            [0.0, math.sin(pitch),  math.cos(pitch), 0.0],
            [0.0,              0.0,              0.0, 1.0],
        ])
        rot_z = np.array([
            [math.cos(roll), -math.sin(roll), 0.0, 0.0],
            [math.sin(roll),  math.cos(roll), 0.0, 0.0],
            [          0.0,              0.0, 1.0, 0.0],
            [          0.0,              0.0, 0.0, 1.0],
        ])
        translation = np.eye(4)
        translation[2, 3] = -distance

        return (translation @ rot_z @ rot_x @ rot_y).astype("f4")

    @staticmethod
    def perspective(fov_rad: float, aspect: float, znear: float, zfar: float) -> np.ndarray:
        import numpy as np

        f = 1.0 / math.tan(fov_rad / 2.0)
        matrix = np.zeros((4, 4), dtype="f4")
        matrix[0, 0] = f / aspect
        matrix[1, 1] = f
        matrix[2, 2] = (zfar + znear) / (znear - zfar)
        matrix[2, 3] = (2 * zfar * znear) / (znear - zfar)
        matrix[3, 2] = -1.0

        return matrix

class NativeModel3DRendererAction(Model3DRendererAction):
    async def _render_batch(
        self,
        models: List[MediaSource],
        cameras: List[Optional[Dict[str, Any]]],
        lightings: List[Optional[Dict[str, Any]]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[ImageStreamResource]:
        return await asyncio.gather(*[
            self._render(model, camera, lighting, params)
            for model, camera, lighting in zip(models, cameras, lightings)
        ])

    async def _render(
        self,
        source: MediaSource,
        camera: Optional[Dict[str, Any]],
        lighting: Optional[Dict[str, Any]],
        params: Dict[str, Any],
    ) -> ImageStreamResource:
        input_path, spooled = await MediaInputPathResolver().resolve(source, default_format=source.format)
        input_format = source.format or (get_file_extension(input_path) if input_path else None)

        if not input_format:
            raise RuntimeError("Cannot determine 3D model input format.")

        logging.debug("Rendering 3D model from '%s' (format=%s)", input_path, input_format)

        try:
            image = await asyncio.to_thread(self._render_image, input_path, input_format, camera, lighting, params)
        finally:
            if spooled:
                try:
                    os.remove(input_path)
                except FileNotFoundError:
                    pass

        return ImageStreamResource(image, format=params["format"])

    def _render_image(
        self,
        input_path: str,
        input_format: str,
        camera: Optional[Dict[str, Any]],
        lighting: Optional[Dict[str, Any]],
        params: Dict[str, Any],
    ) -> PILImage.Image:
        import numpy as np
        import moderngl

        camera   = self._resolve_camera(camera)
        lighting = self._resolve_lighting(lighting)

        width, height = int(params["width"]), int(params["height"])
        background    = params["background"] or (0, 0, 0, 0)

        submeshes = self._load_submeshes(input_path, input_format, camera["up"])

        if not submeshes:
            raise RuntimeError("Loaded 3D model has no renderable geometry.")

        all_vertices = np.vstack([ submesh["positions"] for submesh in submeshes ])
        center       = (all_vertices.min(axis=0) + all_vertices.max(axis=0)) / 2.0
        radius       = float(np.linalg.norm(all_vertices.max(axis=0) - all_vertices.min(axis=0))) / 2.0 or 1.0

        # Fit the bounding sphere into the narrower of the two FOVs so portrait
        # outputs don't clip the model horizontally.
        aspect    = width / height
        fov_rad   = math.radians(camera["fov"])
        half_fov  = min(fov_rad / 2.0, math.atan(math.tan(fov_rad / 2.0) * aspect))
        fit_scale = { "contain": 1.0, "cover": 0.75, "none": 1.0 }.get(params["fit"], 1.0)
        distance  = camera["distance"] if camera["distance"] is not None else radius / math.sin(half_fov) * fit_scale

        # Clip planes hug the bounding sphere, relative to model size, so depth
        # precision holds for millimetre- and kilometre-scale assets alike.
        znear = max(distance - radius * 1.5, radius * 0.005)
        zfar  = distance + radius * 1.5

        model_matrix      = ModelMatrixHelper.translation(-center)
        view_matrix       = CameraMatrixHelper.view(distance, camera["yaw"], camera["pitch"], camera["roll"])
        projection_matrix = CameraMatrixHelper.perspective(fov_rad, aspect, znear=znear, zfar=zfar)

        view_rotation   = view_matrix[:3, :3].astype(np.float64)
        camera_position = -view_rotation.T @ view_matrix[:3, 3].astype(np.float64)  # world space (model centered)

        if lighting["follow_camera"]:
            rig_rotation = view_rotation
        else:
            rig_rotation = CameraMatrixHelper.view(1.0, _DEFAULT_CAMERA["yaw"], _DEFAULT_CAMERA["pitch"], 0.0)[:3, :3].astype(np.float64)

        light_vectors, light_colors, sky_color, ground_color = self._build_lights(lighting, rig_rotation)

        ctx = self._create_context()

        try:
            program = ctx.program(vertex_shader=get_vertex_shader("pbr"), fragment_shader=get_fragment_shader("pbr"))
            self._set_uniform(program, "model",      data=model_matrix.T.astype("f4").tobytes())
            self._set_uniform(program, "view",       data=view_matrix.T.astype("f4").tobytes())
            self._set_uniform(program, "projection", data=projection_matrix.T.astype("f4").tobytes())

            padded_vectors = light_vectors + [ np.zeros(3) ] * (4 - len(light_vectors))
            padded_colors  = light_colors  + [ np.zeros(3) ] * (4 - len(light_colors))
            self._set_uniform(program, "light_count",     len(light_vectors))
            self._set_uniform(program, "light_vectors",   data=np.asarray(padded_vectors, dtype="f4").tobytes())
            self._set_uniform(program, "light_colors",    data=np.asarray(padded_colors,  dtype="f4").tobytes())
            self._set_uniform(program, "sky_color",       tuple(float(c) for c in sky_color))
            self._set_uniform(program, "ground_color",    tuple(float(c) for c in ground_color))
            self._set_uniform(program, "camera_position", tuple(float(c) for c in camera_position))
            self._set_uniform(program, "exposure",        lighting["exposure"])

            for unit, slot in enumerate(_TEXTURE_SLOTS):
                self._set_uniform(program, f"{slot}_texture", unit)

            # Every sampler always gets a valid texture (some drivers warn otherwise):
            # white for color/data maps, a flat (128, 128, 255) one for the normal map.
            placeholders = {
                "default": ctx.texture((1, 1), components=4, data=bytes([255, 255, 255, 255])),
                "normal":  ctx.texture((1, 1), components=4, data=bytes([128, 128, 255, 255])),
            }
            texture_cache: Dict[int, moderngl.Texture] = {}

            samples   = min(_MSAA_SAMPLES, ctx.max_samples) if ctx.max_samples >= 2 else 0
            color_rbo = ctx.renderbuffer((width, height), components=4, samples=samples)
            depth_rbo = ctx.depth_renderbuffer((width, height), samples=samples)
            fbo = ctx.framebuffer(color_attachments=[color_rbo], depth_attachment=depth_rbo)
            fbo.use()

            ctx.enable(moderngl.DEPTH_TEST)
            ctx.disable(moderngl.CULL_FACE)  # two-sided: the shader flips back-facing normals
            fbo.clear(0.0, 0.0, 0.0, 0.0)    # background is composited afterwards, on straight alpha

            opaque  = [ submesh for submesh in submeshes if submesh["alpha_mode"] != "BLEND" ]
            blended = [ submesh for submesh in submeshes if submesh["alpha_mode"] == "BLEND" ]
            blended.sort(key=lambda submesh: -float(np.linalg.norm(submesh["centroid"] - center - camera_position)))

            for submesh in opaque:
                self._draw_submesh(ctx, program, submesh, texture_cache, placeholders)

            if blended:
                ctx.enable(moderngl.BLEND)
                ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA, moderngl.ONE, moderngl.ONE_MINUS_SRC_ALPHA)
                fbo.depth_mask = False

                for submesh in blended:
                    self._draw_submesh(ctx, program, submesh, texture_cache, placeholders)

                fbo.depth_mask = True
                ctx.disable(moderngl.BLEND)

            if samples:
                resolve_rbo = ctx.renderbuffer((width, height), components=4)
                resolve_fbo = ctx.framebuffer(color_attachments=[resolve_rbo])
                ctx.copy_framebuffer(resolve_fbo, fbo)
                pixels = resolve_fbo.read(components=4, alignment=1)
            else:
                pixels = fbo.read(components=4, alignment=1)
        finally:
            ctx.release()

        return self._compose_output_image(pixels, width, height, background, params["format"])

    def _draw_submesh(
        self,
        ctx: moderngl.Context,
        program: moderngl.Program,
        submesh: Dict[str, Any],
        texture_cache: Dict[int, moderngl.Texture],
        placeholders: Dict[str, moderngl.Texture],
    ) -> None:
        import numpy as np
        import moderngl

        interleaved = np.hstack([
            submesh["positions"], submesh["normals"], submesh["uvs"], submesh["colors"],
        ]).astype("f4")
        vbo = ctx.buffer(interleaved.tobytes())
        vao = ctx.vertex_array(program, [
            (vbo, "3f 3f 2f 4f", "in_position", "in_normal", "in_uv", "in_color"),
        ])

        material = submesh["material"]
        self._set_uniform(program, "base_color_factor", tuple(float(c) for c in material["base_color_factor"]))
        self._set_uniform(program, "metallic_factor",   float(material["metallic"]))
        self._set_uniform(program, "roughness_factor",  float(material["roughness"]))
        self._set_uniform(program, "emissive_factor",   tuple(float(c) for c in material["emissive"]))
        self._set_uniform(program, "alpha_mode",        _ALPHA_MODES[material["alpha_mode"]])
        self._set_uniform(program, "alpha_cutoff",      float(material["alpha_cutoff"]))
        self._set_uniform(program, "use_vertex_color",  bool(submesh["has_vertex_color"]))

        for unit, slot in enumerate(_TEXTURE_SLOTS):
            image   = material["textures"].get(slot)
            texture = self._upload_texture(ctx, image, texture_cache) if image is not None else None
            self._set_uniform(program, f"use_{slot}_texture", texture is not None)
            (texture or placeholders.get(slot, placeholders["default"])).use(location=unit)

        vao.render(moderngl.TRIANGLES)

        vao.release()
        vbo.release()

    @staticmethod
    def _compose_output_image(pixels: bytes, width: int, height: int, background: Any, image_format: str) -> PILImage.Image:
        import numpy as np

        rgba  = np.frombuffer(pixels, dtype=np.uint8).reshape(height, width, 4).astype(np.float32)
        alpha = rgba[..., 3:4]

        # Anti-aliased silhouettes (and blended surfaces) were resolved against a
        # transparent black clear, i.e. they are premultiplied. Un-premultiply so
        # PNG gets straight alpha without dark fringes.
        rgb   = np.where(alpha > 0.0, rgba[..., :3] * (255.0 / np.maximum(alpha, 1.0)), 0.0)
        layer = np.concatenate([ np.clip(rgb, 0.0, 255.0), alpha ], axis=-1).round().astype(np.uint8)
        image = PILImage.fromarray(np.ascontiguousarray(layer[::-1]))  # GL rows are bottom-up

        background = tuple(int(channel) for channel in background)

        if len(background) == 3:
            background = background + (255,)

        if image_format != "png":
            # No alpha channel in the output: flatten onto the background color.
            base = PILImage.new("RGBA", image.size, background[:3] + (255,))
            return PILImage.alpha_composite(base, image).convert("RGB")

        if background[3] > 0:
            base  = PILImage.new("RGBA", image.size, background)
            image = PILImage.alpha_composite(base, image)

        return image

    @staticmethod
    def _create_context() -> moderngl.Context:
        import moderngl

        try:
            return moderngl.create_standalone_context()
        except Exception as default_error:
            # Headless Linux (no X display): fall back to EGL.
            try:
                return moderngl.create_standalone_context(backend="egl")
            except Exception:
                raise default_error

    @staticmethod
    def _resolve_camera(value: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        value = value or {}

        return {
            "yaw":      float(value.get("yaw",      _DEFAULT_CAMERA["yaw"])),
            "pitch":    float(value.get("pitch",    _DEFAULT_CAMERA["pitch"])),
            "roll":     float(value.get("roll",     _DEFAULT_CAMERA["roll"])),
            "fov":      float(value.get("fov",      _DEFAULT_CAMERA["fov"])),
            "up":       str(value.get("up",         _DEFAULT_CAMERA["up"])),
            "distance": float(value["distance"]) if value.get("distance") is not None else None,
        }

    @staticmethod
    def _resolve_lighting(value: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        value = value or {}

        return {
            "preset":        str(value.get("preset",          _DEFAULT_LIGHTING["preset"])),
            "ambient":       float(value.get("ambient",       _DEFAULT_LIGHTING["ambient"])),
            "directional":   float(value.get("directional",   _DEFAULT_LIGHTING["directional"])),
            "exposure":      float(value.get("exposure",      _DEFAULT_LIGHTING["exposure"])),
            "follow_camera": bool(value.get("follow_camera",  _DEFAULT_LIGHTING["follow_camera"])),
        }

    @staticmethod
    def _build_lights(lighting: Dict[str, Any], rig_rotation: np.ndarray) -> Tuple[List[np.ndarray], List[np.ndarray], np.ndarray, np.ndarray]:
        """Return (light vectors, light colors, sky color, ground color), all in world space.

        Light vectors point from the surface toward the light. The rig is authored
        in camera space; `rig_rotation` is the world->camera rotation it rides on,
        so world = rig_rotation.T @ camera.
        """
        import numpy as np

        rig = _LIGHT_RIGS.get(lighting["preset"], _LIGHT_RIGS["studio"])
        vectors: List[np.ndarray] = []
        colors:  List[np.ndarray] = []

        for direction, color, weight in rig["lights"][:4]:
            direction = np.asarray(direction, dtype=np.float64)
            direction = direction / np.linalg.norm(direction)
            vectors.append(rig_rotation.T @ direction)
            colors.append(np.asarray(color, dtype=np.float64) * weight * lighting["directional"])

        sky    = np.asarray(rig["sky"],    dtype=np.float64) * lighting["ambient"]
        ground = np.asarray(rig["ground"], dtype=np.float64) * lighting["ambient"]

        return vectors, colors, sky, ground

    def _load_submeshes(self, input_path: str, input_format: str, up: str) -> List[Dict[str, Any]]:
        """Load the model as a list of submeshes (one per scene-graph instance).

        Returned keys per submesh:
          - positions, normals, uvs, colors: numpy arrays, one row per triangle corner
          - has_vertex_color: bool (colors are linear RGBA)
          - material: dict from `_extract_material`
          - alpha_mode: "OPAQUE" | "MASK" | "BLEND"
          - centroid: mean corner position, for sorting blended geometry
        """
        import numpy as np
        import trimesh

        loaded = trimesh.load(input_path, file_type=input_format, force="scene")
        scene: trimesh.Scene = loaded if isinstance(loaded, trimesh.Scene) else trimesh.Scene(loaded)

        up_matrix = np.eye(4)

        if up == "z":
            up_matrix = trimesh.transformations.rotation_matrix(-math.pi / 2.0, [1, 0, 0])

        # glTF vertex colors are linear by spec; PLY/OBJ/... colors are display (sRGB) values.
        colors_are_linear = str(input_format).lower() in ("glb", "gltf")
        submeshes: List[Dict[str, Any]] = []

        # Walk the scene graph instead of `scene.dump()`: dump() copies each geometry
        # without trimesh's cache, which is where the file's own vertex normals live,
        # so they would be silently replaced by recomputed ones.
        for node_name in scene.graph.nodes_geometry:
            transform, geometry_name = scene.graph[node_name]
            mesh = scene.geometry.get(geometry_name)

            # Points and lines (PointCloud / Path3D) have no faces to shade.
            if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
                continue

            matrix = up_matrix @ np.asarray(transform, dtype=np.float64)
            linear = matrix[:3, :3]
            faces  = np.asarray(mesh.faces, dtype=np.int64)

            if np.linalg.det(linear) < 0.0:
                faces = faces[:, ::-1]  # mirrored instance: keep counter-clockwise front faces

            vertices     = np.asarray(mesh.vertices, dtype=np.float64) @ linear.T + matrix[:3, 3]
            file_normals = self._load_cached_vertex_normals(mesh)

            if file_normals is not None:
                normals = (file_normals @ np.linalg.inv(linear))[faces].reshape(-1, 3)  # inverse-transpose
            else:
                normals = self._generate_crease_normals(vertices, faces)

            normals   = normals / np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-12)
            positions = vertices[faces].reshape(-1, 3)
            uvs       = self._extract_uvs(mesh, faces)
            colors    = self._extract_corner_colors(mesh, faces, colors_are_linear)
            material  = self._extract_material(mesh, has_uv=uvs is not None)

            submeshes.append({
                "positions":        positions.astype("f4"),
                "normals":          normals.astype("f4"),
                "uvs":              (uvs if uvs is not None else np.zeros((len(positions), 2))).astype("f4"),
                "colors":           (colors if colors is not None else np.ones((len(positions), 4))).astype("f4"),
                "has_vertex_color": colors is not None,
                "material":         material,
                "alpha_mode":       material["alpha_mode"],
                "centroid":         positions.mean(axis=0),
            })

        return submeshes

    @staticmethod
    def _load_cached_vertex_normals(mesh: trimesh.Trimesh) -> Optional[np.ndarray]:
        """Vertex normals that came with the file, or None when trimesh would have to invent them.

        trimesh keeps loaded normals in its cache, so check the cache before touching
        `mesh.vertex_normals` (which would otherwise compute and cache smoothed ones).
        """
        import numpy as np

        try:
            if "vertex_normals" not in mesh._cache:
                return None
        except Exception:
            return None

        normals = np.asarray(mesh.vertex_normals, dtype=np.float64)

        if normals.shape != mesh.vertices.shape or not np.isfinite(normals).all():
            return None

        return normals

    @staticmethod
    def _generate_crease_normals(vertices: np.ndarray, faces: np.ndarray, crease_deg: float = _CREASE_ANGLE_DEG) -> np.ndarray:
        """Per-corner normals: smooth across edges flatter than `crease_deg`, hard otherwise.

        Corners are grouped by welded position (not vertex index), so UV seams and
        STL triangle soup still shade smoothly. Each corner averages the
        area-weighted normals of the faces around its position whose orientation is
        within `crease_deg` of its own face.
        """
        import numpy as np

        triangles  = vertices[faces]
        face_area  = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])  # |.| = 2 * area
        face_unit  = face_area / np.maximum(np.linalg.norm(face_area, axis=1, keepdims=True), 1e-30)
        corner_cnt = faces.size

        extent = float(np.ptp(vertices, axis=0).max()) or 1.0
        keys   = np.round(vertices / (extent * 1e-6)).astype(np.int64)
        _, welded = np.unique(keys, axis=0, return_inverse=True)
        welded = np.asarray(welded).reshape(-1)

        corner_vertex = welded[faces].reshape(-1)
        corner_face   = np.repeat(np.arange(len(faces)), 3)
        order         = np.argsort(corner_vertex, kind="stable")
        sorted_vertex = corner_vertex[order]
        sorted_face   = corner_face[order]

        starts   = np.flatnonzero(np.r_[True, sorted_vertex[1:] != sorted_vertex[:-1]])
        counts   = np.diff(np.r_[starts, corner_cnt])
        group_of = np.repeat(np.arange(len(starts)), counts)
        size_of  = counts[group_of]
        cos_crease = math.cos(math.radians(crease_deg))
        accum = np.zeros((corner_cnt, 3))

        # Pathological fans (> 64 faces on one position): plain average, no crease test.
        fan = np.flatnonzero(size_of > 64)

        if len(fan) > 0:
            group_sum = np.stack([
                np.bincount(group_of, weights=face_area[sorted_face, axis], minlength=len(starts))
                for axis in range(3)
            ], axis=1)
            accum[fan] = group_sum[group_of[fan]]

        # Everything else: compare each corner against every corner sharing its
        # position, in chunks so memory stays bounded on large meshes.
        regular = np.flatnonzero(size_of <= 64)
        position, max_pairs = 0, 1_000_000

        while position < len(regular):
            pairs_cum = np.cumsum(size_of[regular[position:position + max_pairs]])
            end = position + max(1, int(np.searchsorted(pairs_cum, max_pairs, side="right")))
            rows = regular[position:end]
            reps = size_of[rows]
            left = np.repeat(rows, reps)
            offset = np.arange(int(reps.sum())) - np.repeat(np.cumsum(reps) - reps, reps)
            right = starts[group_of[left]] + offset
            face_left, face_right = sorted_face[left], sorted_face[right]
            keep = np.einsum("ij,ij->i", face_unit[face_left], face_unit[face_right]) >= cos_crease

            for axis in range(3):
                accum[:, axis] += np.bincount(left[keep], weights=face_area[face_right[keep], axis], minlength=corner_cnt)

            position = end

        normals = np.empty_like(accum)
        normals[order] = accum  # back to face-major corner order (= vertices[faces].reshape(-1, 3))

        return normals

    @staticmethod
    def _extract_uvs(mesh: trimesh.Trimesh, faces: np.ndarray) -> Optional[np.ndarray]:
        """Per-corner UVs ready for sampling textures uploaded top row first, or None.

        trimesh stores UVs with a bottom-left origin (its glTF loader already flips
        V), while `_upload_texture` uploads PIL rows top-first, so V is flipped once
        more here.
        """
        import numpy as np

        uv = getattr(getattr(mesh, "visual", None), "uv", None)

        if uv is None or len(uv) != len(mesh.vertices):
            return None

        corner = np.asarray(uv, dtype=np.float64)[:, :2][faces].reshape(-1, 2)
        corner[:, 1] = 1.0 - corner[:, 1]

        return corner

    def _extract_material(self, mesh: trimesh.Trimesh, has_uv: bool) -> Dict[str, Any]:
        """Material as linear-space factors + texture images (PIL) keyed by `_TEXTURE_SLOTS`."""
        import numpy as np
        from trimesh.visual.material import PBRMaterial, SimpleMaterial

        material = getattr(getattr(mesh, "visual", None), "material", None)
        result: Dict[str, Any] = {
            "base_color_factor": np.append(self._srgb_to_linear(_FALLBACK_BASE_COLOR_SRGB), 1.0),
            "metallic":          0.0,
            "roughness":         0.6,
            "emissive":          np.zeros(3),
            "alpha_mode":        "OPAQUE",
            "alpha_cutoff":      0.5,
            "textures":          {},
        }

        if isinstance(material, PBRMaterial):
            # glTF semantics: factors are linear and default to 1. Do NOT use
            # `main_color` here: trimesh returns its 0.4 default gray when
            # baseColorFactor is absent, which would darken every texture.
            factor = material.baseColorFactor
            result["base_color_factor"] = np.ones(4) if factor is None else self._to_unit_color(factor)[:4]
            result["metallic"]     = 1.0 if material.metallicFactor  is None else float(material.metallicFactor)
            result["roughness"]    = 1.0 if material.roughnessFactor is None else float(material.roughnessFactor)
            result["alpha_mode"]   = str(material.alphaMode or "OPAQUE").upper()
            result["alpha_cutoff"] = 0.5 if material.alphaCutoff is None else float(material.alphaCutoff)

            if material.emissiveFactor is not None:
                result["emissive"] = np.asarray(material.emissiveFactor, dtype=np.float64)[:3]

            if has_uv:
                result["textures"] = {
                    "base_color":         material.baseColorTexture,
                    "metallic_roughness": material.metallicRoughnessTexture,
                    "normal":             material.normalTexture,
                    "occlusion":          material.occlusionTexture,
                    "emissive":           material.emissiveTexture,
                }
        elif isinstance(material, SimpleMaterial):
            diffuse = self._to_unit_color(material.diffuse)
            result["base_color_factor"] = np.append(self._srgb_to_linear(diffuse[:3]), 1.0)
            image = material.image if has_uv else None

            if image is not None:
                result["textures"] = { "base_color": image }

                if self._has_cutout_alpha(image):
                    result["alpha_mode"] = "MASK"

        if result["alpha_mode"] not in _ALPHA_MODES:
            result["alpha_mode"] = "OPAQUE"

        result["textures"] = { slot: image for slot, image in result["textures"].items() if image is not None }

        return result

    @staticmethod
    def _has_cutout_alpha(image: PILImage.Image) -> bool:
        import numpy as np

        if image.mode not in ("RGBA", "LA", "PA") and "transparency" not in image.info:
            return False

        alpha = np.asarray(image.convert("RGBA").getchannel("A"))

        return bool((alpha < 128).mean() > 0.001)

    def _extract_corner_colors(self, mesh: trimesh.Trimesh, faces: np.ndarray, linear: bool) -> Optional[np.ndarray]:
        """Per-corner linear RGBA colors from vertex colors, face colors or glTF COLOR_0 on textured meshes."""
        import numpy as np

        visual = getattr(mesh, "visual", None)
        colors = None

        if type(visual).__name__ == "ColorVisuals":
            kind = getattr(visual, "kind", None)

            if kind == "vertex":
                colors = np.asarray(visual.vertex_colors)[faces].reshape(len(faces) * 3, -1)
            elif kind == "face":
                colors = np.repeat(np.asarray(visual.face_colors), 3, axis=0)
        elif type(visual).__name__ == "TextureVisuals":
            attributes = getattr(visual, "vertex_attributes", None)

            if attributes is not None and "color" in attributes:
                raw = np.asarray(attributes["color"])

                if raw.ndim == 2 and len(raw) == len(mesh.vertices):
                    colors = raw[faces].reshape(len(faces) * 3, -1)

        if colors is None or len(colors) == 0:
            return None

        colors = self._to_unit_color(colors)

        if colors.shape[1] == 3:
            colors = np.hstack([ colors, np.ones((len(colors), 1)) ])

        colors = colors[:, :4]

        if not linear:
            colors[:, :3] = self._srgb_to_linear(colors[:, :3])

        return colors

    @staticmethod
    def _upload_texture(ctx: moderngl.Context, image: PILImage.Image, cache: Dict[int, moderngl.Texture]) -> moderngl.Texture:
        """Upload a PIL image as an RGBA 2D texture (once per image per render)."""
        texture = cache.get(id(image))

        if texture is None:
            rgba = image.convert("RGBA")
            texture = ctx.texture(rgba.size, components=4, data=rgba.tobytes())
            texture.build_mipmaps()  # also switches the min filter to trilinear

            if ctx.max_anisotropy > 1.0:
                texture.anisotropy = min(8.0, ctx.max_anisotropy)

            cache[id(image)] = texture

        return texture

    @staticmethod
    def _srgb_to_linear(values: Any) -> np.ndarray:
        import numpy as np

        values = np.asarray(values, dtype=np.float64)

        return np.where(values <= 0.04045, values / 12.92, ((values + 0.055) / 1.055) ** 2.4)

    @staticmethod
    def _to_unit_color(values: Any) -> np.ndarray:
        """Colors as 0..1 floats: trimesh hands out uint8, raw glTF accessors may be float or uint16."""
        import numpy as np

        array = np.asarray(values)

        if array.dtype.kind in "ui":
            return array.astype(np.float64) / float(np.iinfo(array.dtype).max)

        array = array.astype(np.float64)

        return array / 255.0 if array.size and array.max() > 1.0 else array

    @staticmethod
    def _set_uniform(program: moderngl.Program, name: str, value: Any = None, data: Optional[bytes] = None) -> None:
        """Set a uniform, ignoring ones the GLSL compiler optimized away."""
        uniform = program.get(name, None)

        if uniform is None:
            return

        if data is not None:
            uniform.write(data)
        else:
            uniform.value = value

@register_model_3d_renderer_driver(Model3DRendererDriverType.NATIVE)
class NativeModel3DRendererService(Model3DRendererDriver):
    def __init__(self, id: str, config: Model3DRendererComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [
            *(super()._get_setup_requirements() or []),
            "trimesh",
            "moderngl",
            "numpy",
        ]

    async def _run(self, action: Model3DRendererActionConfig, context: ComponentActionContext) -> Any:
        return await NativeModel3DRendererAction(action).run(context)
