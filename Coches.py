"""Coche de carreras de Manuel, karts y casco.

blender -b --factory-startup --python Coches.py

Exporta coches.glb con:
- "Coche": coche de carreras GT blanco y negro con franjas azul claro, azul oscuro y rojo y el número 1
  (inspirado en la foto, sin marcas ni logotipos), sin las ruedas.
- "CocheRueda": una rueda del coche (la web pone cuatro).
- "Kart" y "KartRueda": kart de carreras. Las partes blancas se tiñen en la web con el color de cada niño.
- "CascoManuel": casco blanco con las franjas del coche, para Manuel.
Renderiza coches.png con una vista del coche y un kart.
Todo mira hacia -Y (en la web, hacia +Z) y tiene el suelo en z = 0.
"""
import bpy
import bmesh
import math
import os
from mathutils import Vector, noise

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.preferences.addon_enable(module="io_scene_gltf2")


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
    activar(objs[0])
    for o in objs[1:]:
        o.select_set(True)
    if len(objs) > 1:
        bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    o.name = nombre
    o.data.name = nombre
    return o


def material_vc(nombre, rug=0.35, metal=0.0):
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


PINTURA = material_vc("Pintura", 0.22)
GOMA = material_vc("Goma", 0.8)


def pintar(o, fn, mat=PINTURA):
    me = o.data
    at = me.color_attributes.new("Col", 'FLOAT_COLOR', 'POINT')
    for v in me.vertices:
        c = fn(v.co, v.normal)
        at.data[v.index].color = (*c, 1.0)
    me.materials.clear()
    me.materials.append(mat)


