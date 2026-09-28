import bpy
import math
import os
from mathutils import Vector, noise

# ---------- LIMPIAR ESCENA ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.preferences.addon_enable(module="io_scene_gltf2")

# ---------- FORMA DEL TERRENO ----------
# La misma función está copiada en web/index.html para que el perro pise la arena
# y el agua sepa dónde hay orilla. Si la cambias aquí, cámbiala también allí.
def smoothstep(a, b, v):
    t = min(max((v - a) / (b - a), 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)

def altura(x, y):
    # La orilla está en y≈0: el mar hacia -Y y las dunas hacia +Y
    costa = y - 3.0 * math.sin(0.11 * x) - 1.5 * math.sin(0.27 * x + 1.0)
    h = 0.10 * costa
    h += 0.10 * math.sin(0.55 * x + 0.25 * y) * math.sin(0.35 * y)  # ondulaciones y bancos de arena
    t = smoothstep(12.0, 28.0, costa)
    h += t * (1.4 + 0.9 * math.sin(0.23 * x) * math.sin(0.19 * y + 0.5))  # dunas
    return max(h, -3.0)

# ---------- MATERIALES ----------
def poner(bsdf, nombres, valor):
    """Asigna un input del Principled BSDF probando varios nombres (cambian entre versiones de Blender)."""
    for n in nombres:
        if n in bsdf.inputs:
            bsdf.inputs[n].default_value = valor
            return

def crear_material(nombre, color, rugosidad=0.6):
    mat = bpy.data.materials.new(nombre)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = rugosidad
    return mat

def material_arena():
    """Arena clara bajo el agua, mojada en la orilla y seca arriba (según la altura)."""
    mat = crear_material("Arena", (0.9, 0.8, 0.6), 0.9)
    nodos, enlaces = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodos["Principled BSDF"]
    geo = nodos.new("ShaderNodeNewGeometry")
    xyz = nodos.new("ShaderNodeSeparateXYZ")
    rampa = nodos.new("ShaderNodeValToRGB")
    enlaces.new(geo.outputs["Position"], xyz.inputs[0])
    # Mapear altura -3..5 a 0..1
    mapa = nodos.new("ShaderNodeMapRange")
    mapa.inputs["From Min"].default_value = -3.0
    mapa.inputs["From Max"].default_value = 5.0
    enlaces.new(xyz.outputs["Z"], mapa.inputs["Value"])
    enlaces.new(mapa.outputs["Result"], rampa.inputs["Fac"])
    r = rampa.color_ramp
    r.elements[0].position = 0.0
    r.elements[0].color = (0.92, 0.84, 0.62, 1)   # fondo marino
    r.elements[1].position = 0.36
    r.elements[1].color = (0.50, 0.38, 0.22, 1)   # arena mojada
    e = r.elements.new(0.44)
    e.color = (0.80, 0.60, 0.33, 1)               # arena seca
    e = r.elements.new(0.95)
    e.color = (0.70, 0.55, 0.30, 1)               # dunas
    enlaces.new(rampa.outputs["Color"], bsdf.inputs["Base Color"])
    # Granito de la arena
    ruido = nodos.new("ShaderNodeTexNoise")
    ruido.inputs["Scale"].default_value = 60.0
    relieve = nodos.new("ShaderNodeBump")
    relieve.inputs["Strength"].default_value = 0.15
    enlaces.new(ruido.outputs["Fac"], relieve.inputs["Height"])
    enlaces.new(relieve.outputs["Normal"], bsdf.inputs["Normal"])
    return mat

def material_agua():
    """Agua cristalina: transparente en la orilla y turquesa donde cubre más."""
    mat = bpy.data.materials.new("Agua")
    mat.use_nodes = True
    nodos, enlaces = mat.node_tree.nodes, mat.node_tree.links
    salida = nodos["Material Output"]
    bsdf = nodos["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.85, 1.0, 1.0, 1)
    bsdf.inputs["Roughness"].default_value = 0.02
    bsdf.inputs["IOR"].default_value = 1.33
    poner(bsdf, ["Transmission Weight", "Transmission"], 1.0)
    # Olitas en la superficie
    olas = nodos.new("ShaderNodeTexNoise")
    olas.inputs["Scale"].default_value = 1.5
    olas.inputs["Detail"].default_value = 6.0
    relieve = nodos.new("ShaderNodeBump")
    relieve.inputs["Strength"].default_value = 0.25
    enlaces.new(olas.outputs["Fac"], relieve.inputs["Height"])
    enlaces.new(relieve.outputs["Normal"], bsdf.inputs["Normal"])
    # Truco: los rayos de sombra atraviesan el agua, así el fondo queda iluminado
    camino = nodos.new("ShaderNodeLightPath")
    transparente = nodos.new("ShaderNodeBsdfTransparent")
    mezcla = nodos.new("ShaderNodeMixShader")
    enlaces.new(camino.outputs["Is Shadow Ray"], mezcla.inputs["Fac"])
    enlaces.new(bsdf.outputs["BSDF"], mezcla.inputs[1])
    enlaces.new(transparente.outputs["BSDF"], mezcla.inputs[2])
    enlaces.new(mezcla.outputs["Shader"], salida.inputs["Surface"])
    # El volumen absorbe el rojo: cuanto más profundo, más turquesa
    absorcion = nodos.new("ShaderNodeVolumeAbsorption")
    absorcion.inputs["Color"].default_value = (0.02, 0.70, 0.75, 1)
    absorcion.inputs["Density"].default_value = 0.9
    enlaces.new(absorcion.outputs["Volume"], salida.inputs["Volume"])
    return mat

arena     = material_arena()
agua      = material_agua()
corteza   = crear_material("Corteza", (0.36, 0.24, 0.14), 0.9)
hoja_a    = crear_material("Hoja",    (0.10, 0.40, 0.08), 0.5)
hoja_b    = crear_material("HojaClara", (0.22, 0.52, 0.10), 0.5)
coco      = crear_material("Coco",    (0.30, 0.18, 0.08), 0.6)
roca      = crear_material("Roca",    (0.35, 0.33, 0.30), 0.85)
blanco    = crear_material("Blanco",  (0.95, 0.95, 0.92), 0.6)
coral     = crear_material("Coral",   (0.95, 0.35, 0.25), 0.6)
turquesa  = crear_material("Turquesa", (0.10, 0.65, 0.75), 0.6)

# ---------- HELPERS ----------
def objeto_malla(nombre, verts, caras, material):
    malla = bpy.data.meshes.new(nombre)
    malla.from_pydata(verts, [], caras)
    malla.update()
    obj = bpy.data.objects.new(nombre, malla)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    for poly in obj.data.polygons:
        poly.use_smooth = True
    return obj

# ---------- TERRENO ----------
bpy.ops.mesh.primitive_grid_add(x_subdivisions=160, y_subdivisions=160, size=160)
terreno = bpy.context.object
terreno.name = "Arena"
for v in terreno.data.vertices:
    v.co.z = altura(v.co.x, v.co.y)
terreno.data.materials.append(arena)
for poly in terreno.data.polygons:
    poly.use_smooth = True

# Fondo marino lejano (para que no se vea el vacío mar adentro)
bpy.ops.mesh.primitive_plane_add(size=1000, location=(0, 0, -3.0))
fondo = bpy.context.object
fondo.name = "FondoMar"
fondo.data.materials.append(arena)

# ---------- AGUA (solo para el render; la web dibuja su propia agua animada) ----------
bpy.ops.mesh.primitive_cube_add(location=(0, -200, -2.0))
mar = bpy.context.object
mar.name = "Agua"
mar.scale = (500, 250, 2.0)  # de z=-4 a z=0
mar.data.materials.append(agua)

# ---------- PALMERAS ----------
def palmera(i, x, y, alto, inclinacion, giro):
    base = Vector((x, y, altura(x, y) - 0.3))
    lado = Vector((math.cos(giro), math.sin(giro), 0))
    def punto(t):
        return base + lado * (inclinacion * t ** 1.8) + Vector((0, 0, alto * t))
    # Tronco: anillos que se estrechan, con "escalones" como una palmera de verdad
    anillos, lados = 28, 14
    verts, caras = [], []
    for a in range(anillos + 1):
        t = a / anillos
        r = (0.30 * (1 - t) + 0.17 * t) * (1 + 0.07 * abs(math.sin(t * 60)))
        c = punto(t)
        for s in range(lados):
            ang = 2 * math.pi * s / lados
            verts.append(c + Vector((math.cos(ang) * r, math.sin(ang) * r, 0)))
    for a in range(anillos):
        for s in range(lados):
            n = (s + 1) % lados
            caras.append((a * lados + s, a * lados + n, (a + 1) * lados + n, (a + 1) * lados + s))
    objeto_malla(f"Tronco_{i}", verts, caras, corteza)

    cima = punto(1.0)
    # Hojas: tiras curvadas que caen hacia abajo, con el nervio central levantado
    n_hojas = 9
    for h in range(n_hojas):
        ang = 2 * math.pi * h / n_hojas + i
        largo = 3.2 + 0.5 * math.sin(h * 2.3 + i)
        caida = 0.55 + 0.15 * math.cos(h * 1.7)
        d = Vector((math.cos(ang), math.sin(ang), 0))
        s = Vector((-math.sin(ang), math.cos(ang), 0))
        verts, caras = [], []
        pasos = 14
        for p in range(pasos + 1):
            t = p / pasos
            c = cima + d * (largo * t) + Vector((0, 0, largo * (0.35 * t - caida * t * t)))
            w = 0.16 * largo * math.sin(math.pi * t) ** 0.7
            verts += [c - s * w - Vector((0, 0, 0.25 * w)), c + Vector((0, 0, 0.05 * w)), c + s * w - Vector((0, 0, 0.25 * w))]
        for p in range(pasos):
            a, b = p * 3, (p + 1) * 3
            caras += [(a, a + 1, b + 1, b), (a + 1, a + 2, b + 2, b + 1)]
        objeto_malla(f"Hoja_{i}_{h}", verts, caras, hoja_a if h % 2 else hoja_b)

    # Cocos
    for k in range(3):
        ang = 2 * math.pi * k / 3 + 0.5
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.16,
                                             location=cima + Vector((math.cos(ang) * 0.22, math.sin(ang) * 0.22, -0.2)))
        c = bpy.context.object
        c.name = f"Coco_{i}_{k}"
        c.data.materials.append(coco)
        bpy.ops.object.shade_smooth()

palmeras = [
    (-14, 11, 7.0, 1.8, 0.4),
    (-9, 15, 8.0, 2.4, -0.9),
    (-18, 17, 6.5, 1.2, 2.5),
    (10, 13, 7.5, 2.0, -2.0),
    (15, 18, 8.5, 1.5, 0.8),
    (24, 12, 6.8, 2.2, 3.0),
    (-28, 14, 7.2, 1.6, -0.2),
    (3, 22, 7.8, 1.9, 1.9),
]
for i, (x, y, alto, incl, giro) in enumerate(palmeras):
    palmera(i, x, y, alto, incl, giro)

# ---------- ROCAS ----------
def piedra(i, x, y, tam, aplastar=0.6):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=1.0, location=(x, y, altura(x, y) + tam * 0.2))
    obj = bpy.context.object
    obj.name = f"Roca_{i}"
    semilla = Vector((i * 3.1, i * 1.7, i * 2.3))
    for v in obj.data.vertices:
        v.co *= 1.0 + 0.35 * noise.noise(v.co * 1.3 + semilla)
    obj.scale = (tam, tam * 0.85, tam * aplastar)
    obj.rotation_euler = (0, 0, i * 1.3)
    obj.data.materials.append(roca)
    bpy.ops.object.shade_smooth()

