"""Arrecife de coral para la Playa del Perro.

blender -b --factory-startup --python Arrecife.py

Crea las piezas del arrecife (corales, rocas, peces, tortuga, cofre y la barca) y las exporta en
arrecife.glb, cada una en el origen y con su nombre, para que la web las repita muchas veces.
También monta una escena submarina con todas ellas y la renderiza en arrecife.png.

Los corales llevan colores en los vértices casi blancos (luces y sombras de su forma): la web los
tiñe de colores distintos en cada copia. Peces con dibujo, rocas, tortuga, cofre y barca llevan ya
su color.

Variables de entorno: RENDER=0 no renderiza; MUESTRAS = muestras de Cycles.
"""
import bpy
import bmesh
import math
import os
import random
from mathutils import Euler, Matrix, Vector, noise

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.preferences.addon_enable(module="io_scene_gltf2")
rnd = random.Random(21)


# ---------- UTILIDADES ----------
def lineal(hexa):
    c = [int(hexa[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return Vector([x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c])


def activar(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def aplicar(obj):
    activar(obj)
    for m in list(obj.modifiers):
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


def suave(o):
    for p in o.data.polygons:
        p.use_smooth = True


# Material de exportación: color de los vértices ("Col")
def material_vc(nombre, rugosidad=0.7, doble=False):
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    col = nt.nodes.new("ShaderNodeVertexColor")
    col.layer_name = "Col"
    nt.links.new(col.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = rugosidad
    m.use_backface_culling = not doble
    return m


VC = material_vc("Coral", 0.75)
VC_DOBLE = material_vc("CoralDoble", 0.75, doble=True)  # abanicos, algas y aletas (se ven por los dos lados)
VC_BRILLO = material_vc("Brillante", 0.35)               # peces, tortuga y barca


def pintar(o, fn, mat=VC):
    """Pone el color de cada vértice con fn(co, normal) -> (r, g, b) lineal."""
    me = o.data
    if "Col" in me.color_attributes:
        me.color_attributes.remove(me.color_attributes["Col"])
    at = me.color_attributes.new("Col", 'FLOAT_COLOR', 'POINT')
    for v in me.vertices:
        c = fn(v.co, v.normal)
        at.data[v.index].color = (max(0, c[0]), max(0, c[1]), max(0, c[2]), 1.0)
    me.materials.clear()
    me.materials.append(mat)


def mezclar(a, b, t):
    t = max(0.0, min(1.0, t))
    return a * (1 - t) + b * t


def arbol_skin(nombre, verts, aristas, radios, sub=1):
    """Malla orgánica a partir de un esqueleto de líneas (modificador Skin)."""
    me = bpy.data.meshes.new(nombre)
    me.from_pydata(verts, aristas, [])
    o = objeto(nombre, me)
    sk = o.modifiers.new("Skin", 'SKIN')
    sk.branch_smoothing = 0.8
    for i, r in enumerate(radios):
        o.data.skin_vertices[0].data[i].radius = (r, r)
    o.data.skin_vertices[0].data[0].use_root = True
    if sub:
        s = o.modifiers.new("Sub", 'SUBSURF')
        s.levels = sub
    aplicar(o)
    suave(o)
    return o


def girar_hacia(d, ang_x, ang_z):
    return (Euler((ang_x, 0, ang_z)).to_matrix() @ d).normalized()


# =====================================================================
# ---------- CORALES ----------
# =====================================================================
def coral_cerebro(nombre="Cerebro", r=0.45, semilla=1):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=r)
    o = bpy.context.object
    o.name = nombre
    off = Vector((semilla * 13.1, 0, 0))
    surcos = {}
    for v in o.data.vertices:
        p = v.co.copy()
        if p.z < 0:
            p.z *= 0.2
        n = noise.noise(p * 3.2 + off)
        s = abs(math.sin(n * 16 + p.x * 7 + p.y * 5))  # meandros del coral cerebro
        surcos[v.index] = s
        p += p.normalized() * (0.035 * s + 0.05 * noise.noise(p * 1.4 + off))
        v.co = p
    suave(o)
    pintar(o, lambda co, n: Vector((1, 1, 1)))  # (el color de verdad va abajo, con los surcos de cada vértice)
    at = o.data.color_attributes["Col"]
    for v in o.data.vertices:
        s = surcos[v.index]
        base = 0.42 + 0.58 * s
        abajo = 0.55 + 0.45 * max(0.0, min(1.0, v.co.z / (r * 0.5)))
        c = Vector((1.0, 0.97, 0.9)) * base * abajo
        at.data[v.index].color = (*c, 1)
    return o


def coral_ramas(nombre, semilla, niveles, largo, radio, abrir, hijos, subir=0.6, tronco=0.0, base=1):
    """Coral ramificado (cuerno de ciervo, arbusto...) con Skin."""
    r = random.Random(semilla)
    verts, aristas, radios, profund = [Vector((0, 0, 0))], [], [radio * 1.3], [0]

    def crecer(i0, d, l, rad, nivel):
        p = verts[i0]
        # cada rama en dos tramos, un poco curvada
        for k in range(2):
            d = (d + Vector((r.uniform(-0.25, 0.25), r.uniform(-0.25, 0.25), subir * 0.35))).normalized()
            p = p + d * (l / 2)
            verts.append(p)
            radios.append(rad * (1 - 0.18 * k))
            profund.append(nivel + k * 0.5)
            aristas.append((i0, len(verts) - 1))
            i0 = len(verts) - 1
        if nivel < niveles:
            n = hijos if nivel > 0 else base
            for k in range(n):
                a = (k / n) * math.tau + r.uniform(-0.6, 0.6)
                nd = (d + Vector((math.cos(a), math.sin(a), 0)) * abrir).normalized()
                crecer(i0, nd, l * r.uniform(0.65, 0.85), rad * 0.72, nivel + 1)
            if r.random() < 0.7:
                crecer(i0, d, l * 0.8, rad * 0.8, nivel + 1)

    if tronco:
        verts.append(Vector((0, 0, tronco)))
        radios.append(radio * 1.2)
        profund.append(0)
        aristas.append((0, 1))
        crecer(1, Vector((0, 0, 1)), largo, radio, 0)
    else:
        crecer(0, Vector((0, 0, 1)), largo, radio, 0)
    o = arbol_skin(nombre, verts, aristas, radios)
    zmax = max(v.co.z for v in o.data.vertices) or 1
    # puntas más claras (donde crece) y la base en sombra
    pintar(o, lambda co, n: Vector((1, 0.98, 0.95)) * (0.35 + 0.65 * (co.z / zmax) ** 0.7))
    return o


def coral_dedos(nombre="Dedos", semilla=4):
    r = random.Random(semilla)
    verts, aristas, radios = [Vector((0, 0, 0))], [], [0.12]
    for k in range(9):
        a = k / 9 * math.tau + r.uniform(-0.3, 0.3)
        d = r.uniform(0.05, 0.28)
        base = Vector((math.cos(a) * d, math.sin(a) * d, 0.05))
        verts.append(base)
        radios.append(0.07)
        aristas.append((0, len(verts) - 1))
        i = len(verts) - 1
        h = r.uniform(0.35, 0.8)
        for s in range(1, 4):
            p = base + Vector((math.cos(a) * 0.04 * s, math.sin(a) * 0.04 * s, h * s / 3))
            verts.append(p)
            radios.append(0.065 - 0.008 * s)
            aristas.append((i, len(verts) - 1))
            i = len(verts) - 1
    o = arbol_skin(nombre, verts, aristas, radios)
    for v in o.data.vertices:
        v.co += v.normal * 0.012 * noise.noise(v.co * 25)
    zmax = max(v.co.z for v in o.data.vertices)
    pintar(o, lambda co, n: Vector((1, 0.98, 0.92)) * (0.45 + 0.55 * co.z / zmax))
    return o


def coral_mesa(nombre="Mesa", R=0.85, alto=0.5, pisos=1, semilla=2):
    partes = []
    for piso in range(pisos):
        Rp = R * (1 - 0.35 * piso)
        zp = alto + piso * 0.32
        cx, cy = (0.2 * piso, -0.15 * piso)
        anillos, segs = 10, 56
        verts, caras = [Vector((cx, cy, zp + 0.06))], []
        for i in range(1, anillos + 1):
            for j in range(segs):
                a = j / segs * math.tau
                borde = 1 + 0.16 * noise.noise(Vector((math.cos(a) * 2, math.sin(a) * 2, semilla + piso)))
                rr = Rp * i / anillos * borde
                z = zp + 0.06 * (1 - (i / anillos) ** 2) + 0.012 * noise.noise(Vector((math.cos(a) * rr * 9, math.sin(a) * rr * 9, piso)))
                verts.append(Vector((cx + math.cos(a) * rr, cy + math.sin(a) * rr, z)))
        for j in range(segs):
            caras.append((0, 1 + j, 1 + (j + 1) % segs))
        for i in range(anillos - 1):
            for j in range(segs):
                a0 = 1 + i * segs + j
                a1 = 1 + i * segs + (j + 1) % segs
                caras.append((a0, a0 + segs, a1 + segs, a1))
        me = bpy.data.meshes.new("Plato")
        me.from_pydata(verts, [], caras)
        pl = objeto("Plato", me)
        so = pl.modifiers.new("Grosor", 'SOLIDIFY')
        so.thickness = 0.05
        aplicar(pl)
        suave(pl)
        partes.append(pl)
        # pie
        pie = arbol_skin("Pie", [Vector((cx * 0.3, cy * 0.3, 0)), Vector((cx * 0.8, cy * 0.8, zp * 0.5)), Vector((cx, cy, zp))], [(0, 1), (1, 2)], [0.16, 0.09, 0.14])
        partes.append(pie)
    o = unir(partes, nombre)
    zmax = max(v.co.z for v in o.data.vertices)

    def color(co, n):
        rr = math.hypot(co.x, co.y) / R
        arriba = 0.6 + 0.4 * max(0.0, n.z)
        return Vector((1, 0.97, 0.9)) * (0.3 + 0.55 * co.z / zmax + 0.25 * rr) * arriba
    pintar(o, color)
    return o


def gorgonia(nombre="Gorgonia", semilla=5, alto=1.3):
    """Abanico de mar: una red de ramitas en un plano."""
    r = random.Random(semilla)
    verts, aristas, radios = [Vector((0, 0, 0))], [], [0.035]

    def crecer(i0, a, l, rad, nivel):
        p = verts[i0]
        d = Vector((math.sin(a), 0, math.cos(a)))
        q = p + d * l + Vector((0, r.uniform(-0.02, 0.02), 0))
        verts.append(q)
        radios.append(rad)
        aristas.append((i0, len(verts) - 1))
        i = len(verts) - 1
        if nivel < 6:
            for s in (-1, 1):
                crecer(i, a * 0.75 + s * r.uniform(0.25, 0.5), l * r.uniform(0.72, 0.88), max(rad * 0.75, 0.006), nivel + 1)

    crecer(0, 0, alto * 0.22, 0.03, 0)
    o = arbol_skin(nombre, verts, aristas, radios, sub=0)
    zmax = max(v.co.z for v in o.data.vertices)
    pintar(o, lambda co, n: Vector((1, 0.95, 0.95)) * (0.55 + 0.45 * co.z / zmax), VC_DOBLE)
    return o


def esponjas(nombre="Tubos", semilla=6):
    r = random.Random(semilla)
    partes = []
    for k in range(6):
        a = k / 6 * math.tau + r.uniform(-0.3, 0.3)
        d = r.uniform(0.05, 0.3) if k else 0
        h = r.uniform(0.45, 1.0)
        rad = r.uniform(0.07, 0.12)
        bpy.ops.mesh.primitive_cylinder_add(vertices=14, radius=rad, depth=h, location=(math.cos(a) * d, math.sin(a) * d, h / 2))
        c = bpy.context.object
        bm = bmesh.new()
        bm.from_mesh(c.data)
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.normal.z > 0.9], context='FACES_ONLY')
        bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) > 0.01], cuts=4)
        bm.to_mesh(c.data)
        bm.free()
        for v in c.data.vertices:
            t = (v.co.z + h / 2) / h
            v.co.x += math.cos(a) * 0.12 * t * t
            v.co.y += math.sin(a) * 0.12 * t * t
            v.co.x *= 1 + 0.25 * t
            v.co.y *= 1 + 0.25 * t
        so = c.modifiers.new("Grosor", 'SOLIDIFY')
        so.thickness = 0.025
        sb = c.modifiers.new("Sub", 'SUBSURF')
        sb.levels = 1
        aplicar(c)
        suave(c)
        partes.append(c)
    o = unir(partes, nombre)
    zmax = max(v.co.z for v in o.data.vertices)

    def color(co, n):
        dentro = 0.45 if (n.x * co.x + n.y * co.y) < 0 else 1.0
        return Vector((1, 0.96, 0.96)) * (0.5 + 0.5 * co.z / zmax) * dentro
    pintar(o, color)
    return o


