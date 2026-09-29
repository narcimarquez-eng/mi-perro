"""Papá y mamá de Manuel, en estilo de dibujo, con esqueleto y animaciones.

blender -b --factory-startup --python Padres.py

Crea papa.glb, mama.glb y padres.png (vista previa).
Papá: pelo oscuro rizado, barba, chaqueta de cuero marrón y camisa blanca estampada.
Mamá: melena ondulada color miel hasta los hombros, blusa blanca y pendientes rosas de flecos.
"""
import bpy
import bmesh
import math
import os
import random
from mathutils import Matrix, Quaternion, Vector, noise

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.preferences.addon_enable(module="io_scene_gltf2")
random.seed(7)


# ---------- MATERIALES ----------
def lineal(hexa):
    """Color sRGB en hexadecimal -> lineal (lo que usa Blender)."""
    c = [int(hexa[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def material(nombre, hexa, rugosidad=0.6, emision=0.0, metal=0.0):
    mat = bpy.data.materials.new(nombre)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*lineal(hexa), 1.0)
    bsdf.inputs["Roughness"].default_value = rugosidad
    bsdf.inputs["Metallic"].default_value = metal
    if emision:
        bsdf.inputs["Emission Color"].default_value = (*lineal(hexa), 1.0)
        bsdf.inputs["Emission Strength"].default_value = emision
    return mat


def textura_camisa():
    """Camisa blanca con un estampado pequeño oscuro (como la de la foto)."""
    n = 128
    img = bpy.data.images.new("EstampadoCamisa", n, n)
    px = [1.0] * (n * n * 4)
    rnd = random.Random(3)
    for k in range(70):
        cx, cy = rnd.randrange(n), rnd.randrange(n)
        for dy in range(-2, 3):
            for dx in range(-3, 4):
                if (dx / 3.2) ** 2 + (dy / 2.2) ** 2 <= 1:
                    x, y = (cx + dx) % n, (cy + dy) % n
                    i = (y * n + x) * 4
                    px[i:i + 3] = [0.06, 0.07, 0.09]
    img.pixels = px
    img.pack()
    mat = bpy.data.materials.new("Camisa")
    mat.use_nodes = True
    nt = mat.node_tree
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.links.new(tex.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
    nt.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.7
    return mat


M = {
    "blanco_ojo": material("BlancoOjo", "#f7f4ef", 0.3),
    "iris": material("Iris", "#5a3a22", 0.25),
    "pupila": material("Pupila", "#0d0907", 0.2),
    "brillo": material("Brillo", "#ffffff", 0.1, emision=2.0),
    "labios": material("Labios", "#b0605a", 0.45),
    "ceja_oscura": material("CejaOscura", "#1b1410", 0.8),
}


# ---------- UTILIDADES ----------
def activar(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def aplicar_modificadores(obj):
    activar(obj)
    for m in list(obj.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)


def nuevo_objeto(nombre, me):
    obj = bpy.data.objects.new(nombre, me)
    bpy.context.collection.objects.link(obj)
    return obj


def esfera(loc, escala, mat, nombre="esfera", seg=24):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=seg // 2, radius=1.0, location=loc)
    o = bpy.context.object
    o.name = nombre
    o.scale = escala
    o.data.materials.append(mat)
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.object.shade_smooth()
    return o


def rotar(o, rot):
    """Gira la malla alrededor de su centro (las mallas ya tienen la posición aplicada)."""
    from mathutils import Euler
    c = sum((v.co for v in o.data.vertices), Vector()) / len(o.data.vertices)
    o.data.transform(Matrix.Translation(c) @ Euler(rot).to_matrix().to_4x4() @ Matrix.Translation(-c))


def unir(objs, nombre):
    if len(objs) == 1:
        objs[0].name = nombre
        return objs[0]
    activar(objs[0])
    for o in objs[1:]:
        o.select_set(True)
    bpy.ops.object.join()
    o = bpy.context.object
    o.name = nombre
    return o


def dist_segmento(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
    return (p - (a + ab * t)).length


# ---------- PERSONA ----------
def crear_persona(nombre, o):
    """o: medidas y colores. El personaje mira hacia -Y (en la web, hacia +Z)."""
    s = o["escala"]
    P = lambda x, y, z: Vector((x * s, y * s, z * s))
    # Esqueleto del cuerpo (para el modificador Skin): puntos y grosores (ancho, fondo)
    anchoH = o["hombros"]
    puntos = {
        "pelvis": (P(0, 0.0, 0.95), (0.16 * o["caderas"], 0.11)),
        "cintura": (P(0, 0.0, 1.1), (0.135 * o["cintura"], 0.1)),
        "pecho": (P(0, -0.005, 1.3), (0.17 * anchoH, 0.115 * o["pecho"])),
        "hombros": (P(0, 0.0, 1.42), (0.14 * anchoH, 0.08)),
        "cuello": (P(0, 0.005, 1.52), (0.052, 0.052)),
    }
    lados = {}
    for lado, sx in (("L", 1), ("R", -1)):
        lados[lado] = {
            "hombro": (P(sx * 0.19 * anchoH, 0.0, 1.42), (0.062, 0.062)),
            "codo": (P(sx * 0.235 * anchoH, 0.02, 1.13), (0.047, 0.047)),
            "muneca": (P(sx * 0.255 * anchoH, -0.01, 0.88), (0.034, 0.03)),
            "mano": (P(sx * 0.262 * anchoH, -0.015, 0.8), (0.042, 0.025)),
            "cadera": (P(sx * 0.09 * o["caderas"], 0.0, 0.9), (0.085, 0.085)),
            "rodilla": (P(sx * 0.1, -0.01, 0.5), (0.058, 0.058)),
            "tobillo": (P(sx * 0.1, 0.02, 0.09), (0.042, 0.042)),
            "pie": (P(sx * 0.105, -0.13, 0.035), (0.045, 0.03)),
        }
    verts, radios, idx = [], [], {}

    def add(clave, dato):
        idx[clave] = len(verts)
        verts.append(dato[0])
        radios.append((dato[1][0] * s, dato[1][1] * s))

    for k, v in puntos.items():
        add(k, v)
    for lado, d in lados.items():
        for k, v in d.items():
            add(k + lado, v)
    aristas = [(idx["pelvis"], idx["cintura"]), (idx["cintura"], idx["pecho"]), (idx["pecho"], idx["hombros"]),
               (idx["hombros"], idx["cuello"])]
    for l in ("L", "R"):
        aristas += [(idx["hombros"], idx["hombro" + l]), (idx["hombro" + l], idx["codo" + l]),
                    (idx["codo" + l], idx["muneca" + l]), (idx["muneca" + l], idx["mano" + l]),
                    (idx["pelvis"], idx["cadera" + l]), (idx["cadera" + l], idx["rodilla" + l]),
                    (idx["rodilla" + l], idx["tobillo" + l]), (idx["tobillo" + l], idx["pie" + l])]
    me = bpy.data.meshes.new(nombre + "Cuerpo")
    me.from_pydata(verts, aristas, [])
    cuerpo = nuevo_objeto(nombre + "Cuerpo", me)
    skin = cuerpo.modifiers.new("Skin", 'SKIN')
    skin.branch_smoothing = 0.6
    skin.use_smooth_shade = True
    for i, r in enumerate(radios):
        cuerpo.data.skin_vertices[0].data[i].radius = r
    cuerpo.data.skin_vertices[0].data[idx["pelvis"]].use_root = True
    sub = cuerpo.modifiers.new("Sub", 'SUBSURF')
    sub.levels = 2
    aplicar_modificadores(cuerpo)
    activar(cuerpo)
    bpy.ops.object.shade_smooth()

    # Ropa: cada cara del cuerpo toma el material de la prenda que le toca
    mats = o["materiales"]
    for m in ("piel", "arriba", "camisa", "pantalon", "zapato"):
        cuerpo.data.materials.append(mats[m])
    orden = {"piel": 0, "arriba": 1, "camisa": 2, "pantalon": 3, "zapato": 4}
    zCuello = 1.47 * s
    for pol in cuerpo.data.polygons:
        c = pol.center
        ax = abs(c.x)
        if c.z > zCuello:
            m = "piel"
        elif c.z < 0.115 * s:
            m = "zapato"
        elif ax > 0.17 * anchoH * s and c.z > 0.7 * s:  # brazos
            m = "piel" if c.z < o["manga"] * s else "arriba"
        elif c.z < o["cintura_pantalon"] * s:
            m = "pantalon"
        else:
            m = "arriba"
            # Chaqueta abierta: por delante se ve la camisa en una V
            if o.get("chaqueta") and c.y < -0.04 * s and ax < (0.035 + (c.z / s - 0.95) * 0.12) * s:
                m = "camisa"
            # Escote de la blusa
            if o.get("escote") and c.y < -0.04 * s and c.z > 1.4 * s and ax < (c.z / s - 1.4) * 0.9 * s:
                m = "piel"
        pol.material_index = orden[m]
    activar(cuerpo)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.02, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    for l in cuerpo.data.uv_layers.active.data:  # estampado pequeño (la textura se repite)
        l.uv = l.uv * 9.0

    extras_torso = []
    # Cuello de la chaqueta / blusa y solapas
    bpy.ops.mesh.primitive_torus_add(major_radius=0.066 * s, minor_radius=0.018 * s, location=P(0, 0.004, 1.465))
    cuello = bpy.context.object
    cuello.scale = (1.05, 1.0, 1.4)
    cuello.data.materials.append(mats["arriba"])
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.object.shade_smooth()
    extras_torso.append(cuello)
    # Cinturón (tapa la costura entre la ropa de arriba y el pantalón) y puños de las mangas
    def aro_en(z, filtro, grosor, mat, nombre):
        vs = [v.co for v in cuerpo.data.vertices if abs(v.co.z - z) < 0.012 * s and filtro(v.co)]
        if not vs:
            return None
        cx = sum(v.x for v in vs) / len(vs)
        cy = sum(v.y for v in vs) / len(vs)
        rx = max(abs(v.x - cx) for v in vs)
        ry = max(abs(v.y - cy) for v in vs)
        bpy.ops.mesh.primitive_torus_add(major_radius=1.0, minor_radius=grosor / max(rx, ry), major_segments=32, minor_segments=8,
                                         location=(cx, cy, z))
        a = bpy.context.object
        a.name = nombre
        a.scale = (rx + grosor * 0.3, ry + grosor * 0.3, max(rx, ry) * 0.9)
        a.data.materials.append(mat)
        bpy.ops.object.transform_apply(scale=True)
        bpy.ops.object.shade_smooth()
        return a
    cin = aro_en(o["cintura_pantalon"] * s, lambda c: abs(c.x) < 0.2 * s, 0.014 * s, mats["cinturon"], "Cinturon")
    if cin:
        extras_torso.append(cin)
    punos = {}
    for sx, l in ((1, "L"), (-1, "R")):
        p = aro_en(o["manga"] * s, lambda c, sx=sx: c.x * sx > 0.17 * anchoH * s, 0.008 * s, mats["arriba"], "Puno")
        if p:
            punos[l] = p

    # ---------- CABEZA ----------
    hz = 1.635 * s  # centro de la cabeza
    ra, rb, rc = 0.098 * s, 0.108 * s, 0.123 * s  # semiejes (ancho, fondo, alto)
    cabeza = esfera((0, 0, hz), (ra, rb, rc), mats["piel"], "Cabeza", seg=40)
    # Mandíbula un poco más estrecha
    for v in cabeza.data.vertices:
        dz = (v.co.z - hz) / rc
        if dz < 0:
            v.co.x *= 1 - 0.18 * dz * dz
            v.co.y *= 1 - 0.08 * dz * dz
    partes = [cabeza]

    def frente(x, dz, fuera=0.0):
        """Punto de la cara (y negativa) a la altura dz sobre el centro de la cabeza."""
        k = 1 - (x / ra) ** 2 - (dz / rc) ** 2
        return Vector((x, -rb * math.sqrt(max(k, 0.02)) - fuera, hz + dz))

    # Ojos: blanco, iris, pupila y brillo
    for sx in (1, -1):
        c = frente(sx * 0.036 * s, 0.012 * s, -0.012 * s)
        partes.append(esfera(c, (0.017 * s, 0.013 * s, 0.013 * s), M["blanco_ojo"], "Ojo", 16))
        c2 = c + Vector((0, -0.011 * s, 0))
        partes.append(esfera(c2, (0.0085 * s, 0.004 * s, 0.0095 * s), M["iris"], "Iris", 12))
        partes.append(esfera(c2 + Vector((0, -0.0035 * s, 0)), (0.004 * s, 0.002 * s, 0.0045 * s), M["pupila"], "Pupila", 10))
        partes.append(esfera(c2 + Vector((0.003 * s, -0.005 * s, 0.003 * s)), (0.0018 * s,) * 3, M["brillo"], "Brillo", 8))
        # Párpado de arriba (piel) para que la mirada sea tranquila
        partes.append(esfera(c + Vector((0, 0.001, 0.008 * s)), (0.0185 * s, 0.0138 * s, 0.008 * s), mats["piel"], "Parpado", 16))
        # Ceja
        ce = frente(sx * 0.038 * s, 0.038 * s, 0.002 * s)
        ceja = esfera(ce, (0.022 * s, 0.006 * s, 0.0045 * s * o["ceja"]), mats["ceja"], "Ceja", 12)
        rotar(ceja, (0, sx * 0.12, 0))
        partes.append(ceja)
        # Oreja
        oreja = esfera((sx * ra * 0.97, 0.005 * s, hz - 0.005 * s), (0.014 * s, 0.024 * s, 0.03 * s), mats["piel"], "Oreja", 16)
        partes.append(oreja)
    # Nariz
    partes.append(esfera(frente(0, -0.012 * s, -0.004 * s), (0.014 * s, 0.018 * s, 0.024 * s), mats["piel"], "Nariz", 16))
    for sx in (1, -1):
        partes.append(esfera(frente(sx * 0.011 * s, -0.03 * s, -0.004 * s), (0.009 * s, 0.01 * s, 0.008 * s), mats["piel"], "Aleta", 12))
    # Boca sonriente
    centro_boca = frente(0, -0.05 * s, 0.001 * s)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.02 * s, minor_radius=0.0045 * s, major_segments=24, minor_segments=8,
                                     location=centro_boca)
    boca = bpy.context.object
    boca.rotation_euler = (math.pi / 2, 0, 0)
    boca.scale = (1.0, 0.55, 1.0)
    boca.data.materials.append(M["labios"])
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    # solo la mitad de abajo del aro: una sonrisa
    bm = bmesh.new()
    bm.from_mesh(boca.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z > centro_boca.z + 0.002 * s], context='VERTS')
    bm.to_mesh(boca.data)
    bm.free()
    bpy.ops.object.shade_smooth()
    partes.append(boca)

    # Pelo (y barba) de cada uno
    partes += o["pelo"](hz, ra, rb, rc, s, mats, frente)
    cabeza_obj = unir(partes, nombre + "Cabeza")
    torso_obj = unir(extras_torso, nombre + "Extras") if extras_torso else None

    # ---------- ESQUELETO ----------
    bpy.ops.object.armature_add(location=(0, 0, 0))
    arm = bpy.context.object
    arm.name = nombre
    arm.data.name = nombre + "Esqueleto"
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.data.edit_bones
    eb.remove(eb[0])

    def hueso(n, a, b, padre=None):
        h = eb.new(n)
        h.head, h.tail = a, b
        h.roll = 0
        if padre:
            h.parent = eb[padre]
            h.use_connect = False
        return h

    V = lambda k: puntos[k][0] if k in puntos else None
    hueso("raiz", P(0, 0, 0.9), P(0, 0, 1.05))
    hueso("columna", P(0, 0, 1.05), P(0, 0, 1.42), "raiz")
    hueso("cabeza", P(0, 0, 1.47), P(0, 0, 1.78), "columna")
    for l in ("L", "R"):
        d = {k: v[0] for k, v in lados[l].items()}
        hueso("brazo_" + l, d["hombro"], d["codo"], "columna")
        hueso("antebrazo_" + l, d["codo"], d["muneca"], "brazo_" + l)
        hueso("mano_" + l, d["muneca"], d["mano"] + (d["mano"] - d["muneca"]) * 0.6, "antebrazo_" + l)
        hueso("pierna_" + l, d["cadera"], d["rodilla"], "raiz")
        hueso("espinilla_" + l, d["rodilla"], d["tobillo"], "pierna_" + l)
        hueso("pie_" + l, d["tobillo"], d["pie"], "espinilla_" + l)
    bpy.ops.object.mode_set(mode='OBJECT')
    segs = {b.name: (b.head_local.copy(), b.tail_local.copy()) for b in arm.data.bones}

    # Pesos: cada vértice se reparte entre los dos huesos más cercanos de su zona
    grupos = {n: cuerpo.vertex_groups.new(name=n) for n in segs}
    zPelvis, anchoBrazo = 0.93 * s, 0.155 * anchoH * s
    for v in cuerpo.data.vertices:
        p = v.co
        lado = "L" if p.x > 0 else "R"
        if p.z < zPelvis and abs(p.x) < 0.2 * s and p.z < 0.98 * s:
            cand = ["raiz", "pierna_" + lado, "espinilla_" + lado, "pie_" + lado]
        elif abs(p.x) > anchoBrazo and p.z > 0.7 * s and p.z < 1.47 * s:
            cand = ["columna", "brazo_" + lado, "antebrazo_" + lado, "mano_" + lado]
        else:
            cand = ["raiz", "columna", "cabeza"]
        pesos = sorted(((1.0 / (dist_segmento(p, *segs[n]) + 0.01 * s) ** 4, n) for n in cand), reverse=True)[:2]
        tot = sum(w for w, _ in pesos)
        for w, n in pesos:
            grupos[n].add([v.index], w / tot, 'REPLACE')
    for obj, grupo in [(cabeza_obj, "cabeza"), (torso_obj, "columna")] + [(p, "antebrazo_" + l) for l, p in punos.items()]:
        if obj is None:
            continue
        g = obj.vertex_groups.new(name=grupo)
        g.add([v.index for v in obj.data.vertices], 1.0, 'REPLACE')
    malla = unir([cuerpo, cabeza_obj] + ([torso_obj] if torso_obj else []) + list(punos.values()), nombre + "Malla")
    malla.parent = arm
    mod = malla.modifiers.new("Esqueleto", 'ARMATURE')
    mod.object = arm
    return arm, malla


# ---------- PELO ----------
def casquete(hz, ra, rb, rc, s, mat, limite, crecer=1.06, nombre="Casquete"):
    """Copia de la cabeza algo más grande, quedándose con lo que cumple limite(x, y, dz)."""
    o = esfera((0, 0, hz), (ra * crecer, rb * crecer, rc * crecer), mat, nombre, seg=40)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not limite(v.co.x, v.co.y, v.co.z - hz)], context='VERTS')
    bm.to_mesh(o.data)
    bm.free()
    sol = o.modifiers.new("Grosor", 'SOLIDIFY')
    sol.thickness = 0.012 * s
    sol.offset = -1
    aplicar_modificadores(o)
    return o


def pelo_papa(hz, ra, rb, rc, s, mats, frente):
    oscuro = mats["pelo"]
    partes = []
    # Casquete: hasta la frente por delante y más bajo por detrás
    lim = lambda x, y, dz: dz > 0.045 * s - 0.1 * s * max(0.0, min(1.0, (y / rb + 0.2))) - (0.03 * s if abs(x) > 0.07 * s and y > -0.03 * s else 0)
    cas = casquete(hz, ra, rb, rc, s, oscuro, lim, 1.07)
    partes.append(cas)
    # Rizos: bolitas sobre el casquete, más en la parte de arriba (tupé rizado)
    rnd = random.Random(11)
    cand = [v.co.copy() for v in cas.data.vertices]
    rnd.shuffle(cand)
    for co in cand[:170]:
        d = (co - Vector((0, 0, hz)))
        r = (0.017 + rnd.random() * 0.01) * s * (1.25 if d.z > 0.06 * s else 1.0)
        pos = Vector((0, 0, hz)) + d * (1.06 + rnd.random() * 0.06)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=r, location=pos)
        b = bpy.context.object
        b.data.materials.append(oscuro)
        bpy.ops.object.shade_smooth()
        partes.append(b)
    # Barba: la parte de abajo de la cara y las patillas, con hueco para la boca
    def barba(x, y, dz):
        if y > 0.03 * s:
            return False
        if abs(x) < 0.032 * s and -0.065 * s < dz < -0.036 * s and y < 0:
            return False  # boca
        if dz < -0.036 * s:
            return True
        return abs(x) > 0.075 * s and dz < 0.02 * s and y > -0.07 * s  # patillas
    b = casquete(hz, ra, rb, rc, s, oscuro, barba, 1.05, "Barba")
    for v in b.data.vertices:  # un poco de volumen irregular
        v.co += v.co.normalized() * 0.004 * s * noise.noise(v.co * 90)
    for p in b.data.polygons:
        p.use_smooth = True
    partes.append(b)
    # Bigote
    for sx in (1, -1):
        bg = esfera(frente(sx * 0.016 * s, -0.036 * s, 0.009 * s), (0.02 * s, 0.009 * s, 0.007 * s), oscuro, "Bigote", 12)
        rotar(bg, (0, sx * 0.25, 0))
        partes.append(bg)
    return partes