rocas = [
    (-22, -1, 1.6), (-24, 1, 1.1), (-20, 2, 0.8), (-26, -4, 2.0),   # rocas de la orilla
    (-23, -8, 1.3), (-17, -12, 0.9),                                # rocas dentro del agua
    (20, -6, 1.2), (22, -9, 1.8), (31, 3, 1.4),
    (-5, 26, 1.0), (28, 24, 1.3),
]
for i, (x, y, tam) in enumerate(rocas):
    piedra(i, x, y, tam)

# ---------- SOMBRILLA Y TOALLA ----------
SX, SY = 5.0, 5.5
bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.05, depth=3.2,
                                    location=(SX, SY, altura(SX, SY) + 1.3), rotation=(math.radians(8), 0, 0))
bpy.context.object.name = "PaloSombrilla"
bpy.context.object.data.materials.append(blanco)

bpy.ops.mesh.primitive_cone_add(vertices=16, radius1=1.9, radius2=0.05, depth=0.7,
                                location=(SX, SY - 0.2, altura(SX, SY) + 2.9), rotation=(math.radians(8), 0, 0))
tela = bpy.context.object
tela.name = "Sombrilla"
tela.data.materials.append(coral)
tela.data.materials.append(blanco)
for poly in tela.data.polygons:
    if len(poly.vertices) == 3:  # gajos a rayas
        poly.material_index = poly.index % 2