def pintar_textura(o, fn, tam=1024):
    """Desenvuelve la malla y pinta cada píxel de una textura con fn(posición, normal): la decoración sale nítida."""
    import numpy as np
    activar(o)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=1.1, island_margin=0.004)
    bpy.ops.object.mode_set(mode='OBJECT')
    me = o.data
    me.calc_loop_triangles()
    uv = me.uv_layers.active.data
    img = np.ones((tam, tam, 3), dtype=np.float32) * -1
    for tri in me.loop_triangles:
        P = [me.vertices[v].co for v in tri.vertices]
        U = np.array([uv[l].uv[:] for l in tri.loops]) * (tam - 1)
        n = tri.normal
        x0, y0 = np.floor(U.min(axis=0)).astype(int)
        x1, y1 = np.ceil(U.max(axis=0)).astype(int)
        xs, ys = np.meshgrid(np.arange(max(x0, 0), min(x1, tam - 1) + 1), np.arange(max(y0, 0), min(y1, tam - 1) + 1))
        (ax, ay), (bx, by), (cx, cy) = U
        det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(det) < 1e-9:
            continue
        l1 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / det
        l2 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / det
        l3 = 1 - l1 - l2
        dentro = (l1 >= -0.02) & (l2 >= -0.02) & (l3 >= -0.02)
        for px, py, a, b, c in zip(xs[dentro], ys[dentro], l1[dentro], l2[dentro], l3[dentro]):
            pos = P[0] * a + P[1] * b + P[2] * c
            img[py, px] = fn(pos, n)[:]
    # Rellenar los huecos entre islas con el color vecino (para que no salgan costuras)
    vacio = img[:, :, 0] < 0
    for _ in range(6):
        if not vacio.any():
            break
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            vecino = np.roll(img, (dy, dx), axis=(0, 1))
            ok = vacio & (vecino[:, :, 0] >= 0)
            img[ok] = vecino[ok]
            vacio = img[:, :, 0] < 0
    img[img < 0] = 1.0
    imagen = bpy.data.images.new(o.name + "Textura", tam, tam)
    rgba = np.concatenate([img, np.ones((tam, tam, 1), dtype=np.float32)], axis=2)
    imagen.pixels = rgba.ravel()
    imagen.pack()
    m = bpy.data.materials.new(o.name + "Pintura")
    m.use_nodes = True
    nt = m.node_tree
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = imagen
    nt.links.new(tex.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
    nt.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.22
    me.materials.clear()
    me.materials.append(m)


def caja(loc, esc, rot=(0, 0, 0), bisel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    c = bpy.context.object
    c.scale = esc
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    if bisel:
        b = c.modifiers.new("B", 'BEVEL')
        b.width = bisel
        b.segments = 3
        aplicar(c)
    return c


def cilindro(loc, r, largo, rot=(0, 0, 0), v=16):
    bpy.ops.mesh.primitive_cylinder_add(vertices=v, radius=r, depth=largo, location=loc, rotation=rot)
    c = bpy.context.object
    bpy.ops.object.transform_apply(rotation=True)
    return c


BLANCO, NEGRO = lineal("#f4f5f6"), lineal("#15171a")
AZUL_C, AZUL_O, ROJO = lineal("#1f8fe0"), lineal("#2b2f8f"), lineal("#e2321f")
CRISTAL, GRIS = lineal("#0f1822"), lineal("#50565e")


# =====================================================================
# ---------- COCHE GT ----------
# =====================================================================
L, B = 4.6, 1.98            # largo y ancho
EJE_DEL, EJE_TRAS = -1.45, 1.35
R_RUEDA = 0.34


def techo(t):
    """Altura de la parte de arriba a lo largo del coche (t = 0 delante, 1 detrás)."""
    puntos = [(0.0, 0.62), (0.06, 0.74), (0.3, 0.86), (0.4, 0.92), (0.52, 1.24), (0.62, 1.28), (0.74, 1.22), (0.86, 1.02), (0.95, 0.98), (1.0, 0.9)]
    for (a, ha), (b, hb) in zip(puntos, puntos[1:]):
        if a <= t <= b:
            k = (t - a) / (b - a)
            k = k * k * (3 - 2 * k)
            return ha + (hb - ha) * k
    return puntos[-1][1]


def ancho(t):
    return B / 2 * (0.82 + 0.18 * math.sin(math.pi * min(1.0, 0.1 + t * 0.95)) ** 0.4)


def coche():
    est, per = 90, 56
    verts, caras = [], []
    for i in range(est + 1):
        t = i / est
        y = -L / 2 + t * L
        w = ancho(t)
        top = techo(t)
        abajo = 0.16
        cabina = 0.4 <= t <= 0.9
        for j in range(per):
            a = j / per * math.tau
            ca, sa = math.cos(a), math.sin(a)
            # sección tipo "superelipse": caja con esquinas redondeadas
            x = math.copysign(abs(ca) ** 0.35, ca) * w
            zc = (top + abajo) / 2
            zh = (top - abajo) / 2
            z = zc + math.copysign(abs(sa) ** 0.55, sa) * zh
            # la cabina es más estrecha por arriba
            linea = 0.95
            if z > linea and cabina:
                k = min(1.0, (z - linea) / max(0.01, top - linea))
                x *= 1 - 0.3 * k
            elif z > 0.9:
                x *= 1 - 0.08 * min(1.0, (z - 0.9) / 0.1)
            verts.append((x, y, z))
    for i in range(est):
        for j in range(per):
            a0 = i * per + j
            a1 = i * per + (j + 1) % per
            caras.append((a0, a1, a1 + per, a0 + per))
    for extremo in (0, est):
        c = len(verts)
        y = -L / 2 if extremo == 0 else L / 2
        verts.append((0, y, (techo(extremo / est) + 0.16) / 2))
        base = extremo * per
        for j in range(per):
            if extremo == 0:
                caras.append((c, base + (j + 1) % per, base + j))
            else:
                caras.append((c, base + j, base + (j + 1) % per))
    me = bpy.data.meshes.new("Carroceria")
    me.from_pydata(verts, [], caras)
    cuerpo = objeto("Carroceria", me)
    # Pasos de rueda: hueco redondo en los costados
    for y in (EJE_DEL, EJE_TRAS):
        bpy.ops.mesh.primitive_cylinder_add(vertices=40, radius=R_RUEDA + 0.07, depth=B * 1.3, location=(0, y, R_RUEDA), rotation=(0, math.pi / 2, 0))
        h = bpy.context.object
        b = cuerpo.modifiers.new("Paso", 'BOOLEAN')
        b.operation = 'DIFFERENCE'
        b.object = h
        b.solver = 'EXACT'
        aplicar(cuerpo)
        bpy.data.objects.remove(h)
    for p in cuerpo.data.polygons:
        p.use_smooth = True
    partes = [cuerpo]
    # Alerón trasero sobre dos soportes, faldón delantero, retrovisores y difusor
    partes.append(caja((0, L / 2 - 0.2, 1.45), (B * 0.95, 0.34, 0.04), rot=(-0.15, 0, 0), bisel=0.01))
    for sx in (1, -1):
        partes.append(caja((sx * 0.5, L / 2 - 0.22, 1.18), (0.04, 0.2, 0.5)))
        partes.append(caja((sx * B * 0.475, L / 2 - 0.2, 1.42), (0.03, 0.4, 0.22)))  # placas laterales
        partes.append(caja((sx * (B / 2 - 0.02), -0.25, 1.02), (0.16, 0.08, 0.07), bisel=0.02))  # retrovisores
    partes.append(caja((0, -L / 2 + 0.05, 0.13), (B * 0.95, 0.35, 0.04)))  # faldón
    partes.append(caja((0, L / 2 - 0.05, 0.22), (B * 0.8, 0.3, 0.1)))  # difusor
    # Faros y pilotos
    for sx in (1, -1):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=1, location=(sx * 0.66, -L / 2 + 0.12, 0.6))
        f = bpy.context.object
        f.scale = (0.17, 0.04, 0.045)
        bpy.ops.object.transform_apply(scale=True)
        f.name = "Faro"
        partes.append(f)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=1, location=(sx * 0.7, L / 2 - 0.08, 0.82))
        p = bpy.context.object
        p.scale = (0.24, 0.05, 0.05)
        bpy.ops.object.transform_apply(scale=True)
        p.name = "Piloto"
        partes.append(p)
    # Rejilla delantera (dos entradas de aire grandes)
    for sx in (1, -1):
        partes.append(caja((sx * 0.2, -L / 2 + 0.04, 0.42), (0.3, 0.06, 0.26), bisel=0.05))
    o = unir(partes, "Coche")

    def color(co, n):
        t = (co.y + L / 2) / L
        top = techo(max(0.0, min(1.0, t)))
        # faros, pilotos y rejilla
        if co.y < -L / 2 + 0.2 and abs(co.x) > 0.5 and abs(co.x) < 0.84 and 0.55 < co.z < 0.65:
            return lineal("#fff6d8")
        if co.y > L / 2 - 0.15 and abs(co.x) > 0.45 and 0.75 < co.z < 0.9:
            return ROJO * 1.2
        if co.y < -L / 2 + 0.12 and abs(co.x) < 0.38 and 0.28 < co.z < 0.56:
            return NEGRO
        # alerón, faldón, difusor, retrovisores: negro
        if co.z > 1.3 and co.y > L / 2 - 0.6 or co.z < 0.18 or (co.y > L / 2 - 0.25 and co.z < 0.3):
            return NEGRO
        # cristales: por encima de la línea de cintura en la cabina
        if 0.42 < t < 0.9 and co.z > 1.0 and co.z < top - 0.03:
            return CRISTAL
        # techo y montantes negros
        if 0.42 < t < 0.9 and co.z >= top - 0.03:
            return NEGRO
        # bajos negros y la parte de detrás de las ruedas delanteras en negro (como en la foto)
        if co.z < 0.32 or (0.18 < t < 0.33 and co.z < 0.9 and abs(co.x) > 0.8):
            return NEGRO
        # número 1 en las puertas: círculo blanco con borde negro
        if abs(co.x) > 0.85 and 0.45 < co.z < 0.85:
            d = math.hypot(co.y - 0.1, co.z - 0.62)
            if d < 0.19:
                if abs(co.y - 0.12) < 0.035 and 0.52 < co.z < 0.74:
                    return NEGRO
                if 0.06 < co.y - 0.12 < 0.08 and 0.66 < co.z < 0.74:
                    return NEGRO
                return BLANCO
            if d < 0.22:
                return NEGRO
        # franjas en diagonal: azul claro, azul oscuro y rojo
        if n.z > 0.55 and co.z < 1.0:
            u = (co.y + 2.2) * 0.45 - co.x * 0.3 + 0.1   # en el capó, en diagonal
        else:
            u = co.y * 0.75 + co.z * 1.1           # en los costados, subiendo hacia atrás
        for (c0, c1, col) in ((0.2, 0.42, AZUL_C), (0.42, 0.6, AZUL_O), (0.6, 0.8, ROJO)):
            if c0 < u < c1 and co.y < 1.6:
                return col
        return BLANCO
    pintar_textura(o, color, 1024)
    return o