def pelo_mama(hz, ra, rb, rc, s, mats, frente):
    miel = mats["pelo"]
    partes = []
    # Casquete con raya a un lado y el pelo por detrás de las orejas
    lim = lambda x, y, dz: dz > 0.05 * s - 0.03 * s * (x / ra) - 0.14 * s * max(0.0, min(1.0, (y / rb + 0.35)))
    partes.append(casquete(hz, ra, rb, rc, s, miel, lim, 1.08))
    # Melena: una "cortina" ondulada que baja hasta los hombros por los lados y por detrás
    filas, cols = 16, 40
    a0, a1 = math.radians(86), math.radians(274)  # 0 = delante; deja libre la cara
    verts, caras = [], []
    for i in range(filas + 1):
        t = i / filas
        dz = 0.04 * s - t * 0.25 * s
        for j in range(cols + 1):
            ab = a0 - math.radians(30) * t  # por abajo, la melena cae un poco por delante de los hombros
            a = ab + (2 * math.pi - 2 * ab) * j / cols
            k = max(0.0, 1 - (max(dz, -0.06 * s) / rc) ** 2)
            r = math.sqrt(k) * 1.1 + 0.32 * t + 0.045 * math.sin(a * 9 + t * 5) + (0.05 * math.sin(t * math.pi * 1.7) if t > 0.4 else 0)
            # puntas hacia dentro al final (onda)
            if t > 0.85:
                r -= (t - 0.85) * 0.9
            x = math.sin(a) * ra * r
            y = -math.cos(a) * rb * r
            verts.append((x, y, hz + dz))
    for i in range(filas):
        for j in range(cols):
            a = i * (cols + 1) + j
            caras.append((a, a + 1, a + cols + 2, a + cols + 1))
    me = bpy.data.meshes.new("Melena")
    me.from_pydata(verts, [], caras)
    mel = nuevo_objeto("Melena", me)
    mel.data.materials.append(miel)
    sol = mel.modifiers.new("Grosor", 'SOLIDIFY')
    sol.thickness = 0.022 * s
    sub = mel.modifiers.new("Sub", 'SUBSURF')
    sub.levels = 1
    aplicar_modificadores(mel)
    activar(mel)
    bpy.ops.object.shade_smooth()
    partes.append(mel)
    # Mechones ondulados por encima de la melena (textura de ondas)
    rnd = random.Random(5)
    for k in range(26):
        a = math.radians(96 + rnd.random() * 168)
        t = rnd.random()
        dz = 0.02 * s - t * 0.16 * s
        k2 = max(0.0, 1 - (max(dz, -0.06 * s) / rc) ** 2)
        r = math.sqrt(k2) * 1.13 + 0.32 * t + 0.03
        c = Vector((math.sin(a) * ra * r, -math.cos(a) * rb * r, hz + dz))
        m = esfera(c, (0.02 * s, 0.02 * s, 0.05 * s), miel, "Mechon", 12)
        rotar(m, (0, 0, a))
        partes.append(m)
    # Flequillo de lado
    fl = esfera(frente(-0.035 * s, 0.07 * s, 0.006 * s), (0.06 * s, 0.03 * s, 0.022 * s), miel, "Flequillo", 20)
    rotar(fl, (0.2, 0.3, -0.35))
    partes.append(fl)
    # Pendientes rosas de flecos, con una argolla dorada
    for sx in (1, -1):
        base = Vector((sx * ra * 0.99, -0.004 * s, hz - 0.035 * s))
        bpy.ops.mesh.primitive_torus_add(major_radius=0.007 * s, minor_radius=0.0016 * s, location=base - Vector((0, 0, 0.006 * s)))
        ar = bpy.context.object
        rotar(ar, (0, math.pi / 2, 0))
        ar.data.materials.append(mats["oro"])
        partes.append(ar)
        bpy.ops.mesh.primitive_cone_add(vertices=12, radius1=0.011 * s, radius2=0.003 * s, depth=0.05 * s,
                                        location=base - Vector((0, 0, 0.038 * s)))
        fleco = bpy.context.object
        fleco.data.materials.append(mats["rosa"])
        bpy.ops.object.shade_smooth()
        partes.append(fleco)
    return partes


