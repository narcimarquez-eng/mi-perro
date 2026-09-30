"""Piezas para los circuitos de karts: ciudad, playa y bosque misterioso, y los objetos de las cajas sorpresa.

blender -b --factory-startup --python Pistas.py

Exporta pistas.glb (cada pieza en el origen, con su nombre; la web las repite muchas veces) y
renderiza pistas.png con una muestra de cada escenario.
Las partes pintadas de blanco o gris claro se pueden teñir en la web con el color de cada copia.
"""
import bpy
import bmesh
import math
import os
import random
from mathutils import Euler, Matrix, Vector, noise

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.preferences.addon_enable(module="io_scene_gltf2")
rnd = random.Random(5)


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


def material_vc(nombre, rug=0.6, doble=False):
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    vc = nt.nodes.new("ShaderNodeVertexColor")
    vc.layer_name = "Col"
    nt.links.new(vc.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rug
    m.use_backface_culling = not doble
    return m


VC = material_vc("Pieza", 0.6)
VC_DOBLE = material_vc("PiezaDoble", 0.7, doble=True)


def pintar(o, fn, mat=VC):
    me = o.data
    at = me.color_attributes.new("Col", 'FLOAT_COLOR', 'POINT')
    for v in me.vertices:
        c = fn(v.co, v.normal)
        at.data[v.index].color = (max(0, c[0]), max(0, c[1]), max(0, c[2]), 1.0)
    me.materials.clear()
    me.materials.append(mat)


def mezclar(a, b, t):
    t = max(0.0, min(1.0, t))
    return a * (1 - t) + b * t


def caja(loc, esc, rot=(0, 0, 0), bisel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    c = bpy.context.object
    c.scale = esc
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    if bisel:
        b = c.modifiers.new("B", 'BEVEL')
        b.width = bisel
        b.segments = 2
        aplicar(c)
    return c


def cilindro(loc, r, largo, rot=(0, 0, 0), v=16, r2=None, cortes=0):
    if r2 is None:
        bpy.ops.mesh.primitive_cylinder_add(vertices=v, radius=r, depth=largo, location=loc, rotation=rot)
    else:
        bpy.ops.mesh.primitive_cone_add(vertices=v, radius1=r, radius2=r2, depth=largo, location=loc, rotation=rot)
    c = bpy.context.object
    bpy.ops.object.transform_apply(rotation=True)
    if cortes:  # más anillos a lo largo, para poder pintar franjas
        bm = bmesh.new()
        bm.from_mesh(c.data)
        bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) > 0.01], cuts=cortes)
        bm.to_mesh(c.data)
        bm.free()
    return c