def rueda(nombre, r, ancho_r, llanta=0.62):
    """Rueda que mira hacia +X (eje de giro X), con el centro en el origen."""
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=r, depth=ancho_r, rotation=(0, math.pi / 2, 0))
    neu = bpy.context.object
    bpy.ops.object.transform_apply(rotation=True)
    b = neu.modifiers.new("B", 'BEVEL')
    b.width = r * 0.12
    b.segments = 3
    aplicar(neu)
    for p in neu.data.polygons:
        p.use_smooth = True
    o = unir([neu], nombre)

    def color(co, n):
        rr = math.hypot(co.y, co.z)
        if abs(co.x) > ancho_r * 0.45 and rr < r * llanta:
            a = math.atan2(co.z, co.y)
            radio = abs(math.sin(a * 2.5)) > 0.55 and rr > r * 0.18
            return GRIS * (0.5 if radio else 1.3) if rr > r * 0.12 else NEGRO
        return lineal("#1a1a1a")
    pintar(o, color, GOMA)
    return o


# =====================================================================
# ---------- KART ----------
# =====================================================================
def kart():
    partes = []
    # Chasis de tubos (negro) y suelo
    partes.append(caja((0, 0.05, 0.12), (0.8, 1.5, 0.05)))
    for sx in (1, -1):
        partes.append(cilindro((sx * 0.42, 0.05, 0.14), 0.025, 1.6, rot=(math.pi / 2, 0, 0), v=8))
    partes.append(cilindro((0, -0.72, 0.14), 0.025, 0.9, rot=(0, math.pi / 2, 0), v=8))
    partes.append(cilindro((0, 0.78, 0.14), 0.025, 1.3, rot=(0, math.pi / 2, 0), v=8))
    # Morro (pontón delantero) y pontones laterales: se tiñen con el color de cada niño
    morro = caja((0, -0.78, 0.22), (0.95, 0.35, 0.18), rot=(0.15, 0, 0), bisel=0.06)
    morro.name = "Tinte"
    partes.append(morro)
    for sx in (1, -1):
        p = caja((sx * 0.55, 0.1, 0.2), (0.22, 0.85, 0.16), bisel=0.06)
        p.name = "Tinte"
        partes.append(p)
    # Asiento
    asiento = caja((0, 0.25, 0.3), (0.42, 0.4, 0.08), bisel=0.03)
    respaldo = caja((0, 0.47, 0.5), (0.42, 0.08, 0.45), rot=(-0.35, 0, 0), bisel=0.03)
    asiento.name = respaldo.name = "Asiento"
    partes += [asiento, respaldo]
    # Volante y columna
    partes.append(cilindro((0, -0.32, 0.42), 0.022, 0.5, rot=(-0.9, 0, 0), v=8))
    bpy.ops.mesh.primitive_torus_add(major_radius=0.15, minor_radius=0.022, location=(0, -0.2, 0.58), rotation=(-0.9 + math.pi / 2, 0, 0))
    vol = bpy.context.object
    vol.name = "Volante"
    partes.append(vol)
    # Motor detrás a un lado y parachoques trasero
    partes.append(caja((0.3, 0.62, 0.3), (0.26, 0.26, 0.24), bisel=0.02))
    partes.append(cilindro((0.3, 0.62, 0.48), 0.06, 0.1, v=12))
    parag = caja((0, 0.95, 0.22), (1.15, 0.1, 0.14), bisel=0.03)
    parag.name = "Tinte"
    partes.append(parag)
    # Placa del número delante
    placa = caja((0, -0.95, 0.38), (0.34, 0.03, 0.24), rot=(0.4, 0, 0), bisel=0.02)
    placa.name = "Placa"
    partes.append(placa)
    # Nombres para pintar cada pieza
    tinte = set()
    for o in partes:
        if o.name.startswith("Tinte"):
            for v in o.data.vertices:
                tinte.add(tuple(round(c, 4) for c in (o.matrix_world @ v.co)))
    o = unir(partes, "Kart")

    def color(co, n):
        clave = tuple(round(c, 4) for c in co)
        if clave in tinte:
            return BLANCO  # la web lo tiñe
        if co.y < -0.9 and co.z > 0.26:
            return BLANCO * 1.0  # placa (también se tiñe, un poco)
        if 0.2 < co.z and abs(co.x) < 0.25 and 0.1 < co.y < 0.6:
            return lineal("#22262c")  # asiento
        return lineal("#2a2d33")
    pintar(o, color)
    return o


