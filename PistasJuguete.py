"""Pistas de coches de juguete: diez cochecitos distintos, el lanzador, la caja de las pistas y el set de regalo.

blender -b --factory-startup --python PistasJuguete.py
FICHAS=1 blender -b --factory-startup --python PistasJuguete.py   (fichas del menú: cochesjuguete.png)

Exporta cochesjuguete.glb (cada pieza en el origen, con su nombre; el frente de los coches mira a -Y)
y renderiza pistasjuguete.png.
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


def oscuro(hexa, k=0.62):
    return lineal(hexa) * k


def subdividir(o, cortes):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cortes, use_grid_fill=True)
    bm.to_mesh(o.data)
    bm.free()
    return o


# ---------- RUEDAS Y PIEZAS COMUNES ----------
def rueda(x, y, r, ancho=0.045, llanta="#d9dde2"):
    """Rueda de coche de juguete: goma negra y llanta brillante (el eje va en X)."""
    t = cilindro((x, y, r), r, ancho, rot=(0, math.pi / 2, 0), v=18)
    pintar(t, lambda co, n: lineal(llanta) if abs(n.x) > 0.7 and ((co.y - y) ** 2 + (co.z - r) ** 2) < (r * 0.62) ** 2 else lineal("#1c1c1e"))
    suave(t)
    return t


def ruedas(eje_del, eje_tras, via, r, r_tras=None, ancho=0.045, llanta="#d9dde2"):
    lista = []
    for y, rr in ((eje_del, r), (eje_tras, r_tras or r)):
        for l in (-1, 1):
            lista.append(rueda(l * via, y, rr, ancho, llanta))
    return lista


def carroceria(loc, esc, bisel, col_fn, cortes=3):
    c = caja(loc, esc, bisel=bisel, seg=2)
    subdividir(c, cortes) if cortes else None
    return pintar(c, col_fn)


def faros(y, z, sep, r=0.018, col="#fff6c2"):
    return [color(esfera((l * sep, y, z), (r, r * 0.5, r), 10), col) for l in (-1, 1)]


def cristal(loc, esc, bisel=0.02):
    return color(caja(loc, esc, bisel=bisel, seg=2), "#22303d")


def llamas(base, punta="#ffd21f", medio="#ff7a1a"):
    """Pinta llamas en los laterales delanteros (sobre el color base)."""
    b, m, p = lineal(base), lineal(medio), lineal(punta)

    def fn(co, n):
        if abs(n.x) < 0.6 and n.z < 0.6:
            return b
        f = (co.y + 0.26) / 0.34  # 0 delante, 1 hacia la mitad
        lenguas = 0.55 + 0.3 * math.sin(co.z * 140 + co.x * 60)
        if f < lenguas * 0.55:
            return p
        return m if f < lenguas else b
    return fn


# ---------- LOS COCHES ----------
def musculo():
    rojo = "#d8231b"
    cuerpo = carroceria((0, 0, 0.085), (0.24, 0.52, 0.085), 0.03, llamas(rojo), cortes=7)
    p = [cuerpo, cristal((0, 0.05, 0.155), (0.19, 0.2, 0.07), 0.03),
         color(caja((0, 0.05, 0.195), (0.17, 0.15, 0.015), bisel=0.006), rojo),
         color(caja((0, -0.1, 0.14), (0.08, 0.12, 0.03), bisel=0.012), "#2a2a2a"),
         color(caja((0, 0.245, 0.17), (0.24, 0.05, 0.012), bisel=0.004), "#1c1c1e"),
         color(caja((0.08, 0.245, 0.14), (0.015, 0.02, 0.05)), "#1c1c1e"), color(caja((-0.08, 0.245, 0.14), (0.015, 0.02, 0.05)), "#1c1c1e")]
    p += [color(cilindro((l * 0.07, 0.265, 0.05), 0.014, 0.05, rot=(math.pi / 2, 0, 0)), "#cfd3d8") for l in (-1, 1)]
    p += faros(-0.262, 0.09, 0.08) + ruedas(-0.15, 0.16, 0.115, 0.06, 0.068)
    return unir(p, "JMusculo")


def formula():
    azul = "#1f6fe0"

    def fn(co, n):
        return lineal("#ffffff") if abs(co.x) < 0.02 and co.z > 0.06 else lineal(azul)
    morro = carroceria((0, -0.06, 0.06), (0.1, 0.42, 0.05), 0.02, fn)
    for v in morro.data.vertices:
        if v.co.y < -0.1:
            k = max(0.35, 1 - (-0.1 - v.co.y) * 3.2)
            v.co.x *= k
            v.co.z = 0.06 + (v.co.z - 0.06) * k
    p = [morro, carroceria((0, 0.1, 0.075), (0.2, 0.22, 0.07), 0.03, fn),
         color(caja((0, -0.27, 0.035), (0.3, 0.05, 0.012), bisel=0.004), "#ffffff"),
         color(caja((0, 0.24, 0.17), (0.26, 0.06, 0.014), bisel=0.004), azul),
         color(caja((0.11, 0.24, 0.13), (0.012, 0.06, 0.07)), "#ffffff"), color(caja((-0.11, 0.24, 0.13), (0.012, 0.06, 0.07)), "#ffffff"),
         color(esfera((0, 0.02, 0.135), 0.04, 14), "#ffd21f"),
         color(caja((0, -0.005, 0.135), (0.06, 0.02, 0.025)), "#22303d")]
    p += ruedas(-0.17, 0.17, 0.15, 0.055, 0.065, ancho=0.06)
    return unir(p, "JFormula")


def monstruo():
    verde = "#2fbf4a"

    def fn(co, n):
        if abs(n.x) > 0.5 and 0.27 < co.z < 0.31:
            return lineal("#111111")
        return lineal(verde) if co.z > 0.25 else lineal("#ffd21f")
    p = [carroceria((0, 0, 0.29), (0.26, 0.48, 0.1), 0.03, fn),
         cristal((0, 0.02, 0.375), (0.21, 0.17, 0.08), 0.03),
         color(caja((0, 0.02, 0.42), (0.19, 0.13, 0.015), bisel=0.006), verde),
         color(caja((0, 0, 0.19), (0.18, 0.4, 0.04)), "#333333")]
    for y in (-0.15, 0.15):
        for l in (-1, 1):
            p.append(color(cilindro((l * 0.08, y, 0.2), 0.012, 0.12, rot=(0, 0.6 * l, 0)), "#b8bec6"))
    p += faros(-0.242, 0.3, 0.09) + ruedas(-0.15, 0.15, 0.17, 0.11, ancho=0.08, llanta="#ffd21f")
    return unir(p, "JMonstruo")


def tiburon():
    gris = lineal("#7d8fa3")
    c = esfera((0, 0, 0.1), (0.13, 0.28, 0.08), 24)

    def fn(co, n):
        return lineal("#f2f4f6") if n.z < -0.2 else gris
    pintar(c, fn)
    p = [c, color(cilindro((0, 0.1, 0.22), 0.07, 0.12, r2=0.0, v=4), "#6a7b8e"),
         color(caja((0, 0.27, 0.13), (0.015, 0.08, 0.1), rot=(0.5, 0, 0), bisel=0.005), "#6a7b8e"),
         cristal((0, -0.02, 0.165), (0.14, 0.14, 0.05), 0.03)]
    for k in range(7):
        x = -0.07 + k * 0.023
        p.append(color(cilindro((x, -0.255, 0.075), 0.01, 0.025, r2=0.0, v=6, rot=(math.pi, 0, 0)), "#ffffff"))
    for l in (-1, 1):
        p.append(color(esfera((l * 0.075, -0.19, 0.13), 0.018, 10), "#111111"))
        p.append(color(caja((l * 0.13, 0.03, 0.08), (0.06, 0.07, 0.01), rot=(0, l * 0.5, 0), bisel=0.004), "#6a7b8e"))
    p += ruedas(-0.15, 0.15, 0.115, 0.05)
    return unir(p, "JTiburon")


def dino():
    verde = "#5fbf3a"

    def fn(co, n):
        manchas = math.sin(co.x * 70) * math.sin(co.y * 50) > 0.55
        return lineal("#3e8f25") if manchas and n.z > 0 else lineal(verde)
    p = [carroceria((0, 0, 0.085), (0.24, 0.48, 0.08), 0.035, fn, cortes=5),
         cristal((0, 0.06, 0.155), (0.18, 0.18, 0.07), 0.03),
         color(esfera((0, -0.27, 0.15), (0.07, 0.09, 0.06), 16), verde),
         color(skin("Cola", [(0, 0.22, 0.12), (0, 0.32, 0.16), (0, 0.4, 0.22)], [(0, 1), (1, 2)], [0.035, 0.025, 0.012]), verde)]
    for k in range(6):
        p.append(color(cilindro((0, -0.12 + k * 0.06, 0.2 - abs(k - 2.5) * 0.008), 0.022, 0.06, r2=0.0, v=6), "#ff8c1a"))
    for l in (-1, 1):
        p.append(color(esfera((l * 0.035, -0.32, 0.18), 0.012, 8), "#111111"))
        p.append(color(cilindro((l * 0.02, -0.355, 0.13), 0.008, 0.02, r2=0.0, v=5, rot=(math.pi, 0, 0)), "#ffffff"))
    p += ruedas(-0.14, 0.15, 0.115, 0.058)
    return unir(p, "JDino")


def cohete():
    def fn(co, n):
        return lineal("#e8322a") if abs(co.x) < 0.035 else lineal("#f4f4f4")
    p = [carroceria((0, 0, 0.08), (0.22, 0.5, 0.07), 0.03, fn),
         cristal((0, -0.02, 0.14), (0.14, 0.16, 0.06), 0.03),
         color(cilindro((0, 0.27, 0.12), 0.06, 0.12, rot=(math.pi / 2, 0, 0)), "#9aa3ad"),
         color(cilindro((0, 0.36, 0.12), 0.05, 0.1, r2=0.0, rot=(-math.pi / 2, 0, 0)), "#ff9a2e"),
         color(cilindro((0, 0.33, 0.12), 0.035, 0.05, r2=0.0, rot=(-math.pi / 2, 0, 0)), "#fff3a8")]
    for l in (-1, 1):
        p.append(color(caja((l * 0.13, 0.17, 0.13), (0.012, 0.12, 0.1), rot=(-0.4, 0, 0), bisel=0.004), "#e8322a"))
    p.append(color(caja((0, 0.19, 0.19), (0.012, 0.1, 0.11), rot=(-0.4, 0, 0), bisel=0.004), "#e8322a"))
    p += faros(-0.252, 0.085, 0.07, col="#8fe6ff") + ruedas(-0.15, 0.14, 0.11, 0.055)
    return unir(p, "JCohete")


def policia():
    def fn(co, n):
        return lineal("#f4f4f4") if (abs(n.x) > 0.5 and abs(co.y) < 0.13) or (n.z > 0.5 and abs(co.y) < 0.1) else lineal("#1c1f26")
    p = [carroceria((0, 0, 0.085), (0.23, 0.5, 0.08), 0.03, fn),
         cristal((0, 0.02, 0.155), (0.2, 0.22, 0.07), 0.03),
         color(caja((0, 0.02, 0.193), (0.18, 0.16, 0.012), bisel=0.005), "#f4f4f4"),
         color(caja((-0.04, 0.02, 0.21), (0.07, 0.04, 0.025), bisel=0.008), "#ff2a2a"),
         color(caja((0.04, 0.02, 0.21), (0.07, 0.04, 0.025), bisel=0.008), "#2a6bff")]
    p += faros(-0.252, 0.09, 0.08) + ruedas(-0.15, 0.15, 0.115, 0.058)
    return unir(p, "JPolicia")


def bomberos():
    rojo = "#e2231a"

    def fn(co, n):
        return lineal("#f4f4f4") if abs(n.x) > 0.5 and 0.1 < co.z < 0.12 else lineal(rojo)
    p = [carroceria((0, -0.2, 0.13), (0.24, 0.16, 0.16), 0.03, fn),
         cristal((0, -0.27, 0.17), (0.2, 0.025, 0.07), 0.01),
         carroceria((0, 0.1, 0.12), (0.25, 0.42, 0.14), 0.02, fn),
         color(caja((0, -0.2, 0.22), (0.1, 0.05, 0.025), bisel=0.008), "#2a6bff")]
    for l in (-1, 1):
        p.append(color(caja((l * 0.05, 0.08, 0.215), (0.015, 0.48, 0.015)), "#d9dde2"))
    for k in range(9):
        p.append(color(caja((0, -0.14 + k * 0.055, 0.215), (0.1, 0.01, 0.01)), "#d9dde2"))
    p += faros(-0.282, 0.1, 0.08) + ruedas(-0.19, 0.2, 0.12, 0.058)
    return unir(p, "JBomberos")


def furgo():
    def fn(co, n):
        return lineal("#f6f1e4") if co.z > 0.15 else lineal("#ff8a1f")
    p = [carroceria((0, 0, 0.14), (0.25, 0.48, 0.19), 0.05, fn, cortes=5),
         cristal((0, -0.2, 0.19), (0.22, 0.06, 0.07), 0.02)]
    for y in (-0.06, 0.06, 0.17):
        for l in (-1, 1):
            p.append(cristal((l * 0.124, y, 0.195), (0.01, 0.08, 0.06), 0.005))
    p.append(color(cilindro((0, -0.245, 0.11), 0.03, 0.01, rot=(math.pi / 2, 0, 0)), "#f6f1e4"))
    p += faros(-0.244, 0.11, 0.08) + ruedas(-0.15, 0.15, 0.115, 0.055)
    return unir(p, "JFurgo")


def escarabajo():
    amarillo = "#ffd21f"
    c = esfera((0, 0, 0.11), (0.12, 0.23, 0.12), 24)
    recortar(c, lambda co: co.z < 0.05)
    pintar(c, lambda co, n: lineal("#22303d") if 0.15 < co.z < 0.205 and abs(co.y) < 0.11 and n.z < 0.8 else lineal(amarillo))
    p = [c, color(caja((0, 0, 0.065), (0.2, 0.42, 0.04), bisel=0.015), "#3a3a3a")]
    for y in (-0.13, 0.13):
        for l in (-1, 1):
            g = esfera((l * 0.1, y, 0.08), (0.05, 0.075, 0.05), 14)
            p.append(color(g, amarillo))
    p += faros(-0.215, 0.1, 0.075) + ruedas(-0.13, 0.13, 0.115, 0.052)
    return unir(p, "JEscarabajo")


# ---------- PIEZAS DE LAS PISTAS ----------
def lanzador():
    """Lanzador de muelle: caja naranja con la palanca y el carril de salida."""
    p = [color(caja((0, 0.3, 0.12), (0.5, 0.5, 0.24), bisel=0.04), "#ff7a00"),
         color(caja((0, 0.3, 0.245), (0.42, 0.42, 0.015), bisel=0.01), "#1c1c1e"),
         color(caja((0, -0.25, 0.03), (0.4, 0.7, 0.03)), "#ff7a00"),
         color(cilindro((0.2, 0.42, 0.32), 0.02, 0.2), "#d9dde2"),
         color(esfera((0.2, 0.42, 0.43), 0.045, 14), "#e8322a")]
    for l in (-1, 1):
        p.append(color(caja((l * 0.2, -0.25, 0.06), (0.025, 0.7, 0.05)), "#e65f00"))
    return unir(p, "Lanzador")


def caja_pistas():
    """Caja de juguete de las pistas (para el cuarto de Manuel)."""
    c = caja((0, 0, 0.3), (0.9, 0.25, 0.6), bisel=0.01)
    subdividir(c, 6)

    def fn(co, n):
        if n.y < -0.5 and abs(co.x) < 0.33 and 0.16 < co.z < 0.48:
            return lineal("#bfe6ff")
        if co.z > 0.5:
            return lineal("#1c1c1e")
        return lineal("#ff7a00") if (co.x + co.z) % 0.3 < 0.2 else lineal("#ffd21f")
    pintar(c, fn)
    rizo = toro((0, -0.13, 0.32), 0.12, 0.012, rot=(math.pi / 2, 0, 0))
    return unir([c, color(rizo, "#ff7a00")], "CajaPistas")


def set_pistas():
    """El set de regalo: tablero, pista naranja con rizo y rampa, y el lanzador (los cochecitos los pone la web)."""
    p = [color(caja((0, 0, 0.02), (0.9, 1.5, 0.04), bisel=0.01), "#2a7ae0"),
         color(caja((0, 0.05, 0.05), (0.14, 1.2, 0.012)), "#ff7a00"),
         color(toro((0, -0.15, 0.26), 0.2, 0.022, rot=(0, math.pi / 2, 0), seg=40), "#ff7a00"),
         color(caja((0, -0.62, 0.1), (0.14, 0.3, 0.012), rot=(-0.35, 0, 0)), "#ff7a00"),
         color(caja((0, 0.58, 0.08), (0.2, 0.16, 0.12), bisel=0.02), "#e65f00"),
         color(cilindro((0.06, 0.62, 0.17), 0.008, 0.08), "#d9dde2"),
         color(esfera((0.06, 0.62, 0.22), 0.018, 10), "#e8322a")]
    for l in (-1, 1):
        p.append(color(caja((l * 0.075, 0.05, 0.065), (0.012, 1.2, 0.025)), "#e65f00"))
    return unir(p, "SetPistas")


coches = [musculo(), formula(), monstruo(), tiburon(), dino(), cohete(), policia(), bomberos(), furgo(), escarabajo()]
proto = coches + [lanzador(), caja_pistas(), set_pistas()]
for o in proto:
    print(f"{o.name}: {len(o.data.polygons)} caras")

if os.environ.get("FICHAS") == "1":
    import numpy as np
    escena = bpy.context.scene
    escena.render.engine = 'CYCLES'
    escena.cycles.samples = int(os.environ.get("MUESTRAS", "48"))
    escena.cycles.use_denoising = False
    escena.render.film_transparent = True
    escena.view_settings.view_transform = 'AgX'
    escena.view_settings.look = 'AgX - Punchy'
    escena.render.resolution_x, escena.render.resolution_y = 320, 220
    w = bpy.data.worlds.new("MundoFichas")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.9, 0.93, 0.97, 1)
    escena.world = w
    bpy.ops.object.light_add(type='SUN', rotation=(math.radians(45), math.radians(10), math.radians(30)))
    bpy.context.object.data.energy = 3.5
    bpy.ops.object.camera_add()
    cam = bpy.context.object
    escena.camera = cam
    imgs = []
    for o in coches:
        for q in proto:
            q.hide_render = q is not o
        dims = o.dimensions
        k = max(dims.x * 1.25, dims.y, dims.z * 1.8) / 0.5
        cam.location = (0.55 * k, -0.62 * k, 0.36 * k + dims.z * 0.1)
        direccion = Vector((0, 0, dims.z * 0.42)) - cam.location
        cam.rotation_euler = direccion.to_track_quat('-Z', 'Y').to_euler()
        escena.render.filepath = os.path.abspath(f"ficha_{o.name}.png")
        bpy.ops.render.render(write_still=True)
        im = bpy.data.images.load(os.path.abspath(f"ficha_{o.name}.png"))
        imgs.append(np.array(im.pixels[:], dtype=np.float32).reshape(220, 320, 4))
    tira = np.concatenate(imgs, axis=1)
    out = bpy.data.images.new("Tira", 320 * len(imgs), 220, alpha=True)
    out.pixels = tira.ravel()
    out.filepath_raw = os.path.abspath("cochesjuguete.png")
    out.file_format = 'PNG'
    out.save()
    print("Guardado cochesjuguete.png")
    raise SystemExit

bpy.ops.object.select_all(action='DESELECT')
for o in proto:
    o.select_set(True)
bpy.ops.export_scene.gltf(filepath=os.path.abspath("cochesjuguete.glb"), export_format='GLB', use_selection=True)
print("Exportado cochesjuguete.glb")

if os.environ.get("SIN_RENDER") == "1":
    raise SystemExit

# ---------- MUESTRA ----------
for o in proto:
    o.hide_render = True


def copia(o, loc, rz=0.0, esc=1.0):
    c = bpy.data.objects.new(o.name + "_c", o.data)
    bpy.context.collection.objects.link(c)
    c.location = loc
    c.rotation_euler = (0, 0, rz)
    c.scale = (esc,) * 3
    return c


for k, o in enumerate(coches):
    copia(o, ((k % 5) * 0.62 - 1.24, (k // 5) * 0.75, 0), 0.5)
copia(proto[10], (1.9, 0.2, 0), 0.3)
copia(proto[11], (-2.0, 1.2, 0), 0.2)
copia(proto[12], (0.3, 1.9, 0), 0.1)
bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 1, 0))
s = bpy.context.object
m = bpy.data.materials.new("Suelo")
m.use_nodes = True
m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*lineal("#d9c09a"), 1)
s.data.materials.append(m)
bpy.ops.object.camera_add(location=(0.1, -3.4, 1.9), rotation=(math.radians(62), 0, 0))
bpy.context.scene.camera = bpy.context.object
bpy.context.object.data.lens = 32
bpy.ops.object.light_add(type='SUN', rotation=(math.radians(45), math.radians(10), math.radians(-25)))
bpy.context.object.data.energy = 3.5
w = bpy.data.worlds.new("Mundo")
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.75, 0.85, 1.0, 1)
bpy.context.scene.world = w
esc = bpy.context.scene
esc.render.engine = 'CYCLES'
esc.cycles.samples = int(os.environ.get("MUESTRAS", "48"))
esc.cycles.use_denoising = False
esc.view_settings.view_transform = 'AgX'
esc.view_settings.look = 'AgX - Punchy'
esc.render.resolution_x = 1400
esc.render.resolution_y = 800
esc.render.filepath = os.path.abspath("pistasjuguete.png")
bpy.ops.render.render(write_still=True)