def coliflor(nombre="Coliflor", semilla=7):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4, radius=0.4)
    o = bpy.context.object
    o.name = nombre
    off = Vector((semilla, 3, 1))
    alt = {}
    for v in o.data.vertices:
        p = v.co.copy()
        if p.z < -0.05:
            p.z = -0.05 + (p.z + 0.05) * 0.2
        b = 0.1 * noise.noise(p * 4 + off) + 0.05 * abs(noise.noise(p * 11 + off))
        alt[v.index] = b
        v.co = p + p.normalized() * b
    suave(o)
    at_vals = alt
    pintar(o, lambda co, n: Vector((1, 1, 1)))
    at = o.data.color_attributes["Col"]
    for v in o.data.vertices:
        c = Vector((1, 0.96, 0.95)) * (0.5 + 3.0 * max(-0.05, at_vals[v.index])) * (0.55 + 0.45 * max(0, min(1, v.co.z / 0.3 + 0.3)))
        at.data[v.index].color = (*c, 1)
    return o


def anemona(nombre="Anemona", semilla=8):
    r = random.Random(semilla)
    partes = []
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.16, depth=0.2, location=(0, 0, 0.1))
    col = bpy.context.object
    partes.append(col)
    verts, aristas, radios = [], [], []
    for k in range(56):
        a = r.uniform(0, math.tau)
        d = r.uniform(0.02, 0.2)
        base = Vector((math.cos(a) * d, math.sin(a) * d, 0.2))
        largo = r.uniform(0.18, 0.3)
        i0 = len(verts)
        for s in range(4):
            t = s / 3
            p = base + Vector((math.cos(a) * largo * t * 0.9, math.sin(a) * largo * t * 0.9, largo * (0.9 * t - 0.35 * t * t)))
            verts.append(p)
            radios.append(0.016 * (1 - 0.55 * t))
            if s:
                aristas.append((i0 + s - 1, i0 + s))
    # un skin por tentáculo: cada uno es su propia "raíz"
    me = bpy.data.meshes.new("Tentaculos")
    me.from_pydata(verts, aristas, [])
    t = objeto("Tentaculos", me)
    sk = t.modifiers.new("Skin", 'SKIN')
    for i, rr in enumerate(radios):
        t.data.skin_vertices[0].data[i].radius = (rr, rr)
        t.data.skin_vertices[0].data[i].use_root = (i % 4 == 0)
    aplicar(t)
    suave(t)
    partes.append(t)
    o = unir(partes, nombre)
    pintar(o, lambda co, n: Vector((1, 0.97, 0.95)) * (0.35 + 0.65 * min(1.0, max(0.0, (co.z - 0.12) / 0.3))))
    return o


