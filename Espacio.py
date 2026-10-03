"""El viaje por el espacio: la nave espacial de Manuel, su plataforma de despegue en la playa,
un satélite y un robot explorador (rover) para Marte.

blender -b --factory-startup --python Espacio.py

Exporta web/espacio.glb. La Nave (mira hacia -Y; en la web, hacia +Z) tiene cuatro asientos en una cabina
abierta, y piezas aparte: Nave_Cupula (de cristal, transparente en la web), Nave_Fuego (el fuego de los
motores) y Nave_Patas (las patas de aterrizaje). Los planetas, el Sol, las estrellas y la galaxia se hacen
en la web. Renderiza espacio.png.
"""
import bpy
import bmesh
import math
import os
import random
from mathutils import Vector

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.preferences.addon_enable(module="io_scene_gltf2")
rnd = random.Random(7)


# ---------- UTILIDADES ----------
def lineal(hexa):
    c = [int(hexa[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return Vector([x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c])


def activar(o):
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


def aplicar(o):
    activar(o)
    for m in list(o.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)


def objeto(nombre, me):
    o = bpy.data.objects.new(nombre, me)
    bpy.context.collection.objects.link(o)
    return o


def unir(objs, nombre):
    objs = [o for o in objs if o]
    activar(objs[0])
    for o in objs[1:]:
        o.select_set(True)
    if len(objs) > 1:
        bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    o.name = nombre
    o.data.name = nombre
    return o


def suave(o, si=True):
    for p in o.data.polygons:
        p.use_smooth = si


def material_vc(nombre, rug=0.6, metal=0.0):
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    vc = nt.nodes.new("ShaderNodeVertexColor")
    vc.layer_name = "Col"
    nt.links.new(vc.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rug
    b.inputs["Metallic"].default_value = metal
    return m


VC = material_vc("Pieza", 0.55)
VC_ORO = material_vc("Oro", 0.3, 0.8)


def pintar(o, fn, mat=VC):
    me = o.data
    at = me.color_attributes.get("Col") or me.color_attributes.new("Col", 'FLOAT_COLOR', 'POINT')
    for v in me.vertices:
        c = fn(v.co, v.normal)
        at.data[v.index].color = (max(0, c[0]), max(0, c[1]), max(0, c[2]), 1.0)
    me.materials.clear()
    me.materials.append(mat)
    return o


def color(o, hexa, mat=VC):
    c = lineal(hexa)
    return pintar(o, lambda co, n: c, mat)


def caja(loc, esc, rot=(0, 0, 0), bisel=0.0, seg=2):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    c = bpy.context.object
    c.scale = esc
    bpy.ops.object.transform_apply(location=True, scale=True, rotation=True)
    if bisel:
        b = c.modifiers.new("B", 'BEVEL')
        b.width = bisel
        b.segments = seg
        aplicar(c)
    return c


def cilindro(loc, r, largo, rot=(0, 0, 0), v=20, r2=None):
    if r2 is None:
        bpy.ops.mesh.primitive_cylinder_add(vertices=v, radius=r, depth=largo, location=loc, rotation=rot)
    else:
        bpy.ops.mesh.primitive_cone_add(vertices=v, radius1=r, radius2=r2, depth=largo, location=loc, rotation=rot)
    c = bpy.context.object
    bpy.ops.object.transform_apply(location=True, rotation=True)
    return c


def esfera(loc, esc, seg=20):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=max(8, seg // 2), radius=1, location=loc)
    o = bpy.context.object
    o.scale = esc if isinstance(esc, (tuple, list)) else (esc,) * 3
    bpy.ops.object.transform_apply(location=True, scale=True)
    suave(o)
    return o


def toro(loc, R, r, rot=(0, 0, 0), seg=24):
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=r, major_segments=seg, minor_segments=8, location=loc, rotation=rot)
    o = bpy.context.object
    bpy.ops.object.transform_apply(location=True, rotation=True)
    suave(o)
    return o


def recortar(o, quitar):
    """Borra los vértices (en coordenadas locales) para los que quitar(co) es cierto."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if quitar(v.co)], context='VERTS')
    bm.to_mesh(o.data)
    bm.free()
    return o


def skin(nombre, verts, aristas, radios, sub=1):
    me = bpy.data.meshes.new(nombre)
    me.from_pydata(verts, aristas, [])
    o = objeto(nombre, me)
    sk = o.modifiers.new("Skin", 'SKIN')
    sk.branch_smoothing = 0.8
    for i, r in enumerate(radios):
        o.data.skin_vertices[0].data[i].radius = (r, r) if not isinstance(r, tuple) else r
    o.data.skin_vertices[0].data[0].use_root = True
    if sub:
        s = o.modifiers.new("Sub", 'SUBSURF')
        s.levels = sub
    aplicar(o)
    suave(o)
    return o


def ojos(x, y, z, sep, r, mirada=(0, 0)):
    """Dos ojos grandes de dibujo animado mirando hacia -Y (el frente en la web)."""
    piezas = []
    for l in (-1, 1):
        b = color(esfera((x + l * sep, y, z), (r, r * 0.5, r * 1.15), 16), "#ffffff")
        p = color(esfera((x + l * sep + mirada[0] * r * 0.3, y - r * 0.42, z + mirada[1] * r * 0.3 - r * 0.1), (r * 0.55, r * 0.2, r * 0.62), 12), "#1a1d24")
        brillo = color(esfera((x + l * sep + r * 0.22, y - r * 0.55, z + r * 0.18), r * 0.18, 10), "#ffffff")
        piezas += [b, p, brillo]
    return piezas


def sonrisa(x, y, z, R, r, col="#7a1e22"):
    o = toro((x, y, z), R, r, rot=(math.pi / 2, 0, 0))
    recortar(o, lambda co: co.z > z - R * 0.35)
    return color(o, col)




def subdividir(o, cortes):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cortes, use_grid_fill=True)
    bm.to_mesh(o.data)
    bm.free()
    return o


def barra(a, b, r, col, v=10):
    """Cilindro de a a b."""
    va, vb = Vector(a), Vector(b)
    d = vb - va
    bpy.ops.mesh.primitive_cylinder_add(vertices=v, radius=r, depth=d.length, location=(0, 0, 0))
    c = bpy.context.object
    c.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    bpy.ops.object.transform_apply(location=False, rotation=True)
    c.location = (va + vb) / 2
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    return color(c, col)


def bombillas(puntos, r=0.07):
    return [color(esfera(p, r, 8), "#fff3a8") for p in puntos]


ROJO, BLANCO, AMARILLO, AZUL = "#e8322a", "#f6f4ee", "#ffd21f", "#2a7ae0"



VC_METAL = material_vc("Metal", 0.3, 0.8)
VC_CRISTAL = material_vc("Cristal", 0.05, 0.0)


def parte(nombre, piezas, pivote, padre=None):
    o = unir(piezas, nombre)
    bpy.context.scene.cursor.location = pivote
    activar(o)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    if padre:
        mw = o.matrix_world.copy()
        o.parent = padre
        o.matrix_world = mw
    return o


def mezcla(c1, c2, t):
    a, b = lineal(c1), lineal(c2)
    t = max(0.0, min(1.0, t))
    return a * (1 - t) + b * t


# ---------- LA NAVE (mira hacia -Y; en la web, hacia +Z) ----------
def nave():
    B, N, A, G = "#f4f2ee", "#ff7a1a", "#2a6fdb", "#3a3f4a"
    # fuselaje: un huso alargado, blanco con franjas naranjas
    bpy.ops.mesh.primitive_uv_sphere_add(segments=40, ring_count=24, radius=1, location=(0, 0, 0))
    f = bpy.context.object
    f.rotation_euler = (math.pi / 2, 0, 0)
    f.scale = (1.25, 1.1, 3.6)
    bpy.ops.object.transform_apply(rotation=True, scale=True)
    f.location = (0, 0.2, 1.0)
    bpy.ops.object.transform_apply(location=True)
    suave(f)
    pintar(f, lambda co, n: lineal(N) if abs(co.y - 1.4) < 0.25 or abs(co.y + 2.4) < 0.18 else lineal(B) if co.z > 0.55 else mezcla("#d9dde4", B, co.z + 0.2))
    # hueco de la cabina: se quita la parte de arriba del centro
    recortar(f, lambda co: co.z > 1.55 and -1.9 < co.y < 1.1 and abs(co.x) < 0.95)
    p = [f]
    # suelo y asientos (dos delante y dos detrás)
    p.append(color(caja((0, -0.4, 1.25), (1.9, 3.0, 0.1)), G))
    for x in (-0.45, 0.45):
        for y in (-1.0, 0.45):
            p.append(color(caja((x, y, 1.42), (0.62, 0.62, 0.22), bisel=0.06), "#2f4f7a"))
            p.append(color(caja((x, y + 0.32, 1.8), (0.62, 0.12, 0.62), bisel=0.05), "#2f4f7a"))
    # panel de mandos con luces
    p.append(color(caja((0, -1.65, 1.6), (1.6, 0.3, 0.35), rot=(0.5, 0, 0), bisel=0.04), G))
    for k in range(6):
        p.append(color(esfera((-0.55 + k * 0.22, -1.72, 1.73), 0.04, 8), ["#ff4040", "#40ff70", "#ffd21f", "#40c8ff", "#ff40d0", "#ffffff"][k]))
    p.append(color(toro((-0.45, -1.4, 1.75), 0.16, 0.025, rot=(1.1, 0, 0), seg=18), "#222222"))
    # morro con punta naranja y ventanillas
    p.append(color(cilindro((0, -3.55, 1.0), 0.32, 0.5, rot=(math.pi / 2, 0, 0), v=20, r2=0.05), N))
    for l in (-1, 1):
        for k in range(3):
            p.append(color(cilindro((l * 1.12, 0.6 + k * 0.6, 1.05), 0.14, 0.06, rot=(0, math.pi / 2, 0), v=16), "#7fd0ff"))
        # alas en delta con la punta azul
        me = bpy.data.meshes.new("ala")
        v = [(l * 0.9, -0.4, 0.75), (l * 3.0, 1.9, 0.6), (l * 3.0, 2.5, 0.6), (l * 0.9, 2.6, 0.85),
             (l * 0.9, -0.4, 0.95), (l * 3.0, 1.9, 0.72), (l * 3.0, 2.5, 0.72), (l * 0.9, 2.6, 1.0)]
        caras = [[0, 1, 2, 3], [7, 6, 5, 4], [0, 4, 5, 1], [1, 5, 6, 2], [2, 6, 7, 3], [3, 7, 4, 0]]
        if l < 0:
            caras = [c[::-1] for c in caras]
        me.from_pydata(v, [], caras)
        ala = objeto("ala", me)
        pintar(ala, lambda co, n: lineal(A) if abs(co.x) > 2.4 else lineal(B))
        p.append(ala)
        # aleta de cola
        p.append(color(caja((l * 0.7, 3.0, 2.0), (0.08, 0.9, 1.2), rot=(-0.4, 0, l * 0.35)), A))
    # tres toberas detrás
    for x, z in ((0, 1.25), (-0.5, 0.75), (0.5, 0.75)):
        p.append(color(cilindro((x, 3.75, z), 0.28, 0.5, rot=(math.pi / 2, 0, 0), v=18, r2=0.36), G))
    # antena con luz
    p.append(barra((0, 2.4, 2.0), (0, 2.6, 2.7), 0.025, G, 6))
    p.append(color(esfera((0, 2.6, 2.75), 0.07, 10), "#ff3030"))
    c = parte("Nave", p, (0, 0, 0))
    # la cúpula de cristal (en la web, transparente)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=1, location=(0, -0.4, 1.55))
    cu = bpy.context.object
    cu.scale = (0.98, 1.65, 0.9)
    bpy.ops.object.transform_apply(scale=True)
    recortar(cu, lambda co: co.z < 1.56)
    suave(cu)
    pintar(cu, lambda co, n: lineal("#bfe8ff"), VC_CRISTAL)
    parte("Nave_Cupula", [cu], (0, -0.4, 1.55), c)
    # el fuego de los motores (en la web brilla y se mueve)
    fu = []
    for x, z in ((0, 1.25), (-0.5, 0.75), (0.5, 0.75)):
        fu.append(color(cilindro((x, 4.55, z), 0.26, 1.2, rot=(-math.pi / 2, 0, 0), v=14, r2=0.0), "#ff8a1f"))
        fu.append(color(cilindro((x, 4.35, z), 0.16, 0.8, rot=(-math.pi / 2, 0, 0), v=12, r2=0.0), "#fff1a0"))
    parte("Nave_Fuego", fu, (0, 4.0, 1.0), c)
    # patas de aterrizaje
    pa = []
    for x, y in ((-0.9, -1.8), (0.9, -1.8), (-1.0, 2.2), (1.0, 2.2)):
        pa.append(barra((x * 0.8, y, 0.45), (x * 1.15, y, 0.05), 0.06, G, 8))
        pa.append(color(cilindro((x * 1.15, y, 0.04), 0.2, 0.06, v=12), G))
    parte("Nave_Patas", pa, (0, 0, 0.5), c)
    return c


def plataforma():
    G, Y, N = "#9aa0a8", "#ffd21f", "#222222"
    pad = cilindro((0, 0, 0.25), 7, 0.5, v=48)
    pintar(pad, lambda co, n: (lineal(Y) if math.sin(math.atan2(co.y, co.x) * 24) > 0 else lineal(N)) if math.hypot(co.x, co.y) > 6.5 and co.z > 0.3 else lineal(G))
    p = [pad, color(cilindro((0, 0, 0.52), 3.2, 0.04, v=40), "#5a5f68")]
    # torre de lanzamiento de celosía
    for x in (-1, 1):
        for y in (-1, 1):
            p.append(barra((8 + x * 0.8, y * 0.8, 0.5), (8 + x * 0.8, y * 0.8, 12), 0.08, "#e8322a", 6))
    for k in range(12):
        z = 0.5 + k
        for (a, b) in (((-1, -1), (1, 1)), ((1, -1), (-1, 1))):
            p.append(barra((8 + a[0] * 0.8, a[1] * 0.8, z), (8 + b[0] * 0.8, b[1] * 0.8, z + 1), 0.04, "#e8322a", 5))
    p.append(color(caja((5.6, 0, 9.5), (4, 0.6, 0.3)), "#e8322a"))  # brazo
    p.append(color(esfera((8, 0, 12.3), 0.25, 10), "#ff3030"))
    # salidas de humo
    for a in (0, 2.1, 4.2):
        p.append(color(caja((math.cos(a) * 4.8, math.sin(a) * 4.8, 0.55), (1.2, 0.6, 0.15)), "#3a3f4a"))
    return parte("Plataforma", p, (0, 0, 0))


def satelite():
    O, A = "#d4af37", "#2a4fbf"
    p = [color(caja((0, 0, 0), (0.8, 0.8, 1.0), bisel=0.03), O)]
    for l in (-1, 1):
        p.append(barra((l * 0.4, 0, 0), (l * 0.8, 0, 0), 0.03, "#9aa0a8", 6))
        panel = caja((l * 1.9, 0, 0), (2.2, 0.04, 0.9))
        pintar(panel, lambda co, n: lineal(A) if (math.sin(co.x * 12) > -0.85 and math.sin(co.z * 14) > -0.85) else lineal("#c0c6d0"))
        p.append(panel)
    p.append(color(cilindro((0, 0, 0.7), 0.5, 0.2, v=20, r2=0.08), "#f4f2ee"))
    p.append(barra((0, 0, 0.6), (0, 0, 1.0), 0.02, "#9aa0a8", 6))
    return parte("Satelite", p, (0, 0, 0))


def rover():
    B, G = "#f4f2ee", "#3a3f4a"
    p = [color(caja((0, 0, 0.55), (0.9, 1.3, 0.3), bisel=0.04), B), color(caja((0, 0.1, 0.72), (1.1, 1.0, 0.04)), "#2a4fbf")]
    for x in (-0.6, 0.6):
        for y in (-0.55, 0, 0.55):
            p.append(color(cilindro((x, y, 0.22), 0.2, 0.16, rot=(0, math.pi / 2, 0), v=16), G))
            p.append(barra((x * 0.75, y, 0.45), (x, y, 0.22), 0.025, "#9aa0a8", 6))
    p.append(barra((0, -0.5, 0.7), (0, -0.5, 1.3), 0.03, "#9aa0a8", 6))
    p.append(color(caja((0, -0.5, 1.38), (0.3, 0.16, 0.16)), B))
    for l in (-1, 1):
        p.append(color(esfera((l * 0.07, -0.58, 1.38), 0.04, 8), "#1a1d24"))
    return parte("Rover", p, (0, 0, 0))


protos = [nave(), plataforma(), satelite(), rover()]
todos = [o for o in bpy.data.objects if o.type == 'MESH']
print(f"{len(todos)} piezas, {sum(len(o.data.polygons) for o in todos)} caras")
bpy.ops.object.select_all(action='DESELECT')
for o in todos:
    o.select_set(True)
bpy.ops.export_scene.gltf(filepath=os.path.abspath(os.path.join("web", "espacio.glb")), export_format='GLB', use_selection=True)
print("Exportado web/espacio.glb")

if os.environ.get("SIN_RENDER") == "1":
    raise SystemExit

# ---------- MUESTRA ----------
protos[1].hide_render = True
protos[0].location = (-1, 0, 0.5)
protos[0].rotation_euler = (0, 0, -0.6)
protos[2].location = (4.5, 2, 2.5)
protos[3].location = (4, -2.5, 0)
protos[3].rotation_euler = (0, 0, 0.5)
bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 10, 0))
s = bpy.context.object
m = bpy.data.materials.new("Suelo")
m.use_nodes = True
m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*lineal("#c75b3a"), 1)
s.data.materials.append(m)
bpy.ops.object.camera_add(location=(1.5, -13, 5), rotation=(math.radians(73), 0, 0))
bpy.context.scene.camera = bpy.context.object
bpy.context.object.data.lens = 35
bpy.ops.object.light_add(type='SUN', rotation=(math.radians(45), math.radians(10), math.radians(-25)))
bpy.context.object.data.energy = 3.5
w = bpy.data.worlds.new("Mundo")
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.05, 0.12, 1)
bpy.context.scene.world = w
esc = bpy.context.scene
esc.render.engine = 'CYCLES'
esc.cycles.samples = int(os.environ.get("MUESTRAS", "32"))
esc.cycles.use_denoising = False
esc.view_settings.view_transform = 'AgX'
esc.render.resolution_x = 1200
esc.render.resolution_y = 700
esc.render.filepath = os.path.abspath(os.environ.get("MUESTRA", "espacio.png"))
bpy.ops.render.render(write_still=True)