bpy.ops.object.shade_flat()

# Toalla a rayas que se adapta a la arena
TX, TY = 3.2, 4.0
for franja in range(6):
    verts = []
    for yy in (0, 1):
        for xx in (0, 1):
            x = TX + xx * 1.1
            y = TY + (franja + yy) * 0.35
            verts.append((x, y, altura(x, y) + 0.03))
    objeto_malla(f"Toalla_{franja}", verts, [(0, 1, 3, 2)], turquesa if franja % 2 else blanco)

# ---------- CIELO, SOL Y CÁMARA ----------
mundo = bpy.data.worlds.new("Cielo")
mundo.use_nodes = True
# Degradado de azul claro en el horizonte a azul intenso arriba
coord = mundo.node_tree.nodes.new("ShaderNodeTexCoord")
xyz = mundo.node_tree.nodes.new("ShaderNodeSeparateXYZ")
rampa = mundo.node_tree.nodes.new("ShaderNodeValToRGB")
rampa.color_ramp.elements[0].color = (0.45, 0.72, 0.98, 1)
rampa.color_ramp.elements[1].position = 0.5
rampa.color_ramp.elements[1].color = (0.02, 0.18, 0.75, 1)
fondo_cielo = mundo.node_tree.nodes["Background"]
fondo_cielo.inputs["Strength"].default_value = 0.9
mundo.node_tree.links.new(coord.outputs["Generated"], xyz.inputs[0])
mundo.node_tree.links.new(xyz.outputs["Z"], rampa.inputs["Fac"])
mundo.node_tree.links.new(rampa.outputs["Color"], fondo_cielo.inputs["Color"])
bpy.context.scene.world = mundo

