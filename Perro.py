import bpy
import math
import os
from mathutils import Vector

# ---------- LIMPIAR ESCENA ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.preferences.addon_enable(module="io_scene_gltf2")

# ---------- MATERIALES ----------
def crear_material(nombre, color, rugosidad=0.6, emision=0.0):
    mat = bpy.data.materials.new(nombre)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = rugosidad
    if emision > 0:
        # El nombre del input cambió en Blender 4.0
        nombre_emision = "Emission Color" if "Emission Color" in bsdf.inputs else "Emission"
        bsdf.inputs[nombre_emision].default_value = (*color, 1.0)
        bsdf.inputs["Emission Strength"].default_value = emision
    return mat

# Colores de un beagle tricolor
marron = crear_material("Marron", (0.42, 0.20, 0.07), 0.7)
negro  = crear_material("Manto",  (0.06, 0.04, 0.03), 0.6)   # Mancha oscura del lomo
claro  = crear_material("Claro",  (0.90, 0.85, 0.76), 0.7)   # Hocico, pecho, patas y punta de la cola
fuego  = crear_material("Fuego",  (0.70, 0.40, 0.14), 0.7)   # Cejas
oscuro = crear_material("Oscuro", (0.02, 0.01, 0.01), 0.25)  # Nariz y pupilas (brillantes)
blanco = crear_material("Blanco", (0.95, 0.95, 0.95), 0.2)   # Blanco de los ojos
brillo = crear_material("Brillo", (1.0, 1.0, 1.0), 0.1, emision=3.0)  # Reflejo en los ojos
lengua = crear_material("Lengua", (0.85, 0.30, 0.35), 0.35)
collar = crear_material("Collar", (0.75, 0.05, 0.05), 0.4)
chapa  = crear_material("Chapa",  (0.95, 0.70, 0.20), 0.2)
chapa.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 1.0
cesped = crear_material("Suelo",  (0.28, 0.45, 0.20), 0.9)

# ---------- HELPERS ----------
def suavizar(obj, niveles=2):
    mod = obj.modifiers.new(name="Subsurf", type='SUBSURF')
    mod.levels = niveles
    mod.render_levels = niveles
    for poly in obj.data.polygons:
        poly.use_smooth = True

def esfera(loc, escala, material, nombre, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=1.0,
                                         location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = nombre
    obj.scale = escala
    obj.data.materials.append(material)
    suavizar(obj)
    return obj

def capsula(p1, p2, r1, r2, material, nombre):
    """Tubo que va de p1 a p2, con radio r1 al principio y r2 al final (extremos redondeados)."""
    p1, p2 = Vector(p1), Vector(p2)
    eje = p2 - p1
    bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=r1, radius2=r2, depth=eje.length,
                                    location=(p1 + p2) / 2)
    obj = bpy.context.object
    obj.name = nombre
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_quaternion = eje.to_track_quat('Z', 'Y')
    obj.data.materials.append(material)
    for poly in obj.data.polygons:
        poly.use_smooth = True
    # Rótulas redondas en los extremos para que las uniones no se vean
    esfera(p1, (r1, r1, r1), material, nombre + "_A")
    esfera(p2, (r2, r2, r2), material, nombre + "_B")
    return obj

def sobre_superficie(centro, radio, direccion, fuera=0.0):
    """Punto sobre una esfera (centro, radio) en la dirección dada."""
    d = Vector(direccion).normalized()
    return Vector(centro) + d * (radio + fuera)

# ---------- CONSTRUYENDO EL PERRO ----------
# El perro mira hacia -Y

# Cuerpo
esfera((0, 0.05, 0.95), (0.48, 0.95, 0.46), marron, "Cuerpo")
# Manto oscuro en el lomo (típico del beagle)
esfera((0, 0.15, 1.08), (0.44, 0.78, 0.36), negro, "Manto")
# Pecho y barriga claros
esfera((0, -0.55, 0.90), (0.40, 0.42, 0.42), claro, "Pecho")
esfera((0, 0.05, 0.78), (0.38, 0.75, 0.32), claro, "Barriga")

# Cuello
capsula((0, -0.60, 1.05), (0, -0.95, 1.40), 0.30, 0.26, marron, "Cuello")