def hierba(nombre="Hierba", semilla=9):
    r = random.Random(semilla)
    verts, caras = [], []
    for k in range(30):
        a = r.uniform(0, math.tau)
        d = r.uniform(0, 0.35)
        bx, by = math.cos(a) * d, math.sin(a) * d
        h = r.uniform(0.35, 0.8)
        g = r.uniform(0, math.tau)
        inc = r.uniform(0.1, 0.4)
        w = 0.025
        i0 = len(verts)
        for s in range(6):
            t = s / 5
            cx = bx + math.cos(g) * inc * t * t * h
            cy = by + math.sin(g) * inc * t * t * h
            z = h * t
            ww = w * (1 - 0.7 * t)
            px, py = -math.sin(g) * ww, math.cos(g) * ww
            verts += [(cx - px, cy - py, z), (cx + px, cy + py, z)]
            if s:
                j = i0 + (s - 1) * 2
                caras.append((j, j + 1, j + 3, j + 2))
    me = bpy.data.meshes.new(nombre)
    me.from_pydata(verts, [], caras)
    o = objeto(nombre, me)
    suave(o)
    pintar(o, lambda co, n: lineal("#4f8a3a") * (0.5 + 0.8 * co.z) + lineal("#9ac25a") * 0.4 * co.z, VC_DOBLE)
    return o


def roca(nombre, semilla, escala=(1.6, 1.2, 0.75)):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4, radius=1.0)
    o = bpy.context.object
    o.name = nombre
    off = Vector((semilla * 7.7, semilla * 3.1, 0))
    for v in o.data.vertices:
        p = v.co.copy()
        p += p * (0.28 * noise.noise(p * 1.3 + off) + 0.09 * noise.noise(p * 4 + off))
        p.x *= escala[0]
        p.y *= escala[1]
        p.z *= escala[2]
        if p.z < -0.15:
            p.z = -0.15 + (p.z + 0.15) * 0.15
        v.co = p
    suave(o)
    gris, marron = lineal("#8c8474"), lineal("#6b5a48")
    rosa, lila, verde = lineal("#d77a9b"), lineal("#8a6fc4"), lineal("#6f9a4a")

    def color(co, n):
        c = mezclar(gris, marron, 0.5 + 0.5 * noise.noise(co * 2 + off))
        m = noise.noise(co * 3.3 + off + Vector((5, 0, 0)))
        if m > 0.25:
            c = mezclar(c, rosa, min(0.45, (m - 0.25) * 2))  # algas calcáreas rosas
        elif m < -0.3:
            c = mezclar(c, lila, min(0.35, (-m - 0.3) * 2))
        if n.z > 0.6:
            c = mezclar(c, verde, 0.35 * (n.z - 0.6) / 0.4 * (0.5 + 0.5 * noise.noise(co * 6 + off)))
        return c * (0.7 + 0.3 * max(0.0, n.z))
    pintar(o, color)
    return o


def estrella(nombre="Estrella"):
    verts, caras = [(0, 0, 0.03)], []
    n = 40
    for j in range(n):
        a = j / n * math.tau
        rr = 0.06 + 0.12 * abs(math.cos(a * 2.5)) ** 3
        verts.append((math.cos(a) * rr, math.sin(a) * rr, 0.0))
    for j in range(n):
        caras.append((0, 1 + j, 1 + (j + 1) % n))
    me = bpy.data.meshes.new(nombre)
    me.from_pydata(verts, [], caras)
    o = objeto(nombre, me)
    so = o.modifiers.new("G", 'SOLIDIFY')
    so.thickness = 0.02
    sb = o.modifiers.new("S", 'SUBSURF')
    sb.levels = 1
    aplicar(o)
    suave(o)
    pintar(o, lambda co, n: lineal("#e8532e") * (0.8 + 0.4 * noise.noise(co * 60)), VC_BRILLO)
    return o


def erizo(nombre="Erizo"):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.09, location=(0, 0, 0.06))
    partes = [bpy.context.object]
    r = random.Random(3)
    verts, aristas, radios = [], [], []
    for k in range(36):
        d = Vector((r.gauss(0, 1), r.gauss(0, 1), abs(r.gauss(0, 1)))).normalized()
        base = Vector((0, 0, 0.06)) + d * 0.08
        verts += [base, base + d * r.uniform(0.12, 0.2)]
        radios += [0.008, 0.002]
        aristas.append((len(verts) - 2, len(verts) - 1))
    me = bpy.data.meshes.new("Pinchos")
    me.from_pydata(verts, aristas, [])
    p = objeto("Pinchos", me)
    sk = p.modifiers.new("Skin", 'SKIN')
    for i, rr in enumerate(radios):
        p.data.skin_vertices[0].data[i].radius = (rr, rr)
        p.data.skin_vertices[0].data[i].use_root = (i % 2 == 0)
    aplicar(p)
    partes.append(p)
    o = unir(partes, nombre)
    pintar(o, lambda co, n: lineal("#2a1438"), VC_BRILLO)
    return o


# =====================================================================
# ---------- PECES (miran hacia -Y, un metro de largo; la web los escala) ----------
# =====================================================================
def pez(nombre, alto=0.28, ancho=0.1, cola="horquilla", aleta=0.12, color=None):
    secciones, puntos = 14, 12
    verts, caras = [], []
    for i in range(secciones + 1):
        t = i / secciones                    # 0 = boca, 1 = pedúnculo de la cola
        y = -0.5 + t * 0.78
        perfil = math.sin(math.pi * min(1.0, 0.1 + t * 0.95)) ** 0.8
        h = alto * perfil * (1 - 0.6 * t * t) + 0.02
        w = ancho * perfil + 0.008
        for j in range(puntos):
            a = j / puntos * math.tau
            verts.append((math.cos(a) * w, y, math.sin(a) * h * 0.5))
    for i in range(secciones):
        for j in range(puntos):
            a0 = i * puntos + j
            a1 = i * puntos + (j + 1) % puntos
            caras.append((a0, a1, a1 + puntos, a0 + puntos))
    boca = len(verts)
    verts.append((0, -0.52, 0))
    for j in range(puntos):
        caras.append((boca, (j + 1) % puntos, j))
    # Cola
    yc = 0.28
    hc = alto * 0.55
    if cola == "horquilla":
        cola_v = [(0, yc - 0.02, 0.01), (0, 0.5, hc), (0, 0.42, 0), (0, 0.5, -hc), (0, yc - 0.02, -0.01)]
    else:
        cola_v = [(0, yc - 0.02, 0.012), (0, 0.46, hc * 0.9), (0, 0.5, 0), (0, 0.46, -hc * 0.9), (0, yc - 0.02, -0.012)]
    i0 = len(verts)
    verts += cola_v
    caras += [(i0, i0 + 1, i0 + 2), (i0, i0 + 2, i0 + 4), (i0 + 4, i0 + 2, i0 + 3)]
    # Aleta dorsal y anal
    i0 = len(verts)
    verts += [(0, -0.2, alto * 0.45), (0, 0.0, alto * 0.5 + aleta), (0, 0.25, alto * 0.25),
              (0, -0.05, -alto * 0.45), (0, 0.12, -alto * 0.42 - aleta * 0.6), (0, 0.26, -alto * 0.22)]
    caras += [(i0, i0 + 1, i0 + 2), (i0 + 3, i0 + 5, i0 + 4)]
    me = bpy.data.meshes.new(nombre)
    me.from_pydata(verts, [], caras)
    o = objeto(nombre, me)
    suave(o)
    ojo_y = -0.36
    blanco, negro = Vector((0.9, 0.9, 0.9)), Vector((0.01, 0.01, 0.01))

    def pintura(co, n):
        # ojo
        if abs(co.y - ojo_y) < 0.035 and abs(co.z - alto * 0.12) < 0.035 and abs(co.x) > 0.3 * ancho:
            return negro
        c = color(co) if color else Vector((1, 1, 1)) * (0.75 + 0.25 * (co.z / alto + 0.5))
        vientre = max(0.0, -co.z / (alto * 0.5))
        return mezclar(c, c * 0.6 + Vector((0.4, 0.4, 0.4)), vientre * 0.5)
    pintar(o, pintura, VC_BRILLO)
    return o