def esfera(loc, esc, seg=16):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=max(6, seg // 2), radius=1, location=loc)
    o = bpy.context.object
    o.scale = esc
    bpy.ops.object.transform_apply(scale=True)
    suave(o)
    return o


def skin(nombre, verts, aristas, radios, sub=1):
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


def textura_ventanas(nombre, fondo, cristal, marco, luz_prob=0.25, ancho=128, alto=128):
    """Una celda de fachada con su ventana; la web la repite por todo el edificio."""
    import numpy as np
    img = np.zeros((alto, ancho, 4), dtype=np.float32)
    img[:, :, :3] = fondo
    img[:, :, 3] = 1
    x0, x1, y0, y1 = int(ancho * 0.18), int(ancho * 0.82), int(alto * 0.22), int(alto * 0.86)
    img[y0 - 4:y1 + 4, x0 - 4:x1 + 4, :3] = marco
    img[y0:y1, x0:x1, :3] = cristal
    # reflejo diagonal en el cristal
    for y in range(y0, y1):
        for x in range(x0, x1):
            if abs((x - x0) - (y - y0) * 0.7 - 12) < 6:
                img[y, x, :3] = cristal * 0.6 + Vector((0.9, 0.95, 1.0)) * 0.4
    img[int(alto * 0.53):int(alto * 0.55), x0:x1, :3] = marco
    im = bpy.data.images.new(nombre, ancho, alto)
    im.pixels = img.ravel()
    im.pack()
    return im


def material_textura(nombre, imagen, rug=0.4):
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    nt = m.node_tree
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = imagen
    nt.links.new(tex.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
    nt.nodes["Principled BSDF"].inputs["Roughness"].default_value = rug
    return m


def uv_fachada(o, celda_x=3.0, celda_z=3.2):
    """UV en metros: cada cara vertical repite una celda de ventana cada celda_x por celda_z metros."""
    me = o.data
    if not me.uv_layers:
        me.uv_layers.new(name="UV")
    uv = me.uv_layers.active.data
    for p in me.polygons:
        n = p.normal
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if abs(n.z) > 0.7:
                uv[li].uv = (0.02, 0.02)  # techo: esquina lisa de la textura
            elif abs(n.x) > abs(n.y):
                uv[li].uv = (co.y / celda_x, co.z / celda_z)
            else:
                uv[li].uv = (co.x / celda_x, co.z / celda_z)


# =====================================================================
# ---------- CIUDAD ----------
# =====================================================================
def edificio(nombre, ancho, fondo, alto, fondo_col, cristal, marco, escalones=0, remate="antena"):
    partes = []
    b = caja((0, 0, alto / 2), (ancho, fondo, alto))
    partes.append(b)
    h = alto
    for k in range(escalones):
        f = 0.75 - 0.15 * k
        e = caja((0, 0, h + 3), (ancho * f, fondo * f, 6))
        partes.append(e)
        h += 6
    o = unir(partes, nombre)
    uv_fachada(o)
    im = textura_ventanas(nombre + "Fachada", fondo_col, cristal, marco)
    o.data.materials.append(material_textura(nombre + "Mat", im))
    # color blanco en los vértices (la web multiplica la textura por él)
    at = o.data.color_attributes.new("Col", 'FLOAT_COLOR', 'POINT')
    for d in at.data:
        d.color = (1, 1, 1, 1)
    # remate del tejado (con su propio material de color)
    extra = []
    if remate == "antena":
        extra.append(cilindro((0, 0, h + 4), 0.25, 8, v=8))
        extra.append(cilindro((0, 0, h + 0.6), ancho * 0.18, 1.2, v=12))
    elif remate == "deposito":
        extra.append(cilindro((ancho * 0.2, fondo * 0.2, h + 1.6), 1.2, 2.4, v=14))
        extra.append(caja((-ancho * 0.2, -fondo * 0.1, h + 0.8), (ancho * 0.3, fondo * 0.3, 1.6)))
    elif remate == "tejado":
        bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=ancho * 0.75, depth=4, location=(0, 0, h + 2), rotation=(0, 0, math.pi / 4))
        c = bpy.context.object
        c.scale = (1, fondo / ancho, 1)
        bpy.ops.object.transform_apply(scale=True, rotation=True)
        extra.append(c)
    if extra:
        r = unir(extra, nombre + "Remate")
        pintar(r, lambda co, n: lineal("#b8bcc2") if remate != "tejado" else lineal("#b5523a"))
        activar(r)
        r.select_set(True)
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.join()
    return o


def farola():
    partes = [cilindro((0, 0, 3), 0.1, 6, v=10), cilindro((0, 0, 0.2), 0.22, 0.4, v=12)]
    brazo = cilindro((0.6, 0, 5.9), 0.06, 1.3, rot=(0, math.pi / 2, 0), v=8)
    lamp = esfera((1.2, 0, 5.75), (0.35, 0.2, 0.14))
    lamp.name = "Luz"
    partes += [brazo, lamp]
    luz = set(tuple(round(c, 3) for c in v.co) for v in lamp.data.vertices)
    o = unir(partes, "Farola")
    pintar(o, lambda co, n: lineal("#fff2c0") * 3 if tuple(round(c, 3) for c in co) in luz else lineal("#2c333b"))
    return o


def semaforo_calle():
    partes = [cilindro((0, 0, 2), 0.09, 4, v=10), caja((0, -0.15, 3.6), (0.4, 0.3, 1.1), bisel=0.05)]
    focos = []
    for k, col in enumerate(("#ff3322", "#ffbb22", "#33dd55")):
        f = esfera((0, -0.32, 3.95 - k * 0.34), (0.12, 0.05, 0.12), seg=12)
        focos.append((f, col))
        partes.append(f)
    marcas = {}
    for f, col in focos:
        for v in f.data.vertices:
            marcas[tuple(round(c, 3) for c in v.co)] = col
    o = unir(partes, "Semaforo")
    pintar(o, lambda co, n: lineal(marcas.get(tuple(round(c, 3) for c in co), "#1d2126")) * (2 if tuple(round(c, 3) for c in co) in marcas else 1))
    return o


def arbol_calle():
    partes = [cilindro((0, 0, 0.3), 0.8, 0.6, v=16), cilindro((0, 0, 1.6), 0.15, 2.6, v=8)]
    copa = []
    for k in range(6):
        a = k / 6 * math.tau
        copa.append(esfera((math.cos(a) * 0.8, math.sin(a) * 0.8, 3.4 + rnd.uniform(-0.2, 0.4)), (1.1, 1.1, 1.0), seg=12))
    copa.append(esfera((0, 0, 4.1), (1.2, 1.2, 1.1), seg=12))
    verdes = set()
    for c in copa:
        for v in c.data.vertices:
            verdes.add(tuple(round(x, 3) for x in v.co))
    o = unir(partes + copa, "ArbolCalle")

    def color(co, n):
        if tuple(round(c, 3) for c in co) in verdes:
            return mezclar(lineal("#3f8f35"), lineal("#7cc251"), 0.5 + 0.5 * n.z) * (0.85 + 0.3 * noise.noise(co * 2))
        if co.z < 0.62:
            return lineal("#a9adb3")
        return lineal("#6b4a2e")
    pintar(o, color)
    return o


def valla_publicitaria():
    partes = [cilindro((-2.5, 0, 2.5), 0.15, 5, v=8), cilindro((2.5, 0, 2.5), 0.15, 5, v=8), caja((0, 0.05, 5.6), (7.4, 0.3, 3.4), bisel=0.05)]
    o = unir(partes, "Valla")
    pintar(o, lambda co, n: lineal("#ffffff") if co.y < -0.08 and co.z > 4 else lineal("#2c333b"))
    return o


# =====================================================================
# ---------- PLAYA ----------
# =====================================================================
def palmera(nombre="Palmera", alto=8.0, curva=2.0):
    verts, aristas, radios = [], [], []
    n = 10
    for i in range(n):
        t = i / (n - 1)
        verts.append(Vector((curva * t * t, 0, alto * t)))
        radios.append(0.32 * (1 - 0.45 * t))
        if i:
            aristas.append((i - 1, i))
    tronco = skin("Tronco", verts, aristas, radios)
    cima = verts[-1]
    partes = [tronco]
    hojas = set()
    for k in range(9):
        a = k / 9 * math.tau + rnd.uniform(-0.2, 0.2)
        largo = rnd.uniform(3.2, 4.2)
        pts = []
        for s in range(8):
            t = s / 7
            d = Vector((math.cos(a) * largo * t, math.sin(a) * largo * t, 0.6 * math.sin(math.pi * t * 0.8) - 1.4 * t * t))
            pts.append(cima + d)
        vs, cs = [], []
        for s, p in enumerate(pts):
            ancho = 0.55 * math.sin(math.pi * min(1.0, s / 7 * 0.95 + 0.05))
            lado = Vector((-math.sin(a), math.cos(a), 0)) * ancho
            vs += [p + lado, p - lado + Vector((0, 0, 0.12))]
            if s:
                j = (s - 1) * 2
                cs.append((j, j + 1, j + 3, j + 2))
        me = bpy.data.meshes.new("Hoja")
        me.from_pydata(vs, [], cs)
        h = objeto("Hoja", me)
        for v in h.data.vertices:
            hojas.add(tuple(round(c, 3) for c in v.co))
        partes.append(h)
    for k in range(4):
        a = k / 4 * math.tau
        c = esfera(cima + Vector((math.cos(a) * 0.3, math.sin(a) * 0.3, -0.35)), (0.2, 0.2, 0.22), seg=10)
        partes.append(c)
    o = unir(partes, nombre)

    def color(co, n):
        if tuple(round(c, 3) for c in co) in hojas:
            return mezclar(lineal("#2f7d2a"), lineal("#8fcf4a"), 0.5 + 0.5 * noise.noise(co * 1.5))
        if co.z > alto - 0.7:
            return lineal("#5a3b1c")
        anillo = 0.5 + 0.5 * math.sin(co.z * 9)
        return mezclar(lineal("#8a6a44"), lineal("#b89468"), anillo)
    pintar(o, color, VC_DOBLE)
    return o


def faro():
    partes = [cilindro((0, 0, 7), 2.2, 14, v=24, r2=1.5, cortes=29), cilindro((0, 0, 14.3), 2.0, 0.5, v=24),
              cilindro((0, 0, 15.4), 1.2, 1.8, v=16), cilindro((0, 0, 16.8), 1.5, 1.0, v=16, r2=0.2)]
    o = unir(partes, "Faro")

    def color(co, n):
        if co.z > 14.6 and co.z < 16.3:
            return lineal("#fff4c8") * 2.5  # lámpara
        if co.z > 16.3:
            return lineal("#c0392b")
        if co.z > 14.0:
            return lineal("#2c333b")
        return lineal("#e8392b") if int(co.z / 2.8) % 2 == 0 else lineal("#f8f6f0")
    pintar(o, color)
    return o


def caseta():
    cuerpo = caja((0, 0, 1.4), (2.6, 2.2, 2.8))
    bm = bmesh.new()
    bm.from_mesh(cuerpo.data)
    bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) < 0.01], cuts=11)
    bm.to_mesh(cuerpo.data)
    bm.free()
    partes = [cuerpo, caja((0, -1.2, 1.2), (0.9, 0.1, 2.0))]
    bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=2.3, depth=1.2, location=(0, 0, 3.4), rotation=(0, 0, math.pi / 4))
    tejado = bpy.context.object
    tejado.scale = (1.15, 1.0, 1)
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    partes.append(tejado)
    o = unir(partes, "Caseta")

    def color(co, n):
        if co.z > 2.85:
            return lineal("#ffffff")        # tejado (se tiñe)
        if co.y < -1.15 and abs(co.x) < 0.46:
            return lineal("#6b4a2e")        # puerta
        return lineal("#ffffff") if int((co.x + co.y + 5) / 0.43) % 2 else lineal("#f8f6f0") * 0.55  # rayas
    pintar(o, color)
    return o


