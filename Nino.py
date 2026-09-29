"""Prepara el modelo 3D del niño para el juego de la playa.

- Quita el balón que tiene pegado a la mano y crea un balón aparte que se puede chutar.
- Baja el brazo derecho (estaba levantado sujetando el balón) y rehace sus animaciones
  copiando el brazo izquierdo en espejo.
- Añade dos animaciones: kick (chutar) y pickup (agacharse a coger algo).
- Reduce las texturas a 1024 px para que la web cargue rápido en el móvil.
- Exporta nino.glb con el esqueleto, las animaciones (idle, walk, run, shoot, skill, swim,
  attack, kick, pickup) y el balón como objeto aparte.

Uso:  blender -b --factory-startup --python Nino.py -- modelo_original.glb
(el modelo original no está en el repositorio: es una persona real)
"""
import bpy
import bmesh
import math
import os
import sys
from mathutils import Matrix, Quaternion, Vector, kdtree

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

# El balón va suelto, en el origen: la web lo coloca en la mano o en el suelo
balon.location = (0, 0, 0)

# ---------- Bajar el brazo derecho (el modelo original lo tenía levantado sujetando el balón) ----------
# Ejes del esqueleto: X = izquierda del niño, -Y = hacia delante, Z = arriba
huesos = esqueleto.data.bones
poses = esqueleto.pose.bones
CX = huesos["Spine"].head_local.x  # centro del cuerpo
ESPEJO = Matrix.Diagonal((-1.0, 1.0, 1.0))
def espejo_dir(d):
    return Vector((-d.x, d.y, d.z))

bpy.context.view_layer.objects.active = esqueleto
esqueleto.animation_data.action = None
bpy.ops.object.mode_set(mode='POSE')
for pb in poses:
    pb.rotation_mode = 'QUATERNION'
    pb.rotation_quaternion = (1, 0, 0, 0)
    pb.location = (0, 0, 0)
bpy.context.view_layer.update()

def centroide(grupo):
    """Centro de los vértices de la mano (en reposo), para saber hacia dónde apunta."""
    gi = cuerpo.vertex_groups[grupo].index
    pts = [cuerpo.matrix_world @ v.co for v in malla.vertices for g in v.groups if g.group == gi and g.weight > 0.6]
    return sum(pts, Vector()) / len(pts)

def girar_hacia(nombre, dir_actual, dir_objetivo):
    pb = poses[nombre]
    q = dir_actual.normalized().rotation_difference(dir_objetivo.normalized())
    m = pb.matrix.copy()
    pb.matrix = Matrix.LocRotScale(m.translation, (q.to_matrix() @ m.to_3x3()).to_quaternion(), None)
    bpy.context.view_layer.update()

cadena = [("RightShoulder", "RightArm", "LeftShoulder", "LeftArm"),
          ("RightArm", "RightForeArm", "LeftArm", "LeftForeArm"),
          ("RightForeArm", "RightHand", "LeftForeArm", "LeftHand")]
for hueso, hijo, izq, izq_hijo in cadena:
    objetivo = espejo_dir(huesos[izq_hijo].head_local - huesos[izq].head_local)
    girar_hacia(hueso, poses[hijo].head - poses[hueso].head, objetivo)
# La mano: que apunte como la izquierda (dirección muñeca -> centro de la mano)
mano_d = centroide("RightHand")
mano_d = poses["RightHand"].matrix @ huesos["RightHand"].matrix_local.inverted() @ mano_d
girar_hacia("RightHand", mano_d - poses["RightHand"].head,
            espejo_dir(centroide("LeftHand") - huesos["LeftHand"].head_local))

# Aplicar la nueva postura a la malla y guardarla como postura de reposo
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='DESELECT')
bpy.context.view_layer.objects.active = cuerpo
cuerpo.select_set(True)
mod = next(m for m in cuerpo.modifiers if m.type == 'ARMATURE')
bpy.ops.object.modifier_apply(modifier=mod.name)
nuevo = cuerpo.modifiers.new("Armature", 'ARMATURE')
nuevo.object = esqueleto
cuerpo.select_set(False)
bpy.context.view_layer.objects.active = esqueleto
esqueleto.select_set(True)
bpy.ops.object.mode_set(mode='POSE')
bpy.ops.pose.select_all(action='SELECT')
bpy.ops.pose.armature_apply(selected=False)
bpy.ops.object.mode_set(mode='OBJECT')
print("Brazo derecho bajado y aplicado como postura de reposo")

# ---------- Rehacer las animaciones del brazo derecho copiando el izquierdo en espejo ----------
PARES = [("RightShoulder", "LeftShoulder"), ("RightArm", "LeftArm"),
         ("RightForeArm", "LeftForeArm"), ("RightHand", "LeftHand")]
CICLICAS = {"walk", "run", "swim"}  # en estas, el brazo derecho va medio ciclo desfasado
escena = bpy.context.scene

def ir_a(t):
    escena.frame_set(int(math.floor(t)), subframe=t - math.floor(t))

def rot_pose(nombre):
    return poses[nombre].matrix.to_3x3()

