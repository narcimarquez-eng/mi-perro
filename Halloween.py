"""El castillo del terror: monstruos de Halloween de dibujo (que dan un poco de miedo, pero son simpáticos)
y los objetos del castillo y del cementerio.

blender -b --factory-startup --python Halloween.py

Exporta web/halloween.glb. Los monstruos (Fantasma, Esqueleto, Momia, Bruja, Murcielago, Arana, Monstruo, Gato)
tienen piezas que se mueven colgando de ellos (Esqueleto_Cabeza, Esqueleto_Mandibula, Bruja_BrazoD...), cada una
con el origen donde gira; miran hacia -Y (en la web, hacia +Z). También: Calabaza (con Calabaza_Cara, que en la
web brilla), Calabacita, Cesto de chuches, Tumba, TumbaCruz, Ataud (con su Tapa), Caldero (Pocion y Fuego),
Armadura (con la Cabeza que gira), Mano de zombi, Llave, Vela (con su Llama), Candelabro, ArbolMuerto y Escoba.
Renderiza halloween.png con los monstruos en fila.
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



VC_METAL = material_vc("Metal", 0.3, 0.85)


# ---------- PIEZAS ARTICULADAS ----------
def parte(nombre, piezas, pivote, padre=None):
    """Une las piezas, pone el origen en el pivote (donde gira) y la cuelga del padre."""
    o = unir(piezas, nombre)
    bpy.context.scene.cursor.location = pivote
    activar(o)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    if padre:
        mw = o.matrix_world.copy()
        o.parent = padre
        o.matrix_world = mw
    return o


def cadena(puntos, radios, col):
    o = skin("cadena", puntos, [(k, k + 1) for k in range(len(puntos) - 1)], radios)
    return color(o, col) if not callable(col) else pintar(o, col)


def mezcla(c1, c2, t):
    a, b = lineal(c1), lineal(c2)
    t = max(0.0, min(1.0, t))
    return a * (1 - t) + b * t


def ojo(x, y, z, r, iris="#1a1d24"):
    return [color(esfera((x, y, z), (r, r * 0.6, r * 1.1), 14), "#ffffff"),
            color(esfera((x, y - r * 0.5, z - r * 0.1), (r * 0.5, r * 0.25, r * 0.55), 10), iris),
            color(esfera((x + r * 0.25, y - r * 0.68, z + r * 0.2), r * 0.15, 8), "#ffffff")]


# ---------- FANTASMA ----------
def fantasma():
    B = "#eef3ff"
    cab = esfera((0, 0, 1.4), (0.42, 0.42, 0.46), 32)
    bpy.ops.mesh.primitive_cone_add(vertices=40, radius1=0.68, radius2=0.41, depth=1.25, location=(0, 0, 0.78))
    falda = bpy.context.object
    bpy.ops.object.transform_apply(location=True)
    subdividir(falda, 3)
    for v in falda.data.vertices:
        if v.co.z < 0.3:
            a = math.atan2(v.co.y, v.co.x)
            v.co.z += 0.09 * math.sin(a * 7)
    suave(falda)
    cuerpo = [pintar(cab, lambda co, n: lineal(B)), pintar(falda, lambda co, n: mezcla("#c9d4f0", B, co.z * 1.2))]
    # ojos negros grandes y boca abierta (¡Buuu!)
    for l in (-1, 1):
        cuerpo.append(color(esfera((l * 0.15, -0.37, 1.48), (0.085, 0.05, 0.12), 14), "#15121c"))
        cuerpo.append(color(esfera((l * 0.15 + 0.03, -0.42, 1.52), 0.022, 8), "#ffffff"))
    cuerpo.append(color(esfera((0, -0.39, 1.25), (0.08, 0.05, 0.1), 14), "#2a1424"))
    c = parte("Fantasma", cuerpo, (0, 0, 0))
    for nom, l in (("BrazoI", 1), ("BrazoD", -1)):
        br = cadena([(l * 0.36, 0, 1.08), (l * 0.62, -0.12, 0.92), (l * 0.78, -0.25, 0.86)], [0.11, 0.08, 0.06], B)
        parte(f"Fantasma_{nom}", [br], (l * 0.36, 0, 1.08), c)
    return c


# ---------- ESQUELETO ----------
def esqueleto():
    H = "#f2eedd"
    cu = [barra((0, 0.02, 0.85), (0, 0.04, 1.35), 0.035, H, 8),
          color(esfera((0, 0, 0.82), (0.17, 0.1, 0.08), 14), H)]
    for k in range(4):
        z = 1.05 + k * 0.08
        cu.append(color(toro((0, 0, z), 0.14 - k * 0.01 * (k - 1.5) ** 2 * 0.3, 0.018, rot=(0, 0, 0), seg=18), H))
    cu.append(barra((-0.2, 0, 1.36), (0.2, 0, 1.36), 0.03, H, 8))  # clavículas
    c = parte("Esqueleto", cu, (0, 0, 0))
    cr = [color(esfera((0, 0, 1.6), (0.17, 0.18, 0.19), 24), H),
          color(esfera((0, -0.06, 1.5), (0.12, 0.12, 0.08), 16), H)]
    for l in (-1, 1):
        cr.append(color(esfera((l * 0.065, -0.155, 1.62), (0.05, 0.03, 0.055), 12), "#1a1418"))
    cr.append(color(esfera((0, -0.17, 1.55), (0.02, 0.02, 0.03), 8), "#1a1418"))
    cab = parte("Esqueleto_Cabeza", cr, (0, 0, 1.4), c)
    md = [color(esfera((0, -0.07, 1.42), (0.1, 0.1, 0.035), 14), H)]
    for k in range(5):
        md.append(color(caja(((k - 2) * 0.03, -0.15, 1.455), (0.022, 0.012, 0.03)), "#fffdf2"))
    parte("Esqueleto_Mandibula", md, (0, 0.02, 1.47), cab)
    for nom, l in (("BrazoI", 1), ("BrazoD", -1)):
        br = [barra((l * 0.2, 0, 1.34), (l * 0.25, 0, 1.05), 0.025, H, 8), barra((l * 0.25, 0, 1.05), (l * 0.27, -0.05, 0.8), 0.022, H, 8),
              color(esfera((l * 0.27, -0.06, 0.76), (0.04, 0.025, 0.05), 10), H)]
        parte(f"Esqueleto_{nom}", br, (l * 0.2, 0, 1.34), c)
    for nom, l in (("PiernaI", 1), ("PiernaD", -1)):
        pi = [barra((l * 0.09, 0, 0.8), (l * 0.1, 0, 0.42), 0.03, H, 8), barra((l * 0.1, 0, 0.42), (l * 0.1, 0.01, 0.06), 0.026, H, 8),
              color(esfera((l * 0.1, -0.06, 0.04), (0.05, 0.09, 0.035), 10), H)]
        parte(f"Esqueleto_{nom}", pi, (l * 0.09, 0, 0.8), c)
    return c


# ---------- MOMIA ----------
def momia():
    venda = lambda co, n: mezcla("#d8c9a3", "#efe4c8", 0.5 + 0.5 * math.sin((co.z + 0.35 * co.x) * 48))
    cu = esfera((0, 0, 1.05), (0.26, 0.2, 0.42), 32)
    pintar(cu, venda)
    c = parte("Momia", [cu], (0, 0, 0))
    ca = esfera((0, 0, 1.6), (0.19, 0.19, 0.2), 32)
    pintar(ca, venda)
    cab = [ca, color(caja((0, -0.17, 1.63), (0.26, 0.04, 0.05)), "#2a1e14")]
    cab += ojo(0.06, -0.185, 1.635, 0.04, "#c0392b")
    parte("Momia_Cabeza", cab, (0, 0, 1.45), c)
    for nom, l in (("BrazoI", 1), ("BrazoD", -1)):
        br = cadena([(l * 0.25, 0, 1.32), (l * 0.27, -0.3, 1.3), (l * 0.25, -0.58, 1.28)], [0.075, 0.065, 0.06], venda)
        parte(f"Momia_{nom}", [br], (l * 0.25, 0, 1.32), c)
    for nom, l in (("PiernaI", 1), ("PiernaD", -1)):
        pi = cadena([(l * 0.1, 0, 0.72), (l * 0.11, 0, 0.35), (l * 0.11, -0.04, 0.05)], [0.09, 0.08, 0.075], venda)
        parte(f"Momia_{nom}", [pi], (l * 0.1, 0, 0.72), c)
    # vendas sueltas que cuelgan
    for k in range(3):
        a = k * 2.1
        c2 = cadena([(math.cos(a) * 0.25, math.sin(a) * 0.18, 0.95 + k * 0.1), (math.cos(a) * 0.3, math.sin(a) * 0.22, 0.6 + k * 0.1)], [0.02, 0.015], "#e2d5b4")
        mw = c2.matrix_world.copy()
        c2.parent = c
        c2.matrix_world = mw
        c2.name = f"MomiaVenda{k}"
    return c


# ---------- BRUJA ----------
def bruja():
    P, V = "#3b1f4f", "#8fc46a"
    bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=0.45, radius2=0.16, depth=1.15, location=(0, 0, 0.6))
    vestido = bpy.context.object
    bpy.ops.object.transform_apply(location=True)
    c = parte("Bruja", [color(vestido, P), color(esfera((0, 0, 1.18), (0.2, 0.17, 0.12), 16), P)], (0, 0, 0))
    ca = [color(esfera((0, 0, 1.42), (0.16, 0.16, 0.18), 24), V),
          color(cilindro((0, -0.2, 1.4), 0.04, 0.2, rot=(math.pi / 2 + 0.3, 0, 0), v=10, r2=0.012), V),
          color(esfera((0.03, -0.27, 1.37), 0.018, 8), "#5e8a3a"),
          color(cilindro((0, 0, 1.57), 0.36, 0.03, v=28), "#1c1426"),
          color(cilindro((0, 0, 1.82), 0.17, 0.5, v=20, r2=0.01), "#1c1426"),
          color(cilindro((0, 0, 1.6), 0.175, 0.06, v=20), "#9b59b6")]
    ca += ojo(0.065, -0.14, 1.47, 0.04, "#d4a017") + ojo(-0.065, -0.14, 1.47, 0.04, "#d4a017")
    for k in range(9):
        a = math.pi * (0.15 + 0.7 * k / 8)
        ca.append(cadena([(math.cos(a) * 0.17, math.sin(a) * 0.12, 1.52), (math.cos(a) * 0.24, math.sin(a) * 0.17, 1.2)], [0.03, 0.02], "#e86a1a"))
    sonrisa = toro((0, -0.15, 1.36), 0.05, 0.01, rot=(math.pi / 2, 0, 0))
    recortar(sonrisa, lambda co: co.z > 1.36 - 0.015)
    ca.append(color(sonrisa, "#2a1424"))
    parte("Bruja_Cabeza", ca, (0, 0, 1.28), c)
    for nom, l in (("BrazoI", 1), ("BrazoD", -1)):
        br = [cadena([(l * 0.18, 0, 1.2), (l * 0.32, -0.15, 1.05), (l * 0.3, -0.35, 1.0)], [0.065, 0.055, 0.05], P),
              color(esfera((l * 0.3, -0.4, 1.0), 0.05, 10), V)]
        if l < 0:  # el cucharón
            br.append(barra((l * 0.3, -0.4, 1.12), (l * 0.3, -0.42, 0.55), 0.015, "#7a4a2b", 6))
            br.append(color(esfera((l * 0.3, -0.42, 0.52), (0.06, 0.06, 0.03), 10), "#7a4a2b"))
        parte(f"Bruja_{nom}", br, (l * 0.18, 0, 1.2), c)
    return c


def escoba():
    p = [barra((0, -0.8, 0.0), (0, 0.6, 0.0), 0.025, "#7a4a2b", 8)]
    for k in range(14):
        a = k / 14 * math.pi * 2
        p.append(barra((0, 0.55, 0), (math.cos(a) * 0.1, 0.95, math.sin(a) * 0.1), 0.02, "#c9a24a", 5))
    return parte("Escoba", p, (0, 0, 0))


# ---------- MURCIÉLAGO ----------
def murcielago():
    N = "#2a2233"
    cu = [color(esfera((0, 0, 0), (0.09, 0.08, 0.11), 14), N), color(esfera((0, -0.02, 0.12), 0.075, 12), N)]
    for l in (-1, 1):
        cu.append(color(cilindro((l * 0.045, -0.01, 0.2), 0.03, 0.08, v=8, r2=0.0), N))
        cu.append(color(esfera((l * 0.03, -0.085, 0.13), 0.018, 8), "#ffd21f"))
    cu.append(color(cilindro((0.015, -0.09, 0.09), 0.008, 0.025, rot=(math.pi, 0, 0), v=6, r2=0.0), "#ffffff"))
    c = parte("Murcielago", cu, (0, 0, 0))
    for nom, l in (("AlaI", 1), ("AlaD", -1)):
        ala = esfera((l * 0.24, 0.02, 0.02), (0.2, 0.015, 0.12), 16)
        recortar(ala, lambda co, l=l: co.z < -0.06 and math.sin(abs(co.x) * 40) > 0.2)
        parte(f"Murcielago_{nom}", [color(ala, "#3b2f4a")], (l * 0.06, 0, 0.02), c)
    return c


# ---------- ARAÑA ----------
def arana():
    N = "#1c1820"
    cu = [color(esfera((0, 0.12, 0.12), (0.17, 0.2, 0.15), 18), N), color(esfera((0, -0.1, 0.11), 0.09, 14), N)]
    for k, (x, z) in enumerate([(-0.03, 0.14), (0.03, 0.14), (-0.06, 0.12), (0.06, 0.12)]):
        cu.append(color(esfera((x, -0.18, z), 0.02, 8), "#e8322a"))
    cu.append(color(esfera((0, 0.12, 0.27), (0.07, 0.07, 0.01), 10), "#c0392b"))  # mancha roja
    c = parte("Arana", cu, (0, 0, 0))
    for k in range(4):
        for nom, l in (("I", 1), ("D", -1)):
            y = -0.1 + k * 0.07
            pa = cadena([(l * 0.06, y, 0.12), (l * 0.25, y - 0.05 + k * 0.04, 0.26), (l * 0.42, y - 0.08 + k * 0.06, 0.0)], [0.018, 0.015, 0.01], N)
            parte(f"Arana_Pata{k}{nom}", [pa], (l * 0.06, y, 0.12), c)
    return c


# ---------- MONSTRUO (grande y simpático) ----------
def monstruo():
    V, R, N = "#7fb069", "#3a3a4a", "#1c1c22"
    cu = [color(caja((0, 0, 1.55), (0.85, 0.5, 0.9), bisel=0.12), R),
          color(caja((0, 0, 1.05), (0.8, 0.48, 0.25), bisel=0.05), "#5a4632")]
    c = parte("Monstruo", cu, (0, 0, 0))
    ca = [color(caja((0, 0, 2.35), (0.55, 0.5, 0.6), bisel=0.08), V),
          color(caja((0, 0, 2.66), (0.58, 0.53, 0.08)), N)]
    for k in range(7):
        ca.append(color(caja(((k - 3) * 0.075, -0.255, 2.6), (0.06, 0.03, 0.09 + 0.03 * (k % 2))), N))
    for l in (-1, 1):
        ca.append(color(cilindro((l * 0.32, 0, 2.15), 0.05, 0.14, rot=(0, math.pi / 2, 0), v=10), "#9aa0a8"))
        ca += ojo(l * 0.13, -0.25, 2.42, 0.06, "#2a1a10")
    sonr = toro((0, -0.255, 2.22), 0.12, 0.018, rot=(math.pi / 2, 0, 0))
    recortar(sonr, lambda co: co.z > 2.22 - 0.03)
    ca.append(color(sonr, "#2a1424"))
    for k in range(4):  # puntos de la cicatriz
        ca.append(color(caja((0.12 + k * 0.03, -0.26, 2.52), (0.012, 0.01, 0.05)), "#2a2a2a"))
    ca.append(color(caja((0.165, -0.262, 2.52), (0.11, 0.01, 0.012)), "#2a2a2a"))
    parte("Monstruo_Cabeza", ca, (0, 0, 2.0), c)
    for nom, l in (("BrazoI", 1), ("BrazoD", -1)):
        br = [cadena([(l * 0.48, 0, 1.9), (l * 0.58, 0, 1.45), (l * 0.6, -0.05, 1.05)], [0.13, 0.11, 0.1], R),
              color(esfera((l * 0.6, -0.06, 0.95), (0.12, 0.1, 0.12), 12), V)]
        parte(f"Monstruo_{nom}", br, (l * 0.48, 0, 1.9), c)
    for nom, l in (("PiernaI", 1), ("PiernaD", -1)):
        pi = [cadena([(l * 0.2, 0, 1.0), (l * 0.21, 0, 0.5), (l * 0.21, 0, 0.18)], [0.14, 0.13, 0.13], "#2c3342"),
              color(caja((l * 0.21, -0.07, 0.1), (0.26, 0.42, 0.2), bisel=0.05), N)]
        parte(f"Monstruo_{nom}", pi, (l * 0.2, 0, 1.0), c)
    return c


# ---------- GATO NEGRO ----------
def gato():
    N = "#1a1a22"
    c = parte("Gato", [color(esfera((0, 0.05, 0.2), (0.14, 0.22, 0.2), 16), N),
                       color(esfera((0, -0.08, 0.06), (0.12, 0.08, 0.06), 12), N)], (0, 0, 0))
    ca = [color(esfera((0, -0.12, 0.42), (0.13, 0.12, 0.11), 16), N)]
    for l in (-1, 1):
        ca.append(color(cilindro((l * 0.07, -0.12, 0.54), 0.045, 0.09, v=8, r2=0.0), N))
        ca.append(color(esfera((l * 0.05, -0.22, 0.44), (0.03, 0.015, 0.035), 10), "#f4d03f"))
        ca.append(color(esfera((l * 0.05, -0.232, 0.44), (0.008, 0.008, 0.028), 6), "#111111"))
    parte("Gato_Cabeza", ca, (0, -0.08, 0.32), c)
    co = cadena([(0, 0.25, 0.1), (0, 0.4, 0.15), (0, 0.45, 0.4), (0.05, 0.38, 0.55)], [0.035, 0.03, 0.028, 0.025], N)
    parte("Gato_Cola", [co], (0, 0.25, 0.1), c)
    return c


# ---------- CALABAZAS ----------
def calabaza_cuerpo(r, z0=0.0):
    o = esfera((0, 0, z0 + r * 0.82), (r, r, r * 0.82), 32)
    for v in o.data.vertices:
        a = math.atan2(v.co.y, v.co.x)
        d = Vector((v.co.x, v.co.y, 0))
        k = 1 + 0.07 * math.cos(a * 8)
        v.co.x, v.co.y = d.x * k, d.y * k
    pintar(o, lambda co, n: mezcla("#d35400", "#f39c12", 0.5 + 0.5 * math.cos(math.atan2(co.y, co.x) * 8)))
    tallo = color(cilindro((0, 0, z0 + r * 1.68), r * 0.1, r * 0.3, rot=(0.25, 0, 0), v=8, r2=r * 0.07), "#4e7a2a")
    return [o, tallo]


def calabaza():
    c = parte("Calabaza", calabaza_cuerpo(0.4), (0, 0, 0))
    cara = []
    for l in (-1, 1):
        bpy.ops.mesh.primitive_cone_add(vertices=3, radius1=0.08, radius2=0.0, depth=0.03, location=(l * 0.13, -0.385, 0.42), rotation=(math.pi / 2, 0, 0))
        t = bpy.context.object
        bpy.ops.object.transform_apply(location=True, rotation=True)
        cara.append(color(t, "#ffd84a"))
    bpy.ops.mesh.primitive_cone_add(vertices=3, radius1=0.05, radius2=0.0, depth=0.03, location=(0, -0.395, 0.33), rotation=(math.pi / 2, 0, 0))
    t = bpy.context.object
    bpy.ops.object.transform_apply(location=True, rotation=True)
    cara.append(color(t, "#ffd84a"))
    for k in range(7):  # boca en zigzag
        x = (k - 3) * 0.045
        cara.append(color(caja((x, -0.37, 0.22 + (0.025 if k % 2 else 0)), (0.04, 0.04, 0.05 if k % 2 else 0.07)), "#ffd84a"))
    parte("Calabaza_Cara", cara, (0, 0, 0.3), c)
    return c


def calabacita():
    return parte("Calabacita", calabaza_cuerpo(0.16), (0, 0, 0))


# ---------- CESTO DE CHUCHES ----------
def cesto():
    rnd = random.Random(4)
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.28, depth=0.28, location=(0, 0, 0.14))
    b = bpy.context.object
    bpy.ops.object.transform_apply(location=True)
    subdividir(b, 3)
    for v in b.data.vertices:
        v.co.x *= 1 + 0.25 * v.co.z
        v.co.y *= 1 + 0.25 * v.co.z
    pintar(b, lambda co, n: mezcla("#8b5a2b", "#c48a4a", 0.5 + 0.5 * math.sin(math.atan2(co.y, co.x) * 18 + co.z * 40)))
    asa = toro((0, 0, 0.3), 0.3, 0.025, rot=(math.pi / 2, 0, 0), seg=28)
    recortar(asa, lambda co: co.z < 0.3)
    p = [b, color(asa, "#8b5a2b")]
    colores = ["#e8322a", "#ffd21f", "#2a7ae0", "#3dbe4a", "#e64aa6", "#ff8a1f", "#7e57c2"]
    for k in range(26):
        a, r = rnd.uniform(0, 6.28), rnd.uniform(0, 0.24)
        x, y, z = math.cos(a) * r, math.sin(a) * r, 0.3 + rnd.uniform(0, 0.08) - r * 0.2
        t = k % 3
        col = colores[k % len(colores)]
        if t == 0:
            p.append(color(esfera((x, y, z), 0.045, 10), col))
        elif t == 1:  # caramelo envuelto
            p.append(color(cilindro((x, y, z), 0.03, 0.08, rot=(0, math.pi / 2, a), v=10), col))
            for l in (-1, 1):
                p.append(color(cilindro((x + l * 0.055 * math.cos(a), y + l * 0.055 * math.sin(a), z), 0.03, 0.04, rot=(0, math.pi / 2 * l, a), v=6, r2=0.0), col))
        else:  # piruleta
            p.append(barra((x, y, z - 0.05), (x * 1.2, y * 1.2, z + 0.2), 0.008, "#ffffff", 6))
            p.append(color(cilindro((x * 1.2, y * 1.2, z + 0.24), 0.06, 0.02, rot=(math.pi / 2, 0, a), v=16), col))
    return parte("Cesto", p, (0, 0, 0))


# ---------- DECORADO ----------
def tumba():
    p = [color(caja((0, 0, 0.45), (0.6, 0.15, 0.8), bisel=0.03), "#8a8d94"),
         color(cilindro((0, 0, 0.85), 0.3, 0.15, rot=(math.pi / 2, 0, 0), v=20), "#8a8d94"),
         color(caja((0, -0.08, 0.6), (0.06, 0.02, 0.35)), "#5f6268"), color(caja((0, -0.08, 0.68), (0.22, 0.02, 0.06)), "#5f6268"),
         color(caja((0, -0.25, 0.04), (0.7, 0.5, 0.08)), "#5a4632")]
    for k in range(5):  # musgo
        p.append(color(esfera((rnd_h.uniform(-0.25, 0.25), -0.08, rnd_h.uniform(0.1, 0.5)), (0.06, 0.02, 0.05), 8), "#4e6b3a"))
    return parte("Tumba", p, (0, 0, 0))


def tumba_cruz():
    G = "#7f838a"
    return parte("TumbaCruz", [color(caja((0, 0, 0.6), (0.14, 0.12, 1.2), bisel=0.02), G), color(caja((0, 0, 0.88), (0.6, 0.12, 0.14), bisel=0.02), G),
                               color(caja((0, 0, 0.05), (0.4, 0.3, 0.1)), "#6a6e75")], (0, 0, 0))


def ataud():
    M = "#4a2a1a"
    perfil = [(-0.3, -0.9), (0.3, -0.9), (0.38, 0.35), (0.25, 0.95), (-0.25, 0.95), (-0.38, 0.35)]

    def prisma(z0, z1, col, nombre):
        me = bpy.data.meshes.new(nombre)
        vs = [(x, y, z0) for x, y in perfil] + [(x, y, z1) for x, y in perfil]
        n = len(perfil)
        caras = [list(range(n))[::-1], list(range(n, 2 * n))] + [[k, (k + 1) % n, n + (k + 1) % n, n + k] for k in range(n)]
        me.from_pydata(vs, [], caras)
        return color(objeto(nombre, me), col)
    caja_ = prisma(0.0, 0.42, M, "Caja")
    c = parte("Ataud", [caja_, color(caja((0, 0, 0.43), (0.62, 1.7, 0.02)), "#2a1414")], (0, 0, 0))
    tapa = [prisma(0.42, 0.52, "#5a3422", "Tapa"), color(caja((0, 0.1, 0.53), (0.06, 0.7, 0.02)), "#d4af37"), color(caja((0, 0.3, 0.53), (0.32, 0.06, 0.02)), "#d4af37")]
    parte("Ataud_Tapa", tapa, (0.38, 0, 0.47), c)
    return c


def caldero():
    bpy.ops.mesh.primitive_uv_sphere_add(segments=28, ring_count=14, radius=0.5, location=(0, 0, 0.55))
    o = bpy.context.object
    bpy.ops.object.transform_apply(location=True)
    recortar(o, lambda co: co.z > 0.85)
    suave(o)
    p = [color(o, "#1f1f24"), color(toro((0, 0, 0.85), 0.42, 0.05, seg=28), "#2c2c33")]
    for k in range(3):
        a = k / 3 * math.pi * 2
        p.append(barra((math.cos(a) * 0.3, math.sin(a) * 0.3, 0.2), (math.cos(a) * 0.4, math.sin(a) * 0.4, 0.0), 0.04, "#2c2c33", 6))
    for k in range(4):  # leña y fuego
        a = k / 4 * math.pi + 0.3
        p.append(barra((math.cos(a) * 0.4, math.sin(a) * 0.4, 0.05), (-math.cos(a) * 0.4, -math.sin(a) * 0.4, 0.05), 0.05, "#5a3a22", 6))
    c = parte("Caldero", p, (0, 0, 0))
    pocion = [color(cilindro((0, 0, 0.8), 0.4, 0.02, v=28), "#5dff4a")]
    for k in range(5):
        pocion.append(color(esfera((math.cos(k * 1.3) * 0.2, math.sin(k * 1.3) * 0.2, 0.83), 0.05 + 0.02 * (k % 2), 10), "#8aff7a"))
    parte("Caldero_Pocion", pocion, (0, 0, 0.8), c)
    fuego = [color(cilindro((0, 0, 0.12), 0.25, 0.3, v=10, r2=0.0), "#ff7a1a"), color(cilindro((0, 0, 0.1), 0.15, 0.22, v=8, r2=0.0), "#ffd84a")]
    parte("Caldero_Fuego", fuego, (0, 0, 0.0), c)
    return c


def armadura():
    G = "#9aa3ad"
    cu = [color(caja((0, 0, 1.25), (0.5, 0.32, 0.6), bisel=0.1), G), color(caja((0, 0, 0.9), (0.42, 0.28, 0.2), bisel=0.05), G),
          color(cilindro((0, 0, 0.02), 0.35, 0.04, v=20), "#5a4632")]
    for l in (-1, 1):
        cu.append(color(esfera((l * 0.3, 0, 1.5), (0.14, 0.14, 0.12), 14), G))
        cu += [cadena([(l * 0.32, 0, 1.45), (l * 0.36, -0.05, 1.1), (l * 0.3, -0.15, 0.9)], [0.07, 0.06, 0.06], G),
               cadena([(l * 0.12, 0, 0.82), (l * 0.12, 0, 0.45), (l * 0.12, -0.02, 0.06)], [0.08, 0.07, 0.07], G)]
    cu.append(barra((-0.3, -0.18, 0.05), (-0.3, -0.18, 2.4), 0.025, "#6b4a2a", 8))  # lanza
    cu.append(color(cilindro((-0.3, -0.18, 2.5), 0.06, 0.22, v=8, r2=0.0), G))
    c = parte("Armadura", cu, (0, 0, 0))
    ca = [color(esfera((0, 0, 1.78), (0.17, 0.19, 0.22), 20), G), color(caja((0, -0.17, 1.8), (0.2, 0.03, 0.025)), "#111111"),
          color(cilindro((0, 0, 2.02), 0.03, 0.15, v=8), "#c0392b")]
    parte("Armadura_Cabeza", ca, (0, 0, 1.6), c)
    for o in [c] + list(c.children):
        o.data.materials.clear()
        o.data.materials.append(VC_METAL)
    return c


def mano_zombi():
    V = "#7aa05a"
    p = [cadena([(0, 0, -0.1), (0, 0, 0.25)], [0.06, 0.055], V), color(esfera((0, 0, 0.32), (0.08, 0.04, 0.09), 12), V),
         color(cilindro((0, 0, -0.08), 0.1, 0.08, v=12), "#5a3a5a")]  # manga rota
    for k in range(4):
        x = (k - 1.5) * 0.035
        p.append(cadena([(x, 0, 0.38), (x * 1.3, -0.04, 0.48), (x * 1.4, -0.09, 0.53)], [0.016, 0.014, 0.012], V))
    p.append(cadena([(0.07, 0, 0.3), (0.11, -0.05, 0.36)], [0.016, 0.013], V))
    return parte("Mano", p, (0, 0, 0))


def llave():
    p = [color(toro((0, 0, 0.12), 0.06, 0.018, rot=(math.pi / 2, 0, 0), seg=20), "#ffd700"), barra((0, 0, 0.06), (0, 0, -0.18), 0.015, "#ffd700", 8),
         color(caja((0.025, 0, -0.15), (0.05, 0.02, 0.025)), "#ffd700"), color(caja((0.025, 0, -0.1), (0.04, 0.02, 0.02)), "#ffd700")]
    o = parte("Llave", p, (0, 0, 0))
    for q in [o]:
        q.data.materials.clear()
        q.data.materials.append(VC_METAL)
    return o


def vela():
    c = parte("Vela", [color(cilindro((0, 0, 0.12), 0.04, 0.24, v=12), "#f5efe0"), color(cilindro((0, 0, 0.01), 0.07, 0.02, v=14), "#8a6d3b")], (0, 0, 0))
    parte("Vela_Llama", [color(esfera((0, 0, 0.29), (0.022, 0.022, 0.045), 10), "#ffcc33")], (0, 0, 0.25), c)
    return c


def candelabro():
    O = "#b8962e"
    p = [barra((0, 0, 0), (0, 0, 1.2), 0.03, O, 8), color(cilindro((0, 0, 0.02), 0.18, 0.04, v=16), O)]
    for l in (-1, 0, 1):
        p.append(barra((0, 0, 1.0), (l * 0.25, 0, 1.2), 0.02, O, 6))
        p.append(color(cilindro((l * 0.25, 0, 1.32), 0.03, 0.2, v=10), "#f5efe0"))
        p.append(color(esfera((l * 0.25, 0, 1.47), (0.02, 0.02, 0.04), 8), "#ffcc33"))
    return parte("Candelabro", p, (0, 0, 0))


def arbol_muerto():
    tr = skin("arbol", [(0, 0, 0), (0.1, 0, 1.5), (0.0, 0.1, 2.8), (1.0, 0.2, 3.6), (-0.9, -0.3, 3.4), (0.3, 1.0, 3.3), (1.6, 0.0, 3.9), (-1.4, -0.5, 4.0), (0.1, -0.3, 3.9)],
              [(0, 1), (1, 2), (2, 3), (2, 4), (1, 5), (3, 6), (4, 7), (2, 8)], [0.3, 0.22, 0.16, 0.08, 0.08, 0.07, 0.03, 0.03, 0.05])
    pintar(tr, lambda co, n: mezcla("#2a2420", "#4a3f38", co.z / 4))
    return parte("ArbolMuerto", [tr], (0, 0, 0))


rnd_h = random.Random(9)
protos = [fantasma(), esqueleto(), momia(), bruja(), escoba(), murcielago(), arana(), monstruo(), gato(), calabaza(), calabacita(), cesto(),
          tumba(), tumba_cruz(), ataud(), caldero(), armadura(), mano_zombi(), llave(), vela(), candelabro(), arbol_muerto()]
todos = [o for o in bpy.data.objects if o.type == 'MESH']
print(f"{len(todos)} piezas, {sum(len(o.data.polygons) for o in todos)} caras")
bpy.ops.object.select_all(action='DESELECT')
for o in todos:
    o.select_set(True)
bpy.ops.export_scene.gltf(filepath=os.path.abspath(os.path.join("web", "halloween.glb")), export_format='GLB', use_selection=True)
print("Exportado web/halloween.glb")

if os.environ.get("SIN_RENDER") == "1":
    raise SystemExit

# ---------- MUESTRA ----------
x = -6.5
for o in protos:
    if o.name in ("Escoba", "Llave", "Vela", "Calabacita", "Mano", "ArbolMuerto", "Candelabro", "TumbaCruz"):
        o.hide_render = True
        continue
    ancho = {"Monstruo": 1.4, "Ataud": 0.9, "Caldero": 1.1, "Fantasma": 1.3, "Armadura": 0.9}.get(o.name, 0.8)
    x += ancho / 2
    o.location = (x, 0, 0.6 if o.name in ("Fantasma", "Murcielago") else 0)
    if o.name == "Murcielago":
        o.location.z = 1.6
    o.rotation_euler = (0, 0, -0.35)
    x += ancho / 2 + 0.15
bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 10, 0))
s = bpy.context.object
m = bpy.data.materials.new("Suelo")
m.use_nodes = True
m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*lineal("#3a4a3a"), 1)
s.data.materials.append(m)
bpy.ops.object.camera_add(location=(0.5, -9, 1.6), rotation=(math.radians(85), 0, 0))
bpy.context.scene.camera = bpy.context.object
bpy.context.object.data.lens = 30
bpy.ops.object.light_add(type='SUN', rotation=(math.radians(45), math.radians(10), math.radians(-25)))
bpy.context.object.data.energy = 3
w = bpy.data.worlds.new("Mundo")
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.35, 0.3, 0.5, 1)
bpy.context.scene.world = w
esc = bpy.context.scene
esc.render.engine = 'CYCLES'
esc.cycles.samples = int(os.environ.get("MUESTRAS", "32"))
esc.cycles.use_denoising = False
esc.view_settings.view_transform = 'AgX'
esc.render.resolution_x = 1600
esc.render.resolution_y = 600
esc.render.filepath = os.path.abspath(os.environ.get("MUESTRA", "halloween.png"))
bpy.ops.render.render(write_still=True)