# ---------- LOS DOS ----------
papa, mallaPapa = crear_persona("Papa", {
    "escala": 1.0, "hombros": 1.08, "caderas": 1.0, "cintura": 1.12, "pecho": 1.05, "ceja": 1.4,
    "manga": 0.9, "cintura_pantalon": 0.93, "chaqueta": True,
    "materiales": {
        "piel": material("PielPapa", "#d6a07a", 0.55), "arriba": material("Cuero", "#7a4a2b", 0.38),
        "camisa": textura_camisa(), "pantalon": material("VaqueroOscuro", "#2c3342", 0.8),
        "zapato": material("ZapatoMarron", "#3b2618", 0.5), "pelo": material("PeloOscuro", "#1c1410", 0.75),
        "ceja": material("CejaPapa", "#1c1410", 0.8), "cinturon": material("CinturonPapa", "#2a1a10", 0.4),
    },
    "pelo": pelo_papa,
})
papa.location.x = -0.45
mama, mallaMama = crear_persona("Mama", {
    "escala": 0.93, "hombros": 0.95, "caderas": 1.12, "cintura": 0.92, "pecho": 1.12, "ceja": 1.0,
    "manga": 0.9, "cintura_pantalon": 0.97,
    "materiales": {
        "piel": material("PielMama", "#ecc09e", 0.5), "arriba": material("Blusa", "#f8f6f1", 0.65),
        "camisa": material("Blusa2", "#f8f6f1", 0.65), "pantalon": material("Vaquero", "#5d7fa8", 0.8),
        "zapato": material("Zapatilla", "#f3f1ec", 0.5), "pelo": material("PeloMiel", "#b58150", 0.55),
        "ceja": material("CejaMama", "#6e4a2c", 0.8), "oro": material("Oro", "#d8b25a", 0.3, metal=1.0),
        "rosa": material("Rosa", "#ff5fa2", 0.6), "cinturon": material("CinturonMama", "#8a5a36", 0.4),
    },
    "pelo": pelo_mama,
})
mama.location.x = 0.45


