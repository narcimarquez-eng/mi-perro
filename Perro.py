import bpy
import math
import os
from mathutils import Quaternion, Vector, noise

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

# Colores de un bretón español: blanco y negro, con moteado ("roano") y ojos color miel
pelaje = bpy.data.materials.new("Pelaje")  # el color de cada zona va pintado en la malla (ver pintar_pelaje)
pelaje.use_nodes = True
_bsdf = pelaje.node_tree.nodes["Principled BSDF"]
_col = pelaje.node_tree.nodes.new("ShaderNodeVertexColor")
_col.layer_name = "Col"
pelaje.node_tree.links.new(_col.outputs["Color"], _bsdf.inputs["Base Color"])
_bsdf.inputs["Roughness"].default_value = 0.75
if "Sheen Weight" in _bsdf.inputs:
    _bsdf.inputs["Sheen Weight"].default_value = 0.15  # un poco de brillo aterciopelado de pelo

oscuro = crear_material("Oscuro", (0.02, 0.01, 0.01), 0.25)  # Nariz y pupilas (brillantes)
miel   = crear_material("Miel",   (0.62, 0.33, 0.07), 0.15)  # Iris color miel
brillo = crear_material("Brillo", (1.0, 1.0, 1.0), 0.1, emision=3.0)  # Reflejo en los ojos
lengua = crear_material("Lengua", (0.85, 0.36, 0.42), 0.35)
boca   = crear_material("Boca",   (0.35, 0.08, 0.10), 0.5)
diente = crear_material("Diente", (0.95, 0.93, 0.86), 0.25)
collar = crear_material("Collar", (0.62, 0.55, 0.80), 0.5)   # lila
chapa  = crear_material("Chapa",  (0.55, 0.88, 0.55), 0.3)   # hueso verde
cesped = crear_material("Suelo",  (0.28, 0.45, 0.20), 0.9)

# ---------- HELPERS ----------
def suavizar(obj, niveles=2):
    mod = obj.modifiers.new(name="Subsurf", type='SUBSURF')
    mod.levels = 0               # lo que se exporta al GLB: ligero para que cargue rápido en la web
    mod.render_levels = niveles  # lo que sale en el render: bien suave
    for poly in obj.data.polygons:
        poly.use_smooth = True

def esfera(loc, escala, material, nombre, rot=(0, 0, 0), segmentos=32):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segmentos, ring_count=segmentos // 2, radius=1.0,
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

def mechon(base, direccion, largo, grosor, nombre, curva=0.0):
    """Mechón de pelo: elipsoide alargado que cuelga desde 'base' en la dirección indicada."""
    d = Vector(direccion).normalized()
    centro = Vector(base) + d * largo / 2
    obj = esfera(centro, (grosor, grosor * 0.7, largo / 2), pelaje, nombre, segmentos=16)
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_quaternion = d.to_track_quat('Z', 'Y') @ Quaternion((1, 0, 0), curva)
    return obj

def sobre_superficie(centro, radio, direccion, fuera=0.0):
    """Punto sobre una esfera (centro, radio) en la dirección dada."""
    d = Vector(direccion).normalized()
    return Vector(centro) + d * (radio + fuera)

def sobre_elipsoide(centro, radios, direccion, fuera=0.0):
    """Punto sobre un elipsoide (centro, radios) en la dirección dada."""
    d = Vector(direccion).normalized()
    t = 1.0 / math.sqrt(sum((d[i] / radios[i]) ** 2 for i in range(3)))
    return Vector(centro) + d * (t + fuera)

def smoothstep(a, b, v):
    t = min(max((v - a) / (b - a), 0.0), 1.0)
    return t * t * (3 - 2 * t)

NEGRO = Vector((0.012, 0.010, 0.010))
BLANCO = Vector((0.80, 0.79, 0.76))
MARRON = Vector((0.09, 0.045, 0.025))
GRIS = Vector((0.30, 0.29, 0.28))