def color_payaso(co):
    naranja, blanco, negro = lineal("#ff6a13"), lineal("#ffffff"), lineal("#111111")
    for yb in (-0.3, 0.0, 0.26):
        d = abs(co.y - yb)
        if d < 0.045:
            return blanco
        if d < 0.06:
            return negro
    if co.y > 0.42:
        return negro
    return naranja


def color_angel(co):
    azul, amarillo = lineal("#1b4fd1"), lineal("#ffd21f")
    franja = math.sin(co.y * 40 + co.z * 18)
    return amarillo if franja > 0.35 else azul


def color_mariposa(co):
    blanco, amarillo, negro = lineal("#fbfbf5"), lineal("#ffd400"), lineal("#141414")
    if abs(co.y + 0.34) < 0.04:
        return negro  # banda del ojo
    if co.y > 0.1 or abs(co.z) > 0.12:
        return amarillo
    return blanco


def color_loro(co):
    verde, turquesa, rosa = lineal("#2fc0a0"), lineal("#2a8ad8"), lineal("#ff7fb0")
    c = mezclar(verde, turquesa, 0.5 + 0.5 * math.sin(co.y * 12))
    if co.y > 0.3 or abs(co.z) > 0.13:
        c = mezclar(c, rosa, 0.7)
    return c


# =====================================================================
# ---------- TORTUGA, COFRE Y BARCA ----------
# =====================================================================
def tortuga(nombre="Tortuga"):
    partes = []
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=1.0)
    capa = bpy.context.object
    for v in capa.data.vertices:
        v.co.x *= 0.42
        v.co.y *= 0.55
        v.co.z = v.co.z * (0.2 if v.co.z > 0 else 0.07)
    partes.append(capa)
    cab = bpy.context.object
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=10, radius=0.1, location=(0, -0.66, 0.02))
    cab = bpy.context.object
    cab.scale = (1, 1.4, 0.85)
    bpy.ops.object.transform_apply(scale=True)
    partes.append(cab)
    for sx in (1, -1):
        for (y, largo, ancho, ang) in ((-0.3, 0.55, 0.14, 0.5), (0.4, 0.25, 0.1, -0.5)):
            bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=1.0, location=(sx * (0.38 + largo * 0.45), y, -0.02))
            a = bpy.context.object
            a.scale = (largo * 0.5, ancho, 0.025)
            a.rotation_euler = (0, 0, -sx * ang)
            bpy.ops.object.transform_apply(scale=True, rotation=True)
            partes.append(a)
    o = unir(partes, nombre)
    suave(o)
    placa, borde = lineal("#6b4a2a"), lineal("#3a2a18")
    piel = lineal("#9aa860")

    def color(co, n):
        if abs(co.x) < 0.44 and abs(co.y) < 0.56 and co.z > 0.02:
            c = noise.cell(co * 7) if hasattr(noise, "cell") else 0.5
            return mezclar(placa, borde, abs(math.sin(c * 9))) * (0.8 + 0.4 * co.z / 0.2)
        manchas = 0.5 + 0.5 * noise.noise(co * 30)
        return mezclar(piel, piel * 0.45, manchas * 0.6)
    pintar(o, color, VC_BRILLO)
    return o


def cofre():
    madera, oro, oscuro = lineal("#7a4a24"), lineal("#e2b33c"), lineal("#3b2412")
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.2))
    caja = bpy.context.object
    caja.scale = (0.7, 0.45, 0.4)
    bpy.ops.object.transform_apply(scale=True)
    bev = caja.modifiers.new("B", 'BEVEL')
    bev.width = 0.02
    bev.segments = 2
    aplicar(caja)
    monedas = []
    r = random.Random(4)
    for k in range(40):
        bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=0.035, depth=0.01,
                                            location=(r.uniform(-0.3, 0.3), r.uniform(-0.18, 0.18), 0.4 + r.uniform(0, 0.06)),
                                            rotation=(r.uniform(-0.5, 0.5), r.uniform(-0.5, 0.5), 0))
        monedas.append(bpy.context.object)
    body = unir([caja] + monedas, "Cofre")
    pintar(body, lambda co, n: oro if co.z > 0.41 or abs(co.x) > 0.3 or abs(abs(co.x) - 0.15) < 0.03 else (madera if n.z < 0.9 else oscuro), VC_BRILLO)
    # Tapa (medio cilindro) con la bisagra en el origen (borde de atrás, arriba)
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.225, depth=0.7, location=(0, 0.225, 0), rotation=(0, math.pi / 2, 0))
    tapa = bpy.context.object
    bm = bmesh.new()
    bm.from_mesh(tapa.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -0.001 and False], context='VERTS')
    bm.to_mesh(tapa.data)
    bm.free()
    bpy.ops.object.transform_apply(location=True, rotation=True)
    for v in tapa.data.vertices:
        v.co.z = max(v.co.z, 0.0)
        v.co.y -= 0.45
    tapa.name = "CofreTapa"
    tapa.data.name = "CofreTapa"
    pintar(tapa, lambda co, n: oro if abs(co.x) > 0.3 or abs(abs(co.x) - 0.15) < 0.03 else madera, VC_BRILLO)
    return body, tapa


def barca(nombre="Barca"):
    """Barca de madera pintada: blanca con una franja azul, fondo rojo y el interior de madera."""
    estaciones, perfil = 24, 13
    L, B, H = 4.4, 1.7, 0.8
    verts, caras = [], []
    for i in range(estaciones + 1):
        t = i / estaciones             # 0 = popa (+Y), 1 = proa (-Y)
        y = L / 2 - t * L
        manga = B / 2 * (math.sin(math.pi * (0.35 + 0.65 * (1 - t))) if t > 0.55 else 1.0) * (0.92 + 0.08 * math.sin(math.pi * t))
        manga = max(manga, 0.03)
        arrufo = H + 0.25 * max(0.0, t - 0.6) ** 2 * 6
        for j in range(perfil):
            s = j / (perfil - 1) * 2 - 1       # -1 = babor, 1 = estribor
            x = s * manga
            z = arrufo - (H * (1 - abs(s) ** 2.2)) - 0.15 * (1 - abs(s))
            verts.append((x, y, z * (0.6 + 0.4 * (1 - max(0.0, t - 0.7) * 2)) + 0.0))
    for i in range(estaciones):
        for j in range(perfil - 1):
            a = i * perfil + j
            caras.append((a, a + perfil, a + perfil + 1, a + 1))
    # Espejo de popa
    popa = list(range(perfil))
    caras.append(tuple(reversed(popa)))
    me = bpy.data.meshes.new(nombre)
    me.from_pydata(verts, [], caras)
    casco = objeto(nombre, me)
    so = casco.modifiers.new("Grosor", 'SOLIDIFY')
    so.thickness = 0.05
    sb = casco.modifiers.new("Sub", 'SUBSURF')
    sb.levels = 1
    aplicar(casco)
    suave(casco)
    partes = [casco]
    # Bancos, borda y motor
    for y in (0.9, -0.3):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, y, H * 0.62))
        b = bpy.context.object
        b.scale = (B * 0.86, 0.3, 0.05)
        bpy.ops.object.transform_apply(scale=True)
        partes.append(b)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, L / 2 + 0.12, H + 0.1))
    motor = bpy.context.object
    motor.scale = (0.28, 0.35, 0.4)
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=0.05, depth=0.9, location=(0, L / 2 + 0.2, H - 0.45))
    eje = bpy.context.object
    partes += [motor, eje]
    # Bandera de buceo (azul y blanca) en un mástil pequeño
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.02, depth=1.2, location=(0.6, L / 2 - 0.3, H + 0.55))
    partes.append(bpy.context.object)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0.78, L / 2 - 0.3, H + 1.0))
    band = bpy.context.object
    band.scale = (0.36, 0.01, 0.24)
    bpy.ops.object.transform_apply(scale=True)
    partes.append(band)
    # Escalerilla para bajar al agua
    for z in (0.2, 0.45, 0.7):
        bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.02, depth=0.4, location=(B / 2 + 0.05, 0.5, z - 0.1), rotation=(0, 0, math.pi / 2))
        partes.append(bpy.context.object)
    o = unir(partes, nombre)
    blanco, azul, rojo, madera = lineal("#f4f1ea"), lineal("#1f6fb5"), lineal("#b8322a"), lineal("#a8743f")
    gris = lineal("#5b6168")

    def color(co, n):
        if co.y > L / 2 + 0.05 and co.z > 0.2:
            return gris  # motor
        if co.x > 0.62 and co.z > H + 0.8:
            return blanco if co.x < 0.78 else azul  # bandera
        dentro = abs(co.x) < (B / 2) * 0.93 and co.z > 0.12 and (n.x * co.x < 0 or n.z > 0.7)
        if dentro or abs(co.z - H * 0.62) < 0.04:
            return madera * (0.85 + 0.3 * noise.noise(Vector((co.x * 2, co.y * 30, 0))))
        if co.z < 0.18:
            return rojo
        if co.z > H - 0.12 and co.z < H + 0.02:
            return azul
        return blanco
    pintar(o, color, VC_BRILLO)
    return o


