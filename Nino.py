"""Prepara el modelo 3D del niño para el juego de la playa.

- Quita el balón que tiene pegado a la mano y crea un balón aparte que se puede chutar.
- Reduce las texturas a 1024 px para que la web cargue rápido en el móvil.
- Exporta nino.glb con el esqueleto y las animaciones (idle, walk, run, shoot, skill, swim...).

Uso:  blender -b --factory-startup --python Nino.py -- modelo_original.glb
(el modelo original no está en el repositorio: es una persona real)
"""
import bpy
import bmesh
import math
import os
import sys
from mathutils import Vector, kdtree

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ENTRADA = os.path.abspath(args[0] if args else "manuel.glb")
SALIDA = os.path.abspath(args[1] if len(args) > 1 else "nino.glb")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.preferences.addon_enable(module="io_scene_gltf2")
bpy.ops.import_scene.gltf(filepath=ENTRADA)

# El importador añade una esfera para dibujar los huesos: no forma parte del niño
for o in list(bpy.data.objects):
    if o.type == 'MESH' and not o.parent:
        bpy.data.objects.remove(o)

esqueleto = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
cuerpo = next(o for o in bpy.data.objects if o.type == 'MESH')
esqueleto.name = "Nino"
cuerpo.name = "NinoCuerpo"
for accion in bpy.data.actions:
    accion.name = accion.name.replace("_Armature", "")

malla = cuerpo.data
mat_cuerpo = malla.materials[0]
textura = next(n.image for n in mat_cuerpo.node_tree.nodes
               if n.type == 'TEX_IMAGE' and n.outputs["Color"].links
               and n.outputs["Color"].links[0].to_socket.name == "Base Color")

# ---------- Color de cada vértice (leído de la textura) ----------
ancho, alto = textura.size
pixeles = textura.pixels[:]
def color_uv(uv):
    x = min(int((uv.x % 1.0) * ancho), ancho - 1)
    y = min(int((uv.y % 1.0) * alto), alto - 1)
    i = (y * ancho + x) * 4
    return Vector(pixeles[i:i + 3])

uvs = malla.uv_layers.active.data
color_vert = [None] * len(malla.vertices)
for bucle in malla.loops:
    if color_vert[bucle.vertex_index] is None:
        color_vert[bucle.vertex_index] = color_uv(uvs[bucle.index].uv)

def saturacion(c):
    mx, mn = max(c), min(c)
    return 0.0 if mx < 1e-4 else (mx - mn) / mx

# ---------- Encontrar el balón ----------
# Es la zona roja/naranja cerca de la mano derecha
grupos = {g.index: g.name for g in cuerpo.vertex_groups}
def peso_mano(v):
    return sum(g.weight for g in v.groups if grupos[g.group] in ("RightHand", "RightForeArm"))

rojos = [v.co.copy() for v in malla.vertices
         if peso_mano(v) > 0.5 and color_vert[v.index].x > 0.35
         and color_vert[v.index].y < 0.55 * color_vert[v.index].x
         and color_vert[v.index].z < 0.5 * color_vert[v.index].x]
centro = sum(rojos, Vector()) / len(rojos)
distancias = sorted((c - centro).length for c in rojos)
radio = distancias[int(len(distancias) * 0.6)]
print(f"Balón: {len(rojos)} vértices rojos, centro {tuple(round(c, 3) for c in centro)}, radio {radio:.3f}")

def es_balon(v):
    d = (v.co - centro).length
    if d < radio * 0.8:
        return True  # por dentro del balón
    return d < radio * 1.12 and saturacion(color_vert[v.index]) > 0.45 and peso_mano(v) > 0.3

en_balon = [es_balon(v) for v in malla.vertices]

# Guardar los colores del balón para pintar el balón nuevo
arbol = kdtree.KDTree(sum(en_balon))
colores_balon = []
for v in malla.vertices:
    if en_balon[v.index]:
        arbol.insert(v.co, len(colores_balon))
        colores_balon.append(color_vert[v.index])
arbol.balance()

# Borrar el balón del cuerpo
bm = bmesh.new()
bm.from_mesh(malla)
bm.verts.ensure_lookup_table()
caras = [f for f in bm.faces if sum(en_balon[v.index] for v in f.verts) >= 2]
bmesh.ops.delete(bm, geom=caras, context='FACES_ONLY')
sueltos = [v for v in bm.verts if not v.link_faces]
bmesh.ops.delete(bm, geom=sueltos, context='VERTS')
bm.to_mesh(malla)
bm.free()
print(f"Borradas {len(caras)} caras del balón")

# ---------- Balón nuevo, redondo y con los colores del original ----------
centro_mundo = cuerpo.matrix_world @ centro
escala = cuerpo.matrix_world.to_scale().x
bpy.ops.mesh.primitive_uv_sphere_add(segments=40, ring_count=20, radius=radio * escala, location=centro_mundo)
balon = bpy.context.object
balon.name = "Balon"
atributo = balon.data.color_attributes.new("Col", 'FLOAT_COLOR', 'POINT')
inv = cuerpo.matrix_world.inverted()
for v in balon.data.vertices:
    p = inv @ (balon.matrix_world @ v.co)
    # dirección desde el centro, proyectada sobre la superficie del balón original
    p = centro + (p - centro).normalized() * radio
    cercanos = arbol.find_n(p, 6)
    c = sum((colores_balon[i] for _, i, _ in cercanos), Vector()) / len(cercanos)
    # La textura está en sRGB y los colores de vértice en lineal
    atributo.data[v.index].color = (*(x ** 2.2 for x in c), 1.0)
bpy.ops.object.shade_smooth()

mat = bpy.data.materials.new("Balon")
mat.use_nodes = True
bsdf = mat.node_tree.nodes["Principled BSDF"]
nodo_col = mat.node_tree.nodes.new("ShaderNodeVertexColor")
nodo_col.layer_name = "Col"
mat.node_tree.links.new(nodo_col.outputs["Color"], bsdf.inputs["Base Color"])
bsdf.inputs["Roughness"].default_value = 0.55
balon.data.materials.append(mat)

# El balón cuelga de la mano derecha; la web lo suelta cuando lo chuta
bpy.context.view_layer.update()
mundo = balon.matrix_world.copy()
balon.parent = esqueleto
balon.parent_type = 'BONE'
balon.parent_bone = "RightHand"
bpy.context.view_layer.update()
balon.matrix_world = mundo

# ---------- Texturas más ligeras ----------
for img in bpy.data.images:
    if img.size[0] > 1024:
        img.scale(1024, 1024)

# ---------- Exportar ----------
bpy.ops.object.select_all(action='DESELECT')
for o in (esqueleto, cuerpo, balon):
    o.select_set(True)
bpy.ops.export_scene.gltf(
    filepath=SALIDA,
    export_format='GLB',
    use_selection=True,
    export_animations=True,
    export_animation_mode='ACTIONS',
    export_image_format='JPEG',
    export_jpeg_quality=85,
)
print("¡Niño exportado a GLB correctamente!")
