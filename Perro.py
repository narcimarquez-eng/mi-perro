import bpy
import math
import os

# ---------- LIMPIAR ESCENA ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.preferences.addon_enable(module="io_scene_gltf2")

# ---------- MATERIALES ----------
def crear_material(nombre, color):
    mat = bpy.data.materials.new(nombre)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    return mat

# Colores para un perro tipo beagle
marron = crear_material("Marron", (0.45, 0.25, 0.10))
claro  = crear_material("Claro",  (0.85, 0.75, 0.60)) # Para hocico, pecho y patas
oscuro = crear_material("Oscuro", (0.05, 0.02, 0.01)) # Para nariz y ojos

# ---------- HELPERS ----------
def esfera(loc, escala, material, nombre):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=1.0, location=loc)
    obj = bpy.context.object
    obj.name = nombre
    obj.scale = escala
    obj.data.materials.append(material)
    mod = obj.modifiers.new(name="Subsurf", type='SUBSURF')
    mod.levels = 2
    for poly in obj.data.polygons:
        poly.use_smooth = True
    return obj

def cilindro(loc, rot, escala, material, nombre):
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=1.0, depth=2.0, location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = nombre
    obj.scale = escala
    obj.data.materials.append(material)
    mod = obj.modifiers.new(name="Subsurf", type='SUBSURF')
    mod.levels = 2
    for poly in obj.data.polygons:
        poly.use_smooth = True
    return obj

# ---------- CONSTRUYENDO EL PERRO ----------

# Cuerpo principal (un poco más alargado)
esfera((0, 0, 0.7), (0.65, 1.1, 0.55), marron, "Cuerpo")

# Pecho (color claro)
esfera((0, -0.6, 0.7), (0.55, 0.6, 0.50), claro, "Pecho")

# Cuello
esfera((0, -0.9, 1.0), (0.35, 0.35, 0.35), marron, "Cuello")

# Cabeza (más redonda)
esfera((0, -1.3, 1.3), (0.45, 0.45, 0.45), marron, "Cabeza")

# Hocico (color claro, alargado hacia adelante)
esfera((0, -1.65, 1.15), (0.25, 0.35, 0.22), claro, "Hocico")

# Nariz (oscura y pequeña)
esfera((0, -1.95, 1.20), (0.09, 0.09, 0.08), oscuro, "Nariz")

# Ojos (oscuros)
esfera((-0.18, -1.55, 1.40), (0.06, 0.06, 0.06), oscuro, "OjoIzq")
esfera(( 0.18, -1.55, 1.40), (0.06, 0.06, 0.06), oscuro, "OjoDer")

# Orejas colgantes (tipo beagle, achatadas y hacia abajo)
oreja_izq = esfera((-0.45, -1.25, 1.25), (0.10, 0.25, 0.35), marron, "OrejaIzq")
oreja_izq.rotation_euler = (0, math.radians(15), 0) # Inclinarla un poco hacia fuera

oreja_der = esfera(( 0.45, -1.25, 1.25), (0.10, 0.25, 0.35), marron, "OrejaDer")
oreja_der.rotation_euler = (0, math.radians(-15), 0)

# Patas (cilindros con "pata" en la base)
posiciones_patas = [(-0.35, -0.5), (0.35, -0.5), (-0.35, 0.5), (0.35, 0.5)]
for i, (x, y) in enumerate(posiciones_patas):
    # Pata (cilindro)
    cilindro((x, y, 0.35), (0, 0, 0), (0.12, 0.12, 0.35), marron, f"Pata_{i}")
    # Pie (esfera achatada color claro)
    esfera((x, y - 0.05, 0.05), (0.14, 0.18, 0.08), claro, f"Pie_{i}")

# Cola (cilindro inclinado hacia arriba)
cilindro((0, 0.95, 0.9), (math.radians(60), 0, 0), (0.07, 0.07, 0.45), marron, "Cola")

# Suelo (para que haga sombra y se vea mejor)
bpy.ops.mesh.primitive_plane_add(size=10, location=(0, 0, 0))
suelo = bpy.context.object
suelo.name = "Suelo"
suelo.data.materials.append(crear_material("Suelo", (0.15, 0.15, 0.15)))

# ---------- CÁMARA Y LUZ ----------
bpy.ops.object.camera_add(location=(3.5, -4.5, 3.0), rotation=(math.radians(65), 0, math.radians(35)))
bpy.context.scene.camera = bpy.context.object

bpy.ops.object.light_add(type='SUN', location=(3, -3, 6))
sol = bpy.context.object
sol.data.energy = 4.0

# ---------- RENDER (PNG) ----------
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.use_denoising = False
scene.cycles.samples = 64
scene.render.resolution_x = 800
scene.render.resolution_y = 600
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = os.path.abspath("perro.png")

bpy.ops.render.render(write_still=True)

# ---------- EXPORTAR A GLB ----------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=os.path.abspath("perro.glb"),
    export_format='GLB',
    use_selection=False
)
print("¡Perro exportado a GLB correctamente!")
