"""
ps1.py - the "PlayStation 1" look.

A real PS1 had no perspective-correct texturing, no sub-pixel vertex
precision (verts snapped to a coarse grid -> models 'wobble'), no per-pixel
lighting (flat / Gouraud shading), 15-bit colour and a very short draw
distance hidden by fog.  This tiny GLSL shader fakes all of that:

  * vertex snapping  : clip-space XY is rounded to a low-resolution grid (RETRO mode only)
  * flat shading     : face normal from screen-space derivatives (hard facets)
  * 15-bit colour    : output colour is quantised to 5 bits per channel
  * linear fog       : the PS1 'draw distance' pop-in hider

Every 3D object in the game is created through `ps1.box()` so it uses this
shader.  UI elements (parented to camera.ui) keep Ursina's normal shader.
"""
from ursina import Entity, Shader, Vec4, application

VERTEX = '''
#version 130
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelViewMatrix;
uniform vec4 p3d_ColorScale;
uniform vec2 snap_res;          // size of the fake PS1 vertex grid
uniform vec2 fog_range;         // (near, far) of the fog
in vec4 p3d_Vertex;
in vec4 p3d_Color;
out vec4 v_color;
out vec3 v_viewpos;
out float v_fog;

void main() {
    vec4 pos = p3d_ModelViewProjectionMatrix * p3d_Vertex;

    // --- PS1 vertex snapping: round the screen position to a coarse grid
    if (pos.w > 0.1) {
        vec2 ndc = pos.xy / pos.w;
        ndc = floor(ndc * snap_res * 0.5 + 0.5) / (snap_res * 0.5);
        pos.xy = ndc * pos.w;
    }
    gl_Position = pos;

    vec4 vp = p3d_ModelViewMatrix * p3d_Vertex;
    v_viewpos = vp.xyz;
    v_fog = clamp((length(vp.xyz) - fog_range.x) / (fog_range.y - fog_range.x), 0.0, 1.0);
    v_color = p3d_Color * p3d_ColorScale;
}
'''

FRAGMENT = '''
#version 130
uniform vec4 fog_color;
uniform float color_levels;     // 31 = PS1 15-bit colour, 255 = full colour
in vec4 v_color;
in vec3 v_viewpos;
in float v_fog;
out vec4 fragColor;

void main() {
    // --- flat shading: face normal from screen-space derivatives
    vec3 n = normalize(cross(dFdx(v_viewpos), dFdy(v_viewpos)));
    vec3 light = normalize(vec3(-0.45, 0.80, 0.55));     // view-space sun
    float lit = 0.50 + 0.50 * max(dot(n, light), 0.0);

    vec3 c = v_color.rgb * lit;
    c = mix(c, fog_color.rgb, v_fog);

    // --- 15-bit colour (5 bits per channel)
    c = floor(c * color_levels + 0.5) / color_levels;
    fragColor = vec4(c, v_color.a);
}
'''

_shader = None


def get_shader():
    """Create the shader lazily (it needs the engine to be running)."""
    global _shader
    if _shader is None:
        _shader = Shader(language=Shader.GLSL, vertex=VERTEX, fragment=FRAGMENT)
    return _shader


retro = False          # False = HD look, True = authentic PS1 look


def set_retro(on):
    """Switch between the HD and the retro PS1 look (live)."""
    global retro
    retro = bool(on)
    root = application.base.render
    snap = (320.0, 240.0) if retro else (16384.0, 16384.0)      # huge grid = no wobble
    root.set_shader_input('snap_res', snap)
    root.set_shader_input('color_levels', 31.0 if retro else 255.0)


def set_fog(fog_color, near, far):
    """Set scene-wide fog (applies to every 3D entity) and (re)apply the look."""
    root = application.base.render
    root.set_shader_input('fog_color', Vec4(fog_color.r, fog_color.g, fog_color.b, 1))
    root.set_shader_input('fog_range', (float(near), float(far)))
    set_retro(retro)


def box(parent=None, model='cube', **kwargs):
    """Create a 3D entity that uses the PS1 shader (cube by default)."""
    if parent is not None:          # None would detach it from the scene
        kwargs['parent'] = parent
    return Entity(model=model, shader=get_shader(), **kwargs)