def velero():
    # Casco
    verts, caras = [], []
    est, per = 16, 9
    for i in range(est + 1):
        t = i / est
        y = -3 + t * 6
        manga = 1.0 * math.sin(math.pi * min(1.0, 0.15 + t * 0.9)) ** 0.7 + 0.05
        for j in range(per):
            s = j / (per - 1) * 2 - 1
            verts.append((s * manga, y, 0.9 - 1.1 * (1 - s * s) + 0.3 * max(0, t - 0.8)))
    for i in range(est):
        for j in range(per - 1):
            a = i * per + j
            caras.append((a, a + per, a + per + 1, a + 1))
    me = bpy.data.meshes.new("Casco")
    me.from_pydata(verts, [], caras)
    casco = objeto("Casco", me)
    so = casco.modifiers.new("G", 'SOLIDIFY')
    so.thickness = 0.06
    aplicar(casco)
    suave(casco)
    mastil = cilindro((0, -0.3, 4.2), 0.08, 7.2, v=8)
    vela = [(0, -0.2, 1.2), (0, -0.2, 7.6), (0, 2.4, 1.3)]
    foque = [(0, -0.45, 1.2), (0, -0.45, 6.8), (0, -2.8, 1.0)]
    velas = []
    for pts in (vela, foque):
        me = bpy.data.meshes.new("Vela")
        me.from_pydata(pts, [], [(0, 1, 2)])
        velas.append(objeto("Vela", me))
    marca = set()
    for v in velas:
        for q in v.data.vertices:
            marca.add(tuple(round(c, 3) for c in q.co))
    o = unir([casco, mastil] + velas, "Velero")

    def color(co, n):
        if tuple(round(c, 3) for c in co) in marca:
            return lineal("#fbfaf5")
        if co.z > 1.4:
            return lineal("#a07850")
        return lineal("#1f5fa8") if co.z > 0.2 else lineal("#f4f4f0")
    pintar(o, color, VC_DOBLE)
    return o


