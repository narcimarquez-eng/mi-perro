"""La feria: noria, autos de choque, montaña rusa, sillas voladoras, torre de caída, puestos y el arco de entrada.

blender -b --factory-startup --python Feria.py

Exporta feria.glb (cada pieza con su nombre; las que giran tienen el origen en su eje) y renderiza feria.png.
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


# ---------- NORIA ----------
def noria_rueda():
    R = 9.0
    p = []
    for x in (-0.9, 0.9):
        p.append(color(toro((x, 0, 0), R, 0.12, rot=(0, math.pi / 2, 0), seg=64), ROJO))
        p.append(color(toro((x, 0, 0), R * 0.55, 0.08, rot=(0, math.pi / 2, 0), seg=48), BLANCO))
        for k in range(16):
            a = k / 16 * math.pi * 2
            p.append(barra((x, 0, 0), (x, math.cos(a) * R, math.sin(a) * R), 0.05, BLANCO, 6))
    for k in range(16):
        a = k / 16 * math.pi * 2
        p.append(barra((-1.0, math.cos(a) * R, math.sin(a) * R), (1.0, math.cos(a) * R, math.sin(a) * R), 0.05, AMARILLO, 6))
        p += bombillas([(sx, math.cos(a + 0.2) * R, math.sin(a + 0.2) * R) for sx in (-0.9, 0.9)], 0.11)
    p.append(color(cilindro((0, 0, 0), 0.5, 2.4, rot=(0, math.pi / 2, 0)), "#9aa3ad"))
    p.append(color(cilindro((0, 0, 0), 1.0, 0.3, rot=(0, math.pi / 2, 0)), AMARILLO))
    return unir(p, "NoriaRueda")


def noria_soporte():
    p = []
    H = 10.5
    for x in (-1.6, 1.6):
        for y in (-4.5, 4.5):
            p.append(barra((x, y, 0), (x * 0.75, 0, H), 0.18, BLANCO, 12))
        p.append(barra((x, -2.4, H * 0.45), (x, 2.4, H * 0.45), 0.1, ROJO))
    p.append(barra((-1.4, 0, H), (1.4, 0, H), 0.25, "#9aa3ad", 12))
    p.append(color(caja((0, 0, 0.25), (6, 12, 0.5), bisel=0.08), "#8a6a4a"))
    p.append(color(caja((0, -7, 0.18), (3, 2, 0.36), bisel=0.05), "#8a6a4a"))
    return unir(p, "NoriaSoporte")


def gondola():
    """Cabina colgante: el origen es el punto donde cuelga."""
    p = [barra((0, 0, 0), (0, 0, -0.7), 0.05, "#9aa3ad"),
         color(cilindro((0, 0, -0.75), 0.9, 0.12, r2=0.2), ROJO),
         color(caja((0, 0, -1.65), (1.5, 1.3, 0.12), bisel=0.04), "#8a6a4a")]
    for x, y in ((-0.7, -0.6), (0.7, -0.6), (-0.7, 0.6), (0.7, 0.6)):
        p.append(barra((x, y, -0.85), (x, y, -1.65), 0.035, BLANCO, 6))
    for y in (-0.6, 0.6):
        p.append(color(caja((0, y, -1.38), (1.5, 0.08, 0.45), bisel=0.02), AZUL))
    p.append(color(caja((0, 0, -1.5), (0.5, 1.0, 0.3), bisel=0.04), AMARILLO))
    return unir(p, "Gondola")


# ---------- AUTOS DE CHOQUE ----------
def coche_choque():
    c = caja((0, 0, 0.3), (1.3, 1.9, 0.35), bisel=0.18, seg=3)
    pintar(c, lambda co, n: lineal(BLANCO) if co.z > 0.42 else lineal("#ffffff"))
    p = [c, color(toro((0, 0, 0.18), 1.0, 0.16, seg=32), "#2a2a2a"),
         color(caja((0, 0.45, 0.62), (0.9, 0.35, 0.5), bisel=0.1), "#1c1c1e"),
         color(cilindro((0, -0.45, 0.62), 0.03, 0.3, rot=(0.6, 0, 0)), "#555555"),
         color(toro((0, -0.55, 0.78), 0.16, 0.035, rot=(0.6, 0, 0)), "#1c1c1e"),
         barra((0, 0.75, 0.5), (0, 0.75, 3.2), 0.04, "#9aa3ad"),
         color(esfera((0, 0.75, 3.25), 0.09, 8), "#ffd21f")]
    for l in (-1, 1):
        p.append(color(esfera((l * 0.35, -0.95, 0.35), 0.08, 8), "#fff3a8"))
    return unir(p, "CocheChoque")


def pista_choque():
    W, L = 20, 26
    p = [color(caja((0, 0, 0.1), (W, L, 0.2)), "#4a4f57")]
    for (x, y, w, l) in ((0, -L / 2, W, 0.5), (0, L / 2, W, 0.5), (-W / 2, 0, 0.5, L), (W / 2, 0, 0.5, L)):
        p.append(color(caja((x, y, 0.45), (w + 0.5, l, 0.5), bisel=0.15), AMARILLO))
    for x in (-W / 2, 0, W / 2):
        for y in (-L / 2, 0, L / 2):
            if x == 0 and y == 0:
                continue
            p.append(barra((x, y, 0.2), (x, y, 5.6), 0.15, ROJO, 12))
    techo = caja((0, 0, 5.75), (W + 1.5, L + 1.5, 0.3))
    subdividir(techo, 12)
    pintar(techo, lambda co, n: lineal(ROJO) if int((co.x + 20) / 1.8) % 2 else lineal(BLANCO))
    p.append(techo)
    p.append(color(caja((0, 0, 5.58), (W, L, 0.05)), "#2a2a3a"))
    for x in range(-9, 10, 3):
        p += bombillas([(x, -L / 2 - 0.8, 5.6), (x, L / 2 + 0.8, 5.6)], 0.12)
    return unir(p, "PistaChoque")


# ---------- MONTAÑA RUSA ----------
def vagon():
    p = [color(caja((0, 0, 0.45), (1.5, 2.4, 0.6), bisel=0.15, seg=3), ROJO),
         color(caja((0, -1.1, 0.75), (1.4, 0.3, 0.5), bisel=0.12), AMARILLO)]
    for y in (-0.45, 0.55):
        p.append(color(caja((0, y, 0.75), (1.2, 0.6, 0.15), bisel=0.05), "#1c1c1e"))
        p.append(color(caja((0, y + 0.3, 1.0), (1.2, 0.12, 0.55), bisel=0.05), "#1c1c1e"))
        p.append(barra((-0.55, y - 0.15, 1.15), (0.55, y - 0.15, 1.15), 0.04, AMARILLO, 8))
    for x in (-0.6, 0.6):
        for y in (-0.8, 0.8):
            p.append(color(cilindro((x, y, 0.12), 0.14, 0.1, rot=(0, math.pi / 2, 0)), "#555555"))
    p += bombillas([(-0.45, -1.26, 0.75), (0.45, -1.26, 0.75)], 0.08)
    return unir(p, "Vagon")


def estacion():
    p = [color(caja((0, 0, 0.6), (5, 12, 1.2), bisel=0.08), "#8a6a4a")]
    for x in (-2.3, 2.3):
        for y in (-5.5, 0, 5.5):
            p.append(barra((x, y, 1.2), (x, y, 4.6), 0.12, BLANCO))
    t = caja((0, 0, 4.8), (6, 13, 0.3))
    pintar(t, lambda co, n: lineal(AZUL) if int((co.y + 20) / 1.6) % 2 else lineal(BLANCO))
    p.append(t)
    return unir(p, "Estacion")


# ---------- SILLAS VOLADORAS ----------
def sillas_torre():
    p = [color(cilindro((0, 0, 0.3), 2.6, 0.6), "#8a6a4a"),
         color(cilindro((0, 0, 4.5), 0.45, 8.4, r2=0.3), BLANCO)]
    for k in range(8):
        a = k / 8 * math.pi * 2
        p.append(color(caja((math.cos(a) * 0.4, math.sin(a) * 0.4, 4), (0.12, 0.12, 7.5)), ROJO))
    return unir(p, "SillasTorre")


def sillas_techo():
    """El techo que gira (origen en el eje, arriba de la torre)."""
    t = cilindro((0, 0, 0.6), 5.0, 1.2, r2=1.2, v=24)
    pintar(t, lambda co, n: lineal(ROJO) if int((math.atan2(co.y, co.x) + math.pi) / (math.pi / 6)) % 2 else lineal(AMARILLO))
    p = [t, color(cilindro((0, 0, 0), 5.0, 0.35, v=24), AZUL), color(esfera((0, 0, 1.35), 0.4, 12), AMARILLO)]
    p += bombillas([(math.cos(k / 24 * math.pi * 2) * 5.05, math.sin(k / 24 * math.pi * 2) * 5.05, -0.05) for k in range(24)], 0.1)
    return unir(p, "SillasTecho")


def silla():
    """Una silla colgante (el origen es el punto donde cuelgan las cadenas)."""
    p = [color(caja((0, 0, -3.0), (0.6, 0.6, 0.1), bisel=0.03), AZUL),
         color(caja((0, 0.27, -2.75), (0.6, 0.08, 0.5), bisel=0.03), AZUL),
         barra((-0.25, 0, 0), (-0.25, 0, -2.95), 0.02, "#9aa3ad", 5),
         barra((0.25, 0, 0), (0.25, 0, -2.95), 0.02, "#9aa3ad", 5)]
    return unir(p, "Silla")


# ---------- TORRE DE CAÍDA ----------
def torre_caida():
    H = 22
    p = [color(cilindro((0, 0, 0.3), 3.0, 0.6), "#8a6a4a"),
         color(cilindro((0, 0, H / 2), 0.7, H), BLANCO)]
    for k in range(int(H / 2)):
        p.append(color(cilindro((0, 0, k * 2 + 1), 0.74, 0.25), ROJO if k % 2 else AZUL))
    p.append(color(cilindro((0, 0, H + 0.6), 1.3, 1.2, r2=0.6), AMARILLO))
    p += bombillas([(math.cos(k / 8 * math.pi * 2) * 1.32, math.sin(k / 8 * math.pi * 2) * 1.32, H) for k in range(8)], 0.12)
    return unir(p, "TorreCaida")


def torre_anillo():
    """El anillo de asientos que sube y baja (origen en el centro)."""
    p = [color(cilindro((0, 0, 0), 1.9, 0.5, v=24), AMARILLO)]
    for k in range(8):
        a = k / 8 * math.pi * 2
        x, y = math.cos(a) * 1.7, math.sin(a) * 1.7
        p.append(color(caja((x, y, -0.4), (0.6, 0.6, 0.1)), "#1c1c1e"))
        s = caja((x * 1.08, y * 1.08, 0.0), (0.6, 0.12, 0.8))
        s.rotation_euler = (0, 0, a + math.pi / 2)
        bpy.ops.object.transform_apply(rotation=True)
        p.append(color(s, ROJO))
    return unir(p, "TorreAnillo")


# ---------- PUESTOS, ARCO Y FAROLAS ----------
def puesto(nombre, col_toldo, encima):
    p = [color(caja((0, 0, 0.55), (2.6, 1.6, 1.1), bisel=0.05), BLANCO),
         color(caja((0, -0.85, 1.12), (2.8, 0.25, 0.08)), "#8a6a4a")]
    for x in (-1.25, 1.25):
        for y in (-0.75, 0.75):
            p.append(barra((x, y, 1.1), (x, y, 2.7), 0.05, BLANCO))
    t = caja((0, 0, 2.8), (3.0, 2.0, 0.2))
    subdividir(t, 5)
    pintar(t, lambda co, n: lineal(col_toldo) if int((co.x + 5) / 0.5) % 2 else lineal(BLANCO))
    p.append(t)
    p += encima
    return unir(p, nombre)


def algodon():
    return [color(cilindro((0, 0, 3.0), 0.05, 0.6), BLANCO), color(esfera((0, 0, 3.55), (0.45, 0.45, 0.4), 16), "#ff9cc7"),
            color(cilindro((0.7, -0.2, 1.4), 0.03, 0.5), BLANCO), color(esfera((0.7, -0.2, 1.75), 0.18, 12), "#8fd3ff")]


def palomitas():
    caja1 = cilindro((0, 0, 3.4), 0.4, 0.9, r2=0.5, v=16)
    pintar(caja1, lambda co, n: lineal(ROJO) if int((math.atan2(co.y, co.x) + math.pi) / (math.pi / 6)) % 2 else lineal(BLANCO))
    return [caja1] + [color(esfera((math.cos(k) * 0.3, math.sin(k) * 0.3, 3.9 + (k % 3) * 0.08), 0.13, 8), "#fff3c2") for k in range(9)]


def globos():
    p = []
    for k, c in enumerate(["#ff3b30", "#ffd21f", "#2cb7e6", "#3dbe4a", "#e64aa6"]):
        a = k / 5 * math.pi * 2
        p.append(barra((0, 0, 1.1), (math.cos(a) * 0.4, math.sin(a) * 0.4, 3.2), 0.008, "#ffffff", 4))
        p.append(color(esfera((math.cos(a) * 0.45, math.sin(a) * 0.45, 3.5), (0.3, 0.3, 0.37), 14), c))
    return p


def arco_feria():
    p = []
    for x in (-5, 5):
        p.append(color(cilindro((x, 0, 3.5), 0.45, 7, v=16), ROJO))
        p.append(color(cilindro((x, 0, 7.4), 0.7, 0.8, r2=0.0, v=16), AMARILLO))
    a = toro((0, 0, 6.3), 5.0, 0.35, rot=(math.pi / 2, 0, 0), seg=48)
    recortar(a, lambda co: co.z < 6.3)
    p.append(color(a, AMARILLO))
    p.append(color(caja((0, 0, 6.6), (8.0, 0.5, 1.3), bisel=0.1), ROJO))
    p += bombillas([(math.cos(k / 20 * math.pi) * 5.0, -0.36, 6.3 + math.sin(k / 20 * math.pi) * 5.0) for k in range(21)], 0.12)
    p += bombillas([(x, -0.5, z) for x in (-5, 5) for z in (1.5, 3, 4.5, 6)], 0.12)
    return unir(p, "ArcoFeria")


def farola_feria():
    p = [barra((0, 0, 0), (0, 0, 4), 0.07, "#2a2a2a"), color(caja((0, 0, 0.1), (0.5, 0.5, 0.2)), "#2a2a2a")]
    for k in range(4):
        a = k / 4 * math.pi * 2
        p.append(barra((0, 0, 3.6), (math.cos(a) * 0.6, math.sin(a) * 0.6, 3.9), 0.03, "#2a2a2a", 6))
        p += bombillas([(math.cos(a) * 0.6, math.sin(a) * 0.6, 3.8)], 0.14)
    return unir(p, "FarolaFeria")


rueda = noria_rueda()
rueda.location = (0, 0, 0)
proto = [rueda, noria_soporte(), gondola(), coche_choque(), pista_choque(), vagon(), estacion(), sillas_torre(), sillas_techo(), silla(),
         torre_caida(), torre_anillo(), puesto("PuestoAlgodon", "#ff9cc7", algodon()), puesto("PuestoPalomitas", ROJO, palomitas()),
         puesto("PuestoGlobos", AZUL, globos()), arco_feria(), farola_feria()]
for o in proto:
    print(f"{o.name}: {len(o.data.polygons)} caras")
bpy.ops.object.select_all(action='DESELECT')
for o in proto:
    o.select_set(True)
bpy.ops.export_scene.gltf(filepath=os.path.abspath("feria.glb"), export_format='GLB', use_selection=True)
print("Exportado feria.glb")

if os.environ.get("SIN_RENDER") == "1":
    raise SystemExit

# ---------- MUESTRA ----------
por = {o.name: o for o in proto}
for o in proto:
    o.hide_render = True


def copia(nombre, loc, rz=0.0, rx=0.0):
    o = bpy.data.objects.new(nombre + "_c", por[nombre].data)
    bpy.context.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (rx, 0, rz)
    return o


copia("NoriaSoporte", (-14, 10, 0))
copia("NoriaRueda", (-14, 10, 10.5), 0, 0.2)
for k in range(16):
    a = k / 16 * math.pi * 2 + 0.2
    copia("Gondola", (-14, 10 + math.cos(a) * 9, 10.5 + math.sin(a) * 9))
copia("PistaChoque", (12, 14, 0))
for k, (x, y) in enumerate([(9, 10), (14, 16), (16, 10), (8, 18)]):
    copia("CocheChoque", (x, y, 0.2), k * 1.4)
copia("SillasTorre", (2, 32, 0))
copia("SillasTecho", (2, 32, 8.2))
for k in range(12):
    a = k / 12 * math.pi * 2
    o = copia("Silla", (2 + math.cos(a) * 4.6, 32 + math.sin(a) * 4.6, 8.2))
    o.rotation_euler = (0, 0.5, a)
copia("TorreCaida", (-30, 34, 0))
copia("TorreAnillo", (-30, 34, 9))
copia("Estacion", (24, -4, 0))
copia("Vagon", (24, -6, 1.2))
copia("Vagon", (24, -3.3, 1.2))
copia("PuestoAlgodon", (-4, -6, 0))
copia("PuestoPalomitas", (-0.5, -6, 0))
copia("PuestoGlobos", (3, -6, 0))
copia("ArcoFeria", (-1, -14, 0))
for x in (-10, 8):
    copia("FarolaFeria", (x, -10, 0))
bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 10, 0))
s = bpy.context.object
m = bpy.data.materials.new("Suelo")
m.use_nodes = True
m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*lineal("#8fcf6a"), 1)
s.data.materials.append(m)
bpy.ops.object.camera_add(location=(0, -40, 13), rotation=(math.radians(78), 0, 0))
bpy.context.scene.camera = bpy.context.object
bpy.context.object.data.lens = 26
bpy.ops.object.light_add(type='SUN', rotation=(math.radians(45), math.radians(10), math.radians(-25)))
bpy.context.object.data.energy = 3.5
w = bpy.data.worlds.new("Mundo")
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.6, 0.8, 1.0, 1)
bpy.context.scene.world = w
esc = bpy.context.scene
esc.render.engine = 'CYCLES'
esc.cycles.samples = int(os.environ.get("MUESTRAS", "48"))
esc.cycles.use_denoising = False
esc.view_settings.view_transform = 'AgX'
esc.view_settings.look = 'AgX - Punchy'
esc.render.resolution_x = 1400
esc.render.resolution_y = 800
esc.render.filepath = os.path.abspath("feria.png")
bpy.ops.render.render(write_still=True)