def barco_pirata(nombre="BarcoPirata"):
    """Barco pirata grande, hundido y viejo: casco de madera oscura con algas, castillo de popa, mástiles rotos y cañones."""
    estaciones, perfil = 30, 15
    L, B, H = 13.0, 4.2, 3.2
    verts, caras = [], []
    for i in range(estaciones + 1):
        t = i / estaciones             # 0 = popa (+Y), 1 = proa (-Y)
        y = L / 2 - t * L
        manga = B / 2 * (math.sin(math.pi * (0.3 + 0.7 * (1 - t))) if t > 0.6 else 1.0) * (0.9 + 0.1 * math.sin(math.pi * t))
        manga = max(manga, 0.05)
        arrufo = H + 0.6 * max(0.0, t - 0.7) ** 2 * 10 + 0.5 * max(0.0, 0.2 - t) * 5
        for j in range(perfil):
            s = j / (perfil - 1) * 2 - 1
            z = arrufo - H * (1 - abs(s) ** 1.6) - 0.3 * (1 - abs(s))
            verts.append((s * manga, y, z))
    for i in range(estaciones):
        for j in range(perfil - 1):
            a = i * perfil + j
            caras.append((a, a + perfil, a + perfil + 1, a + 1))
    caras.append(tuple(reversed(range(perfil))))
    me = bpy.data.meshes.new(nombre)
    me.from_pydata(verts, [], caras)
    casco = objeto(nombre, me)
    so = casco.modifiers.new("Grosor", 'SOLIDIFY')
    so.thickness = 0.14
    aplicar(casco)
    suave(casco)
    partes = [casco]

    def caja(loc, esc, rot=(0, 0, 0)):
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
        c = bpy.context.object
        c.scale = esc
        bpy.ops.object.transform_apply(scale=True, rotation=True)
        partes.append(c)
        return c

    def cilindro(loc, r, largo, rot=(0, 0, 0), v=12):
        bpy.ops.mesh.primitive_cylinder_add(vertices=v, radius=r, depth=largo, location=loc, rotation=rot)
        c = bpy.context.object
        bpy.ops.object.transform_apply(rotation=True)
        partes.append(c)
        return c

    caja((0, 0.3, H * 0.74), (B * 0.86, L * 0.78, 0.12))              # cubierta
    caja((0, L / 2 - 1.5, H * 0.74 + 0.9), (B * 0.82, 2.8, 1.8))       # castillo de popa
    caja((0, L / 2 - 1.5, H * 0.74 + 1.85), (B * 0.9, 3.0, 0.12))      # techo del castillo
    cilindro((0.4, -1.2, H + 2.2), 0.2, 6.0, rot=(0.35, 0.3, 0))        # mástil roto e inclinado
    cilindro((0.9, -1.9, H + 3.6), 0.09, 3.6, rot=(0.35, 1.3, 0))       # verga
    cilindro((0, 3.0, H + 0.8), 0.18, 1.8)                              # mástil partido
    cilindro((0, -L / 2 - 0.6, H + 0.4), 0.1, 2.6, rot=(1.1, 0, 0))    # bauprés
    for sx in (1, -1):
        for k in range(4):
            y = -3.2 + k * 1.8
            cilindro((sx * (B / 2 * 0.95), y, H * 0.86), 0.13, 1.1, rot=(0, math.pi / 2, 0))
    # Timón del barco
    bpy.ops.mesh.primitive_torus_add(major_radius=0.45, minor_radius=0.05, location=(0, L / 2 - 3.2, H * 0.74 + 0.9), rotation=(math.pi / 2, 0, 0))
    partes.append(bpy.context.object)
    o = unir(partes, nombre)
    madera, oscura = lineal("#6b4a2c"), lineal("#3a2616")
    alga, negro = lineal("#56733c"), lineal("#1a1a1a")

    def color(co, n):
        if abs(abs(co.x) - B / 2 * 0.95) < 0.6 and abs(co.z - H * 0.86) < 0.16 and abs(co.y + 0.5) < 3.4:
            return negro  # cañones
        tabla = 0.5 + 0.5 * math.sin(co.z * 9 + 0.3 * math.sin(co.y))
        c = mezclar(madera, oscura, 0.35 * tabla + 0.3 * (0.5 + 0.5 * noise.noise(co * 0.8)))
        if n.z > 0.5:
            c = mezclar(c, alga, 0.55 * (0.5 + 0.5 * noise.noise(co * 1.3)))
        return c
    pintar(o, color, VC_BRILLO)
    return o


def cueva(nombre="Cueva"):
    """Gran roca con un túnel y agujeros: la cueva de las morenas."""
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=5, radius=1.0)
    o = bpy.context.object
    o.name = nombre
    off = Vector((4.4, 1.3, 0))
    for v in o.data.vertices:
        p = v.co.copy()
        p += p * (0.22 * noise.noise(p * 1.5 + off) + 0.08 * noise.noise(p * 4.5 + off))
        p.x *= 4.2
        p.y *= 3.0
        p.z *= 2.6
        if p.z < -0.3:
            p.z = -0.3 + (p.z + 0.3) * 0.1
        v.co = p
    # Túnel de lado a lado y agujeros para las morenas
    huecos = []
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=1.25, depth=10, location=(0, 0, 0.9), rotation=(0, math.pi / 2, 0))
    huecos.append(bpy.context.object)
    for (x, y, z) in ((-1.8, -2.2, 1.6), (1.6, -2.3, 1.2), (0.2, -2.0, 2.3), (2.2, 2.2, 1.4)):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.42, location=(x, y, z))
        huecos.append(bpy.context.object)
    for h in huecos:
        b = o.modifiers.new("Hueco", 'BOOLEAN')
        b.operation = 'DIFFERENCE'
        b.object = h
        b.solver = 'EXACT'
        activar(o)
        bpy.ops.object.modifier_apply(modifier=b.name)
        bpy.data.objects.remove(h)
    suave(o)
    gris, marron = lineal("#857d6c"), lineal("#5d4d3c")
    rosa, lila, verde = lineal("#d77a9b"), lineal("#8a6fc4"), lineal("#6f9a4a")

    def color(co, n):
        c = mezclar(gris, marron, 0.5 + 0.5 * noise.noise(co * 0.9 + off))
        m = noise.noise(co * 1.6 + off + Vector((5, 0, 0)))
        if m > 0.2:
            c = mezclar(c, rosa, min(0.5, (m - 0.2) * 2))
        elif m < -0.3:
            c = mezclar(c, lila, min(0.4, (-m - 0.3) * 2))
        if n.z > 0.6:
            c = mezclar(c, verde, 0.4)
        # dentro del túnel, más oscuro
        if abs(co.y) < 2.6 and co.z < 2.2 and math.hypot(co.y, co.z - 0.9) < 1.5:
            c = c * 0.35
        return c
    pintar(o, color)
    return o


