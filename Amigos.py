"""Los amigos de Manuel en el circuito de karts: cuatro niños de dibujo con esqueleto, animaciones y casco.

blender -b --factory-startup --python Amigos.py

Usa el creador de personas de Padres.py (con la cabeza más grande, como los niños) y exporta
amigo1.glb ... amigo4.glb y una vista previa (amigos.png).
Cada niño lleva su casco como una malla aparte ("Casco"), que la web enseña al subir al kart.
Animaciones: reposo, saludar, conducir (sentado con las manos en el volante), celebrar, andar y las de atletismo
de AnimAtletismo.py (correr, agachado, lanzar, saltar y cansado). Se ejecuta desde la carpeta web/ (exporta ahí).
"""
import bpy
import bmesh
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import Padres as P  # noqa: E402  (crea la escena vacía y trae crear_persona y las animaciones)
from AnimAtletismo import ANIMS_ATLETISMO  # noqa: E402
from mathutils import Vector  # noqa: E402

X, Y, Z, S2 = P.X, P.Y, P.Z, P.S2


# ---------- PEINADOS ----------
def pelo_rizos(hz, ra, rb, rc, s, mats, frente):
    lim = lambda x, y, dz: dz > 0.04 * s - 0.09 * s * max(0.0, min(1.0, (y / rb + 0.2)))
    cas = P.casquete(hz, ra, rb, rc, s, mats["pelo"], lim, 1.07)
    partes = [cas]
    rnd = random.Random(13)
    cand = [v.co.copy() for v in cas.data.vertices]
    rnd.shuffle(cand)
    for co in cand[:120]:
        d = co - Vector((0, 0, hz))
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=(0.018 + rnd.random() * 0.01) * s, location=Vector((0, 0, hz)) + d * (1.05 + rnd.random() * 0.06))
        b = bpy.context.object
        b.data.materials.append(mats["pelo"])
        bpy.ops.object.shade_smooth()
        partes.append(b)
    return partes


def pelo_coleta(hz, ra, rb, rc, s, mats, frente):
    lim = lambda x, y, dz: dz > 0.05 * s - 0.03 * s * (x / ra) - 0.16 * s * max(0.0, min(1.0, (y / rb + 0.35)))
    partes = [P.casquete(hz, ra, rb, rc, s, mats["pelo"], lim, 1.07)]
    # Coleta alta que cae por detrás, con un lazo
    for k in range(6):
        t = k / 5
        c = Vector((0, rb * (1.05 + 0.25 * t), hz + rc * (0.55 - 0.9 * t)))
        partes.append(P.esfera(c, ((0.045 - 0.015 * t) * s, (0.045 - 0.015 * t) * s, 0.05 * s), mats["pelo"], "Coleta", 14))
    lazo = P.esfera(Vector((0, rb * 1.02, hz + rc * 0.62)), (0.05 * s, 0.02 * s, 0.03 * s), mats["lazo"], "Lazo", 14)
    partes.append(lazo)
    return partes


def pelo_media(hz, ra, rb, rc, s, mats, frente):
    lim = lambda x, y, dz: dz > 0.05 * s - 0.14 * s * max(0.0, min(1.0, (y / rb + 0.35)))
    partes = [P.casquete(hz, ra, rb, rc, s, mats["pelo"], lim, 1.08)]
    # Media melena lisa hasta la barbilla, con flequillo recto
    for k in range(18):
        a = math.radians(80 + k * 11.2)
        c = Vector((math.sin(a) * ra * 1.08, -math.cos(a) * rb * 1.08, hz - 0.02 * s))
        m = P.esfera(c, (0.035 * s, 0.035 * s, 0.075 * s), mats["pelo"], "Melena", 12)
        partes.append(m)
    fl = P.esfera(frente(0, 0.07 * s, 0.008 * s), (0.08 * s, 0.03 * s, 0.03 * s), mats["pelo"], "Flequillo", 16)
    partes.append(fl)
    return partes


def pelo_corto_limpio(hz, ra, rb, rc, s, mats, frente):
    lim = lambda x, y, dz: dz > 0.035 * s - 0.1 * s * max(0.0, min(1.0, (y / rb + 0.2))) - (0.02 * s if abs(x) > 0.07 * s and y > -0.03 * s else 0)
    partes = [P.casquete(hz, ra, rb, rc, s, mats["pelo"], lim, 1.07)]
    for k in range(5):
        x = (k - 2) * 0.028 * s
        m = P.esfera(frente(x, 0.085 * s, 0.012 * s), (0.02 * s, 0.018 * s, 0.03 * s), mats["pelo"], "Punta", 10)
        P.rotar(m, (0.5, 0, 0))
        partes.append(m)
    return partes