# ---------- ANIMACIONES ----------
FPS = 24
bpy.context.scene.render.fps = FPS


def girar(arm, hueso, eje, ang):
    """Quaternion local de un hueso para girarlo 'ang' alrededor de un eje del mundo (en reposo)."""
    b = arm.data.bones[hueso]
    r = b.matrix_local.to_quaternion()
    return r.inverted() @ Quaternion(eje, ang) @ r


X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))


def animar(arm, nombre, segundos, pose):
    """pose(t) -> {hueso: [(eje, ángulo), ...]} con t en [0, 1); se hace en bucle."""
    accion = bpy.data.actions.new(nombre)
    accion.use_fake_user = True
    arm.animation_data_create()
    arm.animation_data.action = accion
    n = int(segundos * FPS)
    pasos = 16
    for k in range(pasos + 1):
        t = (k % pasos) / pasos
        f = 1 + n * k / pasos
        rot = pose(t)
        for pb in arm.pose.bones:
            pb.rotation_mode = 'QUATERNION'
            q = Quaternion()
            for eje, ang in rot.get(pb.name, []):
                q = girar(arm, pb.name, eje, ang) @ q
            pb.rotation_quaternion = q
            pb.keyframe_insert("rotation_quaternion", frame=f)
    pista = arm.animation_data.nla_tracks.new()
    pista.name = nombre
    pista.strips.new(nombre, 1, accion)
    pista.mute = True
    arm.animation_data.action = None