def morena(nombre="Morena"):
    """Morena: cuerpo largo y ondulado (mira hacia -Y), boca abierta y manchas."""
    verts, aristas, radios = [], [], []
    n = 14
    for i in range(n):
        t = i / (n - 1)
        verts.append(Vector((0, -0.8 + t * 1.8, 0)))
        radios.append(0.085 * (1 - 0.65 * t) * (0.75 + 0.25 * math.sin(math.pi * min(1.0, t * 4 + 0.2))))
        if i:
            aristas.append((i - 1, i))
    o = arbol_skin(nombre, verts, aristas, radios)
    for v in o.data.vertices:  # cabeza un poco más alta, cuerpo aplanado de lado
        v.co.x *= 0.8
        if v.co.y < -0.6:
            v.co.z *= 1.15
    partes = [o]
    for sx in (1, -1):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=10, ring_count=6, radius=0.018, location=(sx * 0.05, -0.74, 0.04))
        partes.append(bpy.context.object)
    o = unir(partes, nombre)
    verde, oscuro, amarillo = lineal("#7a8f2a"), lineal("#2a3312"), lineal("#d8d060")

    def color(co, n):
        if co.y < -0.72 and abs(co.x) > 0.035 and co.z > 0.02:
            return lineal("#101010")  # ojos
        if co.y < -0.78 and abs(co.z) < 0.012:
            return lineal("#3a0e0e")  # boca
        manchas = noise.noise(co * 22)
        return mezclar(verde, oscuro, 0.6 if manchas > 0.2 else 0.0) + (amarillo * 0.25 if co.z < -0.03 else Vector((0, 0, 0)))
    pintar(o, color, VC_BRILLO)
    return o


def aleta_plana(puntos, grosor=0.012):
    """Aleta: un polígono plano (lista de vértices 3D) con un poco de grosor."""
    me = bpy.data.meshes.new("Aleta")
    me.from_pydata(puntos, [], [tuple(range(len(puntos)))])
    o = objeto("Aleta", me)
    so = o.modifiers.new("G", 'SOLIDIFY')
    so.thickness = grosor
    so.offset = 0
    aplicar(o)
    return o


def cuerpo_loft(nombre, largo, alto_fn, ancho_fn, secciones=28, puntos=16, y0=-0.5):
    """Cuerpo alargado que mira hacia -Y: secciones elípticas de boca a cola."""
    verts, caras = [], []
    for i in range(secciones + 1):
        t = i / secciones
        y = y0 + t * largo
        h, w = alto_fn(t), ancho_fn(t)
        for j in range(puntos):
            a = j / puntos * math.tau
            verts.append((math.cos(a) * w, y, math.sin(a) * h))
    for i in range(secciones):
        for j in range(puntos):
            a0 = i * puntos + j
            a1 = i * puntos + (j + 1) % puntos
            caras.append((a0, a1, a1 + puntos, a0 + puntos))
    for extremo, yy in ((0, y0 - 0.005), (secciones, y0 + largo + 0.005)):
        c = len(verts)
        verts.append((0, yy, 0))
        base = extremo * puntos
        for j in range(puntos):
            if extremo == 0:
                caras.append((c, base + (j + 1) % puntos, base + j))
            else:
                caras.append((c, base + j, base + (j + 1) % puntos))
    me = bpy.data.meshes.new(nombre)
    me.from_pydata(verts, [], caras)
    o = objeto(nombre, me)
    suave(o)
    return o


def tiburon(nombre="Tiburon"):
    """Tiburón de puntas negras (mide 1 de largo, mira hacia -Y)."""
    perfil = lambda t: math.sin(math.pi * min(1.0, 0.06 + t * 1.05)) ** 0.7
    cuerpo = cuerpo_loft(nombre, 0.86, lambda t: 0.095 * perfil(t) * (1 - 0.6 * t) + 0.006,
                         lambda t: 0.08 * perfil(t) * (1 - 0.65 * t) + 0.005, y0=-0.5)
    for v in cuerpo.data.vertices:  # hocico aplastado y un poco hacia arriba
        if v.co.y < -0.35:
            v.co.z *= 0.8
            v.co.z += 0.01
    partes = [cuerpo]
    partes.append(aleta_plana([(0, -0.1, 0.07), (0, 0.04, 0.18), (0, 0.075, 0.175), (0, 0.06, 0.12), (0, 0.1, 0.07)]))  # dorsal
    partes.append(aleta_plana([(0, 0.2, 0.04), (0, 0.25, 0.08), (0, 0.27, 0.03)]))                           # segunda dorsal
    for sx in (1, -1):                                                                                       # pectorales
        partes.append(aleta_plana([(sx * 0.05, -0.18, -0.035), (sx * 0.16, -0.03, -0.1), (sx * 0.13, -0.01, -0.095), (sx * 0.05, -0.08, -0.045)]))
    partes.append(aleta_plana([(0, 0.33, 0.012), (0, 0.5, 0.16), (0, 0.47, 0.02), (0, 0.45, -0.08), (0, 0.33, -0.012)]))  # cola, con el lóbulo de arriba más largo
    o = unir(partes, nombre)
    gris, blanco, negro = lineal("#6f7f8c"), lineal("#eef1f2"), lineal("#141414")

    def color(co, n):
        if abs(co.y + 0.37) < 0.02 and co.z > 0.0 and abs(co.x) > 0.02:
            return negro  # ojos
        punta = (co.z > 0.155) or (abs(co.x) > 0.13) or (co.y > 0.46 and co.z > 0.11) or (co.y > 0.43 and co.z < -0.06)
        if punta:
            return negro  # puntas negras de las aletas
        return mezclar(gris, blanco, max(0.0, min(1.0, 0.5 - co.z * 25)))
    pintar(o, color, VC_BRILLO)
    return o


def delfin(nombre="Delfin"):
    """Delfín mular (mide 1 de largo, mira hacia -Y), con su pico, la frente redonda y la cola horizontal."""
    def cuerpo_d(t):
        return 0.075 * math.sin(math.pi * min(1.0, 0.25 + (t - 0.18) * 0.95)) ** 0.8 + 0.006

    def alto(t):
        if t < 0.08:
            return 0.016 + 0.1 * t        # pico
        if t < 0.18:
            k = (t - 0.08) / 0.1           # frente redonda (melón) que se une suave con el cuerpo
            return 0.024 + (cuerpo_d(0.18) - 0.024) * math.sin(k * math.pi / 2)
        return cuerpo_d(t)

    def ancho(t):
        return alto(t) * 0.75
    cuerpo = cuerpo_loft(nombre, 0.9, alto, ancho, secciones=36, y0=-0.5)
    partes = [cuerpo]
    partes.append(aleta_plana([(0, -0.02, 0.06), (0, 0.1, 0.15), (0, 0.13, 0.145), (0, 0.11, 0.1), (0, 0.15, 0.055)]))  # aleta dorsal curvada
    for sx in (1, -1):
        partes.append(aleta_plana([(sx * 0.045, -0.2, -0.035), (sx * 0.11, -0.1, -0.08), (sx * 0.09, -0.08, -0.075), (sx * 0.045, -0.14, -0.04)]))
    partes.append(aleta_plana([(0, 0.37, 0.0), (-0.08, 0.43, 0.0), (-0.16, 0.5, 0.0), (-0.08, 0.48, 0.0), (0, 0.45, 0.0), (0.08, 0.48, 0.0), (0.16, 0.5, 0.0), (0.08, 0.43, 0.0)]))  # cola horizontal
    o = unir(partes, nombre)
    gris, claro, negro = lineal("#6d8196"), lineal("#dfe5ea"), lineal("#141414")

    def color(co, n):
        if abs(co.y + 0.36) < 0.015 and abs(co.x) > 0.03 and abs(co.z) < 0.02:
            return negro  # ojos
        return mezclar(gris, claro, max(0.0, min(1.0, 0.45 - co.z * 16)))
    pintar(o, color, VC_BRILLO)
    return o