def sombrilla():
    partes = [cilindro((0, 0, 1.3), 0.05, 2.6, v=8)]
    bpy.ops.mesh.primitive_cone_add(vertices=16, radius1=1.6, depth=0.6, location=(0, 0, 2.6))
    partes.append(bpy.context.object)
    o = unir(partes, "Sombrilla")

    def color(co, n):
        if co.z > 2.25:
            a = math.atan2(co.y, co.x)
            return lineal("#ffffff") if int((a + math.pi) / (math.tau / 8)) % 2 else lineal("#e8392b")
        return lineal("#dcdcdc")
    pintar(o, color, VC_DOBLE)
    return o


def roca_playa():
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=1)
    o = bpy.context.object
    o.name = "RocaPlaya"
    for v in o.data.vertices:
        v.co += v.co * 0.3 * noise.noise(v.co * 1.6)
        v.co.x *= 1.6
        v.co.z *= 0.8
    suave(o)
    pintar(o, lambda co, n: mezclar(lineal("#8a8378"), lineal("#b9b0a0"), 0.5 + 0.5 * noise.noise(co * 2)) * (0.8 + 0.2 * n.z))
    return o


# =====================================================================
# ---------- BOSQUE MISTERIOSO ----------
# =====================================================================
def arbol_misterio(nombre="ArbolMisterio", semilla=3):
    r = random.Random(semilla)
    verts, aristas, radios = [Vector((0, 0, 0))], [], [0.9]
    # tronco retorcido con raíces
    for k in range(4):
        a = k / 4 * math.tau + 0.4
        verts.append(Vector((math.cos(a) * 1.6, math.sin(a) * 1.6, -0.2)))
        radios.append(0.25)
        aristas.append((0, len(verts) - 1))
    i0 = 0
    p = Vector((0, 0, 0))
    for s in range(1, 7):
        p = p + Vector((0.5 * math.sin(s * 1.3), 0.5 * math.cos(s * 1.1), 1.4))
        verts.append(p.copy())
        radios.append(0.8 - s * 0.08)
        aristas.append((i0, len(verts) - 1))
        i0 = len(verts) - 1
    tope = i0
    for k in range(5):
        a = k / 5 * math.tau + r.uniform(-0.3, 0.3)
        q = verts[tope] + Vector((math.cos(a) * 2.4, math.sin(a) * 2.4, r.uniform(0.6, 1.8)))
        verts.append(q)
        radios.append(0.2)
        aristas.append((tope, len(verts) - 1))
    tronco = skin("Tronco", verts, aristas, radios)
    for v in tronco.data.vertices:
        v.co += v.normal * 0.08 * noise.noise(v.co * 3)
    copa = []
    for k in range(9):
        a = k / 9 * math.tau
        c = verts[tope] + Vector((math.cos(a) * r.uniform(1.5, 3.2), math.sin(a) * r.uniform(1.5, 3.2), r.uniform(1.2, 3.2)))
        copa.append(esfera(c, (r.uniform(1.6, 2.4),) * 3, seg=10))
    hojas = set()
    for c in copa:
        for v in c.data.vertices:
            v.co += v.normal * 0.25 * noise.noise(v.co * 1.5)
            hojas.add(tuple(round(x, 3) for x in v.co))
    o = unir([tronco] + copa, nombre)

    def color(co, n):
        if tuple(round(c, 3) for c in co) in hojas:
            return mezclar(lineal("#173b2c"), lineal("#2f6b45"), 0.5 + 0.5 * n.z) * (0.8 + 0.3 * noise.noise(co))
        musgo = max(0.0, n.z) * (0.5 + 0.5 * noise.noise(co * 2))
        return mezclar(lineal("#3a2a22"), lineal("#3f6a3a"), musgo)
    pintar(o, color)
    return o