S2 = lambda t, k=1: math.sin(2 * math.pi * t * k)
brazos_abajo = lambda sx: -0.08 * sx  # los brazos algo separados del cuerpo


def reposo(t):
    return {
        "columna": [(X, 0.02 * S2(t))],
        "cabeza": [(Z, 0.08 * S2(t)), (X, 0.03 * S2(t, 2))],
        "brazo_L": [(Y, 0.03 * S2(t))], "brazo_R": [(Y, -0.03 * S2(t))],
        "antebrazo_L": [(X, -0.12)], "antebrazo_R": [(X, -0.12)],
    }


def hablar(t):
    return {
        "columna": [(X, 0.02 * S2(t)), (Z, 0.05 * S2(t))],
        "cabeza": [(X, 0.07 * S2(t, 2)), (Z, 0.1 * S2(t))],
        "brazo_L": [(X, -0.35 - 0.2 * S2(t)), (Y, -0.15)],
        "antebrazo_L": [(X, -1.1 - 0.3 * S2(t, 2)), (Z, 0.3)],
        "brazo_R": [(X, -0.2 + 0.15 * S2(t)), (Y, 0.1)],
        "antebrazo_R": [(X, -0.9 + 0.35 * S2(t + 0.25, 2)), (Z, -0.3)],
        "mano_L": [(Y, 0.4 * S2(t, 2))], "mano_R": [(Y, -0.4 * S2(t + 0.3, 2))],
    }


