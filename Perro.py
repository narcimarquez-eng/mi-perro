import bpy
import math
import os

# ---------- LIMPIAR ESCENA ----------
bpy.ops.wm.read_factory_settings(use_empty=True)

# ---------- MATERIALES ----------
def crear_material(nombre, color):
    mat = bpy.data.materials.new(nombre)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    return mat

marron = crear_material("Marron", (0.45, 0.25, 0.10))
oscuro = crear_material("Oscuro", (0.08, 0.04, 0.02))
blanco = crear_material("Blanco", (0.90, 0.90, 0.90))

# ---------- HELPERS ----------
def esfera(loc, escala, material, nombre):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=32, ring_count=16, radius=1.0, location=loc
    )
    obj = bpy.context.object
    obj.name = nombre
    obj.scale = escala
    obj.data.materials.append(material)
    bpy.ops.object.shade_smooth()
    return obj

def cilindro(loc, rot, escala, material, nombre):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=32, radius=1.0, depth=2.0,
        location=loc, rotation=rot
    )
    obj = bpy.context.object
    obj.name = nombre
    obj.scale = escala
    obj.data.materials.append(material)
    bpy.ops.object.shade_smooth()
    return obj

# ---------- PERRO ----------
# Cuerpo (alargado en Y)
esfera((0, 0, 0.7), (0.8, 1.2, 0.6), marron, "Cuerpo")

# Cabeza
esfera((0, -1.2, 1.1), (0.55, 0.55, 0.50), marron, "Cabeza")

# Hocico
esfera((0, -1.7, 1.0), (0.25, 0.30, 0.20), oscuro, "Hocico")

# Nariz
esfera((0, -1.95, 1.05), (0.08, 0.08, 0.08), oscuro, "Nariz")

# Ojos
esfera((-0.20, -1.65, 1.25), (0.07, 0.07, 0.07), oscuro, "OjoIzq")
esfera(( 0.20, -1.65, 1.25), (0.07, 0.07, 0.07), oscuro, "OjoDer")

# Orejas
esfera((-0.40, -1.20, 1.40), (0.18, 0.10, 0.30), marron, "OrejaIzq")
esfera(( 0.40, -1.20, 1.40), (0.18, 0.10, 0.30), marron, "OrejaDer")

# Patas
for x in (-0.35, 0.35):
    for y in (-0.60, 0.60):
        cilindro((x, y, 0.30), (0, 0, 0), (0.12, 0.12, 0.30), marron, f"Pata_{x}_{y}")

# Cola
cilindro((0, 1.20, 1.00), (math.radians(45), 0, 0), (0.08, 0.08, 0.50), marron, "Cola")

# Suelo
bpy.ops.mesh.primitive_plane_add(size=10, location=(0, 0, 0))
suelo = bpy.context.object
suelo.name = "Suelo"
suelo.data.materials.append(crear_material("Suelo", (0.2, 0.2, 0.2)))

# ---------- CÁMARA Y LUZ ----------
bpy.ops.object.camera_add(
    location=(4, -4, 3),
    rotation=(math.radians(60), 0, math.radians(45))
)
bpy.context.scene.camera = bpy.context.object

bpy.ops.object.light_add(type='SUN', location=(3, -3, 6))
sol = bpy.context.object
sol.data.energy = 5.0

# ---------- RENDER ----------
scene = bpy.context.scene
scene.render.engine = 'CYCLES'          # Cycles funciona bien en headless
scene.cycles.samples = 64
scene.render.resolution_x = 800
scene.render.resolution_y = 600
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = os.path.abspath("perro.png")

bpy.ops.render.render(write_still=True)

# Opcional: exportar a glTF
# bpy.ops.export_scene.gltf(filepath=os.path.abspath("perro.glb"))