CUELLO_A, CUELLO_B = Vector((0, -0.60, 1.08)), Vector((0, -0.95, 1.40))

def color_pelaje(p, pieza):
    """Color del pelo en cada punto (coordenadas del mundo; el perro mira hacia -Y)."""
    x, y, z = p
    if pieza.startswith(("Oreja", "CabOreja")):
        # Orejas negras con las puntas del pelo tirando a marrón
        return NEGRO.lerp(MARRON, smoothstep(1.45, 1.0, z) * 0.9)
    if pieza.startswith(("Cabeza", "Frente", "Ceja", "CabPelo")):
        return NEGRO.copy()
    if pieza.startswith(("Hocico", "Moflete", "Mandibula")):
        # Hocico negro moteado de blanco; más claro hacia la barbilla
        motas = smoothstep(0.30, 0.55, noise.noise(p * 38.0))
        claro = 0.35 + 0.45 * smoothstep(1.50, 1.33, z)
        zona = smoothstep(-1.32, -1.45, y)
        return NEGRO.lerp(BLANCO, motas * claro * zona)
    c = BLANCO.copy()
    if pieza.startswith("Cuello"):
        # La nuca es negra (sigue a la cabeza); la garganta, blanca
        t = min(max((y - CUELLO_A.y) / (CUELLO_B.y - CUELLO_A.y), 0.0), 1.0)
        eje_z = CUELLO_A.z + (CUELLO_B.z - CUELLO_A.z) * t
        c = c.lerp(NEGRO, smoothstep(0.0, 0.08, z - eje_z + 0.05 * t))
        return c
    # Manchas negras de bordes irregulares en el cuerpo
    ruido = noise.noise(p * 3.0)
    manchas = [((-0.40, -0.30, 1.00), 0.34), ((0.0, 0.55, 1.22), 0.42), ((0.42, 0.25, 0.98), 0.28),
               ((0.0, 1.05, 1.15), 0.22)]
    negro = 0.0
    for centro, radio in manchas:
        d = (p - Vector(centro)).length + ruido * 0.12
        negro = max(negro, smoothstep(radio + 0.05, radio - 0.05, d))
    c = c.lerp(NEGRO, negro)
    # Moteado suave en lo blanco, sobre todo en las patas
    motas = smoothstep(0.35, 0.6, noise.noise(p * 11.0)) * (0.55 if z < 0.75 else 0.3)
    return c.lerp(GRIS, motas * (1 - negro))

def pintar_pelaje():
    """Pinta los colores del pelaje en los vértices de todas las piezas de pelo."""
    bpy.context.view_layer.update()
    for obj in bpy.data.objects:
        if obj.type != 'MESH' or not obj.data.materials or obj.data.materials[0] != pelaje:
            continue
        attr = obj.data.color_attributes.new("Col", 'FLOAT_COLOR', 'POINT')
        for v in obj.data.vertices:
            c = color_pelaje(obj.matrix_world @ v.co, obj.name)
            attr.data[v.index].color = (*c, 1.0)

def densificar(obj, niveles=2):
    """Más vértices donde hay motas o manchas, para que el color no quede en escalones."""
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    mod = obj.modifiers.new("Densidad", 'SUBSURF')
    mod.levels = niveles
    bpy.ops.object.modifier_move_to_index(modifier="Densidad", index=0)
    bpy.ops.object.modifier_apply(modifier="Densidad")

# ---------- CONSTRUYENDO EL PERRO ----------
# El perro mira hacia -Y. Las articulaciones están donde las espera web/index.html:
# patas delanteras (±0.24, -0.55, 0.80), traseras (±0.26, 0.67, 0.70), cola (0, 0.90, 1.05), cuello (0, -0.95, 1.40)

# Cuerpo: más estilizado que el del beagle
esfera((0, 0.05, 0.98), (0.42, 0.95, 0.43), pelaje, "Cuerpo")
esfera((0, -0.55, 0.92), (0.38, 0.40, 0.44), pelaje, "Pecho")
esfera((0, 0.10, 0.80), (0.34, 0.70, 0.28), pelaje, "Barriga")