# =====================================================================
# ---------- CREAR TODAS LAS PIEZAS ----------
# =====================================================================
proto = []
proto.append(coral_cerebro("Cerebro"))
proto.append(coral_ramas("Cuerno", 11, niveles=3, largo=0.55, radio=0.07, abrir=0.9, hijos=2, base=3))
proto.append(coral_ramas("Arbusto", 12, niveles=3, largo=0.3, radio=0.05, abrir=1.2, hijos=2, subir=0.4, base=6))
proto.append(coral_dedos("Dedos"))
proto.append(coral_mesa("Mesa", pisos=1))
proto.append(coral_mesa("Mesa2", R=0.75, pisos=2, semilla=5))
proto.append(gorgonia("Gorgonia"))
proto.append(esponjas("Tubos"))
proto.append(coliflor("Coliflor"))
proto.append(anemona("Anemona"))
proto.append(hierba("Hierba"))
proto.append(roca("Roca1", 1))
proto.append(roca("Roca2", 2, (1.2, 1.4, 0.9)))
proto.append(roca("Roca3", 3, (2.2, 1.0, 0.6)))
proto.append(estrella())
proto.append(erizo())
proto.append(pez("PezPequeno", alto=0.26, ancho=0.09, cola="horquilla", aleta=0.08))
proto.append(pez("PezPayaso", alto=0.32, ancho=0.12, cola="redonda", aleta=0.1, color=color_payaso))
proto.append(pez("PezCirujano", alto=0.62, ancho=0.08, cola="redonda", aleta=0.14))
proto.append(pez("PezAngel", alto=0.7, ancho=0.07, cola="redonda", aleta=0.3, color=color_angel))
proto.append(pez("PezMariposa", alto=0.62, ancho=0.07, cola="redonda", aleta=0.16, color=color_mariposa))
proto.append(pez("PezLoro", alto=0.34, ancho=0.13, cola="horquilla", aleta=0.08, color=color_loro))
proto.append(tortuga())
proto += list(cofre())
proto.append(barca())
proto.append(barco_pirata())
proto.append(cueva())
proto.append(morena())
proto.append(tiburon())
proto.append(delfin())
for o in proto:
    o.location = (0, 0, 0)
    print(f"{o.name}: {len(o.data.polygons)} caras")


# =====================================================================
# ---------- EXPORTAR ----------
# =====================================================================
bpy.ops.object.select_all(action='DESELECT')
for o in proto:
    o.select_set(True)
bpy.context.view_layer.objects.active = proto[0]
bpy.ops.export_scene.gltf(filepath=os.path.abspath("arrecife.glb"), export_format='GLB', use_selection=True, export_apply=True)
print("Exportado arrecife.glb")

if os.environ.get("RENDER", "1") == "0":
    raise SystemExit


# =====================================================================
# ---------- ESCENA SUBMARINA PARA EL RENDER ----------
# =====================================================================
for o in proto:
    o.hide_render = True
    o.hide_viewport = True