def andar(t):
    a = 0.45 * S2(t)
    rod = lambda fase: 0.1 + 0.55 * max(0.0, S2(t + fase))
    return {
        "raiz": [(Z, 0.06 * S2(t))],
        "columna": [(Z, -0.1 * S2(t))],
        "pierna_L": [(X, -a)], "pierna_R": [(X, a)],
        "espinilla_L": [(X, rod(0.25))], "espinilla_R": [(X, rod(0.75))],
        "pie_L": [(X, -0.2 * S2(t + 0.1))], "pie_R": [(X, 0.2 * S2(t + 0.1))],
        "brazo_L": [(X, 0.4 * S2(t))], "brazo_R": [(X, -0.4 * S2(t))],
        "antebrazo_L": [(X, -0.35)], "antebrazo_R": [(X, -0.35)],
    }


def llevar(t):
    # Andando con el plato: brazos hacia delante y las piernas como al andar
    p = andar(t)
    for l in ("L", "R"):
        p["brazo_" + l] = [(X, -0.55)]
        p["antebrazo_" + l] = [(X, -0.95), (Z, 0.35 if l == "L" else -0.35)]
    return p


def saludar(t):
    return {
        "cabeza": [(Z, 0.12 * S2(t)), (X, -0.05)],
        "brazo_R": [(Y, 2.4)],
        "antebrazo_R": [(Y, 0.4 + 0.45 * S2(t, 2))],
        "brazo_L": [(Y, -0.05)],
        "antebrazo_L": [(X, -0.15)],
    }


