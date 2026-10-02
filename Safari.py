"""El safari: animales de la sabana con piezas que se mueven (cabeza, patas, cola, orejas, trompa,
mandíbula, alas o brazos), el jeep del safari y la decoración (acacias, baobab, termitero, roca y arco).

blender -b --factory-startup --python Safari.py

Exporta web/safari.glb. Cada animal es un objeto (Elefante, Jirafa, Cebra, Leon, Leona, Hipo, Rino, Gacela,
Avestruz, Flamenco, Mono, Suricata) con sus piezas colgando de él (Cebra_Cabeza, Cebra_PataDI...), cada una con
el origen donde gira. Miran hacia -Y (en la web, hacia +Z). Renderiza safari.png con todos en fila.
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


def pierna(x, y, alto, radios, col, pezuna=None, n=4, curva=0.0):
    """Pata de abajo (z=0) a la cadera (z=alto); con varios anillos para poder pintarla a rayas."""
    pts = [(x, y + curva * math.sin(k / n * math.pi), 0.06 + (alto - 0.06) * k / n) for k in range(n + 1)]
    rr = [radios[0] + (radios[1] - radios[0]) * k / n for k in range(n + 1)]
    o = skin("pierna", pts, [(k, k + 1) for k in range(n)], rr)
    piezas = [o if callable(col) else color(o, col)]
    if callable(col):
        pintar(o, col)
    if pezuna:
        piezas.append(color(esfera((x, y - radios[0] * 0.25, radios[0] * 0.75), (radios[0] * 1.1, radios[0] * 1.25, radios[0] * 0.8), 12), pezuna))
    return piezas


def patas(nombre, padre, xs, ys, alto, radios, col, pezuna=None, n=4, extra=None):
    """Cuatro patas (PataDI, PataDD, PataTI, PataTD) con el pivote en la cadera."""
    out = []
    for etiqueta, y in (("D", ys[0]), ("T", ys[1])):
        for lado, x in (("I", xs), ("D", -xs)):
            pz = pierna(x, y, alto, radios, col, pezuna, n) + (extra(x, y) if extra else [])
            out.append(parte(f"{nombre}_Pata{etiqueta}{lado}", pz, (x, y, alto * 0.92), padre))
    return out


def cola(nombre, padre, puntos, r, col, borla=None, col_borla="#2a2522"):
    o = skin("cola", puntos, [(k, k + 1) for k in range(len(puntos) - 1)], [r * (1 - 0.4 * k / len(puntos)) for k in range(len(puntos))])
    p = [color(o, col) if not callable(col) else pintar(o, col)]
    if borla:
        p.append(color(esfera(puntos[-1], borla, 10), col_borla))
    return parte(nombre + "_Cola", p, puntos[0], padre)


def mezcla(c1, c2, t):
    a, b = lineal(c1), lineal(c2)
    t = max(0.0, min(1.0, t))
    return a * (1 - t) + b * t


def manchas(base, mancha, linea, tam):
    """Manchas de jirafa: celdas (Voronoi) marrones separadas por líneas claras."""
    cb, cm, cl = lineal(base), lineal(mancha), lineal(linea)
    azar = random.Random(3)
    cache = {}

    def punto(i, j, k):
        if (i, j, k) not in cache:
            cache[(i, j, k)] = Vector(((i + azar.random()) * tam, (j + azar.random()) * tam, (k + azar.random()) * tam))
        return cache[(i, j, k)]

    def fn(co, n):
        i0, j0, k0 = int(math.floor(co.x / tam)), int(math.floor(co.y / tam)), int(math.floor(co.z / tam))
        ds = sorted((co - punto(i, j, k)).length for i in range(i0 - 1, i0 + 2) for j in range(j0 - 1, j0 + 2) for k in range(k0 - 1, k0 + 2))
        if ds[1] - ds[0] < tam * 0.12:
            return cl
        return cm
    return fn


# ---------- ANIMALES (mirando hacia -Y; en la web, hacia +Z) ----------
def elefante():
    G, G2 = "#a3a7ae", "#8f939b"
    c = parte("Elefante", [color(esfera((0, 0.1, 2.05), (1.25, 1.75, 1.15), 40), G),
                           color(esfera((0, 0.2, 1.55), (1.0, 1.4, 0.6), 24), G2)], (0, 0, 0))
    patas("Elefante", c, 0.7, (-0.95, 1.05), 1.55, (0.4, 0.33), G, None, 3,
          lambda x, y: [color(esfera((x + k * 0.17, y - 0.36, 0.1), (0.09, 0.06, 0.08), 8), "#f3eee2") for k in (-1, 0, 1)])
    ca = [color(esfera((0, -1.85, 2.55), (0.85, 0.8, 0.9), 32), G),
          color(esfera((0, -2.05, 2.95), (0.6, 0.5, 0.45), 20), G)]
    ca += ojos(0, -2.5, 2.8, 0.36, 0.15)
    for l in (-1, 1):
        ca.append(barra((l * 0.3, -2.35, 2.2), (l * 0.36, -2.95, 2.0), 0.075, "#fffaf0", 10))
    cab = parte("Elefante_Cabeza", ca, (0, -1.45, 2.5), c)
    for nom, l in (("OrejaI", 1), ("OrejaD", -1)):
        ore = [color(esfera((l * 1.15, -1.7, 2.55), (0.62, 0.09, 0.78), 24), G),
               color(esfera((l * 1.15, -1.79, 2.52), (0.47, 0.03, 0.6), 20), "#d9a3a8")]
        parte(f"Elefante_{nom}", ore, (l * 0.7, -1.72, 2.7), cab)
    tr = skin("trompa", [(0, -2.45, 2.45), (0, -2.75, 2.1), (0, -2.9, 1.6), (0, -2.95, 1.1), (0, -3.0, 0.72), (0, -3.15, 0.58)],
              [(k, k + 1) for k in range(5)], [0.3, 0.25, 0.2, 0.16, 0.13, 0.12])
    parte("Elefante_Trompa", [color(tr, G)], (0, -2.55, 2.4), cab)
    cola("Elefante", c, [(0, 1.82, 2.35), (0, 1.98, 1.8), (0, 2.03, 1.35)], 0.07, G, (0.08, 0.08, 0.14))
    return c


def jirafa():
    piel = manchas("#f0c35a", "#b5682c", "#f6dfa0", 0.32)
    claro = "#f6dfa0"
    cu = [esfera((0, 0.05, 2.35), (0.5, 0.92, 0.58), 40), esfera((0, -0.45, 2.55), (0.5, 0.6, 0.62), 32)]
    for o in cu:
        pintar(o, piel)
    c = parte("Jirafa", cu, (0, 0, 0))
    for etiqueta, y, alto in (("D", -0.6, 2.4), ("T", 0.65, 2.25)):
        for lado, x in (("I", 0.27), ("D", -0.27)):
            pz = pierna(x, y, alto, (0.1, 0.13), lambda co, n: lineal(claro) if co.z < 1.2 else piel(co, n), "#3a2a20", 6)
            parte(f"Jirafa_Pata{etiqueta}{lado}", pz, (x, y, alto * 0.92), c)
    cue = skin("cuello", [(0, -0.75, 2.7), (0, -0.95, 3.4), (0, -1.1, 4.1), (0, -1.2, 4.7)], [(0, 1), (1, 2), (2, 3)], [0.27, 0.2, 0.16, 0.14])
    pintar(cue, piel)
    crin = color(skin("crin", [(0, -0.6, 2.95), (0, -0.85, 3.6), (0, -1.0, 4.3), (0, -1.07, 4.75)], [(0, 1), (1, 2), (2, 3)], [0.05, 0.05, 0.045, 0.04]), "#8a4b1c")
    cabeza = esfera((0, -1.42, 4.86), (0.22, 0.38, 0.24), 24)
    pintar(cabeza, lambda co, n: lineal("#f0c35a"))
    ca = [cue, crin, cabeza, color(esfera((0, -1.76, 4.8), (0.17, 0.16, 0.16), 16), "#f3d79a"),
          color(esfera((0, -1.9, 4.82), (0.06, 0.03, 0.03), 8), "#5a3020")]
    for l in (-1, 1):
        ca.append(barra((l * 0.09, -1.3, 5.02), (l * 0.12, -1.28, 5.3), 0.035, "#c4883f", 8))
        ca.append(color(esfera((l * 0.12, -1.28, 5.32), 0.06, 10), "#4a2c18"))
        ca.append(color(esfera((l * 0.24, -1.22, 5.0), (0.14, 0.05, 0.065), 12), "#f0c35a"))
    ca += ojos(0, -1.6, 4.96, 0.16, 0.075)
    parte("Jirafa_Cabeza", ca, (0, -0.72, 2.75), c)
    cola("Jirafa", c, [(0, 0.92, 2.5), (0, 1.05, 2.0), (0, 1.08, 1.6)], 0.04, "#f0c35a", (0.06, 0.06, 0.13), "#3a2a20")
    return c


def cebra():
    B, N = lineal("#f4f2ec"), lineal("#1f1f22")
    cuerpo_r = lambda co, n: N if (co.z > 0.92 and math.sin(co.y * 19 + math.sin(co.z * 6) * 1.6) > 0.15) else B
    anillos = lambda co, n: N if math.sin(co.z * 26) > 0.25 else B
    c = parte("Cebra", [pintar(esfera((0, 0, 1.2), (0.4, 0.82, 0.45), 64), cuerpo_r)], (0, 0, 0))
    for etiqueta, y in (("D", -0.5), ("T", 0.5)):
        for lado, x in (("I", 0.2), ("D", -0.2)):
            parte(f"Cebra_Pata{etiqueta}{lado}", pierna(x, y, 1.15, (0.06, 0.1), anillos, "#1f1f22", 8), (x, y, 1.05), c)
    cue = skin("cuello", [(0, -0.6, 1.3), (0, -0.82, 1.68), (0, -0.95, 1.95)], [(0, 1), (1, 2)], [0.21, 0.17, 0.15])
    subdividir(cue, 1)
    pintar(cue, lambda co, n: N if math.sin((co.z + co.y * 0.6) * 24) > 0.2 else B)
    crin = color(skin("crin", [(0, -0.52, 1.6), (0, -0.75, 1.95), (0, -0.92, 2.17)], [(0, 1), (1, 2)], [0.07, 0.07, 0.06]), "#1f1f22")
    cab = esfera((0, -1.12, 1.98), (0.15, 0.3, 0.17), 32)
    pintar(cab, lambda co, n: N if math.sin(co.y * 30) > 0.35 and co.y > -1.3 else B)
    ca = [cue, crin, cab, color(esfera((0, -1.38, 1.88), (0.12, 0.13, 0.12), 16), "#2a2a2e")]
    for l in (-1, 1):
        ca.append(color(esfera((l * 0.1, -0.98, 2.22), (0.05, 0.04, 0.13), 10), "#f4f2ec"))
    ca += ojos(0, -1.18, 2.06, 0.12, 0.06)
    parte("Cebra_Cabeza", ca, (0, -0.62, 1.42), c)
    cola("Cebra", c, [(0, 0.8, 1.38), (0, 0.9, 1.05), (0, 0.92, 0.8)], 0.035, "#f4f2ec", (0.05, 0.05, 0.12), "#1f1f22")
    return c


def leon(nombre, melena):
    T, C, M = "#dca85a", "#f0d39a", "#9a531f"
    piel = lambda co, n: mezcla(C, T, (co.z - 0.7) * 3)
    esc = 1.0 if melena else 0.92
    c = parte(nombre, [pintar(esfera((0, 0, 0.95), (0.4 * esc, 0.85, 0.42 * esc), 32), piel)], (0, 0, 0))
    patas(nombre, c, 0.22, (-0.5, 0.55), 0.95, (0.12, 0.13), piel, C)
    ca = [color(skin("cuello", [(0, -0.6, 1.05), (0, -0.82, 1.28)], [(0, 1)], [0.26, 0.24]), T),
          color(esfera((0, -1.05, 1.38), 0.27, 24), T),
          color(esfera((0, -1.3, 1.28), (0.16, 0.12, 0.11), 16), C),
          color(esfera((0, -1.42, 1.34), (0.065, 0.035, 0.045), 10), "#5a3020")]
    if melena:
        for k in range(14):
            a = k / 14 * math.pi * 2
            ca.append(color(esfera((math.cos(a) * 0.32, -0.92, 1.38 + math.sin(a) * 0.32), (0.17, 0.2, 0.17), 12), M))
        ca.append(color(esfera((0, -0.82, 1.38), (0.4, 0.22, 0.4), 20), M))
    for l in (-1, 1):
        ca.append(color(esfera((l * 0.2, -1.0, 1.62), (0.08, 0.05, 0.08), 10), T if not melena else M))
    ca += ojos(0, -1.25, 1.47, 0.11, 0.06)
    cab = parte(nombre + "_Cabeza", ca, (0, -0.65, 1.15), c)
    parte(nombre + "_Mandibula", [color(esfera((0, -1.27, 1.17), (0.13, 0.13, 0.06), 14), C),
                                  color(esfera((0, -1.25, 1.2), (0.09, 0.09, 0.03), 10), "#d9607a")], (0, -1.12, 1.22), cab)
    cola(nombre, c, [(0, 0.85, 1.02), (0, 1.15, 0.8), (0, 1.42, 0.85)], 0.045, T, (0.07, 0.07, 0.1), M)
    return c


def hipo():
    P, R = "#8a7e98", "#d9a0aa"
    piel = lambda co, n: mezcla(R, P, (co.z - 0.55) * 4)
    c = parte("Hipo", [pintar(esfera((0, 0, 0.95), (0.8, 1.25, 0.72), 36), piel)], (0, 0, 0))
    patas("Hipo", c, 0.48, (-0.7, 0.75), 0.6, (0.24, 0.24), P, "#5a5060", 3)
    ca = [color(esfera((0, -1.42, 1.18), (0.58, 0.55, 0.45), 28), P),
          color(esfera((0, -1.85, 1.13), (0.56, 0.42, 0.28), 24), P)]
    for l in (-1, 1):
        ca.append(color(esfera((l * 0.18, -2.18, 1.3), (0.06, 0.04, 0.04), 8), "#3a3040"))
        ca.append(color(esfera((l * 0.33, -1.2, 1.6), (0.09, 0.05, 0.09), 10), P))
    ca += ojos(0, -1.55, 1.5, 0.26, 0.11)
    cab = parte("Hipo_Cabeza", ca, (0, -1.05, 1.1), c)
    ma = [color(esfera((0, -1.82, 0.86), (0.54, 0.44, 0.17), 24), R), color(esfera((0, -1.85, 0.95), (0.4, 0.32, 0.06), 16), "#e0607a")]
    for l in (-1, 1):
        ma.append(barra((l * 0.34, -2.1, 0.9), (l * 0.34, -2.1, 1.08), 0.05, "#fffaf0", 8))
    parte("Hipo_Mandibula", ma, (0, -1.35, 0.95), cab)
    cola("Hipo", c, [(0, 1.22, 1.05), (0, 1.32, 0.85)], 0.05, P)
    return c


def rino():
    G = "#9a948c"
    c = parte("Rino", [color(esfera((0, 0, 1.15), (0.7, 1.25, 0.7), 36), G),
                       color(esfera((0, -0.5, 1.45), (0.55, 0.45, 0.4), 20), G)], (0, 0, 0))
    patas("Rino", c, 0.42, (-0.75, 0.8), 0.85, (0.2, 0.2), G, "#7b766f", 3)
    ca = [color(esfera((0, -1.5, 1.08), (0.42, 0.62, 0.42), 28), G),
          color(cilindro((0, -1.98, 1.42), 0.15, 0.55, v=12, r2=0.0), "#e3dccd"),
          color(cilindro((0, -1.72, 1.45), 0.09, 0.25, v=10, r2=0.0), "#e3dccd")]
    for l in (-1, 1):
        ca.append(color(cilindro((l * 0.25, -1.12, 1.52), 0.09, 0.22, v=10, r2=0.02), G))
    ca += ojos(0, -1.72, 1.24, 0.3, 0.075)
    parte("Rino_Cabeza", ca, (0, -1.0, 1.2), c)
    cola("Rino", c, [(0, 1.22, 1.25), (0, 1.32, 0.9)], 0.04, G, (0.05, 0.05, 0.08))
    return c


def gacela():
    T, B, O = "#c98945", "#f6efe2", "#5a3518"
    piel = lambda co, n: lineal(B) if co.z < 0.82 else lineal(O) if co.z < 0.87 else lineal(T)
    c = parte("Gacela", [pintar(esfera((0, 0, 0.9), (0.24, 0.5, 0.28), 32), piel),
                         color(esfera((0, 0.45, 0.95), (0.12, 0.06, 0.12), 10), B)], (0, 0, 0))
    patas("Gacela", c, 0.12, (-0.32, 0.34), 0.88, (0.035, 0.055), T, "#2a2018")
    cue = color(skin("cuello", [(0, -0.38, 0.98), (0, -0.5, 1.25), (0, -0.55, 1.42)], [(0, 1), (1, 2)], [0.09, 0.07, 0.06]), T)
    ca = [cue, color(esfera((0, -0.66, 1.45), (0.09, 0.17, 0.1), 16), T), color(esfera((0, -0.8, 1.42), (0.05, 0.04, 0.04), 8), "#2a2018")]
    for l in (-1, 1):
        cu = skin("cuerno", [(l * 0.04, -0.6, 1.52), (l * 0.09, -0.55, 1.72), (l * 0.05, -0.62, 1.9)], [(0, 1), (1, 2)], [0.022, 0.02, 0.012])
        ca.append(color(cu, "#3a2a1c"))
        ca.append(color(esfera((l * 0.11, -0.56, 1.52), (0.085, 0.02, 0.035), 10), T))
    ca += ojos(0, -0.71, 1.5, 0.068, 0.04)
    parte("Gacela_Cabeza", ca, (0, -0.38, 1.0), c)
    cola("Gacela", c, [(0, 0.5, 1.0), (0, 0.58, 0.85)], 0.025, B)
    return c


def avestruz():
    N, B, P = "#2a2526", "#f4f1ea", "#e6b6a6"
    c = parte("Avestruz", [color(esfera((0, 0, 1.35), (0.42, 0.6, 0.38), 32), N), color(esfera((0, 0.55, 1.5), (0.3, 0.2, 0.18), 16), B)], (0, 0, 0))
    for lado, x in (("I", 0.15), ("D", -0.15)):
        pz = color(skin("pata", [(x, 0, 1.22), (x, -0.12, 0.65), (x, 0, 0.05)], [(0, 1), (1, 2)], [0.09, 0.05, 0.045]), P)
        dedo = color(esfera((x, -0.12, 0.04), (0.06, 0.14, 0.04), 8), P)
        parte(f"Avestruz_PataD{lado}", [pz, dedo], (x, 0, 1.2), c)
    for nom, l in (("AlaI", 1), ("AlaD", -1)):
        ala = esfera((l * 0.45, 0.05, 1.32), (0.08, 0.45, 0.26), 16)
        pintar(ala, lambda co, n: lineal(B) if co.y > 0.3 or co.z < 1.13 else lineal(N))
        parte(f"Avestruz_{nom}", [ala], (l * 0.38, 0.0, 1.5), c)
    ca = [color(skin("cuello", [(0, -0.45, 1.5), (0, -0.55, 2.0), (0, -0.55, 2.35)], [(0, 1), (1, 2)], [0.08, 0.05, 0.045]), P),
          color(esfera((0, -0.6, 2.4), (0.09, 0.12, 0.085), 14), P),
          color(esfera((0, -0.75, 2.37), (0.05, 0.08, 0.025), 10), "#e8c79a")]
    ca += ojos(0, -0.68, 2.44, 0.065, 0.045)
    parte("Avestruz_Cabeza", ca, (0, -0.45, 1.55), c)
    return c


def flamenco():
    R, R2 = "#f48fb1", "#ec6a9a"
    c = parte("Flamenco", [color(esfera((0, 0, 1.05), (0.2, 0.33, 0.2), 24), R), color(cilindro((0, 0.36, 1.08), 0.08, 0.18, rot=(math.pi / 2 - 0.3, 0, 0), v=8, r2=0.0), R2)], (0, 0, 0))
    parte("Flamenco_PataDI", [color(skin("p", [(0.05, 0, 1.0), (0.05, 0, 0.5), (0.05, 0, 0.03)], [(0, 1), (1, 2)], [0.025, 0.022, 0.02]), R2),
                              color(esfera((0.05, -0.06, 0.02), (0.05, 0.08, 0.02), 8), R2)], (0.05, 0, 1.0), c)
    parte("Flamenco_PataDD", [color(skin("p", [(-0.05, 0, 1.0), (-0.05, 0.18, 0.72), (-0.05, 0.02, 0.6)], [(0, 1), (1, 2)], [0.025, 0.022, 0.02]), R2)], (-0.05, 0, 1.0), c)
    for nom, l in (("AlaI", 1), ("AlaD", -1)):
        ala = esfera((l * 0.19, 0.05, 1.07), (0.05, 0.28, 0.15), 16)
        pintar(ala, lambda co, n: lineal("#1f1f22") if co.y > 0.27 else lineal(R2))
        parte(f"Flamenco_{nom}", [ala], (l * 0.16, -0.05, 1.12), c)
    ca = [color(skin("cuello", [(0, -0.25, 1.1), (0, -0.38, 1.3), (0, -0.3, 1.5), (0, -0.36, 1.7), (0, -0.45, 1.78)], [(k, k + 1) for k in range(4)], [0.045, 0.04, 0.035, 0.035, 0.04]), R),
          color(esfera((0, -0.47, 1.8), (0.06, 0.08, 0.06), 12), R)]
    pico = skin("pico", [(0, -0.53, 1.79), (0, -0.62, 1.74), (0, -0.62, 1.65)], [(0, 1), (1, 2)], [0.03, 0.025, 0.018])
    pintar(pico, lambda co, n: lineal("#1f1f22") if co.z < 1.7 else lineal("#f6efe2"))
    ca.append(pico)
    ca += ojos(0, -0.5, 1.84, 0.045, 0.028)
    parte("Flamenco_Cabeza", ca, (0, -0.25, 1.1), c)
    return c


def mono():
    M, C = "#7a4a2b", "#e9c9a3"
    cu = [color(esfera((0, 0, 0.45), (0.24, 0.2, 0.3), 20), M), color(esfera((0, -0.1, 0.42), (0.17, 0.12, 0.22), 16), C)]
    for l in (-1, 1):
        cu.append(color(skin("pierna", [(l * 0.12, -0.05, 0.25), (l * 0.15, -0.3, 0.25), (l * 0.15, -0.32, 0.06)], [(0, 1), (1, 2)], [0.07, 0.06, 0.05]), M))
        cu.append(color(esfera((l * 0.15, -0.38, 0.04), (0.06, 0.09, 0.04), 8), C))
    c = parte("Mono", cu, (0, 0, 0))
    for nom, l in (("BrazoI", 1), ("BrazoD", -1)):
        br = [color(skin("brazo", [(l * 0.22, 0, 0.62), (l * 0.3, -0.05, 0.4), (l * 0.27, -0.15, 0.24)], [(0, 1), (1, 2)], [0.06, 0.05, 0.045]), M),
              color(esfera((l * 0.26, -0.18, 0.2), 0.055, 8), C)]
        parte(f"Mono_{nom}", br, (l * 0.22, 0, 0.62), c)
    ca = [color(esfera((0, 0, 0.92), (0.2, 0.19, 0.19), 20), M), color(esfera((0, -0.1, 0.89), (0.15, 0.12, 0.14), 16), C)]
    for l in (-1, 1):
        ca.append(color(esfera((l * 0.2, 0, 0.95), (0.05, 0.03, 0.065), 10), C))
    ca += ojos(0, -0.19, 0.96, 0.06, 0.045)
    ca.append(sonrisa(0, -0.21, 0.86, 0.05, 0.012))
    parte("Mono_Cabeza", ca, (0, 0, 0.72), c)
    cola("Mono", c, [(0, 0.18, 0.3), (0, 0.45, 0.2), (0, 0.6, 0.4), (0, 0.5, 0.56)], 0.03, M)
    return c


def suricata():
    T, C, O = "#c9a06a", "#ead2a8", "#4a3424"
    piel = lambda co, n: mezcla(C, T, (co.y + 0.05) * 9)
    cu = [pintar(esfera((0, 0, 0.32), (0.12, 0.11, 0.24), 20), piel)]
    for l in (-1, 1):
        cu.append(color(esfera((l * 0.07, -0.03, 0.08), (0.05, 0.08, 0.08), 8), T))
    c = parte("Suricata", cu, (0, 0, 0))
    for nom, l in (("BrazoI", 1), ("BrazoD", -1)):
        parte(f"Suricata_{nom}", [color(skin("brazo", [(l * 0.08, -0.06, 0.45), (l * 0.07, -0.11, 0.35), (l * 0.05, -0.12, 0.3)], [(0, 1), (1, 2)], [0.028, 0.024, 0.02]), T)],
              (l * 0.08, -0.06, 0.45), c)
    ca = [color(esfera((0, -0.02, 0.62), (0.08, 0.09, 0.08), 16), T), color(esfera((0, -0.11, 0.6), (0.045, 0.07, 0.045), 12), C),
          color(esfera((0, -0.18, 0.61), (0.018, 0.012, 0.014), 6), "#1f1f22")]
    for l in (-1, 1):
        ca.append(color(esfera((l * 0.04, -0.07, 0.65), (0.03, 0.02, 0.032), 8), O))
        ca.append(color(esfera((l * 0.075, 0.0, 0.67), (0.02, 0.015, 0.02), 6), O))
    ca += ojos(0, -0.085, 0.655, 0.038, 0.022)
    parte("Suricata_Cabeza", ca, (0, 0, 0.52), c)
    cola("Suricata", c, [(0, 0.08, 0.12), (0, 0.22, 0.05), (0, 0.38, 0.03)], 0.022, T, (0.02, 0.03, 0.02), O)
    return c


# ---------- EL JEEP DEL SAFARI (mirando a -Y) ----------
def jeep():
    V, A, N = "#5f7d3a", "#e2cf98", "#2a2a2a"
    p = [color(caja((0, 0.1, 0.85), (1.8, 4.0, 0.62), bisel=0.1), V),
         color(caja((0, -1.4, 1.2), (1.7, 1.2, 0.14), bisel=0.05), V),
         color(caja((0, -2.08, 0.88), (1.3, 0.1, 0.42), bisel=0.03), N),
         color(caja((0, -2.15, 0.52), (1.9, 0.18, 0.18), bisel=0.04), "#3a3a3a"),
         color(caja((0, 2.15, 0.6), (1.85, 0.16, 0.16), bisel=0.04), "#3a3a3a")]
    for l in (-1, 1):
        p.append(color(esfera((l * 0.58, -2.12, 0.98), (0.14, 0.05, 0.14), 12), "#fff3a8"))
        # guardabarros
        for y in (-1.35, 1.35):
            g = toro((l * 0.95, y, 0.5), 0.55, 0.12, rot=(0, math.pi / 2, 0), seg=20)
            recortar(g, lambda co, y=y: co.z < 0.48)
            p.append(color(g, V))
        # rayas de cebra en el costado
        for k in range(8):
            p.append(color(caja((l * 0.905, -1.3 + k * 0.4, 0.95), (0.02, 0.12, 0.5), rot=(0.25, 0, 0)), "#f4f2ec"))
    # parabrisas y barras
    p.append(color(caja((0, -0.75, 1.6), (1.7, 0.06, 0.7)), "#b8e0f0"))
    for l in (-1, 1):
        p.append(barra((l * 0.85, -0.75, 1.2), (l * 0.85, -0.75, 1.95), 0.04, N))
        p.append(barra((l * 0.85, -0.6, 2.35), (l * 0.85, 1.95, 2.35), 0.045, N))
        p.append(barra((l * 0.85, 1.95, 1.15), (l * 0.85, 1.95, 2.35), 0.045, N))
        p.append(barra((l * 0.85, -0.6, 1.95), (l * 0.85, -0.6, 2.35), 0.045, N))
    p.append(barra((-0.85, -0.6, 2.35), (0.85, -0.6, 2.35), 0.045, N))
    p.append(barra((-0.85, 1.95, 2.35), (0.85, 1.95, 2.35), 0.045, N))
    # techo de lona
    p.append(color(caja((0, 0.68, 2.42), (1.85, 2.75, 0.06), bisel=0.02), A))
    # asientos: dos delante y un banco alto detrás
    for x in (-0.45, 0.45):
        p.append(color(caja((x, -0.15, 1.2), (0.62, 0.6, 0.14), bisel=0.04), "#7a4a2b"))
        p.append(color(caja((x, 0.15, 1.5), (0.62, 0.12, 0.6), bisel=0.04), "#7a4a2b"))
    p.append(color(caja((0, 1.05, 1.4), (1.6, 0.7, 0.14), bisel=0.04), "#7a4a2b"))
    p.append(color(caja((0, 1.42, 1.72), (1.6, 0.12, 0.6), bisel=0.04), "#7a4a2b"))
    # volante
    p.append(color(toro((-0.45, -0.62, 1.55), 0.2, 0.03, rot=(1.1, 0, 0), seg=20), N))
    p.append(barra((-0.45, -0.62, 1.55), (-0.45, -0.85, 1.25), 0.03, N))
    # rueda de repuesto
    p.append(color(toro((0, 2.28, 1.15), 0.34, 0.13, rot=(math.pi / 2, 0, 0), seg=20), N))
    c = parte("Jeep", p, (0, 0, 0))
    for nom, x, y in (("RuedaDI", 0.95, -1.35), ("RuedaDD", -0.95, -1.35), ("RuedaTI", 0.95, 1.35), ("RuedaTD", -0.95, 1.35)):
        r = [color(toro((x, y, 0.44), 0.3, 0.14, rot=(0, math.pi / 2, 0), seg=20), N),
             color(cilindro((x, y, 0.44), 0.22, 0.2, rot=(0, math.pi / 2, 0), v=16), "#d9d4c4"),
             color(cilindro((x + (0.1 if x > 0 else -0.1), y, 0.44), 0.08, 0.04, rot=(0, math.pi / 2, 0), v=10), "#7a7a7a")]
        parte(f"Jeep_{nom}", r, (x, y, 0.44), c)
    return c


# ---------- LA SABANA ----------
def acacia():
    tr = skin("tronco", [(0, 0, 0), (0.1, 0, 1.6), (0.25, 0, 2.6), (1.4, 0.3, 3.9), (-1.0, -0.4, 3.8), (0.1, 1.1, 4.0)],
              [(0, 1), (1, 2), (2, 3), (2, 4), (2, 5)], [0.28, 0.22, 0.18, 0.08, 0.08, 0.08])
    p = [color(tr, "#6b4a32")]
    for x, y, z, rx in ((0, 0, 4.25, 3.2), (1.6, 0.4, 4.0, 1.8), (-1.3, -0.5, 4.0, 1.7), (0.2, 1.4, 4.15, 1.6), (0.4, -1.2, 4.2, 1.5)):
        o = esfera((x, y, z), (rx, rx * 0.9, 0.45), 18)
        pintar(o, lambda co, n: mezcla("#55801f", "#86b13a", (co.z - 3.8) * 1.6 + 0.15 * math.sin(co.x * 3)))
        p.append(o)
    return parte("Acacia", p, (0, 0, 0))


def baobab():
    tr = cilindro((0, 0, 2.2), 1.3, 4.4, v=18, r2=0.8)
    pintar(tr, lambda co, n: mezcla("#8f7a68", "#b09a84", 0.5 + 0.5 * math.sin(math.atan2(co.y, co.x) * 9)))
    p = [tr]
    for k in range(6):
        a = k / 6 * math.pi * 2
        r = skin("rama", [(math.cos(a) * 0.4, math.sin(a) * 0.4, 4.2), (math.cos(a) * 1.4, math.sin(a) * 1.4, 5.0), (math.cos(a) * 1.9, math.sin(a) * 1.9, 5.6)],
                 [(0, 1), (1, 2)], [0.3, 0.18, 0.1])
        p.append(color(r, "#9a8572"))
        p.append(color(esfera((math.cos(a) * 1.95, math.sin(a) * 1.95, 5.8), (0.7, 0.7, 0.45), 12), "#6f9a3c"))
    return parte("Baobab", p, (0, 0, 0))


def termitero():
    p = []
    for x, y, h, r in ((0, 0, 2.6, 0.9), (0.6, 0.3, 1.6, 0.55), (-0.5, -0.2, 1.9, 0.5), (0.1, -0.6, 1.2, 0.5)):
        o = cilindro((x, y, h / 2), r, h, v=12, r2=r * 0.25)
        pintar(o, lambda co, n: mezcla("#a8643a", "#c98a55", co.z / 2.6 + 0.1 * math.sin(co.x * 8)))
        p.append(o)
    return parte("Termitero", p, (0, 0, 0))


def roca_leones():
    """La roca de los leones: varias peñas y una losa que sobresale."""
    p = []
    rr = random.Random(5)
    for x, y, z, s in ((0, 0, 1.2, (4.5, 3.6, 2.2)), (2.5, 1.5, 2.8, (2.8, 2.2, 1.6)), (-1.8, 1.8, 2.4, (2.6, 2.4, 1.6)),
                       (0.8, 2.6, 3.8, (2.0, 1.8, 1.2)), (-3.5, -1.0, 0.8, (1.8, 1.6, 1.0))):
        o = esfera((x, y, z), s, 14)
        bm = bmesh.new()
        bm.from_mesh(o.data)
        for v in bm.verts:
            v.co *= 1 + rr.uniform(-0.08, 0.08)
        bm.to_mesh(o.data)
        bm.free()
        suave(o, False)
        pintar(o, lambda co, n: mezcla("#9c8a72", "#c9b08a", (co.z / 5) + 0.15 * n.z))
        p.append(o)
    losa = caja((0.3, -1.2, 4.6), (2.4, 4.2, 0.5), rot=(0.08, 0, 0.1), bisel=0.2)
    pintar(losa, lambda co, n: mezcla("#a8957a", "#d4bc96", 0.5 + 0.5 * n.z))
    p.append(losa)
    return parte("RocaLeones", p, (0, 0, 0))


def arco_safari():
    M, P = "#8a5a33", "#d9b56a"
    p = []
    for l in (-1, 1):
        p.append(color(cilindro((l * 3.2, 0, 2.5), 0.28, 5.0, v=10), M))
        p.append(color(cilindro((l * 3.2, 0, 5.3), 0.45, 0.8, v=10, r2=0.05), P))
    p.append(color(cilindro((0, 0, 4.6), 0.22, 7.2, rot=(0, math.pi / 2, 0), v=10), M))
    p.append(color(cilindro((0, 0, 3.9), 0.16, 6.6, rot=(0, math.pi / 2, 0), v=10), M))
    for l in (-1, 1):
        p.append(barra((l * 3.2, 0, 3.4), (l * 2.0, 0, 4.6), 0.12, M))
    p.append(color(caja((0, 0, 5.15), (7.4, 1.6, 0.18), rot=(0, 0, 0)), P))
    return parte("ArcoSafari", p, (0, 0, 0))


animales = [elefante(), jirafa(), cebra(), leon("Leon", True), leon("Leona", False), hipo(), rino(), gacela(), avestruz(), flamenco(), mono(), suricata()]
deco = [jeep(), acacia(), baobab(), termitero(), roca_leones(), arco_safari()]
todos = [o for o in bpy.data.objects if o.type == 'MESH']
caras = sum(len(o.data.polygons) for o in todos)
print(f"{len(todos)} piezas, {caras} caras")
bpy.ops.object.select_all(action='DESELECT')
for o in todos:
    o.select_set(True)
bpy.ops.export_scene.gltf(filepath=os.path.abspath(os.path.join("web", "safari.glb")), export_format='GLB', use_selection=True)
print("Exportado web/safari.glb")

if os.environ.get("SIN_RENDER") == "1":
    raise SystemExit

# ---------- MUESTRA: todos en fila ----------
x = -14
for o in animales + deco[:1]:
    ancho = {"Elefante": 3.4, "Jirafa": 2.2, "Hipo": 2.6, "Rino": 2.4, "Jeep": 3.0}.get(o.name, 1.6)
    x += ancho / 2
    o.location = (x, 0, 0)
    o.rotation_euler = (0, 0, -0.5)
    x += ancho / 2 + 0.3
for o in deco[1:]:
    o.hide_render = True
bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 10, 0))
s = bpy.context.object
m = bpy.data.materials.new("Suelo")
m.use_nodes = True
m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*lineal("#d8c27a"), 1)
s.data.materials.append(m)
bpy.ops.object.camera_add(location=(float(os.environ.get("CAMX", "4")), -float(os.environ.get("CAMD", "26")), 3.5), rotation=(math.radians(84), 0, 0))
bpy.context.scene.camera = bpy.context.object
bpy.context.object.data.lens = 30
bpy.ops.object.light_add(type='SUN', rotation=(math.radians(45), math.radians(10), math.radians(-25)))
bpy.context.object.data.energy = 3.5
w = bpy.data.worlds.new("Mundo")
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.6, 0.8, 1.0, 1)
bpy.context.scene.world = w
esc = bpy.context.scene
esc.render.engine = 'CYCLES'
esc.cycles.samples = int(os.environ.get("MUESTRAS", "32"))
esc.cycles.use_denoising = False
esc.view_settings.view_transform = 'AgX'
esc.view_settings.look = 'AgX - Punchy'
esc.render.resolution_x = 1600
esc.render.resolution_y = 600
esc.render.filepath = os.path.abspath(os.environ.get("MUESTRA", "safari.png"))
bpy.ops.render.render(write_still=True)