# Cuello
capsula((0, -0.60, 1.08), (0, -0.95, 1.40), 0.28, 0.24, pelaje, "Cuello")

# Collar lila con la chapa verde en forma de hueso (sin el número de teléfono)
bpy.ops.mesh.primitive_torus_add(major_radius=0.27, minor_radius=0.04,
                                 location=(0, -0.80, 1.25), rotation=(math.radians(-45), 0, 0))
obj = bpy.context.object
obj.name = "Collar"
obj.data.materials.append(collar)
suavizar(obj, 1)
CHAPA = Vector((0, -1.02, 1.04))
esfera(CHAPA, (0.055, 0.012, 0.025), chapa, "Chapa")
for lx in (-1, 1):
    for lz in (-1, 1):
        esfera(CHAPA + Vector((lx * 0.055, 0, lz * 0.022)), (0.025, 0.012, 0.025), chapa, f"ChapaBola_{lx}_{lz}")

# Cabeza: más alargada que la del beagle
CABEZA = Vector((0, -1.08, 1.66))
R_CABEZA = 0.33
RADIOS_CABEZA = (R_CABEZA, R_CABEZA * 1.25, R_CABEZA * 0.95)
cabeza = esfera(CABEZA, RADIOS_CABEZA, pelaje, "Cabeza")
esfera(sobre_superficie(CABEZA, R_CABEZA, (0, -1.0, 0.25), -0.08), (0.10, 0.10, 0.12), pelaje, "Frente")

# Hocico largo, boca abierta "sonriendo"
hocico = esfera((0, -1.50, 1.54), (0.18, 0.34, 0.16), pelaje, "Hocico")
esfera((-0.11, -1.46, 1.46), (0.10, 0.20, 0.09), pelaje, "MofleteIzq")
esfera(( 0.11, -1.46, 1.46), (0.10, 0.20, 0.09), pelaje, "MofleteDer")
mandibula = esfera((0, -1.46, 1.33), (0.13, 0.27, 0.055), pelaje, "Mandibula", rot=(math.radians(8), 0, 0))
esfera((0, -1.47, 1.40), (0.12, 0.25, 0.06), boca, "CabBoca")
esfera((0, -1.55, 1.39), (0.08, 0.17, 0.03), lengua, "Lengua", rot=(math.radians(6), 0, 0))
for lado in (-1, 1):
    # Colmillos arriba y abajo
    bpy.ops.mesh.primitive_cone_add(vertices=8, radius1=0.018, radius2=0.002, depth=0.06,
                                    location=(lado * 0.085, -1.68, 1.44), rotation=(math.pi, 0, 0))
    obj = bpy.context.object
    obj.name = f"CabColmillo_{lado}"
    obj.data.materials.append(diente)
    for k in range(3):
        esfera((lado * (0.02 + k * 0.022), -1.71 + k * 0.012, 1.375), (0.011, 0.011, 0.014), diente,
               f"CabDiente_{lado}_{k}", segmentos=8)

# Nariz grande y negra
esfera((0, -1.85, 1.58), (0.105, 0.075, 0.08), oscuro, "Nariz")

# Ojos color miel: iris + pupila + reflejo
for lado, nombre in ((-1, "Izq"), (1, "Der")):
    direccion = (lado * 0.62, -1.0, 0.42)
    esfera(sobre_elipsoide(CABEZA, RADIOS_CABEZA, direccion, -0.035), (0.062, 0.045, 0.055), miel, "Ojo" + nombre)
    esfera(sobre_elipsoide(CABEZA, RADIOS_CABEZA, direccion, -0.002), (0.026,) * 3, oscuro, "Pupila" + nombre)
    esfera(sobre_elipsoide(CABEZA, RADIOS_CABEZA, (lado * 0.56, -1.0, 0.52), 0.012), (0.011,) * 3, brillo, "Reflejo" + nombre)
    # Cejas: pequeño relieve negro encima de cada ojo
    esfera(sobre_elipsoide(CABEZA, RADIOS_CABEZA, (lado * 0.6, -0.9, 0.8), -0.03), (0.07, 0.05, 0.035),
           pelaje, "Ceja" + nombre)