def seta_gigante():
    tallo = skin("Tallo", [Vector((0, 0, 0)), Vector((0.2, 0, 1.2)), Vector((0.1, 0, 2.4))], [(0, 1), (1, 2)], [0.45, 0.35, 0.32])
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=1)
    som = bpy.context.object
    bm = bmesh.new()
    bm.from_mesh(som.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -0.05], context='VERTS')
    bm.to_mesh(som.data)
    bm.free()
    for v in som.data.vertices:
        v.co = Vector((v.co.x * 1.8, v.co.y * 1.8, v.co.z * 1.1 + 2.3))
    so = som.modifiers.new("G", 'SOLIDIFY')
    so.thickness = 0.12
    aplicar(som)
    suave(som)
    o = unir([tallo, som], "SetaGigante")

    def color(co, n):
        if co.z > 2.25:
            d = noise.noise(Vector((co.x * 1.8, co.y * 1.8, co.z)))
            return lineal("#f6f2e8") if d > 0.35 else lineal("#ffffff")  # sombrero (se tiñe) con motas
        return lineal("#efe6d2")
    pintar(o, color)
    return o


def cristales():
    partes = []
    r = random.Random(8)
    for k in range(7):
        a = r.uniform(0, math.tau)
        inc = r.uniform(0.1, 0.5)
        largo = r.uniform(1.0, 2.6)
        c = cilindro((0, 0, largo / 2), r.uniform(0.18, 0.32), largo, v=6)
        bpy.ops.mesh.primitive_cone_add(vertices=6, radius1=0.3, depth=0.5, location=(0, 0, largo + 0.25))
        punta = bpy.context.object
        punta.scale = c.dimensions.x / 0.6, c.dimensions.y / 0.6, 1
        bpy.ops.object.transform_apply(scale=True)
        pieza = unir([c, punta], "Cristal")
        pieza.data.transform(Euler((inc * math.cos(a), inc * math.sin(a), a)).to_matrix().to_4x4())
        pieza.data.transform(Matrix.Translation(Vector((math.cos(a) * 0.3, math.sin(a) * 0.3, 0))))
        partes.append(pieza)
    o = unir(partes, "Cristales")
    suave(o, False)
    pintar(o, lambda co, n: lineal("#ffffff") * (0.75 + 0.25 * co.z / 3))
    return o


