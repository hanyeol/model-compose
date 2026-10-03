"""GLSL sources for the native model-3d-renderer driver.

Kept out of `native.py` so the Python render loop and the GLSL program don't
share screen space during review. The strings are embedded in bytecode as
module constants, so there's no runtime cost to this split.

Lookup via `get_vertex_shader(name)` / `get_fragment_shader(name)` keyed by
shading model (e.g. "pbr"); adding a new model means adding a pair of
`_<name>_VERTEX_SHADER` / `_<name>_FRAGMENT_SHADER` constants and an entry in
the maps at the bottom of this file.
"""

_PBR_VERTEX_SHADER = """
#version 330
uniform mat4 model;
uniform mat4 view;
uniform mat4 projection;
in vec3 in_position;
in vec3 in_normal;
in vec2 in_uv;
in vec4 in_color;
out vec3 v_position;
out vec3 v_normal;
out vec2 v_uv;
out vec4 v_color;
void main() {
    vec4 world = model * vec4(in_position, 1.0);
    v_position = world.xyz;
    v_normal   = mat3(model) * in_normal;  // model is a pure translation
    v_uv       = in_uv;
    v_color    = in_color;
    gl_Position = projection * view * world;
}
"""

_PBR_FRAGMENT_SHADER = """
#version 330
#define MAX_LIGHTS 4
const float PI = 3.14159265359;

uniform int   light_count;
uniform vec3  light_vectors[MAX_LIGHTS];  // world space, surface -> light, unit length
uniform vec3  light_colors[MAX_LIGHTS];   // linear RGB * intensity
uniform vec3  sky_color;                  // linear, hemisphere light from +Y
uniform vec3  ground_color;               // linear, hemisphere light from -Y
uniform vec3  camera_position;
uniform float exposure;

uniform vec4  base_color_factor;          // linear
uniform float metallic_factor;
uniform float roughness_factor;
uniform vec3  emissive_factor;            // linear
uniform int   alpha_mode;                 // 0 OPAQUE, 1 MASK, 2 BLEND
uniform float alpha_cutoff;
uniform bool  use_vertex_color;

uniform bool use_base_color_texture;
uniform bool use_metallic_roughness_texture;
uniform bool use_normal_texture;
uniform bool use_occlusion_texture;
uniform bool use_emissive_texture;
uniform sampler2D base_color_texture;          // sRGB
uniform sampler2D metallic_roughness_texture;  // linear, G = roughness, B = metallic
uniform sampler2D normal_texture;              // linear, OpenGL (+Y up) convention as in glTF
uniform sampler2D occlusion_texture;           // linear, R
uniform sampler2D emissive_texture;            // sRGB

in vec3 v_position;
in vec3 v_normal;
in vec2 v_uv;
in vec4 v_color;
out vec4 frag_color;

vec3 srgb_to_linear(vec3 c) {
    return mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(vec3(0.04045), c));
}

vec3 linear_to_srgb(vec3 c) {
    c = clamp(c, 0.0, 1.0);
    return mix(c * 12.92, 1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, step(vec3(0.0031308), c));
}

// Highlight roll-off of Khronos PBR Neutral: values below 0.76 pass through untouched
// (albedo stays faithful), brighter ones compress smoothly toward white. Its toe offset
// is left out on purpose: it assumes a white-furnace environment and would crush dark
// albedos under this rig.
vec3 tonemap_neutral(vec3 color) {
    const float start_compression = 0.76;
    const float desaturation = 0.15;
    float peak = max(color.r, max(color.g, color.b));
    if (peak < start_compression) return color;
    const float d = 1.0 - start_compression;
    float new_peak = 1.0 - d * d / (peak + d - start_compression);
    color *= new_peak / peak;
    float g = 1.0 - 1.0 / (desaturation * (peak - new_peak) + 1.0);
    return mix(color, vec3(new_peak), g);
}

// Normal mapping without a tangent attribute: cotangent frame from screen-space derivatives.
vec3 perturb_normal(vec3 n, vec3 p, vec2 uv, vec3 tangent_normal) {
    vec3 dp1 = dFdx(p);
    vec3 dp2 = dFdy(p);
    vec2 duv1 = dFdx(uv);
    vec2 duv2 = dFdy(uv);
    vec3 dp2perp = cross(dp2, n);
    vec3 dp1perp = cross(n, dp1);
    vec3 t = dp2perp * duv1.x + dp1perp * duv2.x;
    vec3 b = dp2perp * duv1.y + dp1perp * duv2.y;
    float inv_max = inversesqrt(max(max(dot(t, t), dot(b, b)), 1e-20));
    return normalize(mat3(t * inv_max, b * inv_max, n) * tangent_normal);
}

// Analytic split-sum environment BRDF (Karis, "Physically Based Shading on Mobile").
vec3 env_brdf_approx(vec3 f0, float roughness, float n_dot_v) {
    const vec4 c0 = vec4(-1.0, -0.0275, -0.572, 0.022);
    const vec4 c1 = vec4( 1.0,  0.0425,  1.04, -0.04);
    vec4 r = roughness * c0 + c1;
    float a004 = min(r.x * r.x, exp2(-9.28 * n_dot_v)) * r.x + r.y;
    vec2 ab = vec2(-1.04, 1.04) * a004 + r.zw;
    return f0 * ab.x + ab.y;
}

vec3 hemisphere(vec3 dir) {
    return mix(ground_color, sky_color, clamp(dir.y * 0.5 + 0.5, 0.0, 1.0));
}

void main() {
    // ---- material, all in linear space
    vec4 base = base_color_factor;
    if (use_base_color_texture) {
        vec4 texel = texture(base_color_texture, v_uv);
        base *= vec4(srgb_to_linear(texel.rgb), texel.a);
    }
    if (use_vertex_color) base *= v_color;

    float metallic  = metallic_factor;
    float roughness = roughness_factor;
    if (use_metallic_roughness_texture) {
        vec4 mr = texture(metallic_roughness_texture, v_uv);
        roughness *= mr.g;
        metallic  *= mr.b;
    }
    roughness = clamp(roughness, 0.045, 1.0);
    metallic  = clamp(metallic, 0.0, 1.0);

    // ---- normal: two-sided, geometric fallback for degenerate input, optional normal map
    vec3 geometric = normalize(cross(dFdx(v_position), dFdy(v_position)));  // always faces the camera
    vec3 n = geometric;
    if (dot(v_normal, v_normal) > 1e-12) {
        n = normalize(v_normal);
        if (!gl_FrontFacing) n = -n;
    }
    if (use_normal_texture) {
        vec3 tangent_normal = texture(normal_texture, v_uv).xyz * 2.0 - 1.0;
        // v_uv carries a flipped V (see _extract_uvs); un-flip it so +Y in the map points "up" in the texture.
        n = perturb_normal(n, v_position, vec2(v_uv.x, -v_uv.y), tangent_normal);
    }

    vec3  v       = normalize(camera_position - v_position);
    float n_dot_v = max(dot(n, v), 1e-4);

    vec3  diffuse_color = base.rgb * (1.0 - metallic);
    vec3  f0            = mix(vec3(0.04), base.rgb, metallic);
    float a             = roughness * roughness;
    float a2            = a * a;

    // ---- direct lights: Lambert + GGX / height-correlated Smith / Schlick
    vec3 color = vec3(0.0);
    for (int i = 0; i < light_count; ++i) {
        vec3  l       = light_vectors[i];
        float n_dot_l = dot(n, l);
        if (n_dot_l <= 0.0) continue;
        vec3  h       = normalize(l + v);
        float n_dot_h = max(dot(n, h), 0.0);
        float v_dot_h = max(dot(v, h), 0.0);
        float dd      = n_dot_h * n_dot_h * (a2 - 1.0) + 1.0;
        float D       = a2 / (PI * dd * dd);
        float vis_v   = n_dot_l * sqrt(n_dot_v * n_dot_v * (1.0 - a2) + a2);
        float vis_l   = n_dot_v * sqrt(n_dot_l * n_dot_l * (1.0 - a2) + a2);
        float V       = 0.5 / max(vis_v + vis_l, 1e-5);
        vec3  F       = f0 + (1.0 - f0) * pow(1.0 - v_dot_h, 5.0);
        color += light_colors[i] * n_dot_l * ((1.0 - F) * diffuse_color + PI * D * V * F);
    }

    // ---- ambient: hemisphere irradiance + hemisphere reflection
    float ao = use_occlusion_texture ? texture(occlusion_texture, v_uv).r : 1.0;
    vec3  irradiance = hemisphere(n);
    vec3  reflection = mix(hemisphere(reflect(-v, n)), irradiance, a);  // rough surfaces see a blurred environment
    color += ao * (diffuse_color * irradiance + env_brdf_approx(f0, roughness, n_dot_v) * reflection);

    vec3 emissive = emissive_factor;
    if (use_emissive_texture) emissive *= srgb_to_linear(texture(emissive_texture, v_uv).rgb);
    color += emissive;

    // Alpha mode last: discarding earlier would leave dFdx/dFdy (normal map, mip
    // selection) undefined for the rest of the 2x2 quad on some drivers.
    float alpha = base.a;
    if (alpha_mode == 0) {
        alpha = 1.0;
    } else if (alpha_mode == 1) {
        if (alpha < alpha_cutoff) discard;
        alpha = 1.0;
    }

    frag_color = vec4(linear_to_srgb(tonemap_neutral(color * exposure)), alpha);
}
"""

_VERTEX_SHADERS = {
    "pbr": _PBR_VERTEX_SHADER,
}

_FRAGMENT_SHADERS = {
    "pbr": _PBR_FRAGMENT_SHADER,
}

def get_vertex_shader(name: str) -> str:
    try:
        return _VERTEX_SHADERS[name]
    except KeyError:
        raise ValueError(f"Unknown vertex shader: {name!r}; available: {sorted(_VERTEX_SHADERS)}")

def get_fragment_shader(name: str) -> str:
    try:
        return _FRAGMENT_SHADERS[name]
    except KeyError:
        raise ValueError(f"Unknown fragment shader: {name!r}; available: {sorted(_FRAGMENT_SHADERS)}")
