"""Los acompañantes de la historia: los primos Carlos y Miguel y papá vestido de verano.

blender -b --factory-startup --python Primos.py

Usa el creador de personas de Padres.py (personajes de dibujo, sin parecido con nadie real) y exporta
carlos.glb, miguel.glb y papa_verano.glb, y una vista previa (primos.png).
- Carlos: primo de la misma edad que Manuel, algo más alto (unos 5 cm), pelo más rubio y gafas.
- Miguel: primo de 14 años, alto (1,75 m) y con el pelo oscuro.
- Papá de verano: pantalón corto y polo (para el arroyo, el mar, el safari y el parque acuático).
Animaciones: reposo, andar, saludar, hablar, celebrar, sentado (en las atracciones), nadar y las de atletismo de AnimAtletismo.py
(correr, correr_pertiga, agachado, lanzar, saltar y cansado).
"""
import bpy
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
def pelo_flequillo(hz, ra, rb, rc, s, mats, frente):
    """Pelo liso con flequillo hacia un lado (Carlos)."""
    lim = lambda x, y, dz: dz > 0.03 * s - 0.11 * s * max(0.0, min(1.0, (y / rb + 0.25))) - (0.02 * s if abs(x) > 0.075 * s and y > -0.02 * s else 0)
    partes = [P.casquete(hz, ra, rb, rc, s, mats["pelo"], lim, 1.08)]
    for k in range(7):
        x = (k - 3) * 0.022 * s
        m = P.esfera(frente(x, 0.078 * s - abs(k - 1) * 0.003 * s, 0.014 * s), (0.02 * s, 0.016 * s, 0.034 * s), mats["pelo"], "Mecha", 10)
        P.rotar(m, (0.45, 0, -0.35))
        partes.append(m)
    return partes


def gafas(hz, ra, rb, rc, s, mats, frente):
    """Gafas de pasta: dos aros delante de los ojos, el puente y las patillas hasta las orejas."""
    partes = []
    for sx in (1, -1):
        c = frente(sx * 0.036 * s, 0.012 * s, 0.008 * s)
        bpy.ops.mesh.primitive_torus_add(major_radius=0.024 * s, minor_radius=0.0035 * s, major_segments=28, minor_segments=8, location=c)
        aro = bpy.context.object
        aro.rotation_euler = (math.pi / 2, 0, 0)
        aro.scale = (1.0, 1.0, 0.85)
        bpy.ops.object.transform_apply(scale=True, rotation=True)
        bpy.ops.object.shade_smooth()
        aro.data.materials.append(mats["gafas"])
        partes.append(aro)
        # cristal
        cr = P.esfera(c + Vector((0, 0.001, 0)), (0.022 * s, 0.002 * s, 0.019 * s), mats["cristal"], "Cristal", 16)
        partes.append(cr)
        # patilla hacia la oreja
        a = c + Vector((sx * 0.024 * s, 0, 0))
        b = Vector((sx * ra * 1.0, 0.01 * s, hz + 0.012 * s))
        d = b - a
        bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.0028 * s, depth=d.length, location=(a + b) / 2)
        pat = bpy.context.object
        pat.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
        bpy.ops.object.transform_apply(rotation=True)
        pat.data.materials.append(mats["gafas"])
        partes.append(pat)
    pu = P.esfera(frente(0, 0.016 * s, 0.012 * s), (0.012 * s, 0.003 * s, 0.003 * s), mats["gafas"], "Puente", 8)
    partes.append(pu)
    return partes


def pelo_carlos(hz, ra, rb, rc, s, mats, frente):
    return pelo_flequillo(hz, ra, rb, rc, s, mats, frente) + gafas(hz, ra, rb, rc, s, mats, frente)