for accion in list(bpy.data.actions):
    esqueleto.animation_data.action = accion
    for fc in list(accion.fcurves):
        if any(f'"{r}"' in fc.data_path for r, _ in PARES):
            accion.fcurves.remove(fc)
    ini, fin = accion.frame_range
    T = fin - ini
    tiempos = sorted({round(k.co.x, 3) for fc in accion.fcurves for k in fc.keyframe_points})
    anterior = {}
    for t in tiempos:
        tl = t + (T / 2 if accion.name in CICLICAS else 0)
        if tl > fin:
            tl -= T
        ir_a(tl)
        # Cuánto se ha girado cada hueso izquierdo respecto a su reposo (en ejes del esqueleto)
        giro_izq = {l: rot_pose(l) @ huesos[l].matrix_local.to_3x3().inverted() for _, l in PARES}
        ir_a(t)
        padre = rot_pose("Spine1")
        for r, l in PARES:
            reposo = huesos[r].matrix_local.to_3x3()
            deseada = ESPEJO @ giro_izq[l] @ ESPEJO @ reposo
            reposo_padre = huesos[r].parent.matrix_local.to_3x3()
            base = (padre @ reposo_padre.inverted() @ reposo).inverted() @ deseada
            q = base.to_quaternion()
            if r in anterior and anterior[r].dot(q) < 0:
                q.negate()  # evitar saltos al interpolar
            anterior[r] = q
            poses[r].rotation_quaternion = q
            poses[r].keyframe_insert("rotation_quaternion", frame=t, group=r)
            padre = deseada
    print(f"Animación {accion.name}: brazo derecho rehecho ({len(tiempos)} fotogramas)")

# ---------- Animaciones nuevas: chutar y agacharse a coger ----------
def giro(nombre, eje, angulo):
    """Cuaternión local para girar un hueso 'angulo' alrededor de un eje del esqueleto."""
    reposo = huesos[nombre].matrix_local.to_3x3()
    d = Matrix.Rotation(angulo, 3, eje)
    return (reposo.inverted() @ d @ reposo).to_quaternion()

def nueva_accion(nombre, claves):
    """claves: {fotograma: {hueso: [('X'|'Y'|'Z', ángulo), ...] o ('loc', Vector)}}"""
    accion = bpy.data.actions.new(nombre)
    esqueleto.animation_data.action = accion
    usados = {h for pose in claves.values() for h in pose}
    for f, pose in sorted(claves.items()):
        for h in usados:
            pb = poses[h]
            q = Quaternion()
            loc = Vector()
            for eje, valor in pose.get(h, []):
                if eje == 'loc':
                    loc = huesos[h].matrix_local.to_3x3().inverted() @ valor
                else:
                    q = giro(h, eje, valor) @ q
            pb.rotation_quaternion = q
            pb.keyframe_insert("rotation_quaternion", frame=f, group=h)
            if h == "Hips":
                pb.location = loc
                pb.keyframe_insert("location", frame=f, group=h)
    accion.use_fake_user = True
    print(f"Animación nueva: {nombre}")

# Chutar (contacto con el balón en el fotograma 10, a 24 fps = 0,42 s)
brazos = {"LeftArm": [('Y', -0.4)], "RightArm": [('Y', 0.4)]}
nueva_accion("kick", {
    0: {},
    7: {"RightUpLeg": [('X', 0.55)], "RightLeg": [('X', 1.3)], "LeftUpLeg": [('X', -0.1)], "LeftLeg": [('X', 0.2)],
        "Spine": [('X', -0.05)], **brazos},
    10: {"RightUpLeg": [('X', -0.9)], "RightLeg": [('X', 0.4)], "LeftUpLeg": [('X', -0.1)], "LeftLeg": [('X', 0.2)],
         "Spine": [('X', -0.15)], **brazos},
    13: {"RightUpLeg": [('X', -1.15)], "RightLeg": [('X', 0.15)], "Spine": [('X', -0.18)], **brazos},
    17: {"RightUpLeg": [('X', -0.8)], "RightLeg": [('X', 0.4)], "Spine": [('X', -0.1)], **brazos},
    26: {},
})
# Agacharse a coger algo del suelo
agachado = {"Hips": [('loc', Vector((0, 0.18, -0.30)))],
            "LeftUpLeg": [('X', -1.1)], "RightUpLeg": [('X', -1.1)],
            "LeftLeg": [('X', 1.7)], "RightLeg": [('X', 1.7)],
            "LeftFoot": [('X', -0.6)], "RightFoot": [('X', -0.6)],
            "Spine": [('X', 0.55)], "Spine1": [('X', 0.25)], "Head": [('X', 0.2)],
            "LeftArm": [('X', -0.5)], "RightArm": [('X', -0.5)]}
nueva_accion("pickup", {0: {}, 10: agachado, 16: agachado, 28: {}})

# Guardar cada animación en su pista para que se exporten todas
for accion in bpy.data.actions:
    pista = esqueleto.animation_data.nla_tracks.new()
    pista.name = accion.name
    pista.strips.new(accion.name, int(accion.frame_range[0]), accion)
    pista.mute = True
esqueleto.animation_data.action = None
for pb in poses:
    pb.rotation_quaternion = (1, 0, 0, 0)
    pb.location = (0, 0, 0)

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