# Collar con chapa
bpy.ops.mesh.primitive_torus_add(major_radius=0.29, minor_radius=0.045,
                                 location=(0, -0.80, 1.24), rotation=(math.radians(-45), 0, 0))
obj = bpy.context.object
obj.name = "Collar"
obj.data.materials.append(collar)
suavizar(obj, 1)
esfera((0, -1.03, 1.08), (0.07, 0.02, 0.07), chapa, "Chapa", rot=(math.radians(-30), 0, 0))

# Cabeza
CABEZA = Vector((0, -1.05, 1.62))
R_CABEZA = 0.38
esfera(CABEZA, (R_CABEZA, R_CABEZA * 1.05, R_CABEZA * 0.95), marron, "Cabeza")
# Franja clara en la frente
esfera(sobre_superficie(CABEZA, R_CABEZA, (0, -1.0, 0.35), -0.05), (0.07, 0.05, 0.20), claro, "Frente",
       rot=(math.radians(-20), 0, 0))

# Hocico, mofletes y mandíbula
esfera((0, -1.48, 1.47), (0.22, 0.30, 0.18), claro, "Hocico")
esfera((-0.10, -1.55, 1.40), (0.12, 0.16, 0.10), claro, "MofleteIzq")
esfera(( 0.10, -1.55, 1.40), (0.12, 0.16, 0.10), claro, "MofleteDer")
esfera((0, -1.44, 1.33), (0.15, 0.22, 0.08), claro, "Mandibula")

# Nariz y lengua
esfera((0, -1.77, 1.52), (0.09, 0.06, 0.065), oscuro, "Nariz")
esfera((0, -1.58, 1.28), (0.07, 0.10, 0.025), lengua, "Lengua", rot=(math.radians(-25), 0, 0))

# Ojos: blanco + pupila + reflejo, colocados justo sobre la superficie de la cabeza
for lado, nombre in ((-1, "Izq"), (1, "Der")):
    direccion = (lado * 0.42, -1.0, 0.38)
    esfera(sobre_superficie(CABEZA, R_CABEZA, direccion, -0.03), (0.075,) * 3, blanco, "Ojo" + nombre)
    esfera(sobre_superficie(CABEZA, R_CABEZA, direccion, 0.015), (0.05,) * 3, oscuro, "Pupila" + nombre)
    esfera(sobre_superficie(CABEZA, R_CABEZA, (lado * 0.36, -1.0, 0.48), 0.05), (0.014,) * 3, brillo, "Reflejo" + nombre)
    # Cejas color fuego (manchas encima de los ojos)
    esfera(sobre_superficie(CABEZA, R_CABEZA, (lado * 0.45, -0.9, 0.80), -0.02), (0.06, 0.04, 0.03),
           fuego, "Ceja" + nombre)

# Orejas largas y caídas, pegadas a los lados de la cabeza
for lado, nombre in ((-1, "Izq"), (1, "Der")):
    esfera((lado * 0.36, -0.98, 1.42), (0.07, 0.20, 0.34), marron, "Oreja" + nombre,
           rot=(math.radians(10), math.radians(lado * -12), 0))

# Patas: muslo + pata + pie
patas = {
    "DelIzq": (-0.24, -0.55),
    "DelDer": ( 0.24, -0.55),
    "TraIzq": (-0.26,  0.62),
    "TraDer": ( 0.26,  0.62),
}
for nombre, (x, y) in patas.items():
    trasera = y > 0
    if trasera:
        # Muslo trasero más grueso y una rodilla ligeramente hacia atrás
        esfera((x, y, 0.80), (0.17, 0.30, 0.30), marron, "Muslo" + nombre)
        capsula((x, y + 0.05, 0.70), (x, y + 0.10, 0.12), 0.12, 0.09, marron, "Pata" + nombre)
    else:
        capsula((x, y, 0.80), (x, y - 0.02, 0.12), 0.12, 0.09, claro, "Pata" + nombre)
    esfera((x, y - 0.06 + (0.10 if trasera else -0.02), 0.07), (0.11, 0.15, 0.07), claro, "Pie" + nombre)