for arm in (papa, mama):
    animar(arm, "reposo", 4.0, reposo)
    animar(arm, "hablar", 2.0, hablar)
    animar(arm, "andar", 1.1, andar)
    animar(arm, "llevar", 1.1, llevar)
    animar(arm, "saludar", 1.2, saludar)


# ---------- VISTA PREVIA ----------
def pose_foto(arm, nombre, t):
    acc = bpy.data.actions[nombre]
    arm.animation_data.action = acc
    bpy.context.scene.frame_set(int(1 + t * (acc.frame_range[1] - 1)))


pose_foto(papa, "hablar", 0.3)
pose_foto(mama, "saludar", 0.25)
bpy.ops.mesh.primitive_plane_add(size=8, location=(0, 0, 0))
suelo = bpy.context.object
suelo.data.materials.append(material("Suelo", "#b86f4a", 0.8))
if os.environ.get("CERCA") == "1":
    bpy.ops.object.camera_add(location=(0.0, -1.5, 1.6), rotation=(math.radians(90), 0, 0))
else:
    bpy.ops.object.camera_add(location=(0.0, -3.6, 1.1), rotation=(math.radians(88), 0, 0))
camara = bpy.context.object
camara.data.lens = 45
bpy.context.scene.camera = camara
bpy.ops.object.light_add(type='SUN', location=(2, -3, 5), rotation=(math.radians(40), math.radians(15), math.radians(20)))
sol = bpy.context.object
sol.data.energy = 3.5
bpy.ops.object.light_add(type='AREA', location=(-2, -2.5, 2.5))
relleno = bpy.context.object
relleno.data.energy = 250
relleno.data.size = 3
relleno.rotation_euler = (math.radians(50), 0, math.radians(-40))
mundo = bpy.data.worlds.new("Mundo")
mundo.use_nodes = True
mundo.node_tree.nodes["Background"].inputs[0].default_value = (0.8, 0.88, 0.95, 1)
mundo.node_tree.nodes["Background"].inputs[1].default_value = 0.6
bpy.context.scene.world = mundo
escena = bpy.context.scene
escena.render.engine = 'CYCLES'
escena.cycles.samples = int(os.environ.get("MUESTRAS", "96"))
escena.cycles.use_denoising = False
escena.cycles.sample_clamp_indirect = 3.0
escena.view_settings.view_transform = 'AgX'
escena.render.resolution_x = 900
escena.render.resolution_y = 700
escena.render.filepath = os.path.abspath("padres.png")
if os.environ.get("SIN_RENDER") != "1":
    bpy.ops.render.render(write_still=True)

# ---------- EXPORTAR ----------
for arm, malla, archivo in ((papa, mallaPapa, "papa.glb"), (mama, mallaMama, "mama.glb")):
    for a in (papa, mama):
        a.animation_data.action = None
        for pista in a.animation_data.nla_tracks:
            pista.mute = False
    bpy.context.scene.frame_set(1)
    arm.location.x = 0
    bpy.ops.object.select_all(action='DESELECT')
    arm.select_set(True)
    malla.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.export_scene.gltf(
        filepath=os.path.abspath(archivo),
        export_format='GLB',
        use_selection=True,
        export_animation_mode='NLA_TRACKS',
        export_force_sampling=True,
        export_skins=True,
    )
    print("Exportado", archivo)