bpy.ops.object.light_add(type='SUN', rotation=(math.radians(50), 0, math.radians(-40)))
sol = bpy.context.object
sol.data.energy = 4.0
sol.data.angle = math.radians(2)
sol.data.color = (1.0, 0.96, 0.88)

bpy.ops.object.empty_add(location=(-6, -4, 0.5))
objetivo = bpy.context.object
bpy.ops.object.camera_add(location=(-38, 12, 7.0))
camara = bpy.context.object
camara.data.lens = 24
seguir = camara.constraints.new(type='TRACK_TO')
seguir.target = objetivo
seguir.track_axis = 'TRACK_NEGATIVE_Z'
seguir.up_axis = 'UP_Y'
bpy.context.scene.camera = camara

# ---------- RENDER (PNG) ----------
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 128
scene.cycles.use_denoising = False  # el Blender de Ubuntu viene sin denoiser
scene.cycles.sample_clamp_indirect = 3.0
scene.cycles.max_bounces = 8
scene.cycles.transmission_bounces = 8
if bpy.app.version >= (4, 0, 0):
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Punchy'
else:
    scene.view_settings.view_transform = 'Filmic'
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = os.path.abspath("playa.png")

bpy.ops.render.render(write_still=True)

# ---------- EXPORTAR A GLB ----------
# La web pone su propia agua animada y su propio cielo, así que no exportamos ni el agua ni luces ni cámara
bpy.ops.object.select_all(action='DESELECT')
for obj in bpy.context.scene.objects:
    if obj.type == 'MESH' and obj is not mar:
        obj.select_set(True)
bpy.ops.export_scene.gltf(
    filepath=os.path.abspath("playa.glb"),
    export_format='GLB',
    use_selection=True,
    export_apply=True,
)
print("¡Playa exportada a GLB correctamente!")
