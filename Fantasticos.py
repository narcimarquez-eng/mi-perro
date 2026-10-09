"""El arroyo mágico: animales fantásticos de dibujo con piezas que se mueven, y las cosas del bosque encantado.

blender -b --factory-startup --python Fantasticos.py

Exporta web/fantasticos.glb. Cada criatura es un objeto con sus piezas colgando de él, cada una con el origen
donde gira; miran hacia -Y (en la web, hacia +Z):
  Unicornio (Cabeza, Cola, cuatro patas), Pegaso (además AlaI y AlaD), Grifo (Cabeza, AlaI, AlaD, Cola, patas),
  Hidra (tres cuellos con su cabeza: Hidra_Cuello1..3, cada uno con su Mandibula), DragonAgua (la Cabeza sale del
  agua; DragonAgua_Joroba es una joroba suelta para repetir detrás), Fenix (AlaI, AlaD, Cola), Dragoncito
  (Cabeza, AlaI, AlaD, Cola, patas) y Hada (AlaI, AlaD).
Y además: Diana (cuelga de su origen), ArbolDianas (un roble con una rama larga para colgar dianas), Flecha (con
ventosa, de juguete), TroncoHueco, Nido y Seta. Renderiza fantasticos.png con todos en fila.
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



def cadena(puntos, radios, col):
    o = skin("cadena", puntos, [(k, k + 1) for k in range(len(puntos) - 1)], radios)
    return color(o, col) if not callable(col) else pintar(o, col)


ARCOIRIS = ["#ff5a7a", "#ffa63d", "#ffe04a", "#6fdc6a", "#4ab8ff", "#9b7bff"]


def ala(nombre, padre, l, base, largo, ancho, col_fn, plumas=6):
    """Ala de plumas que sale hacia el lado l (+1 izquierda = +X, -1 derecha) desde el hombro."""
    bx, by, bz = base
    piezas = [pintar(esfera((bx + l * largo * 0.42, by + ancho * 0.05, bz + 0.05), (largo * 0.48, ancho * 0.32, 0.06), 20), lambda co, n: col_fn(0.0))]
    for k in range(plumas):
        t = k / (plumas - 1)
        x = bx + l * (0.12 + largo * 0.88 * t)
        largo_p = ancho * (0.75 + 0.35 * math.sin(t * math.pi * 0.9))
        piezas.append(pintar(esfera((x, by + largo_p * 0.45, bz - 0.02 - 0.03 * t), (largo * 0.09, largo_p * 0.55, 0.035), 12), lambda co, n, t=t: col_fn(0.3 + 0.7 * t)))
    return parte(nombre, piezas, base, padre)


def ojo_grande(x, y, z, r, iris="#3a2a6a"):
    return [color(esfera((x, y, z), (r, r * 0.6, r * 1.1), 14), "#ffffff"),
            color(esfera((x, y - r * 0.45, z - r * 0.08), (r * 0.6, r * 0.3, r * 0.68), 12), iris),
            color(esfera((x, y - r * 0.62, z - r * 0.08), (r * 0.32, r * 0.14, r * 0.38), 10), "#14121c"),
            color(esfera((x + r * 0.25, y - r * 0.7, z + r * 0.25), r * 0.17, 8), "#ffffff")]


# ---------- CABALLOS MÁGICOS ----------
def caballo(nombre, piel, crin_cols, cuerno=False, alas=None):
    c = parte(nombre, [color(esfera((0, 0, 1.2), (0.42, 0.85, 0.46), 40), piel)], (0, 0, 0))
    for etiqueta, y in (("D", -0.5), ("T", 0.5)):
        for lado, x in (("I", 0.2), ("D", -0.2)):
            parte(f"{nombre}_Pata{etiqueta}{lado}", pierna(x, y, 1.15, (0.065, 0.1), piel, "#c9a24a", 5), (x, y, 1.05), c)
    cue = color(skin("cuello", [(0, -0.6, 1.3), (0, -0.82, 1.68), (0, -0.95, 1.95)], [(0, 1), (1, 2)], [0.22, 0.18, 0.16]), piel)
    cab = color(esfera((0, -1.12, 1.98), (0.16, 0.31, 0.18), 32), piel)
    hocico = color(esfera((0, -1.38, 1.9), (0.13, 0.13, 0.12), 16), "#f2c6d6")
    ca = [cue, cab, hocico]
    # crin de colores: mechones a lo largo del cuello y un flequillo
    for k in range(9):
        t = k / 8
        p = (0, -0.5 - 0.47 * t, 1.62 + 0.55 * t)
        ca.append(color(esfera((0.06 * (1 if k % 2 else -1), p[1] + 0.06, p[2]), (0.08, 0.14, 0.13), 12), crin_cols[k % len(crin_cols)]))
    ca.append(color(esfera((0, -1.12, 2.18), (0.1, 0.1, 0.07), 12), crin_cols[0]))
    for l in (-1, 1):
        ca.append(color(cilindro((l * 0.09, -1.0, 2.25), 0.045, 0.16, rot=(0.2, l * 0.3, 0), v=8, r2=0.0), piel))
    ca += ojo_grande(0.12, -1.2, 2.05, 0.055) + ojo_grande(-0.12, -1.2, 2.05, 0.055)
    if cuerno:
        # cuerno dorado en espiral
        bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=0.055, radius2=0.0, depth=0.42, location=(0, -1.18, 2.36), rotation=(-0.35, 0, 0))
        cu = bpy.context.object
        bpy.ops.object.transform_apply(location=True, rotation=True)
        subdividir(cu, 4)
        pintar(cu, lambda co, n: lineal("#ffd34a") if math.sin(co.z * 70 + math.atan2(co.x, co.y + 1.18) * 2) > 0 else lineal("#fff1a8"), VC_ORO)
        ca.append(cu)
    parte(f"{nombre}_Cabeza", ca, (0, -0.62, 1.42), c)
    # cola de colores
    pc = []
    for k, col in enumerate(crin_cols):
        a = (k - len(crin_cols) / 2) * 0.09
        pc.append(color(skin("cola", [(a, 0.82, 1.38), (a * 1.6, 1.0, 1.1), (a * 2.2, 1.05, 0.75)], [(0, 1), (1, 2)], [0.06, 0.07, 0.04]), col))
    parte(f"{nombre}_Cola", pc, (0, 0.82, 1.38), c)
    if alas:
        for nom, l in (("AlaI", 1), ("AlaD", -1)):
            ala(f"{nombre}_{nom}", c, l, (l * 0.3, -0.35, 1.55), 1.5, 0.75, alas)
    return c


def unicornio():
    return caballo("Unicornio", "#fbf8ff", ARCOIRIS, cuerno=True)


def pegaso():
    return caballo("Pegaso", "#eef0ff", ["#7fd3ff", "#b9a4ff", "#ffffff"], alas=lambda t: mezcla("#ffffff", "#b9c8ff", t))


# ---------- GRIFO: cabeza y alas de águila, cuerpo de león ----------
def grifo():
    L, Lc, P, B = "#d9a75a", "#efd49a", "#8a5a2e", "#fbf6ea"
    piel = lambda co, n: mezcla(Lc, L, (co.z - 0.7) * 3)
    c = parte("Grifo", [pintar(esfera((0, 0, 0.95), (0.42, 0.85, 0.44), 32), piel)], (0, 0, 0))
    # patas de delante de águila (amarillas con garras), de detrás de león
    for etiqueta, y, col in (("D", -0.5, "#f2c23a"), ("T", 0.55, L)):
        for lado, x in (("I", 0.22), ("D", -0.22)):
            pz = pierna(x, y, 0.95, (0.07, 0.12), col, None, 4)
            if etiqueta == "D":
                for g in (-1, 0, 1):
                    pz.append(color(cilindro((x + g * 0.05, y - 0.1, 0.04), 0.022, 0.12, rot=(math.pi / 2 + 0.3, 0, 0), v=6, r2=0.0), "#3a3030"))
            else:
                pz.append(color(esfera((x, y - 0.03, 0.07), (0.09, 0.11, 0.07), 10), Lc))
            parte(f"Grifo_Pata{etiqueta}{lado}", pz, (x, y, 0.88), c)
    ca = [color(skin("cuello", [(0, -0.6, 1.05), (0, -0.82, 1.35)], [(0, 1)], [0.27, 0.22]), B),
          color(esfera((0, -0.98, 1.52), (0.24, 0.26, 0.25), 24), B)]
    # plumas del cuello
    for k in range(10):
        a = k / 10 * math.pi * 2
        ca.append(color(esfera((math.cos(a) * 0.24, -0.78, 1.28 + math.sin(a) * 0.2), (0.1, 0.14, 0.1), 10), B))
    pico = cilindro((0, -1.27, 1.48), 0.1, 0.3, rot=(math.pi / 2 + 0.35, 0, 0), v=16, r2=0.0)
    ca.append(color(pico, "#ffc21a"))
    ca += ojo_grande(0.12, -1.13, 1.6, 0.06, "#c97a10") + ojo_grande(-0.12, -1.13, 1.6, 0.06, "#c97a10")
    for l in (-1, 1):
        ca.append(color(cilindro((l * 0.1, -0.86, 1.75), 0.05, 0.22, rot=(-0.4, l * 0.35, 0), v=8, r2=0.0), B))
    parte("Grifo_Cabeza", ca, (0, -0.65, 1.15), c)
    for nom, l in (("AlaI", 1), ("AlaD", -1)):
        ala(f"Grifo_{nom}", c, l, (l * 0.3, -0.3, 1.25), 1.6, 0.8, lambda t: mezcla("#b0743a", P, t))
    cola("Grifo", c, [(0, 0.85, 1.02), (0, 1.15, 0.8), (0, 1.42, 0.85)], 0.045, L, (0.07, 0.07, 0.1), P)
    return c


# ---------- HIDRA: tres cabezas simpáticas que salen del agua ----------
def hidra():
    V, Vc, Vo = "#3fae6a", "#c6ef9a", "#237a48"
    cuerpo = esfera((0, 0, 0.3), (1.0, 1.25, 0.75), 40)
    pintar(cuerpo, lambda co, n: lineal(Vc) if n.z < -0.2 or co.y < -0.9 else mezcla(V, Vo, 0.5 + 0.5 * math.sin(co.x * 9) * math.sin(co.y * 9)))
    pz = [cuerpo]
    for k in range(6):  # crestas de la espalda
        pz.append(color(cilindro((0, -0.3 + k * 0.3, 0.98 - abs(k - 2) * 0.05), 0.14, 0.32, rot=(0.3, 0, 0), v=4, r2=0.0), "#ffb03a"))
    c = parte("Hidra", pz, (0, 0, 0))
    # cola que sale por detrás
    cola("Hidra", c, [(0, 1.1, 0.3), (0.3, 1.7, 0.25), (0.7, 2.1, 0.4), (1.0, 2.3, 0.6)], 0.32, V)
    cols_ojo = ["#e2a21a", "#3a6ad8", "#c83a6a"]
    for k, (x, ang) in enumerate(((0.55, 0.45), (0.0, 0.0), (-0.55, -0.45))):
        base = (x * 0.9, -0.55, 0.65)
        tope = (x * 1.7, -1.2, 2.5 - abs(x) * 0.4)
        medio = ((base[0] + tope[0]) / 2, -1.15, (base[2] + tope[2]) / 2 - 0.15)
        cu = skin("cuello", [base, medio, tope], [(0, 1), (1, 2)], [0.3, 0.22, 0.2])
        pintar(cu, lambda co, n: lineal(Vc) if n.y < -0.6 else lineal(V))
        hx, hy, hz = tope
        ca = [cu, color(esfera((hx, hy - 0.15, hz + 0.1), (0.3, 0.38, 0.26), 24), V),
              color(esfera((hx, hy - 0.45, hz + 0.02), (0.22, 0.22, 0.14), 18), V)]
        for l in (-1, 1):
            ca += ojo_grande(hx + l * 0.14, hy - 0.32, hz + 0.24, 0.075, cols_ojo[k])
            ca.append(color(cilindro((hx + l * 0.14, hy, hz + 0.38), 0.05, 0.22, rot=(-0.5, l * 0.4, 0), v=8, r2=0.0), "#fff3c4"))
            ca.append(color(esfera((hx + l * 0.07, hy - 0.66, hz + 0.08), 0.022, 8), "#1c3a24"))
        cuello = parte(f"Hidra_Cuello{k + 1}", ca, base, c)
        man = [color(esfera((hx, hy - 0.4, hz - 0.1), (0.2, 0.22, 0.07), 16), Vc),
               color(esfera((hx, hy - 0.4, hz - 0.06), (0.14, 0.15, 0.04), 12), "#e0607a")]
        for l in (-1, 1):
            man.append(color(cilindro((hx + l * 0.1, hy - 0.55, hz - 0.03), 0.025, 0.07, v=6, r2=0.0), "#ffffff"))
        parte(f"Hidra_Mandibula{k + 1}", man, (hx, hy - 0.2, hz - 0.05), cuello)
    return c


# ---------- DRAGÓN DE AGUA: cabeza que sale del arroyo y jorobas ----------
def dragon_agua():
    A, Ac, Ao = "#2fb6c8", "#bff4f0", "#1a7a9a"
    piel = lambda co, n: lineal(Ac) if n.y < -0.55 else mezcla(A, Ao, 0.5 + 0.5 * math.sin(co.z * 12))
    c = parte("DragonAgua", [color(toro((0, 0, -0.05), 0.42, 0.06, seg=24), "#e9fbff")], (0, 0, 0))  # ondas del agua
    # cuello en forma de S, más gordo abajo
    espina = [(0, 0.25, -0.6), (0.32, 0.55, 0.35), (-0.28, 0.35, 1.15), (0.12, -0.15, 1.75), (0, -0.5, 2.05)]
    cu = skin("cuello", espina, [(k, k + 1) for k in range(len(espina) - 1)], [0.55, 0.45, 0.36, 0.29, 0.25])
    pintar(cu, piel)
    ca = [cu, color(esfera((0, -0.8, 2.2), (0.32, 0.45, 0.28), 24), A),
          color(esfera((0, -1.18, 2.12), (0.22, 0.22, 0.16), 18), Ac)]
    for l in (-1, 1):
        ca += ojo_grande(l * 0.17, -0.95, 2.36, 0.08, "#1a8a6a")
        # aletas a los lados de la cabeza
        aleta = esfera((l * 0.38, -0.68, 2.3), (0.04, 0.22, 0.18), 12)
        ca.append(color(aleta, "#ff9ac0"))
        # bigotes
        ca.append(color(skin("bigote", [(l * 0.12, -1.3, 2.1), (l * 0.4, -1.4, 1.95), (l * 0.55, -1.3, 1.75)], [(0, 1), (1, 2)], [0.025, 0.02, 0.012], 0), "#ffe08a"))
    for k in range(7):  # aleta de la espalda, siguiendo la curva del cuello
        t = k / 6 * (len(espina) - 1.3)
        i = int(t)
        a, b = Vector(espina[i]), Vector(espina[min(i + 1, len(espina) - 1)])
        q = a.lerp(b, t - i)
        r = 0.44 - 0.2 * t / (len(espina) - 1)
        ca.append(color(esfera((q.x, q.y + r * 0.85, q.z + 0.05), (0.035, 0.16, 0.2), 10), "#ff9ac0"))
    cab = parte("DragonAgua_Cabeza", ca, (0, 0, 0), c)
    parte("DragonAgua_Mandibula", [color(esfera((0, -1.08, 2.0), (0.18, 0.24, 0.06), 14), Ac),
                                   color(esfera((0, -1.08, 2.03), (0.13, 0.17, 0.03), 10), "#e0607a")], (0, -0.78, 2.08), cab)
    # joroba suelta (se repite detrás de la cabeza, asomando del agua)
    jo = toro((0, 0, 0), 0.5, 0.24, rot=(0, math.pi / 2, 0), seg=28)
    recortar(jo, lambda co: co.z < -0.12)
    pintar(jo, piel)
    pj = [jo]
    for k in range(3):
        a = (k + 1) / 4 * math.pi
        pj.append(color(esfera((0, math.cos(a) * 0.5, math.sin(a) * 0.5 + 0.22), (0.03, 0.12, 0.14), 10), "#ff9ac0"))
    parte("DragonAgua_Joroba", pj, (0, 0, 0))
    return c


# ---------- FÉNIX: pájaro de fuego ----------
def fenix():
    fuego = lambda t: mezcla("#ffd23a", "#ff3a1a", t)
    c = parte("Fenix", [pintar(esfera((0, 0, 0), (0.28, 0.5, 0.3), 24), lambda co, n: mezcla("#ffb02a", "#ff4a1a", co.y + 0.5)),
                        color(esfera((0, -0.08, -0.1), (0.2, 0.32, 0.18), 16), "#ffe08a")], (0, 0, 0))
    ca = [color(esfera((0, -0.55, 0.22), (0.18, 0.2, 0.18), 20), "#ff7a1a"),
          color(cilindro((0, -0.78, 0.2), 0.06, 0.2, rot=(math.pi / 2 + 0.3, 0, 0), v=12, r2=0.0), "#ffe24a")]
    ca += ojo_grande(0.09, -0.68, 0.28, 0.045, "#c0301a") + ojo_grande(-0.09, -0.68, 0.28, 0.045, "#c0301a")
    for k in range(4):  # cresta de fuego
        ca.append(color(esfera((0, -0.5 + k * 0.08, 0.4 + k * 0.05), (0.03, 0.06, 0.12 + k * 0.02), 10), ["#ffe24a", "#ffb02a", "#ff7a1a", "#ff3a1a"][k]))
    parte("Fenix_Cabeza", ca, (0, -0.4, 0.1), c)
    for nom, l in (("AlaI", 1), ("AlaD", -1)):
        ala(f"Fenix_{nom}", c, l, (l * 0.2, -0.1, 0.12), 1.3, 0.6, fuego)
    co = []
    for k in range(5):
        a = (k - 2) * 0.2
        co.append(color(skin("pluma", [(0, 0.4, 0), (math.sin(a) * 0.6, 1.0, -0.05), (math.sin(a) * 1.0, 1.5, 0.1)], [(0, 1), (1, 2)], [0.07, 0.06, 0.03]), ["#ff3a1a", "#ff7a1a", "#ffd23a", "#ff7a1a", "#ff3a1a"][k]))
        co.append(color(esfera((math.sin(a) * 1.0, 1.55, 0.1), (0.1, 0.16, 0.04), 10), "#ffe24a"))
    parte("Fenix_Cola", co, (0, 0.4, 0), c)
    return c


# ---------- DRAGONCITO: un dragón bebé, morado y simpático ----------
def dragoncito():
    M, Mc = "#8a5ad8", "#f6d6ff"
    piel = lambda co, n: lineal(Mc) if n.y < -0.5 and co.z < 0.75 else lineal(M)
    c = parte("Dragoncito", [pintar(esfera((0, 0, 0.55), (0.38, 0.45, 0.42), 32), piel)], (0, 0, 0))
    patas("Dragoncito", c, 0.22, (-0.22, 0.25), 0.35, (0.09, 0.11), M, "#fff3c4", 3)
    ca = [color(esfera((0, -0.3, 1.05), (0.34, 0.32, 0.3), 28), M),
          color(esfera((0, -0.6, 0.98), (0.22, 0.16, 0.15), 18), Mc)]
    for l in (-1, 1):
        ca += ojo_grande(l * 0.14, -0.55, 1.15, 0.09, "#2a8a4a")
        ca.append(color(cilindro((l * 0.15, -0.2, 1.38), 0.06, 0.2, rot=(-0.3, l * 0.3, 0), v=8, r2=0.0), "#fff3c4"))
        ca.append(color(esfera((l * 0.08, -0.75, 1.0), 0.025, 8), "#4a2a7a"))
    parte("Dragoncito_Cabeza", ca, (0, -0.2, 0.85), c)
    for nom, l in (("AlaI", 1), ("AlaD", -1)):
        ala(f"Dragoncito_{nom}", c, l, (l * 0.22, 0.05, 0.8), 0.55, 0.35, lambda t: mezcla("#b98aff", "#ff9ad8", t), 4)
    cola("Dragoncito", c, [(0, 0.4, 0.35), (0, 0.75, 0.2), (0.15, 1.0, 0.3)], 0.11, M, (0.08, 0.08, 0.1), "#ff9ad8")
    return c


# ---------- HADA: pequeñita, con alas que brillan ----------
def hada():
    c = parte("Hada", [color(cilindro((0, 0, 0.0), 0.11, 0.3, v=16, r2=0.02), "#7ae0a0"),
                       color(esfera((0, 0, 0.25), 0.1, 16), "#ffd9c0"),
                       color(esfera((0, 0.02, 0.29), (0.11, 0.1, 0.09), 14), "#ffcf3a")]
              + ojo_grande(0.04, -0.08, 0.27, 0.025, "#3a6ad8") + ojo_grande(-0.04, -0.08, 0.27, 0.025, "#3a6ad8"), (0, 0, 0))
    for nom, l in (("AlaI", 1), ("AlaD", -1)):
        parte(f"Hada_{nom}", [color(esfera((l * 0.13, 0.05, 0.15), (0.12, 0.02, 0.17), 12), "#c9f4ff"),
                              color(esfera((l * 0.1, 0.05, -0.02), (0.08, 0.02, 0.1), 10), "#ffd0f0")], (l * 0.03, 0.05, 0.1), c)
    return c


# ---------- COSAS DEL BOSQUE ----------
def diana():
    """Diana redonda colgando de dos cuerdas; el origen es el punto de donde cuelga."""
    pz = []
    for l in (-1, 1):
        pz.append(barra((l * 0.25, 0, 0), (l * 0.3, 0, -0.62), 0.012, "#c9a46a", 6))
    cols = ["#e8322a", "#ffffff", "#e8322a", "#ffffff", "#ffd21f"]
    for k, col in enumerate(cols):
        r = 0.5 - k * 0.1
        pz.append(color(cilindro((0, -0.03 - k * 0.006, -1.1), r, 0.05, rot=(math.pi / 2, 0, 0), v=40), col))
    pz.append(color(toro((0, -0.01, -1.1), 0.5, 0.03, rot=(math.pi / 2, 0, 0), seg=40), "#7a4a20"))
    return parte("Diana", pz, (0, 0, 0))


def arbol_dianas():
    tr = cadena([(0, 0, 0), (0.05, 0, 1.6), (0, 0, 3.0), (-0.05, 0, 4.2)], [0.42, 0.34, 0.3, 0.22], "#7a5232")
    pz = [tr]
    # rama larga horizontal para colgar las dianas (a 3,2 m, de -2,1 a 2,1)
    pz.append(cadena([(-2.2, 0, 3.15), (-1.0, 0, 3.3), (0, 0, 3.2), (1.0, 0, 3.3), (2.2, 0, 3.15)], [0.09, 0.13, 0.17, 0.13, 0.09], "#7a5232"))
    for l in (-1, 1):  # raíces
        pz.append(cadena([(0, 0, 0.5), (l * 0.6, -0.2, 0.05)], [0.16, 0.08], "#6a4428"))
        pz.append(cadena([(0, 0, 0.5), (0.2, l * 0.6, 0.05)], [0.15, 0.08], "#6a4428"))
    for k in range(9):
        a = k / 9 * math.pi * 2
        r = 1.4 + 0.5 * math.sin(k * 2.3)
        pz.append(color(esfera((math.cos(a) * r, math.sin(a) * r * 0.7, 4.7 + 0.4 * math.sin(k * 1.7)), 1.0 + 0.25 * math.cos(k), 16), ["#4aa04a", "#5cb85a", "#3f8f45"][k % 3]))
    pz.append(color(esfera((0, 0, 5.4), 1.5, 18), "#5cb85a"))
    return parte("ArbolDianas", pz, (0, 0, 0))


def flecha():
    """Flecha de juguete con ventosa; apunta hacia -Y."""
    pz = [color(cilindro((0, 0, 0), 0.025, 0.9, rot=(math.pi / 2, 0, 0), v=10), "#f2d28a"),
          color(cilindro((0, -0.5, 0), 0.08, 0.1, rot=(math.pi / 2, 0, 0), v=16, r2=0.03), "#e8322a")]
    for k in range(3):
        a = k / 3 * math.pi * 2
        pz.append(color(caja((math.cos(a) * 0.05, 0.38, math.sin(a) * 0.05), (0.01 + 0.08 * abs(math.cos(a)), 0.16, 0.01 + 0.08 * abs(math.sin(a)))), "#4ab8ff"))
    return parte("Flecha", pz, (0, 0, 0))


def tronco_hueco():
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.7, depth=2.6, end_fill_type='NOTHING', location=(0, 0, 0.62), rotation=(0, math.pi / 2, 0))
    t = bpy.context.object
    bpy.ops.object.transform_apply(location=True, rotation=True)
    s = t.modifiers.new("S", 'SOLIDIFY')
    s.thickness = 0.14
    aplicar(t)
    pintar(t, lambda co, n: lineal("#e0b67a") if abs(co.x) > 1.25 or math.hypot(co.y, co.z - 0.62) < 0.64 else mezcla("#6a4428", "#8a5a34", 0.5 + 0.5 * math.sin(co.x * 9 + co.y * 3)))
    pz = [t]
    for k in range(5):
        pz.append(color(esfera((-1.0 + k * 0.5, 0.2 * math.sin(k), 1.28), (0.25, 0.25, 0.08), 10), "#4aa04a"))
    return parte("TroncoHueco", pz, (0, 0, 0))


def nido():
    pz = [color(toro((0, 0, 0.18), 0.55, 0.2, seg=24), "#8a6a3a")]
    for k in range(18):
        a = k / 18 * math.pi * 2
        pz.append(barra((math.cos(a) * 0.4, math.sin(a) * 0.4, 0.05), (math.cos(a + 0.9) * 0.75, math.sin(a + 0.9) * 0.75, 0.35), 0.025, "#6a4a28", 5))
    pz.append(color(esfera((0, 0, 0.12), (0.45, 0.45, 0.1), 16), "#6a4a28"))
    return parte("Nido", pz, (0, 0, 0))


def seta():
    pz = [color(cilindro((0, 0, 0.18), 0.07, 0.36, v=12, r2=0.06), "#f6f0e0")]
    som = esfera((0, 0, 0.38), (0.26, 0.26, 0.16), 20)
    recortar(som, lambda co: co.z < 0.36)
    pz.append(pintar(som, lambda co, n: lineal("#ffffff") if math.sin(co.x * 40) * math.sin(co.y * 40) > 0.55 else lineal("#e83a6a")))
    return parte("Seta", pz, (0, 0, 0))


protos = [unicornio(), pegaso(), grifo(), hidra(), dragon_agua(), fenix(), dragoncito(), hada(),
          diana(), arbol_dianas(), flecha(), tronco_hueco(), nido(), seta()]
protos.append(bpy.data.objects["DragonAgua_Joroba"])
todos = [o for o in bpy.data.objects if o.type == 'MESH']
print(f"{len(todos)} piezas, {sum(len(o.data.polygons) for o in todos)} caras")
bpy.ops.object.select_all(action='DESELECT')
for o in todos:
    o.select_set(True)
bpy.ops.export_scene.gltf(filepath=os.path.abspath(os.path.join("web", "fantasticos.glb")), export_format='GLB', use_selection=True)
print("Exportado web/fantasticos.glb")

if os.environ.get("SIN_RENDER") == "1":
    raise SystemExit

# ---------- MUESTRA ----------
pos = {"Unicornio": (-7.5, 0, 0), "Pegaso": (-5.0, 0, 0), "Grifo": (-2.6, 0, 0), "Hidra": (0.4, 0.6, 0), "DragonAgua": (3.6, 0, 0),
       "DragonAgua_Joroba": (4.3, 1.2, 0), "Fenix": (5.6, 0, 2.2), "Dragoncito": (6.4, -0.5, 0), "Hada": (7.4, -0.8, 1.2),
       "Diana": (-4.0, 2.4, 3.2), "ArbolDianas": (-4.0, 2.4, 0), "Flecha": (8.4, -0.5, 0.5), "TroncoHueco": (9.5, 1.5, 0), "Nido": (5.6, 0.2, 0), "Seta": (7.8, -1.2, 0)}
for o in protos:
    o.location = pos.get(o.name, (0, 0, 0))
    o.rotation_euler = (0, 0, -0.45 if o.name not in ("ArbolDianas", "Diana", "TroncoHueco") else 0)
bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 10, 0))
s = bpy.context.object
m = bpy.data.materials.new("Suelo")
m.use_nodes = True
m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*lineal("#7fbf6a"), 1)
s.data.materials.append(m)
bpy.ops.object.camera_add(location=(1.0, -15, 3.2), rotation=(math.radians(82), 0, 0))
bpy.context.scene.camera = bpy.context.object
bpy.context.object.data.lens = 26
bpy.ops.object.light_add(type='SUN', rotation=(math.radians(45), math.radians(10), math.radians(-25)))
bpy.context.object.data.energy = 3.5
w = bpy.data.worlds.new("Mundo")
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.6, 0.8, 0.95, 1)
bpy.context.scene.world = w
esc = bpy.context.scene
esc.render.engine = 'CYCLES'
esc.cycles.samples = int(os.environ.get("MUESTRAS", "32"))
esc.cycles.use_denoising = False
esc.view_settings.view_transform = 'AgX'
esc.render.resolution_x = 1800
esc.render.resolution_y = 700
esc.render.filepath = os.path.abspath(os.environ.get("MUESTRA", "fantasticos.png"))
bpy.ops.render.render(write_still=True)