# ---------- CASCO (se ve al conducir) ----------
def casco(arm, color, s, k_cabeza):
    hz = 1.635 * s + 0.11 * s * (k_cabeza - 1)
    sc = s * k_cabeza
    ra, rb, rc = 0.098 * sc * 1.32, 0.108 * sc * 1.3, 0.123 * sc * 1.18
    centro = Vector((0, 0, hz + 0.012 * sc))

    def esfera_recortada(nombre, borrar, escala, desplaza=Vector()):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=1.0)
        o = bpy.context.object
        o.name = nombre
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if borrar(v.co)], context='VERTS')
        bm.to_mesh(o.data)
        bm.free()
        for v in o.data.vertices:
            v.co = Vector((v.co.x * escala[0], v.co.y * escala[1], v.co.z * escala[2])) + centro + desplaza
        for p in o.data.polygons:
            p.use_smooth = True
        return o
    # Carcasa: abierta por abajo y con el hueco de la cara (mira hacia -Y)
    c = esfera_recortada("Carcasa", lambda q: q.z < -0.5 or (q.y < -0.35 and -0.5 < q.z < 0.3 and abs(q.x) < 0.72), (ra, rb, rc))
    so = c.modifiers.new("G", 'SOLIDIFY')
    so.thickness = 0.02 * sc
    P.aplicar_modificadores(c)
    c.data.materials.append(P.material("Casco" + color, color, 0.25))
    # Visera oscura delante del hueco
    v = esfera_recortada("Visera", lambda q: q.y > -0.3 or q.z < -0.45 or q.z > 0.35 or abs(q.x) > 0.8, (ra * 1.02, rb * 1.04, rc * 1.02))
    v.data.materials.append(P.material("Visera", "#1b2a3a", 0.05, metal=0.3))
    # Franja blanca de delante a atrás
    f = esfera_recortada("Franja", lambda q: abs(q.x) > 0.12 or q.z < 0.3, (ra * 1.01, rb * 1.01, rc * 1.01))
    f.data.materials.append(P.material("Franja", "#ffffff", 0.3))
    o = P.unir([c, v, f], arm.name + "Casco")
    o.name = "Casco"
    g = o.vertex_groups.new(name="cabeza")
    g.add([q.index for q in o.data.vertices], 1.0, 'REPLACE')
    o.parent = arm
    m = o.modifiers.new("Esqueleto", 'ARMATURE')
    m.object = arm
    return o


# ---------- LOS CUATRO AMIGOS ----------
AMIGOS = [
    # nombre, piel, camiseta, pantalón, zapatillas, pelo, peinado, casco
    ("Lucia", "#f0c4a0", "#ff5a8a", "#3a5fa8", "#ffffff", "#6b3f22", pelo_coleta, "#ff4f8b", 0.64),
    ("Hugo", "#e8b48e", "#2f9e5a", "#2c3342", "#f24b3a", "#2a1a10", pelo_corto_limpio, "#29b35a", 0.67),
    ("Martina", "#c98b62", "#ffc629", "#6a4fb0", "#ffffff", "#1c1410", pelo_media, "#ffb400", 0.65),
    ("Leo", "#f3d0b0", "#2a8ad8", "#e8e2d0", "#2c2c2c", "#c98a3a", pelo_rizos, "#2a7ae0", 0.66),
]
K_CABEZA = 1.55


def conducir(t):
    # Sentado en el kart: piernas estiradas hacia delante y manos en el volante
    return {
        "columna": [(X, 0.12 + 0.01 * S2(t))],
        "cabeza": [(X, -0.1), (Z, 0.05 * S2(t))],
        "pierna_L": [(X, -1.45)], "pierna_R": [(X, -1.45)],
        "espinilla_L": [(X, 0.35)], "espinilla_R": [(X, 0.35)],
        "brazo_L": [(X, -0.95), (Y, -0.12)], "brazo_R": [(X, -0.95), (Y, 0.12)],
        "antebrazo_L": [(X, -0.55), (Z, 0.25)], "antebrazo_R": [(X, -0.55), (Z, -0.25)],
    }


def celebrar(t):
    # Salta con los brazos arriba
    return {
        "raiz": [(X, 0.03 * S2(t))],
        "cabeza": [(X, -0.2)],
        "brazo_L": [(Y, -2.6 - 0.2 * S2(t, 2))], "brazo_R": [(Y, 2.6 + 0.2 * S2(t, 2))],
        "antebrazo_L": [(Y, -0.3)], "antebrazo_R": [(Y, 0.3)],
        "pierna_L": [(X, -0.2 * max(0.0, S2(t, 2)))], "pierna_R": [(X, -0.2 * max(0.0, S2(t, 2)))],
    }