def ruina():
    partes = []
    for x in (-3.2, 3.2):
        for k in range(5):
            partes.append(caja((x + rnd.uniform(-0.05, 0.05), 0, 0.55 + k * 1.05), (1.2, 1.2, 1.0), rot=(0, 0, rnd.uniform(-0.05, 0.05)), bisel=0.08))
    for k in range(9):
        a = math.pi * k / 8
        partes.append(caja((-3.2 * math.cos(a), 0, 5.2 + 2.8 * math.sin(a)), (1.2, 1.25, 0.9), rot=(0, a - math.pi / 2, 0), bisel=0.08))
    o = unir(partes, "Ruina")
    pintar(o, lambda co, n: mezclar(lineal("#6f6a60"), lineal("#8e887b"), 0.5 + 0.5 * noise.noise(co * 1.5)) * (1 if n.z < 0.6 else 1.0)
           if noise.noise(co * 0.9 + Vector((3, 0, 0))) < 0.25 else lineal("#3f6a3a"))
    return o


def helecho():
    partes = []
    hojas = []
    for k in range(9):
        a = k / 9 * math.tau
        vs, cs = [], []
        for s in range(7):
            t = s / 6
            p = Vector((math.cos(a) * 1.3 * t, math.sin(a) * 1.3 * t, 1.1 * math.sin(math.pi * t * 0.7)))
            w = 0.25 * math.sin(math.pi * min(1.0, t + 0.1))
            lado = Vector((-math.sin(a), math.cos(a), 0)) * w
            vs += [p + lado, p - lado]
            if s:
                j = (s - 1) * 2
                cs.append((j, j + 1, j + 3, j + 2))
        me = bpy.data.meshes.new("Fronda")
        me.from_pydata(vs, [], cs)
        hojas.append(objeto("Fronda", me))
    o = unir(hojas, "Helecho")
    pintar(o, lambda co, n: mezclar(lineal("#1f5a2c"), lineal("#5fae4a"), co.z / 1.1), VC_DOBLE)
    return o