def pelo_miguel(hz, ra, rb, rc, s, mats, frente):
    """Pelo oscuro corto por los lados y algo más largo y despeinado arriba (Miguel)."""
    lim = lambda x, y, dz: dz > 0.035 * s - 0.1 * s * max(0.0, min(1.0, (y / rb + 0.2))) - (0.025 * s if abs(x) > 0.07 * s and y > -0.03 * s else 0)
    cas = P.casquete(hz, ra, rb, rc, s, mats["pelo"], lim, 1.06)
    partes = [cas]
    rnd = random.Random(21)
    for k in range(26):
        a = rnd.uniform(0, math.pi * 2)
        r = rnd.uniform(0.0, 0.07) * s
        c = Vector((math.cos(a) * r, math.sin(a) * r - 0.02 * s, hz + rc * 0.95 + rnd.uniform(-0.01, 0.012) * s))
        m = P.esfera(c, (0.03 * s, 0.022 * s, 0.022 * s), mats["pelo"], "Mecha", 10)
        P.rotar(m, (rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6), a))
        partes.append(m)
    # tupé hacia delante
    for k in range(4):
        m = P.esfera(frente((k - 1.5) * 0.03 * s, 0.085 * s, 0.018 * s), (0.026 * s, 0.02 * s, 0.03 * s), mats["pelo"], "Tupe", 10)
        P.rotar(m, (0.7, 0, 0))
        partes.append(m)
    return partes


# ---------- ANIMACIONES EXTRA ----------
def celebrar(t):
    return {
        "raiz": [(X, 0.03 * S2(t))],
        "cabeza": [(X, -0.2)],
        "brazo_L": [(Y, -2.6 - 0.2 * S2(t, 2))], "brazo_R": [(Y, 2.6 + 0.2 * S2(t, 2))],
        "antebrazo_L": [(Y, -0.3)], "antebrazo_R": [(Y, 0.3)],
        "pierna_L": [(X, -0.2 * max(0.0, S2(t, 2)))], "pierna_R": [(X, -0.2 * max(0.0, S2(t, 2)))],
    }


def sentado(t):
    # Sentado en una atracción, agarrado a la barra de delante
    return {
        "columna": [(X, 0.08 + 0.02 * S2(t))],
        "cabeza": [(Z, 0.15 * S2(t)), (X, -0.05)],
        "pierna_L": [(X, -1.5)], "pierna_R": [(X, -1.5)],
        "espinilla_L": [(X, 1.3)], "espinilla_R": [(X, 1.3)],
        "brazo_L": [(X, -0.8), (Y, -0.1)], "brazo_R": [(X, -0.8), (Y, 0.1)],
        "antebrazo_L": [(X, -0.5)], "antebrazo_R": [(X, -0.5)],
    }


def nadar(t):
    # Braza: la web tumba al personaje; aquí brazos y piernas se abren y se cierran
    a = S2(t)
    return {
        "cabeza": [(X, -0.5)],
        "brazo_L": [(X, -2.6 + 0.5 * a), (Y, -0.5 - 0.4 * a)], "brazo_R": [(X, -2.6 + 0.5 * a), (Y, 0.5 + 0.4 * a)],
        "antebrazo_L": [(X, -0.3 - 0.3 * max(0.0, a))], "antebrazo_R": [(X, -0.3 - 0.3 * max(0.0, a))],
        "pierna_L": [(X, 0.25 * S2(t + 0.25)), (Y, 0.15)], "pierna_R": [(X, -0.25 * S2(t + 0.25)), (Y, -0.15)],
        "espinilla_L": [(X, 0.4 + 0.3 * S2(t))], "espinilla_R": [(X, 0.4 - 0.3 * S2(t))],
    }


ANIMS = (("reposo", 4.0, P.reposo), ("andar", 1.1, P.andar), ("saludar", 1.2, P.saludar), ("hablar", 2.0, P.hablar),
         ("celebrar", 1.0, celebrar), ("sentado", 3.0, sentado), ("nadar", 1.6, nadar)) + ANIMS_ATLETISMO


def mats(nombre, piel, arriba, pantalon, zapas, pelo, extra=None):
    m = {
        "piel": P.material("Piel" + nombre, piel, 0.5), "arriba": P.material("Arriba" + nombre, arriba, 0.7),
        "camisa": P.material("Camisa" + nombre, arriba, 0.7), "pantalon": P.material("Pantalon" + nombre, pantalon, 0.8),
        "zapato": P.material("Zapas" + nombre, zapas, 0.5), "pelo": P.material("Pelo" + nombre, pelo, 0.6),
        "ceja": P.material("Ceja" + nombre, pelo, 0.8), "cinturon": P.material("Cinturon" + nombre, pantalon, 0.8),
    }
    m.update(extra or {})
    return m