def material_tinte(nombre, rug=0.6):
    """Color de los vértices por el color del objeto (para teñir cada copia en el render)."""
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    vc = nt.nodes.new("ShaderNodeVertexColor")
    vc.layer_name = "Col"
    info = nt.nodes.new("ShaderNodeObjectInfo")
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type = 'RGBA'
    mul.blend_type = 'MULTIPLY'
    mul.inputs["Factor"].default_value = 1.0
    nt.links.new(vc.outputs["Color"], mul.inputs[6])
    nt.links.new(info.outputs["Color"], mul.inputs[7])
    nt.links.new(mul.outputs[2], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = rug
    # un poco de brillo propio, como los corales fluorescentes
    bsdf.inputs["Emission Color"].default_value = (1, 1, 1, 1)
    nt.links.new(mul.outputs[2], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = 0.08
    bsdf.inputs["Subsurface Weight"].default_value = 0.15
    return m


TINTE = material_tinte("Tinte")
por_nombre = {o.name: o for o in proto}


def copia(nombre, loc, rot_z=0.0, esc=1.0, color="#ffffff", inclinar=0.0):
    src = por_nombre[nombre]
    o = bpy.data.objects.new(nombre + "_c", src.data)
    bpy.context.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (inclinar * rnd.uniform(-1, 1), inclinar * rnd.uniform(-1, 1), rot_z)
    o.scale = (esc, esc, esc)
    o.color = (*lineal(color), 1)
    o.material_slots[0].link = 'OBJECT'
    o.material_slots[0].material = TINTE
    return o


def lecho(x, y):
    h = -9.0 + 0.4 * noise.noise(Vector((x * 0.1, y * 0.1, 0.3))) + 0.06 * math.sin(x * 2.2 + y * 0.5)
    # montículos del arrecife delante de la cámara
    for (cx, cy, r, alto) in ((0, 7, 6, 4.0), (-6, 9, 5, 3.6), (7, 10, 6, 4.4), (2, 16, 9, 5.5), (-12, 18, 8, 4.0),
                              (14, 22, 9, 5.0), (-3, 30, 12, 4.5)):
        d = math.hypot(x - cx, y - cy) / r
        h += alto * math.exp(-d * d * 2)
    return h


# Fondo de arena
n = 120
verts, caras = [], []
for i in range(n + 1):
    for j in range(n + 1):
        x, y = -40 + 80 * i / n, -20 + 80 * j / n
        verts.append((x, y, lecho(x, y)))
for i in range(n):
    for j in range(n):
        a = i * (n + 1) + j
        caras.append((a, a + n + 1, a + n + 2, a + 1))
me = bpy.data.meshes.new("Lecho")
me.from_pydata(verts, [], caras)
fondo = objeto("Lecho", me)
suave(fondo)
arena_c, arena_o = lineal("#e8d9b4"), lineal("#b3a27c")
pintar(fondo, lambda co, nn: mezclar(arena_c, arena_o, 0.5 + 0.5 * noise.noise(co * 0.5)))
fondo.material_slots[0].link = 'OBJECT'
fondo.material_slots[0].material = TINTE

# Corales repartidos por los montículos (colores como en la foto)
PALETA = {
    "Cerebro": ["#e8c25a", "#d9a24a", "#9fcf6a"],
    "Cuerno": ["#e9c49a", "#c8a0e0", "#f0b87a"],
    "Arbusto": ["#4a7df0", "#6a8cff", "#8e6ce8"],
    "Dedos": ["#f0a060", "#e8d070", "#f2c9a0"],
    "Mesa": ["#d9b27a", "#e8cf8a", "#b9d08a"],
    "Mesa2": ["#e0b07a", "#f0d090"],
    "Gorgonia": ["#c43c9a", "#e0503c", "#9a3cc8", "#ff8a3c"],
    "Tubos": ["#8a4ad8", "#e85a8a", "#ff8a3c"],
    "Coliflor": ["#ff8fb0", "#f07aa0", "#ffb0c0"],
    "Anemona": ["#c9a0ff", "#9ae070", "#ff90c8"],
    "Hierba": ["#ffffff"],
}
tipos = list(PALETA.keys())
peso = {"Cerebro": 3, "Cuerno": 3, "Arbusto": 3, "Dedos": 2, "Mesa": 2, "Mesa2": 1, "Gorgonia": 2, "Tubos": 2,
        "Coliflor": 3, "Anemona": 1, "Hierba": 1}
bolsa = [t for t in tipos for _ in range(peso[t])]
colocados = 0
for k in range(9000):
    x, y = rnd.uniform(-24, 24), rnd.uniform(1, 40)
    z = lecho(x, y)
    if z < -8.2 or rnd.random() > 0.25 + 0.75 * min(1.0, (z + 8.2) / 2.5):
        continue
    if colocados > 2200:
        break
    t = rnd.choice(bolsa)
    esc = rnd.uniform(1.0, 2.0) * (1.3 if t == "Gorgonia" else 0.8 if t in ("Mesa", "Mesa2") else 1)
    copia(t, (x, y, z - 0.05), rnd.uniform(0, math.tau), esc, rnd.choice(PALETA[t]), 0.15)
    colocados += 1
for k in range(90):
    x, y = rnd.uniform(-22, 22), rnd.uniform(3, 38)
    if lecho(x, y) < -8:
        continue
    copia(rnd.choice(["Roca1", "Roca2", "Roca3"]), (x, y, lecho(x, y) - 0.5), rnd.uniform(0, math.tau), rnd.uniform(1.0, 2.2))
print("corales:", colocados)

# Peces: nubes de anthias naranjas y moradas y otros peces de colores
def banco(nombre, n, centro, radio, colores, esc):
    for k in range(n):
        p = Vector(centro) + Vector((rnd.gauss(0, radio[0]), rnd.gauss(0, radio[1]), rnd.gauss(0, radio[2])))
        if p.z < lecho(p.x, p.y) + 0.5:
            p.z = lecho(p.x, p.y) + 0.5 + rnd.random()
        rumbo = rnd.gauss(0.6, 0.5)
        copia(nombre, p, rumbo, esc * rnd.uniform(0.8, 1.2), rnd.choice(colores))


banco("PezPequeno", 1400, (-3, 12, -3.0), (9, 7, 1.6), ["#ff7a2f", "#ff8f3a", "#ff6a28", "#b35cf0", "#d05ae8", "#ff5a8a"], 0.2)
banco("PezPequeno", 500, (0, 5, -3.6), (4, 3, 1.0), ["#ff7a2f", "#ff8f3a", "#ff6a28", "#b35cf0", "#d05ae8"], 0.24)
banco("PezPequeno", 700, (8, 26, -1.5), (14, 9, 1.4), ["#8fd6ff", "#5ab0e8", "#ff8f3a", "#2c4870", "#2c4870"], 0.18)
banco("PezCirujano", 25, (2, 12, -4), (6, 5, 1), ["#ffd21f"], 0.25)
banco("PezMariposa", 12, (-2, 10, -4.5), (5, 4, 1), ["#ffffff"], 0.2)
banco("PezAngel", 6, (4, 10, -4), (5, 4, 1), ["#ffffff"], 0.3)
banco("PezLoro", 8, (0, 14, -4.5), (7, 5, 1), ["#ffffff"], 0.45)
banco("PezPayaso", 6, (-3, 7, -5.2), (1.5, 1, 0.3), ["#ffffff"], 0.13)
copia("Tortuga", (-6, 20, -2.2), 0.9, 1.0, "#ffffff")

# Luz: sol entrando desde arriba, con rayos a través del agua
bpy.ops.object.light_add(type='SUN', location=(0, 0, 20), rotation=(math.radians(12), math.radians(-8), 0))
sol = bpy.context.object
sol.data.energy = 11.0
sol.data.color = (1.0, 0.97, 0.9)
sol.data.angle = math.radians(1.0)
# Superficie con "agujeros" que corta la luz en rayos (no se ve desde la cámara)
bpy.ops.mesh.primitive_plane_add(size=120, location=(0, 20, 0.0))
sup = bpy.context.object
ms = bpy.data.materials.new("Rayos")
ms.use_nodes = True
nt = ms.node_tree
nt.nodes.clear()
out = nt.nodes.new("ShaderNodeOutputMaterial")
tr = nt.nodes.new("ShaderNodeBsdfTransparent")
ho = nt.nodes.new("ShaderNodeBsdfDiffuse")
ho.inputs["Color"].default_value = (0, 0, 0, 1)
mx = nt.nodes.new("ShaderNodeMixShader")
tex = nt.nodes.new("ShaderNodeTexVoronoi")
tex.inputs["Scale"].default_value = 0.9
tex.feature = 'DISTANCE_TO_EDGE'
rampa = nt.nodes.new("ShaderNodeValToRGB")
rampa.color_ramp.elements[0].position = 0.05
rampa.color_ramp.elements[1].position = 0.12
nt.links.new(tex.outputs["Distance"], rampa.inputs["Fac"])
nt.links.new(rampa.outputs["Color"], mx.inputs["Fac"])
nt.links.new(tr.outputs[0], mx.inputs[1])
nt.links.new(ho.outputs[0], mx.inputs[2])
nt.links.new(mx.outputs[0], out.inputs["Surface"])
# al revés: la luz pasa por las líneas finas (como las cáusticas) y el resto la tapa a medias
rampa.color_ramp.elements[0].color = (0, 0, 0, 1)
rampa.color_ramp.elements[1].color = (0.8, 0.8, 0.8, 1)
sup.data.materials.append(ms)
sup.visible_camera = False
# Superficie que se ve desde abajo: brillante y ondulada
bpy.ops.mesh.primitive_plane_add(size=160, location=(0, 30, 0.05))
vista = bpy.context.object
sb = vista.modifiers.new("Sub", 'SUBSURF')
sb.subdivision_type = 'SIMPLE'
sb.levels = 6
sb.render_levels = 6
dsp = vista.modifiers.new("Olas", 'DISPLACE')
tx = bpy.data.textures.new("OlasTex", 'CLOUDS')
tx.noise_scale = 1.5
dsp.texture = tx
dsp.strength = 0.4
mv = bpy.data.materials.new("SuperficieVista")
mv.use_nodes = True
b = mv.node_tree.nodes["Principled BSDF"]
b.inputs["Base Color"].default_value = (0.5, 0.9, 1.0, 1)
b.inputs["Emission Color"].default_value = (0.6, 0.95, 1.0, 1)
b.inputs["Emission Strength"].default_value = 0.9
b.inputs["Roughness"].default_value = 0.1
vista.data.materials.append(mv)
vista.visible_shadow = False

# Agua: volumen azul que da la profundidad y deja ver los rayos de sol
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 20, -5))
vol = bpy.context.object
vol.scale = (120, 120, 10)
mvol = bpy.data.materials.new("Agua")
mvol.use_nodes = True
nt = mvol.node_tree
nt.nodes.remove(nt.nodes["Principled BSDF"])
pv = nt.nodes.new("ShaderNodeVolumePrincipled")
pv.inputs["Color"].default_value = (0.0, 0.35, 0.8, 1)
pv.inputs["Density"].default_value = 0.04
pv.inputs["Anisotropy"].default_value = 0.8
pv.inputs["Absorption Color"].default_value = (0.05, 0.45, 0.75, 1)
nt.links.new(pv.outputs[0], nt.nodes["Material Output"].inputs["Volume"])
vol.data.materials.append(mvol)

mundo = bpy.data.worlds.new("Mundo")
mundo.use_nodes = True
mundo.node_tree.nodes["Background"].inputs[0].default_value = (*lineal("#075a9a"), 1)
mundo.node_tree.nodes["Background"].inputs[1].default_value = 0.6
bpy.context.scene.world = mundo

bpy.ops.object.camera_add(location=(0, -1.5, -5.2), rotation=(math.radians(88), 0, 0))
cam = bpy.context.object
cam.data.lens = 16
cam.data.clip_end = 200
bpy.context.scene.camera = cam

esc = bpy.context.scene
esc.render.engine = 'CYCLES'
esc.cycles.samples = int(os.environ.get("MUESTRAS", "48"))
esc.cycles.use_denoising = False
esc.cycles.max_bounces = 4
esc.cycles.volume_bounces = 1
esc.cycles.volume_step_rate = 4.0
esc.cycles.sample_clamp_indirect = 2.0
esc.view_settings.view_transform = 'Filmic'
esc.view_settings.look = 'Medium High Contrast'
esc.render.resolution_x = int(os.environ.get("ANCHO", "1280"))
esc.render.resolution_y = int(os.environ.get("ALTO", "700"))
esc.render.filepath = os.path.abspath("arrecife.png")
bpy.ops.render.render(write_still=True)
print("Render hecho")