def tronco_caido():
    t = cilindro((0, 0, 0.55), 0.55, 6, rot=(0, math.pi / 2, 0.2), v=16)
    for v in t.data.vertices:
        v.co += v.normal * 0.06 * noise.noise(v.co * 3)
    suave(t)
    o = unir([t], "TroncoCaido")
    pintar(o, lambda co, n: mezclar(lineal("#4a3325"), lineal("#3f6a3a"), max(0.0, n.z) * 0.8))
    return o


def farolillo():
    partes = [cilindro((0, 0, 1.2), 0.06, 2.4, v=8), caja((0.25, 0, 2.3), (0.5, 0.06, 0.06)),
              esfera((0.5, 0, 2.0), (0.18, 0.18, 0.24), seg=12)]
    luz = set(tuple(round(c, 3) for c in v.co) for v in partes[-1].data.vertices)
    o = unir(partes, "Farolillo")
    pintar(o, lambda co, n: lineal("#9fffcf") * 3 if tuple(round(c, 3) for c in co) in luz else lineal("#2a2622"))
    return o


# =====================================================================
# ---------- OBJETOS DE LAS CAJAS SORPRESA ----------
# =====================================================================
def platano():
    verts, aristas, radios = [], [], []
    for i in range(9):
        t = i / 8
        a = (t - 0.5) * 1.8
        verts.append(Vector((math.sin(a) * 0.5, 0, (1 - math.cos(a)) * 0.5 + 0.12)))
        radios.append(0.03 + 0.09 * math.sin(math.pi * t))
        if i:
            aristas.append((i - 1, i))
    o = skin("Platano", verts, aristas, radios)
    pintar(o, lambda co, n: lineal("#3a2a10") if abs(co.x) > 0.36 else lineal("#ffd92e"))
    return o


def caparazon():
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=1)
    c = bpy.context.object
    for v in c.data.vertices:
        v.co.z = max(v.co.z, -0.15) * 0.75
    c.scale = (0.32, 0.32, 0.32)
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.31, minor_radius=0.05, location=(0, 0, -0.03))
    borde = bpy.context.object
    o = unir([c, borde], "Caparazon")
    suave(o)

    def color(co, n):
        if co.z < 0.02:
            return lineal("#ffffff") * 0.95  # borde blanco
        celda = abs(math.sin(math.atan2(co.y, co.x) * 3)) * (co.z / 0.24)
        return lineal("#ffffff") if celda < 0.55 else lineal("#dcdcdc")  # dibujo (se tiñe verde o rojo)
    pintar(o, color)
    return o


def seta_turbo():
    tallo = cilindro((0, 0, 0.15), 0.12, 0.3, v=16)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=1)
    som = bpy.context.object
    for v in som.data.vertices:
        v.co = Vector((v.co.x * 0.3, v.co.y * 0.3, max(v.co.z, 0) * 0.28 + 0.28))
    o = unir([tallo, som], "SetaTurbo")
    suave(o)

    def color(co, n):
        if co.z > 0.3:
            mota = any(Vector((co.x - mx, co.y - my, co.z - mz)).length < 0.1 for mx, my, mz in ((0, 0, 0.56), (0.2, 0, 0.45), (-0.1, 0.17, 0.45), (-0.1, -0.17, 0.45)))
            return lineal("#ffffff") if mota else lineal("#e8322a")
        return lineal("#f6ecd2")
    pintar(o, color)
    return o