# Cola: curva levantada hacia arriba con la punta blanca
curva = bpy.data.curves.new("Cola", type='CURVE')
curva.dimensions = '3D'
curva.bevel_depth = 0.06
curva.bevel_resolution = 6
curva.use_fill_caps = True
spline = curva.splines.new('BEZIER')
puntos_cola = [(0, 0.90, 1.05), (0, 1.15, 1.35), (0, 1.12, 1.75)]
spline.bezier_points.add(len(puntos_cola) - 1)
for bp, p in zip(spline.bezier_points, puntos_cola):
    bp.co = p
    bp.handle_left_type = bp.handle_right_type = 'AUTO'
spline.bezier_points[0].radius = 1.2
spline.bezier_points[-1].radius = 0.6
cola = bpy.data.objects.new("Cola", curva)
bpy.context.collection.objects.link(cola)
cola.data.materials.append(marron)
# Convertir a malla para que se exporte bien a GLB
bpy.ops.object.select_all(action='DESELECT')
bpy.context.view_layer.objects.active = cola
cola.select_set(True)
bpy.ops.object.convert(target='MESH')
esfera((0, 1.12, 1.78), (0.055, 0.055, 0.09), claro, "PuntaCola")

# ---------- ESCENARIO ----------
bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
suelo = bpy.context.object
suelo.name = "Suelo"
suelo.data.materials.append(cesped)

# Cielo: ilumina la escena de forma suave
mundo = bpy.data.worlds.new("Cielo")
mundo.use_nodes = True
fondo = mundo.node_tree.nodes["Background"]
fondo.inputs["Color"].default_value = (0.55, 0.75, 1.0, 1.0)
fondo.inputs["Strength"].default_value = 0.8
bpy.context.scene.world = mundo

# ---------- CÁMARA Y LUZ ----------
# Un punto invisible en el perro al que siempre mira la cámara
bpy.ops.object.empty_add(location=(0, -0.2, 1.0))
objetivo = bpy.context.object
objetivo.name = "Objetivo"

bpy.ops.object.camera_add(location=(-3.6, -4.6, 2.2))
camara = bpy.context.object
camara.data.lens = 45
seguir = camara.constraints.new(type='TRACK_TO')
seguir.target = objetivo
seguir.track_axis = 'TRACK_NEGATIVE_Z'
seguir.up_axis = 'UP_Y'
bpy.context.scene.camera = camara

# Luz principal (sol cálido) + luz de relleno suave
bpy.ops.object.light_add(type='SUN', rotation=(math.radians(45), math.radians(-20), math.radians(-40)))
sol = bpy.context.object
sol.data.energy = 3.5
sol.data.angle = math.radians(8)  # sombras más suaves
sol.data.color = (1.0, 0.95, 0.85)

bpy.ops.object.light_add(type='AREA', location=(3, -3, 3))
relleno = bpy.context.object
relleno.data.energy = 300
relleno.data.size = 3
relleno.constraints.new(type='TRACK_TO').target = objetivo

# ---------- RENDER (PNG) ----------
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 256
# El Blender de Ubuntu viene sin denoiser (OpenImageDenoise), así que usamos más muestras
scene.cycles.use_denoising = False
scene.cycles.sample_clamp_indirect = 3.0  # quita los "puntitos" de ruido brillantes
if bpy.app.version >= (4, 0, 0):
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Punchy'  # colores más vivos
else:
    scene.view_settings.view_transform = 'Filmic'
scene.render.resolution_x = 1280
scene.render.resolution_y = 960
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = os.path.abspath("perro.png")

bpy.ops.render.render(write_still=True)

# ---------- EXPORTAR A GLB ----------
# El suelo, la cámara y las luces no forman parte del perro
bpy.ops.object.select_all(action='SELECT')
for obj in (suelo, camara, sol, relleno, objetivo):
    obj.select_set(False)
bpy.ops.export_scene.gltf(
    filepath=os.path.abspath("perro.glb"),
    export_format='GLB',
    use_selection=True,
    export_apply=True,  # aplica el suavizado (Subsurf) al modelo exportado
)
print("¡Perro exportado a GLB correctamente!")