personas = []
for i, (nombre, piel, camiseta, pantalon, zapas, pelo, peinado, color_casco, esc) in enumerate(AMIGOS):
    arm, malla = P.crear_persona(nombre, {
        "escala": esc, "hombros": 0.95, "caderas": 1.0, "cintura": 1.05, "pecho": 1.0, "ceja": 1.0,
        "manga": 1.3, "cintura_pantalon": 0.93, "corto": True, "cabeza": K_CABEZA, "grosor": 1.3,
        "materiales": {
            "piel": P.material("Piel" + nombre, piel, 0.5), "arriba": P.material("Camiseta" + nombre, camiseta, 0.7),
            "camisa": P.material("Camiseta2" + nombre, camiseta, 0.7), "pantalon": P.material("Pantalon" + nombre, pantalon, 0.8),
            "zapato": P.material("Zapas" + nombre, zapas, 0.5), "pelo": P.material("Pelo" + nombre, pelo, 0.6),
            "ceja": P.material("Ceja" + nombre, pelo, 0.8), "cinturon": P.material("Cinturon" + nombre, pantalon, 0.8),
            "lazo": P.material("Lazo" + nombre, "#ff4f8b", 0.5), "oro": P.material("Oro" + nombre, "#d8b25a", 0.3, metal=1.0),
            "rosa": P.material("Rosa" + nombre, "#ff5fa2", 0.6),
        },
        "pelo": peinado,
    })
    c = casco(arm, color_casco, esc, K_CABEZA)
    for nombreA, seg, pose in (("reposo", 4.0, P.reposo), ("saludar", 1.2, P.saludar), ("conducir", 2.0, conducir),
                               ("celebrar", 1.0, celebrar), ("andar", 1.0, P.andar)) + ANIMS_ATLETISMO:
        P.animar(arm, nombreA, seg, pose)
    personas.append((arm, malla, c))

# ---------- VISTA PREVIA ----------
for i, (arm, malla, c) in enumerate(personas):
    arm.location.x = (i - 1.5) * 0.75
for i, (arm, malla, c) in enumerate(personas):
    nombreA = ["saludar", "reposo", "celebrar", "saludar"][i]
    # cada niño tiene su acción (Blender añade .001, .002...): buscamos la de su pista NLA
    pista = [t for t in arm.animation_data.nla_tracks if t.name == nombreA][0]
    arm.animation_data.action = pista.strips[0].action
    c.hide_render = i != 2  # uno con el casco puesto
bpy.context.scene.frame_set(8)
bpy.ops.mesh.primitive_plane_add(size=8)
bpy.context.object.data.materials.append(P.material("Suelo", "#7dbb5a", 0.9))
bpy.ops.object.camera_add(location=(0, -3.4, 0.95), rotation=(math.radians(84), 0, 0))
cam = bpy.context.object
cam.data.lens = 40
bpy.context.scene.camera = cam
bpy.ops.object.light_add(type='SUN', rotation=(math.radians(40), math.radians(15), math.radians(20)))
bpy.context.object.data.energy = 3.5
bpy.ops.object.light_add(type='AREA', location=(-2, -2.5, 2.5))
bpy.context.object.data.energy = 200
bpy.context.object.data.size = 3
bpy.context.object.rotation_euler = (math.radians(50), 0, math.radians(-40))
mundo = bpy.data.worlds.new("Mundo")
mundo.use_nodes = True
mundo.node_tree.nodes["Background"].inputs[0].default_value = (0.75, 0.87, 0.96, 1)
bpy.context.scene.world = mundo
esc = bpy.context.scene
esc.render.engine = 'CYCLES'
esc.cycles.samples = int(os.environ.get("MUESTRAS", "64"))
esc.cycles.use_denoising = False
esc.view_settings.view_transform = 'AgX'
esc.render.resolution_x = 1000
esc.render.resolution_y = 600
esc.render.filepath = os.path.abspath("amigos.png")
if os.environ.get("SIN_RENDER") != "1":
    bpy.ops.render.render(write_still=True)

# ---------- EXPORTAR ----------
for i, (arm, malla, c) in enumerate(personas):
    for a, _, cc in personas:
        a.animation_data.action = None
        for pista in a.animation_data.nla_tracks:
            pista.mute = False
        cc.hide_render = False
    bpy.context.scene.frame_set(1)
    arm.location.x = 0
    bpy.ops.object.select_all(action='DESELECT')
    for o in (arm, malla, c):
        o.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.export_scene.gltf(filepath=os.path.abspath(f"amigo{i + 1}.glb"), export_format='GLB', use_selection=True,
                              export_animation_mode='NLA_TRACKS', export_force_sampling=True, export_skins=True)
    print("Exportado", f"amigo{i + 1}.glb")