# Orejas largas, caídas y con flecos ondulados
for lado, nombre in ((-1, "Izq"), (1, "Der")):
    x = lado * 0.31
    esfera((x, -1.00, 1.44), (0.07, 0.21, 0.32), pelaje, "Oreja" + nombre,
           rot=(math.radians(8), math.radians(lado * -10), 0))
    for k in range(6):
        y = -1.12 + k * 0.05
        mechon((x + lado * 0.02, y, 1.36 + 0.03 * math.sin(k * 1.7)),
               (lado * 0.12, 0.05 * math.sin(k), -1.0), 0.30 + 0.05 * math.sin(k * 2.3), 0.035,
               f"CabOreja{nombre}_{k}", curva=0.25 * math.sin(k * 1.3))

# Patas: muslo + pata + pie, con flecos detrás de las delanteras
patas = {
    "DelIzq": (-0.24, -0.55),
    "DelDer": ( 0.24, -0.55),
    "TraIzq": (-0.26,  0.62),
    "TraDer": ( 0.26,  0.62),
}
for nombre, (x, y) in patas.items():
    trasera = y > 0
    if trasera:
        esfera((x, y, 0.82), (0.16, 0.30, 0.30), pelaje, "Muslo" + nombre)
        capsula((x, y + 0.05, 0.70), (x, y + 0.10, 0.12), 0.11, 0.08, pelaje, "Pata" + nombre)
    else:
        capsula((x, y, 0.80), (x, y - 0.02, 0.12), 0.11, 0.08, pelaje, "Pata" + nombre)
        for k in range(3):
            mechon((x, y + 0.08, 0.62 - k * 0.12), (0, 0.6, -1.0), 0.16, 0.035, f"Pata{nombre}_Fleco{k}")
    esfera((x, y - 0.06 + (0.10 if trasera else -0.02), 0.07), (0.10, 0.14, 0.07), pelaje, "Pie" + nombre)

# Cola corta y con flecos (el bretón suele tenerla corta)
curva = bpy.data.curves.new("Cola", type='CURVE')
curva.dimensions = '3D'
curva.bevel_depth = 0.06
curva.bevel_resolution = 6
curva.use_fill_caps = True
spline = curva.splines.new('BEZIER')
puntos_cola = [(0, 0.90, 1.05), (0, 1.12, 1.22), (0, 1.25, 1.38)]
spline.bezier_points.add(len(puntos_cola) - 1)
for bp, p in zip(spline.bezier_points, puntos_cola):
    bp.co = p
    bp.handle_left_type = bp.handle_right_type = 'AUTO'
spline.bezier_points[0].radius = 1.3
spline.bezier_points[-1].radius = 0.8
cola = bpy.data.objects.new("Cola", curva)
bpy.context.collection.objects.link(cola)
cola.data.materials.append(pelaje)
bpy.ops.object.select_all(action='DESELECT')
bpy.context.view_layer.objects.active = cola
cola.select_set(True)
bpy.ops.object.convert(target='MESH')
for poly in cola.data.polygons:
    poly.use_smooth = True
mechon((0, 1.24, 1.37), (0, 0.8, 0.3), 0.26, 0.06, "PuntaCola")

# Más vértices en la cabeza y el hocico para que se vea el moteado, y pintar todo el pelaje
for obj in (hocico, mandibula, bpy.data.objects["MofleteIzq"], bpy.data.objects["MofleteDer"]):
    densificar(obj, 1)
for nombre in ("Cuerpo", "Pecho", "Barriga", "Cuello"):
    densificar(bpy.data.objects[nombre], 1)
pintar_pelaje()

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