def casco_manuel():
    """Casco blanco con las franjas del coche, para Manuel (la web lo coloca en su cabeza)."""
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=1.0)
    c = bpy.context.object
    bm = bmesh.new()
    bm.from_mesh(c.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -0.5 or (v.co.y < -0.35 and -0.5 < v.co.z < 0.3 and abs(v.co.x) < 0.72)], context='VERTS')
    bm.to_mesh(c.data)
    bm.free()
    so = c.modifiers.new("G", 'SOLIDIFY')
    so.thickness = 0.06
    aplicar(c)
    for p in c.data.polygons:
        p.use_smooth = True
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=1.0)
    v = bpy.context.object
    bm = bmesh.new()
    bm.from_mesh(v.data)
    bmesh.ops.delete(bm, geom=[q for q in bm.verts if q.co.y > -0.3 or q.co.z < -0.45 or q.co.z > 0.35 or abs(q.co.x) > 0.8], context='VERTS')
    bm.to_mesh(v.data)
    bm.free()
    v.scale = (1.02, 1.04, 1.02)
    bpy.ops.object.transform_apply(scale=True)
    v.name = "Visera"
    for p in v.data.polygons:
        p.use_smooth = True
    visera = set(tuple(round(c, 4) for c in q.co) for q in v.data.vertices)
    o = unir([c, v], "CascoManuel")

    def color(co, n):
        if tuple(round(c, 4) for c in co) in visera:
            return CRISTAL
        u = co.y * 0.8 + co.z
        if abs(co.x) < 0.5:
            if 0.1 < u < 0.3:
                return AZUL_C
            if 0.3 < u < 0.45:
                return AZUL_O
            if 0.45 < u < 0.6:
                return ROJO
        return BLANCO
    pintar(o, color)
    return o