# ---------- LOS TRES ----------
# Manuel mide 1,31 m en la web y la escala 0,67 de los amigos da 1,30 m: Carlos (unos 5 cm más) va a 0,70.
carlos, mallaC = P.crear_persona("Carlos", {
    "escala": 0.70, "hombros": 0.95, "caderas": 1.0, "cintura": 1.05, "pecho": 1.0, "ceja": 1.0,
    "manga": 1.3, "sin_punos": True, "cintura_pantalon": 0.93, "corto": True, "cabeza": 1.55, "grosor": 1.3,
    "materiales": mats("Carlos", "#f2cdb0", "#e8463a", "#2f4f7a", "#ffffff", "#d0a24e",
                       {"gafas": P.material("Gafas", "#1f3a6e", 0.3), "cristal": P.material("Cristal", "#cfe8f5", 0.05)}),
    "pelo": pelo_carlos,
})
# Miguel: 14 años y 1,75 m (papá, a escala 1, mide 1,80 m con el pelo)
miguel, mallaMi = P.crear_persona("Miguel", {
    "escala": 0.955, "hombros": 0.98, "caderas": 0.95, "cintura": 0.95, "pecho": 0.95, "ceja": 1.2,
    "manga": 1.25, "sin_punos": True, "cintura_pantalon": 0.93, "cabeza": 1.08,
    "materiales": mats("Miguel", "#e2b08a", "#2e9a6a", "#3b3f4c", "#f4f4f4", "#1b1512"),
    "pelo": pelo_miguel,
})
papa, mallaP = P.crear_persona("PapaVerano", {
    "escala": 1.0, "hombros": 1.08, "caderas": 1.0, "cintura": 1.12, "pecho": 1.05, "ceja": 1.4,
    "manga": 1.25, "sin_punos": True, "cintura_pantalon": 0.93, "corto": True,
    "materiales": mats("PapaVerano", "#d6a07a", "#24497e", "#c9b48a", "#f1efe8", "#1c1410"),
    "pelo": P.pelo_papa,
})
personas = [(carlos, mallaC, "carlos.glb"), (miguel, mallaMi, "miguel.glb"), (papa, mallaP, "papa_verano.glb")]
for arm, _, _ in personas:
    for nombreA, seg, pose in ANIMS:
        P.animar(arm, nombreA, seg, pose)

# ---------- VISTA PREVIA ----------
if os.environ.get("SIN_RENDER") != "1":
    for i, (arm, malla, _) in enumerate(personas):
        arm.location.x = (i - 1) * 0.85
        pista = [t for t in arm.animation_data.nla_tracks if t.name == ["saludar", "reposo", "hablar"][i]][0]
        arm.animation_data.action = pista.strips[0].action
    bpy.context.scene.frame_set(8)
    bpy.ops.mesh.primitive_plane_add(size=8)
    bpy.context.object.data.materials.append(P.material("Suelo", "#7dbb5a", 0.9))
    bpy.ops.object.camera_add(location=(0, -4.2, 1.1), rotation=(math.radians(86), 0, 0))
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
    esc.cycles.samples = int(os.environ.get("MUESTRAS", "48"))
    esc.cycles.use_denoising = False
    esc.view_settings.view_transform = 'AgX'
    esc.render.resolution_x = 1000
    esc.render.resolution_y = 700
    esc.render.filepath = os.path.abspath(os.environ.get("MUESTRA", "primos.png"))
    bpy.ops.render.render(write_still=True)
    if os.environ.get("CERCA") == "1":
        cam.location = (-0.85, -1.2, 1.25)
        cam.data.lens = 50
        esc.render.filepath = os.path.abspath(os.environ.get("MUESTRA", "primos.png").replace(".png", "_cerca.png"))
        bpy.ops.render.render(write_still=True)

# ---------- EXPORTAR ----------
for arm, malla, archivo in personas:
    for a, _, _ in personas:
        a.animation_data.action = None
        for pista in a.animation_data.nla_tracks:
            pista.mute = False
    bpy.context.scene.frame_set(1)
    arm.location.x = 0
    bpy.ops.object.select_all(action='DESELECT')
    arm.select_set(True)
    malla.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.export_scene.gltf(filepath=os.path.abspath(os.path.join("web", archivo)), export_format='GLB', use_selection=True,
                              export_animation_mode='NLA_TRACKS', export_force_sampling=True, export_skins=True)
    print("Exportado", archivo)