proto = [
    edificio("Edificio1", 14, 14, 42, lineal("#2c5f8a"), lineal("#8fd0f0"), lineal("#1c3350"), escalones=1, remate="antena"),
    edificio("Edificio2", 12, 10, 20, lineal("#a0503a"), lineal("#2d3f55"), lineal("#f2e6d0"), remate="deposito"),
    edificio("Edificio3", 12, 12, 28, lineal("#e8dcc0"), lineal("#3f6a8a"), lineal("#ffffff"), remate="deposito"),
    edificio("Edificio4", 10, 16, 34, lineal("#2f8a82"), lineal("#b8f0ea"), lineal("#194a45"), escalones=2, remate="antena"),
    edificio("Edificio5", 9, 9, 12, lineal("#f2c14e"), lineal("#34495e"), lineal("#ffffff"), remate="tejado"),
    farola(), semaforo_calle(), arbol_calle(), valla_publicitaria(),
    palmera("Palmera", 8, 2.0), palmera("Palmera2", 6.5, 1.2), faro(), caseta(), velero(), sombrilla(), roca_playa(),
    arbol_misterio("ArbolMisterio", 3), arbol_misterio("ArbolMisterio2", 9), seta_gigante(), cristales(), ruina(), helecho(), tronco_caido(), farolillo(),
    platano(), caparazon(), seta_turbo(),
]
for o in proto:
    o.location = (0, 0, 0)
    print(f"{o.name}: {len(o.data.polygons)} caras")
bpy.ops.object.select_all(action='DESELECT')
for o in proto:
    o.select_set(True)
bpy.ops.export_scene.gltf(filepath=os.path.abspath("pistas.glb"), export_format='GLB', use_selection=True)
print("Exportado pistas.glb")

if os.environ.get("SIN_RENDER") == "1":
    raise SystemExit

# ---------- MUESTRA DE LOS TRES ESCENARIOS ----------
por = {o.name: o for o in proto}


def copia(nombre, loc, rz=0.0, esc=1.0, color=None):
    o = bpy.data.objects.new(nombre + "_c", por[nombre].data)
    bpy.context.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (0, 0, rz)
    o.scale = (esc,) * 3
    return o


for o in proto:
    o.hide_render = True
# Ciudad a la izquierda, playa en el centro, bosque a la derecha
for k, n in enumerate(["Edificio1", "Edificio2", "Edificio3", "Edificio4", "Edificio5", "Edificio3"]):
    copia(n, (-70 + (k % 3) * 16, 20 + (k // 3) * 18, 0), 0, 0.8)
for k in range(4):
    copia("Farola", (-72 + k * 10, 8, 0))
copia("ArbolCalle", (-60, 6, 0))
copia("Semaforo", (-52, 8, 0))
copia("Faro", (4, 40, 0))
for k in range(5):
    copia("Palmera" if k % 2 else "Palmera2", (-12 + k * 7, 10 + (k % 2) * 6, 0), k)
copia("Velero", (14, 26, -0.6), 0.5)
copia("Caseta", (-4, 22, 0))
copia("Sombrilla", (6, 8, 0))
for k in range(4):
    copia("ArbolMisterio" if k % 2 else "ArbolMisterio2", (40 + k * 9, 20 + (k % 2) * 8, 0), k, 1.0)
for k in range(3):
    copia("SetaGigante", (44 + k * 6, 8, 0), k, 1.2)
copia("Cristales", (62, 10, 0))
copia("Ruina", (52, 30, 0))
copia("Helecho", (38, 6, 0))
copia("Farolillo", (58, 4, 0))
bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 30, 0))
suelo = bpy.context.object
m = bpy.data.materials.new("Suelo")
m.use_nodes = True
m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*lineal("#9aa65c"), 1)
suelo.data.materials.append(m)
bpy.ops.object.camera_add(location=(-2, -40, 12), rotation=(math.radians(78), 0, 0))
bpy.context.scene.camera = bpy.context.object
bpy.context.object.data.lens = 22
bpy.ops.object.light_add(type='SUN', rotation=(math.radians(50), math.radians(15), math.radians(30)))
bpy.context.object.data.energy = 3.5
w = bpy.data.worlds.new("Mundo")
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.75, 0.95, 1)
bpy.context.scene.world = w
esc = bpy.context.scene
esc.render.engine = 'CYCLES'
esc.cycles.samples = int(os.environ.get("MUESTRAS", "48"))
esc.cycles.use_denoising = False
esc.view_settings.view_transform = 'AgX'
esc.view_settings.look = 'AgX - Punchy'
esc.render.resolution_x = 1400
esc.render.resolution_y = 600
esc.render.filepath = os.path.abspath("pistas.png")
bpy.ops.render.render(write_still=True)