proto = [coche(), rueda("CocheRueda", R_RUEDA, 0.28), kart(), rueda("KartRueda", 0.13, 0.14, 0.55), casco_manuel()]
for o in proto:
    print(f"{o.name}: {len(o.data.polygons)} caras")

bpy.ops.object.select_all(action='DESELECT')
for o in proto:
    o.select_set(True)
bpy.ops.export_scene.gltf(filepath=os.path.abspath("coches.glb"), export_format='GLB', use_selection=True)
print("Exportado coches.glb")

if os.environ.get("SIN_RENDER") == "1":
    raise SystemExit

# ---------- VISTA PREVIA ----------
coche_o, rueda_o, kart_o, krueda_o, casco_o = proto
for y in (EJE_DEL, EJE_TRAS):
    for sx in (1, -1):
        r = bpy.data.objects.new("R", rueda_o.data)
        bpy.context.collection.objects.link(r)
        r.location = (sx * (B / 2 - 0.12), y, R_RUEDA)
kart_o.location = (2.6, -1.4, 0)
for y in (-0.62, 0.72):
    for sx in (1, -1):
        r = bpy.data.objects.new("RK", krueda_o.data)
        bpy.context.collection.objects.link(r)
        r.location = (2.6 + sx * 0.62, -1.4 + y, 0.13)
casco_o.location = (2.6, -1.4, 0.85)
casco_o.scale = (0.13, 0.14, 0.15)
bpy.ops.mesh.primitive_plane_add(size=30)
suelo = bpy.context.object
m = bpy.data.materials.new("Suelo")
m.use_nodes = True
m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*lineal("#9a9ea4"), 1)
suelo.data.materials.append(m)
bpy.ops.object.camera_add(location=(-5.5, -6.2, 2.9), rotation=(math.radians(72), 0, math.radians(-42)))
bpy.context.scene.camera = bpy.context.object
bpy.context.object.data.lens = 38
bpy.ops.object.light_add(type='SUN', rotation=(math.radians(45), math.radians(10), math.radians(30)))
bpy.context.object.data.energy = 3.5
bpy.ops.object.light_add(type='AREA', location=(-3, -4, 4))
bpy.context.object.data.energy = 600
bpy.context.object.data.size = 5
bpy.context.object.rotation_euler = (math.radians(45), 0, math.radians(-35))
w = bpy.data.worlds.new("Mundo")
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.8, 0.88, 0.95, 1)
bpy.context.scene.world = w
esc = bpy.context.scene
esc.render.engine = 'CYCLES'
esc.cycles.samples = int(os.environ.get("MUESTRAS", "64"))
esc.cycles.use_denoising = False
esc.view_settings.view_transform = 'AgX'
esc.view_settings.look = 'AgX - Punchy'
esc.render.resolution_x = 1100
esc.render.resolution_y = 620
esc.render.filepath = os.path.abspath("coches.png")
bpy.ops.render.render(write_still=True)
