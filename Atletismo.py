"""El estadio de atletismo: el utillaje de las siete pruebas y lo que hay alrededor de la pista.

blender -b --factory-startup --python Atletismo.py

Exporta web/atletismo.glb. Todo son objetos sueltos que la web coloca (miran hacia -Y; en la web, hacia +Z):
  Jabalina, Peso, Pertiga (con el origen donde se agarran; la punta apunta hacia delante),
  PostesAltura (con Soporte, la barra va aparte: Barra) y PostesPertiga, ColchonetaAltura, ColchonetaPertiga,
  CajaPertiga (donde se clava la pértiga), Taco (de salida), Valla, Cono,
  Podio (con los números 1, 2 y 3), Trofeo, MedallaOro, MedallaPlata y MedallaBronce,
  Marcador (con Marcador_Pantalla, que la web cubre con un lienzo dibujado), Foco (torre de luz con Foco_Luces),
  Mastil, Banco, Nevera, Mochila y Botella.
Las gradas, la pista, el césped y el público se hacen en la web. Renderiza atletismo.png con todo en fila.
"""
import bpy
import bmesh
import math
import os
import random
from mathutils import Vector

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.preferences.addon_enable(module="io_scene_gltf2")
rnd = random.Random(7)


# ---------- UTILIDADES ----------
def lineal(hexa):
    c = [int(hexa[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return Vector([x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c])


def activar(o):
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


def aplicar(o):
    activar(o)
    for m in list(o.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)


def objeto(nombre, me):
    o = bpy.data.objects.new(nombre, me)
    bpy.context.collection.objects.link(o)
    return o


def unir(objs, nombre):
    objs = [o for o in objs if o]
    activar(objs[0])
    for o in objs[1:]:
        o.select_set(True)
    if len(objs) > 1:
        bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    o.name = nombre
    o.data.name = nombre
    return o


def suave(o, si=True):
    for p in o.data.polygons:
        p.use_smooth = si


def material_vc(nombre, rug=0.6, metal=0.0):
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    vc = nt.nodes.new("ShaderNodeVertexColor")
    vc.layer_name = "Col"
    nt.links.new(vc.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rug
    b.inputs["Metallic"].default_value = metal
    return m


VC = material_vc("Pieza", 0.55)
VC_ORO = material_vc("Oro", 0.3, 0.8)


def pintar(o, fn, mat=VC):
    me = o.data
    at = me.color_attributes.get("Col") or me.color_attributes.new("Col", 'FLOAT_COLOR', 'POINT')
    for v in me.vertices:
        c = fn(v.co, v.normal)
        at.data[v.index].color = (max(0, c[0]), max(0, c[1]), max(0, c[2]), 1.0)
    me.materials.clear()
    me.materials.append(mat)
    return o


def color(o, hexa, mat=VC):
    c = lineal(hexa)
    return pintar(o, lambda co, n: c, mat)


def caja(loc, esc, rot=(0, 0, 0), bisel=0.0, seg=2):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    c = bpy.context.object
    c.scale = esc
    bpy.ops.object.transform_apply(location=True, scale=True, rotation=True)
    if bisel:
        b = c.modifiers.new("B", 'BEVEL')
        b.width = bisel
        b.segments = seg
        aplicar(c)
    return c


def cilindro(loc, r, largo, rot=(0, 0, 0), v=20, r2=None):
    if r2 is None:
        bpy.ops.mesh.primitive_cylinder_add(vertices=v, radius=r, depth=largo, location=loc, rotation=rot)
    else:
        bpy.ops.mesh.primitive_cone_add(vertices=v, radius1=r, radius2=r2, depth=largo, location=loc, rotation=rot)
    c = bpy.context.object
    bpy.ops.object.transform_apply(location=True, rotation=True)
    return c


def esfera(loc, esc, seg=20):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=max(8, seg // 2), radius=1, location=loc)
    o = bpy.context.object
    o.scale = esc if isinstance(esc, (tuple, list)) else (esc,) * 3
    bpy.ops.object.transform_apply(location=True, scale=True)
    suave(o)
    return o


def toro(loc, R, r, rot=(0, 0, 0), seg=24):
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=r, major_segments=seg, minor_segments=8, location=loc, rotation=rot)
    o = bpy.context.object
    bpy.ops.object.transform_apply(location=True, rotation=True)
    suave(o)
    return o


def recortar(o, quitar):
    """Borra los vértices (en coordenadas locales) para los que quitar(co) es cierto."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if quitar(v.co)], context='VERTS')
    bm.to_mesh(o.data)
    bm.free()
    return o


def skin(nombre, verts, aristas, radios, sub=1):
    me = bpy.data.meshes.new(nombre)
    me.from_pydata(verts, aristas, [])
    o = objeto(nombre, me)
    sk = o.modifiers.new("Skin", 'SKIN')
    sk.branch_smoothing = 0.8
    for i, r in enumerate(radios):
        o.data.skin_vertices[0].data[i].radius = (r, r) if not isinstance(r, tuple) else r
    o.data.skin_vertices[0].data[0].use_root = True
    if sub:
        s = o.modifiers.new("Sub", 'SUBSURF')
        s.levels = sub
    aplicar(o)
    suave(o)
    return o


def ojos(x, y, z, sep, r, mirada=(0, 0)):
    """Dos ojos grandes de dibujo animado mirando hacia -Y (el frente en la web)."""
    piezas = []
    for l in (-1, 1):
        b = color(esfera((x + l * sep, y, z), (r, r * 0.5, r * 1.15), 16), "#ffffff")
        p = color(esfera((x + l * sep + mirada[0] * r * 0.3, y - r * 0.42, z + mirada[1] * r * 0.3 - r * 0.1), (r * 0.55, r * 0.2, r * 0.62), 12), "#1a1d24")
        brillo = color(esfera((x + l * sep + r * 0.22, y - r * 0.55, z + r * 0.18), r * 0.18, 10), "#ffffff")
        piezas += [b, p, brillo]
    return piezas


def sonrisa(x, y, z, R, r, col="#7a1e22"):
    o = toro((x, y, z), R, r, rot=(math.pi / 2, 0, 0))
    recortar(o, lambda co: co.z > z - R * 0.35)
    return color(o, col)




def subdividir(o, cortes):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cortes, use_grid_fill=True)
    bm.to_mesh(o.data)
    bm.free()
    return o


def barra(a, b, r, col, v=10):
    """Cilindro de a a b."""
    va, vb = Vector(a), Vector(b)
    d = vb - va
    bpy.ops.mesh.primitive_cylinder_add(vertices=v, radius=r, depth=d.length, location=(0, 0, 0))
    c = bpy.context.object
    c.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    bpy.ops.object.transform_apply(location=False, rotation=True)
    c.location = (va + vb) / 2
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    return color(c, col)


def bombillas(puntos, r=0.07):
    return [color(esfera(p, r, 8), "#fff3a8") for p in puntos]


ROJO, BLANCO, AMARILLO, AZUL = "#e8322a", "#f6f4ee", "#ffd21f", "#2a7ae0"



VC_METAL = material_vc("Metal", 0.3, 0.85)


# ---------- PIEZAS ARTICULADAS ----------
def parte(nombre, piezas, pivote, padre=None):
    """Une las piezas, pone el origen en el pivote (donde gira) y la cuelga del padre."""
    o = unir(piezas, nombre)
    bpy.context.scene.cursor.location = pivote
    activar(o)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    if padre:
        mw = o.matrix_world.copy()
        o.parent = padre
        o.matrix_world = mw
    return o


def cadena(puntos, radios, col):
    o = skin("cadena", puntos, [(k, k + 1) for k in range(len(puntos) - 1)], radios)
    return color(o, col) if not callable(col) else pintar(o, col)


def mezcla(c1, c2, t):
    a, b = lineal(c1), lineal(c2)
    t = max(0.0, min(1.0, t))
    return a * (1 - t) + b * t


def ojo(x, y, z, r, iris="#1a1d24"):
    return [color(esfera((x, y, z), (r, r * 0.6, r * 1.1), 14), "#ffffff"),
            color(esfera((x, y - r * 0.5, z - r * 0.1), (r * 0.5, r * 0.25, r * 0.55), 10), iris),
            color(esfera((x + r * 0.25, y - r * 0.68, z + r * 0.2), r * 0.15, 8), "#ffffff")]




GRIS, ACERO, NEGRO = "#9aa4ae", "#6c7884", "#23262d"
VC_BRILLO = material_vc("Brillo", 0.28, 0.25)


def digito(n, x, y, z, alto=0.28, ancho=0.16, grueso=0.02, col="#ffffff"):
    """Un número 1, 2 o 3 hecho con rayitas (como un marcador), mirando hacia -Y."""
    seg = {1: "bc", 2: "abged", 3: "abgcd"}[n]
    g, a = grueso, alto / 2
    pos = {"a": (0, a), "g": (0, 0), "d": (0, -a), "b": (ancho / 2, a / 2), "c": (ancho / 2, -a / 2),
           "f": (-ancho / 2, a / 2), "e": (-ancho / 2, -a / 2)}
    piezas = []
    for s in seg:
        px, pz = pos[s]
        horizontal = s in "agd"
        piezas.append(color(caja((x + px, y, z + pz), (ancho if horizontal else g, grueso, g if horizontal else a), bisel=0.004, seg=1), col))
    return piezas


def bandas(o, c1, c2, largo, eje=1):
    """Pinta un cilindro a anillos alternos de dos colores (eje 1 = Y)."""
    a, b = lineal(c1), lineal(c2)
    pintar(o, lambda co, n: a if int(math.floor(co[eje] / largo)) % 2 == 0 else b)
    return o


# ---------- LAS COSAS QUE SE LANZAN ----------
def jabalina():
    piezas = [barra((0, -1.0, 0), (0, 1.2, 0), 0.017, "#eef2f5", 12),
              color(cilindro((0, -1.15, 0), 0.02, 0.32, rot=(math.pi / 2, 0, 0), v=12, r2=0.0), "#8d98a4"),
              color(esfera((0, 1.22, 0), (0.02, 0.025, 0.02), 8), NEGRO)]
    for k in range(9):  # la cuerda de la empuñadura, a rayas rojas y oscuras
        piezas.append(color(cilindro((0, -0.1 + k * 0.045, 0), 0.0215, 0.04, rot=(math.pi / 2, 0, 0), v=12), "#e8322a" if k % 2 == 0 else "#7a1a16"))
    return parte("Jabalina", piezas, (0, 0.1, 0))


def peso():
    bola = esfera((0, 0, 0), 0.14, 24)
    pintar(bola, lambda co, n: mezcla("#3a424e", "#8793a0", 0.5 + 0.5 * co.z / 0.14))
    banda = color(toro((0, 0, 0), 0.141, 0.012, seg=32), "#e8322a")
    return parte("Peso", [bola, banda], (0, 0, 0))


def pertiga():
    largo = 4.6
    p = barra((0, -3.3, 0), (0, 1.3, 0), 0.02, "#ff9a1f", 12)
    ca, cb = lineal("#ff9a1f"), lineal("#ffd21f")
    pintar(p, lambda co, n: lineal("#f6f2e4") if co.y > 0.15 else (cb if int(math.floor(co.y / 0.55)) % 2 == 0 else ca))
    piezas = [p, color(esfera((0, -3.3, 0), (0.026, 0.026, 0.026), 8), NEGRO), color(esfera((0, 1.3, 0), (0.024, 0.03, 0.024), 8), NEGRO)]
    return parte("Pertiga", piezas, (0, 0, 0))


# ---------- SALTOS ----------
def postes(nombre, alto, ancho, mat_color):
    piezas = []
    for l in (-1, 1):
        x = l * ancho / 2
        piezas.append(color(caja((x, 0.05, 0.02), (0.5, 0.9, 0.04), bisel=0.01), "#4a525c"))
        poste = caja((x, 0.0, alto / 2), (0.08, 0.08, alto), bisel=0.01)
        pintar(poste, lambda co, n: lineal("#1f2630") if abs(co.z * 10 - round(co.z * 10)) < 0.045 and co.z > 0.3 else lineal(mat_color))
        piezas += [poste, color(caja((x, 0.0, alto + 0.03), (0.12, 0.12, 0.06), bisel=0.02), NEGRO)]
        for h in range(2, int(alto * 5)):
            piezas.append(color(caja((x, -0.042, h * 0.2), (0.05, 0.004, 0.012 if h % 5 else 0.026)), "#ffffff"))
    return parte(nombre, piezas, (0, 0, 0))


def soporte():
    piezas = [color(cilindro((0, -0.04, 0), 0.025, 0.14, rot=(math.pi / 2, 0, 0), v=10), GRIS),
              color(caja((0, 0.03, 0.0), (0.07, 0.03, 0.05), bisel=0.008), NEGRO)]
    return parte("Soporte", piezas, (0, 0, 0))


def barra_salto():
    b = barra((-2.1, 0, 0), (2.1, 0, 0), 0.016, "#ffffff", 12)
    bandas(b, "#e8322a", "#ffffff", 0.35, 0)
    return parte("Barra", [b], (0, 0, 0))


def colchoneta(nombre, ancho, fondo, alto, c_arriba, c_lado):
    ca, cl = lineal(c_arriba), lineal(c_lado)
    m = caja((0, fondo / 2 + 0.15, alto / 2), (ancho, fondo, alto), bisel=0.14, seg=4)
    pintar(m, lambda co, n: ca if (co.z > alto - 0.1 and n.z > 0.3) else (mezcla(c_lado, "#ffffff", 0.2) if abs(co.z - alto * 0.5) < 0.04 else cl))
    piezas = [m]
    # costuras acolchadas en la cara de arriba
    oscuro = mezcla(c_arriba, "#000000", 0.25)
    for k in range(1, 5):
        costura = caja((-ancho / 2 + k * ancho / 5, fondo / 2 + 0.15, alto - 0.04), (0.04, fondo * 0.96, 0.05), bisel=0.01, seg=1)
        piezas.append(pintar(costura, lambda co, n, v=oscuro: v))
    return parte(nombre, piezas, (0, 0, 0))


def caja_pertiga():
    piezas = [color(caja((0, -0.55, 0.0), (0.9, 1.4, 0.04), bisel=0.01), "#3a4048"),
              color(caja((0, -0.55, 0.0005), (0.6, 1.2, 0.02)), "#16181d"),
              color(caja((0, 0.04, 0.12), (0.9, 0.08, 0.26), bisel=0.02), "#e8322a")]
    for l in (-1, 1):
        piezas.append(color(caja((l * 0.43, -0.55, 0.06), (0.05, 1.4, 0.12), bisel=0.01), GRIS))
    return parte("CajaPertiga", piezas, (0, 0, 0))


# ---------- PISTA ----------
def taco():
    piezas = [color(caja((0, 0.0, 0.03), (0.34, 0.5, 0.06), bisel=0.012), "#4a525c")]
    for k, y in enumerate((-0.12, 0.12)):
        piezas.append(color(caja((0, y, 0.12), (0.2, 0.09, 0.13), rot=(0.7 if k == 0 else 0.5, 0, 0), bisel=0.012), "#e8322a"))
    return parte("Taco", piezas, (0, 0, 0))


def valla():
    piezas = []
    for l in (-1, 1):
        piezas.append(barra((l * 0.55, 0, 0.0), (l * 0.55, 0, 0.8), 0.025, "#f6f4ee", 8))
        piezas.append(color(caja((l * 0.55, 0, 0.012), (0.1, 0.55, 0.025), bisel=0.005, seg=1), "#f6f4ee"))
    piezas.append(color(caja((0, 0, 0.72), (1.2, 0.04, 0.16), bisel=0.01), "#ffffff"))
    piezas.append(color(caja((0, -0.021, 0.72), (0.4, 0.002, 0.1)), "#e8322a"))
    return parte("Valla", piezas, (0, 0, 0))


def cono():
    piezas = [color(caja((0, 0, 0.012), (0.22, 0.22, 0.024), bisel=0.006, seg=1), "#ff7a1a"),
              color(cilindro((0, 0, 0.14), 0.095, 0.24, v=16, r2=0.025), "#ff7a1a"),
              color(cilindro((0, 0, 0.11), 0.07, 0.04, v=16, r2=0.062), "#ffffff")]
    return parte("Cono", piezas, (0, 0, 0))


# ---------- PODIO, TROFEO Y MEDALLAS ----------
def podio():
    piezas = []
    for x, h, top, n in ((-1.0, 0.46, "#cfd6de", 2), (0.0, 0.64, "#ffd23a", 1), (1.0, 0.34, "#d98a48", 3)):
        piezas.append(color(caja((x, 0, h / 2), (0.96, 0.9, h), bisel=0.025, seg=2), "#2a6edb"))
        piezas.append(color(caja((x, 0, h - 0.015), (1.0, 0.94, 0.04), bisel=0.015, seg=2), top))
        piezas += digito(n, x, -0.455, h * 0.52, alto=0.3, ancho=0.17, grueso=0.03)
    return parte("Podio", piezas, (0, 0, 0))


def trofeo():
    piezas = [color(caja((0, 0, 0.04), (0.32, 0.32, 0.08), bisel=0.02), "#3a2a1c"),
              color(cilindro((0, 0, 0.14), 0.07, 0.12, v=18, r2=0.1), "#ffd23a"),
              color(cilindro((0, 0, 0.3), 0.025, 0.22, v=14), "#ffd23a"),
              color(esfera((0, 0, 0.4), 0.05, 14), "#ffd23a")]
    cuenco = esfera((0, 0, 0.58), (0.19, 0.19, 0.19), 28)
    recortar(cuenco, lambda co: co.z > 0.58 + 0.02)
    piezas.append(color(cuenco, "#ffd23a"))
    piezas.append(color(toro((0, 0, 0.6), 0.19, 0.012, seg=30), "#fff0a0"))
    for l in (-1, 1):
        piezas.append(color(toro((l * 0.22, 0, 0.6), 0.075, 0.016, rot=(math.pi / 2, 0, 0), seg=18), "#ffd23a"))
    piezas.append(color(esfera((0, 0, 0.66), (0.045, 0.012, 0.045), 12), "#e8322a"))
    return parte("Trofeo", piezas, (0, 0, 0))


def medalla(nombre, col, col2):
    piezas = [color(cilindro((0, 0, -0.2), 0.1, 0.014, rot=(math.pi / 2, 0, 0), v=32), col),
              color(toro((0, -0.008, -0.2), 0.082, 0.008, rot=(math.pi / 2, 0, 0), seg=32), col2),
              color(esfera((0, -0.014, -0.2), (0.04, 0.01, 0.04), 12), col2)]
    for l in (-1, 1):  # la cinta, en V hasta el cuello
        piezas.append(barra((l * 0.055, 0, -0.08), (0.0, 0, 0.0), 0.012, "#2a6edb", 6))
        piezas.append(barra((l * 0.055, 0.002, -0.08), (l * 0.012, 0.002, -0.01), 0.005, "#ffffff", 6))
    return parte(nombre, piezas, (0, 0, 0))


# ---------- EL ENTORNO ----------
def marcador():
    piezas = [color(caja((0, 0.1, 3.9), (6.6, 0.4, 3.1), bisel=0.08), "#1f2630"),
              color(caja((0, -0.06, 3.9), (6.3, 0.06, 2.8)), "#2b3440")]
    for x in (-2.8, 2.8):
        piezas.append(color(caja((x, 0.15, 1.2), (0.28, 0.28, 2.4), bisel=0.03), "#4a525c"))
    for k in range(7):
        piezas.append(color(esfera((-3.0 + k, -0.1, 5.58), 0.09, 8), "#fff3a8"))
    cuerpo = parte("Marcador", piezas, (0, 0, 0))
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, -0.16, 3.9), rotation=(math.pi / 2, 0, 0))
    pan = bpy.context.object
    pan.scale = (6.0, 2.6, 1)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    color(pan, "#101820")
    pan = parte("Marcador_Pantalla", [pan], (0, -0.16, 3.9), cuerpo)
    return cuerpo


def foco():
    piezas = [color(cilindro((0, 0, 7.0), 0.22, 14.0, v=14, r2=0.14), "#8a929c"),
              color(caja((0, 0, 0.3), (0.9, 0.9, 0.6), bisel=0.04), "#6c7884"),
              color(caja((0, -0.1, 14.4), (4.2, 0.5, 2.4), bisel=0.06), "#3a4048")]
    luces = []
    for i in range(5):
        for j in range(3):
            luces.append(color(cilindro((-1.6 + i * 0.8, -0.38, 13.7 + j * 0.7), 0.26, 0.1, rot=(math.pi / 2, 0, 0), v=12), "#fff6c8"))
    cuerpo = parte("Foco", piezas, (0, 0, 0))
    parte("Foco_Luces", luces, (0, -0.4, 14.4), cuerpo)
    return cuerpo


def mastil():
    piezas = [color(cilindro((0, 0, 4.0), 0.07, 8.0, v=10, r2=0.04), "#e8ecef"),
              color(esfera((0, 0, 8.08), 0.1, 10), "#ffd23a"),
              color(cilindro((0, 0, 0.1), 0.2, 0.2, v=12), "#6c7884")]
    return parte("Mastil", piezas, (0, 0, 0))


def banco():
    piezas = [color(caja((0, 0, 0.42), (2.0, 0.4, 0.07), bisel=0.01), "#c9a06a"),
              color(caja((0, 0.2, 0.7), (2.0, 0.06, 0.4), bisel=0.01), "#2a6edb")]
    for l in (-1, 1):
        piezas.append(color(caja((l * 0.85, 0, 0.2), (0.07, 0.34, 0.4), bisel=0.01), "#4a525c"))
    return parte("Banco", piezas, (0, 0, 0))


def nevera():
    piezas = [color(caja((0, 0, 0.3), (0.5, 0.4, 0.6), bisel=0.03), "#2a6edb"),
              color(caja((0, 0, 0.62), (0.52, 0.42, 0.05), bisel=0.02), "#f6f4ee"),
              color(cilindro((0, -0.23, 0.35), 0.03, 0.07, rot=(math.pi / 2, 0, 0), v=8), "#ffd23a")]
    return parte("Nevera", piezas, (0, 0, 0))


def mochila():
    piezas = [color(caja((0, 0, 0.22), (0.3, 0.2, 0.42), bisel=0.05), "#e8463a"),
              color(caja((0, -0.11, 0.12), (0.22, 0.05, 0.16), bisel=0.02), "#ffd23a"),
              color(toro((0, 0.02, 0.43), 0.07, 0.012, rot=(math.pi / 2, 0, 0), seg=14), "#1f2630")]
    return parte("Mochila", piezas, (0, 0, 0))


def botella():
    piezas = [color(cilindro((0, 0, 0.12), 0.04, 0.2, v=12), "#7fd3ff"),
              color(cilindro((0, 0, 0.245), 0.018, 0.05, v=10, r2=0.014), "#7fd3ff"),
              color(cilindro((0, 0, 0.275), 0.02, 0.02, v=10), "#e8322a")]
    return parte("Botella", piezas, (0, 0, 0))


protos = [jabalina(), peso(), pertiga(), postes("PostesAltura", 2.5, 4.0, "#f2f3f5"), postes("PostesPertiga", 6.2, 4.6, "#f2f3f5"),
          soporte(), barra_salto(), colchoneta("ColchonetaAltura", 5.0, 3.0, 0.65, "#2a6edb", "#ffd21f"),
          colchoneta("ColchonetaPertiga", 6.0, 5.4, 0.9, "#e8322a", "#2a6edb"), caja_pertiga(), taco(), valla(), cono(),
          podio(), trofeo(), medalla("MedallaOro", "#ffd23a", "#fff0a0"), medalla("MedallaPlata", "#cfd6de", "#ffffff"),
          medalla("MedallaBronce", "#c47a3a", "#e8b080"), marcador(), foco(), mastil(), banco(), nevera(), mochila(), botella()]
todos = [o for o in bpy.data.objects if o.type == 'MESH']
print(f"{len(todos)} piezas, {sum(len(o.data.polygons) for o in todos)} caras")
bpy.ops.object.select_all(action='DESELECT')
for o in todos:
    o.select_set(True)
bpy.ops.export_scene.gltf(filepath=os.path.abspath(os.path.join("web", "atletismo.glb")), export_format='GLB', use_selection=True)
print("Exportado web/atletismo.glb")

if os.environ.get("SIN_RENDER") == "1":
    raise SystemExit

# ---------- MUESTRA ----------
fila = {"Jabalina": (-9.0, -1.5, 0.8), "Peso": (-8.2, -1.5, 0.2), "Pertiga": (-6.6, 0.0, 0.8), "PostesAltura": (-5.2, 0, 0), "PostesPertiga": (-3.4, 0, 0),
        "Soporte": (-7.6, -1.6, 0.4), "Barra": (-5.2, -1.8, 0.2), "ColchonetaAltura": (-1.0, 0, 0), "ColchonetaPertiga": (5.0, 0, 0),
        "CajaPertiga": (-3.0, -3.5, 0), "Taco": (-7.2, -2.6, 0), "Valla": (-8.2, -2.6, 0), "Cono": (-9.0, -2.6, 0), "Podio": (-2.0, -4.2, 0),
        "Trofeo": (0.8, -4.2, 0), "MedallaOro": (1.8, -4.2, 0.2), "MedallaPlata": (2.3, -4.2, 0.2), "MedallaBronce": (2.8, -4.2, 0.2),
        "Marcador": (9.0, 0, 0), "Foco": (13.5, 2, 0), "Mastil": (12.0, 2, 0), "Banco": (4.0, -4.2, 0), "Nevera": (5.2, -4.2, 0),
        "Mochila": (5.9, -4.2, 0), "Botella": (6.4, -4.2, 0)}
for o in protos:
    o.location = fila.get(o.name, (0, 0, 0))
    if o.name in ("Foco", "Mastil", "PostesPertiga"):
        o.scale = (0.5, 0.5, 0.5)
bpy.data.objects["Pertiga"].rotation_euler = (math.radians(5), 0, math.radians(90))
bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 10, 0))
s = bpy.context.object
m = bpy.data.materials.new("Suelo")
m.use_nodes = True
m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*lineal("#7fbf6a"), 1)
s.data.materials.append(m)
bpy.ops.object.camera_add(location=(2.5, -23, 6.5), rotation=(math.radians(76), 0, 0))
bpy.context.scene.camera = bpy.context.object
bpy.context.object.data.lens = 28
bpy.ops.object.light_add(type='SUN', rotation=(math.radians(45), math.radians(10), math.radians(-25)))
bpy.context.object.data.energy = 3.5
w = bpy.data.worlds.new("Mundo")
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.6, 0.8, 0.95, 1)
bpy.context.scene.world = w
esc = bpy.context.scene
esc.render.engine = 'CYCLES'
esc.cycles.samples = int(os.environ.get("MUESTRAS", "32"))
esc.cycles.use_denoising = False
esc.view_settings.view_transform = 'AgX'
esc.render.resolution_x = 2000
esc.render.resolution_y = 800
esc.render.filepath = os.path.abspath(os.environ.get("MUESTRA", "atletismo.png"))
bpy.ops.render.render(write_still=True)
