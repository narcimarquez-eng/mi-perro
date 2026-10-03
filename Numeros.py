"""El pueblo de los números: personajes hechos de bloques (del 1 al 10), juguetes, regalos, el carrito
de Manuel y la decoración de la zona de juegos de matemáticas.

blender -b --factory-startup --python Numeros.py

Exporta numeros.glb (cada pieza en el origen, con su nombre) y renderiza numeros.png.
Las piezas blancas (regalos, globos, toldos) se tiñen en la web con el color de cada copia.
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


# ---------- PERSONAJES DE BLOQUES ----------
CUBO = 0.5
# Forma de cada número: columnas x filas (en bloques)
FORMAS = {1: (1, 1), 2: (1, 2), 3: (1, 3), 4: (1, 4), 5: (1, 5), 6: (2, 3), 7: (1, 7), 8: (2, 4), 9: (3, 3), 10: (2, 5)}
COLORES = {1: "#ee3b33", 2: "#ff8c1a", 3: "#ffd21f", 4: "#3dbe4a", 5: "#2cb7e6", 6: "#6b52d9", 8: "#e64aa6", 9: "#8f9aa6", 10: "#f6f6f2"}
ARCOIRIS = ["#ee3b33", "#ff8c1a", "#ffd21f", "#3dbe4a", "#2cb7e6", "#3a64d8", "#8e4fd6"]


def oscuro(hexa, k=0.62):
    return lineal(hexa) * k


def bloque(cx, cz, hexa, borde=None, huecos=()):
    """Un bloque con marco y paneles un poco más claros en las caras que se ven."""
    s = CUBO
    marco = caja((cx, 0, cz), (s, s, s), bisel=0.05, seg=2)
    pintar(marco, lambda co, n: oscuro(borde or hexa, 0.75 if borde else 0.62))
    piezas = [marco]
    base = lineal(hexa)
    for eje, signo in ((0, 1), (0, -1), (1, 1), (1, -1), (2, 1), (2, -1)):
        if (eje, signo) in huecos:
            continue
        esc = [s * 0.8] * 3
        esc[eje] = 0.02
        loc = [cx, 0, cz]
        loc[eje] += signo * (s / 2 + 0.004)
        p = caja(tuple(loc), tuple(esc))
        pintar(p, lambda co, n: base)
        piezas.append(p)
    return piezas


def personaje(n):
    cols, filas = FORMAS[n]
    s = CUBO
    ancho = cols * s
    piezas = []
    pies = 0.18  # piernas cortitas
    for c in range(cols):
        for f in range(filas):
            k = f * cols + c
            hexa = ARCOIRIS[f] if n == 7 else COLORES[n]
            borde = "#e8322a" if n == 10 else None
            huecos = []
            if c > 0:
                huecos.append((0, -1))
            if c < cols - 1:
                huecos.append((0, 1))
            if f > 0:
                huecos.append((2, -1))
            if f < filas - 1:
                huecos.append((2, 1))
            cx = -ancho / 2 + s / 2 + c * s
            cz = pies + s / 2 + f * s
            piezas += bloque(cx, cz, hexa, borde, huecos)
    alto = pies + filas * s
    cara_z = alto - s * 0.5
    cara_y = -s / 2 - 0.02
    top = ARCOIRIS[filas - 1] if n == 7 else COLORES[n]
    sep = 0.11 if cols == 1 else 0.14
    piezas += ojos(0, cara_y, cara_z + 0.04, sep, 0.075 if cols == 1 else 0.09)
    piezas.append(sonrisa(0, cara_y - 0.005, cara_z - 0.09, 0.07 if cols == 1 else 0.09, 0.016))
    for l in (-1, 1):
        mej = color(esfera((l * (sep + 0.08), cara_y + 0.01, cara_z - 0.08), (0.045, 0.012, 0.03), 12), "#ff8fa3")
        piezas.append(mej)
    # Brazos (del bloque de arriba, hacia los lados) y piernas
    hombro_z = alto - s * (0.75 if filas > 1 else 0.55)
    brazo = top if n != 7 else ARCOIRIS[min(filas - 2, 6)] if filas > 1 else top
    for l in (-1, 1):
        x0 = l * (ancho / 2 - 0.02)
        b = skin("Brazo", [(x0, 0, hombro_z), (x0 + l * 0.16, 0, hombro_z - 0.12), (x0 + l * 0.22, -0.02, hombro_z - 0.28)], [(0, 1), (1, 2)],
                 [0.045, 0.04, 0.038], sub=1)
        color(b, brazo)
        mano = color(esfera((x0 + l * 0.23, -0.02, hombro_z - 0.31), 0.065, 14), brazo)
        mano_o = pintar(mano, lambda co, nn: oscuro(brazo, 0.85))
        piezas += [b, mano_o]
    patas = [-ancho / 4, ancho / 4] if cols > 1 else [-0.11, 0.11]
    pierna = ARCOIRIS[0] if n == 7 else COLORES[n]
    for px in patas:
        p = cilindro((px, 0, pies / 2 + 0.03), 0.06, pies, v=14)
        pintar(p, lambda co, nn: oscuro(pierna, 0.8))
        pie = esfera((px, -0.05, 0.045), (0.09, 0.12, 0.055), 14)
        pintar(pie, lambda co, nn: oscuro(pierna, 0.55))
        piezas += [p, pie]
    o = unir(piezas, f"Bloque{n}")
    return o


# ---------- JUGUETES ----------
def osito():
    marron, claro = "#b07a45", "#ead0a8"
    p = [color(esfera((0, 0, 0.14), (0.12, 0.1, 0.14)), marron),
         color(esfera((0, -0.04, 0.13), (0.07, 0.07, 0.09)), claro),
         color(esfera((0, 0, 0.33), 0.1), marron),
         color(esfera((0, -0.08, 0.31), (0.045, 0.04, 0.035)), claro),
         color(esfera((0, -0.115, 0.32), 0.015, 10), "#2a1a12")]
    for l in (-1, 1):
        p.append(color(esfera((l * 0.075, 0, 0.42), (0.04, 0.025, 0.04), 12), marron))
        p.append(color(esfera((l * 0.04, -0.085, 0.36), 0.013, 8), "#111111"))
        p.append(color(esfera((l * 0.13, -0.02, 0.17), (0.04, 0.04, 0.075)), marron))
        p.append(color(esfera((l * 0.07, -0.06, 0.04), (0.05, 0.07, 0.045)), marron))
    for l in (-1, 1):
        p.append(color(esfera((l * 0.035, -0.06, 0.245), (0.035, 0.02, 0.025), 10), "#e8322a"))
    return unir(p, "Osito")


def robot():
    p = [color(caja((0, 0, 0.17), (0.2, 0.14, 0.18), bisel=0.02), "#9fb6cc"),
         color(caja((0, -0.072, 0.18), (0.11, 0.01, 0.08), bisel=0.005), "#2b3a4a"),
         color(caja((0, 0, 0.34), (0.15, 0.13, 0.12), bisel=0.02), "#c8d6e4"),
         color(cilindro((0, 0, 0.43), 0.008, 0.07), "#555555"),
         color(esfera((0, 0, 0.47), 0.022, 10), "#ff3b30")]
    for k, c in enumerate(["#ff3b30", "#ffd21f", "#3dbe4a"]):
        p.append(color(esfera((-0.03 + k * 0.03, -0.08, 0.19), 0.012, 8), c))
    for l in (-1, 1):
        p.append(color(cilindro((l * 0.04, -0.066, 0.35), 0.024, 0.01, rot=(math.pi / 2, 0, 0)), "#4ff0ff"))
        p.append(color(cilindro((l * 0.13, 0, 0.17), 0.025, 0.14), "#7d90a6"))
        p.append(color(esfera((l * 0.13, 0, 0.09), 0.032, 10), "#ffb400"))
        p.append(color(caja((l * 0.055, 0, 0.04), (0.06, 0.08, 0.08), bisel=0.01), "#7d90a6"))
    return unir(p, "Robot")


def cohete():
    cuerpo = cilindro((0, 0, 0.22), 0.07, 0.3)
    pintar(cuerpo, lambda co, n: lineal("#e8322a") if abs(co.z - 0.0) < 0.02 else lineal("#f4f4f4"))
    p = [cuerpo, color(cilindro((0, 0, 0.44), 0.07, 0.14, r2=0.0), "#e8322a"),
         color(cilindro((0, -0.068, 0.27), 0.032, 0.012, rot=(math.pi / 2, 0, 0)), "#2c9ae8"),
         color(cilindro((0, 0, 0.055), 0.05, 0.05, r2=0.07), "#555c66")]
    for k in range(3):
        a = k * 2 * math.pi / 3 + math.pi / 2
        f = caja((math.cos(a) * 0.085, math.sin(a) * 0.085, 0.1), (0.03, 0.012, 0.1), rot=(0, 0, a + math.pi / 2), bisel=0.004)
        p.append(color(f, "#e8322a"))
    return unir(p, "Cohete")


def dinosaurio():
    verde = lineal("#4cc25a")
    d = skin("Dino", [(0, 0.3, 0.12), (0, 0.15, 0.17), (0, 0.0, 0.2), (0, -0.12, 0.22), (0, -0.18, 0.36), (0, -0.24, 0.42)],
             [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)], [0.02, 0.06, 0.11, 0.09, 0.05, 0.07], sub=2)
    pintar(d, lambda co, n: lineal("#f2e27a") if n.z < -0.4 and co.z < 0.2 else verde)
    p = [d]
    for l in (-1, 1):
        for y in (-0.07, 0.09):
            p.append(color(cilindro((l * 0.07, y, 0.06), 0.035, 0.12), "#3a9e47"))
        p.append(color(esfera((l * 0.03, -0.3, 0.45), 0.014, 8), "#111111"))
    for k in range(5):
        y = 0.18 - k * 0.07
        z = 0.24 + (0.06 if k > 2 else 0.04) + k * 0.012
        p.append(color(cilindro((0, y, z), 0.025, 0.06, r2=0.0, v=8), "#ff9a2e"))
    return unir(p, "Dinosaurio")


def tren():
    p = [color(caja((0, 0.02, 0.12), (0.14, 0.28, 0.12), bisel=0.015), "#2a6fe0"),
         color(caja((0, 0.1, 0.24), (0.15, 0.12, 0.14), bisel=0.015), "#e8322a"),
         color(caja((0, 0.1, 0.32), (0.18, 0.15, 0.025), bisel=0.005), "#ffd21f"),
         color(cilindro((0, -0.06, 0.22), 0.025, 0.08), "#222222"),
         color(cilindro((0, -0.06, 0.27), 0.04, 0.03, r2=0.025), "#222222"),
         color(cilindro((0, -0.125, 0.12), 0.05, 0.02, rot=(math.pi / 2, 0, 0)), "#ffd21f")]
    for l in (-1, 1):
        for y in (-0.08, 0.04, 0.13):
            p.append(color(cilindro((l * 0.075, y, 0.05), 0.05, 0.025, rot=(0, math.pi / 2, 0)), "#e8322a"))
        p.append(color(caja((l * 0.076, 0.1, 0.26), (0.005, 0.07, 0.05)), "#bfe6ff"))
    return unir(p, "Tren")


def cochecito():
    p = [color(caja((0, 0, 0.09), (0.18, 0.34, 0.08), bisel=0.03), "#ff7a1a"),
         color(caja((0, 0.03, 0.16), (0.15, 0.17, 0.08), bisel=0.03), "#ff7a1a"),
         color(caja((0, 0.03, 0.165), (0.155, 0.13, 0.055), bisel=0.01), "#bfe6ff"),
         color(caja((0, -0.172, 0.09), (0.12, 0.01, 0.03)), "#fff3b0")]
    for l in (-1, 1):
        for y in (-0.11, 0.11):
            p.append(color(cilindro((l * 0.09, y, 0.05), 0.05, 0.035, rot=(0, math.pi / 2, 0)), "#222222"))
            p.append(color(cilindro((l * 0.108, y, 0.05), 0.025, 0.004, rot=(0, math.pi / 2, 0)), "#dddddd"))
    return unir(p, "Cochecito")


def pelota():
    o = esfera((0, 0, 0.15), 0.15, 28)
    cols = [lineal(h) for h in ("#ee3b33", "#ffffff", "#2c9ae8", "#ffffff", "#ffd21f", "#ffffff")]

    def col(co, n):
        if abs(co.z - 0.15) > 0.135:
            return lineal("#ffffff")
        a = (math.atan2(co.y, co.x) + math.pi) / (2 * math.pi)
        return cols[int(a * 6) % 6]
    pintar(o, col)
    return unir([o], "Pelota")


def patito():
    p = [color(esfera((0, 0.02, 0.1), (0.13, 0.15, 0.1)), "#ffd21f"),
         color(esfera((0, -0.08, 0.24), 0.08), "#ffd21f"),
         color(esfera((0, -0.16, 0.225), (0.05, 0.04, 0.02)), "#ff8c1a"),
         color(esfera((0, 0.15, 0.15), (0.04, 0.04, 0.05)), "#ffd21f")]
    for l in (-1, 1):
        p.append(color(esfera((l * 0.035, -0.14, 0.27), 0.013, 8), "#111111"))
        p.append(color(esfera((l * 0.12, 0.03, 0.12), (0.03, 0.08, 0.05)), "#f5c400"))
    return unir(p, "Patito")


def tambor():
    t = cilindro((0, 0, 0.1), 0.14, 0.18, v=28)

    def col(co, n):
        if n.z > 0.5:
            return lineal("#fdf6e3")
        a = math.atan2(co.y, co.x)
        zig = 0.1 + 0.05 * abs(((a * 8 / math.pi) % 2) - 1)
        return lineal("#2c9ae8") if co.z > zig else lineal("#e8322a")
    pintar(t, col)
    p = [t, color(toro((0, 0, 0.19), 0.14, 0.012), "#ffd21f"), color(toro((0, 0, 0.012), 0.14, 0.012), "#ffd21f")]
    for l in (-1, 1):
        p.append(color(cilindro((l * 0.06, -0.05, 0.215), 0.007, 0.2, rot=(math.radians(80), 0, l * 0.5)), "#c8955a"))
        p.append(color(esfera((l * 0.06 + l * 0.05, -0.15, 0.23), 0.016, 8), "#e8322a"))
    return unir(p, "Tambor")


def xilofono():
    p = [color(caja((-0.1, 0, 0.03), (0.02, 0.36, 0.04)), "#c8955a"), color(caja((0.1, 0, 0.03), (0.02, 0.36, 0.04)), "#c8955a")]
    for k, c in enumerate(ARCOIRIS[:6]):
        ancho = 0.3 - k * 0.025
        p.append(color(caja((0, -0.15 + k * 0.06, 0.06), (ancho, 0.045, 0.02), bisel=0.005), c))
    p.append(color(cilindro((0.06, -0.24, 0.09), 0.006, 0.18, rot=(0, math.pi / 2, 0.4)), "#c8955a"))
    p.append(color(esfera((0.15, -0.28, 0.09), 0.018, 10), "#ffffff"))
    return unir(p, "Xilofono")


def peonza():
    c = cilindro((0, 0, 0.14), 0.14, 0.18, r2=0.0, rot=(math.pi, 0, 0), v=28)
    pintar(c, lambda co, n: lineal(ARCOIRIS[int((co.z) / 0.04) % 7]))
    p = [c, color(cilindro((0, 0, 0.245), 0.14, 0.03, r2=0.1, v=28), "#ee3b33"),
         color(cilindro((0, 0, 0.3), 0.02, 0.08), "#8f4fd6"), color(esfera((0, 0, 0.345), 0.028, 10), "#ffd21f")]
    return unir(p, "Peonza")


def avion():
    f = cilindro((0, 0, 0.12), 0.055, 0.42, rot=(math.pi / 2, 0, 0))
    p = [color(f, "#ffd21f"), color(cilindro((0, -0.23, 0.12), 0.055, 0.05, r2=0.02, rot=(math.pi / 2, 0, 0)), "#ee3b33"),
         color(caja((0, -0.03, 0.11), (0.5, 0.1, 0.018), bisel=0.008), "#2c9ae8"),
         color(caja((0, 0.18, 0.13), (0.18, 0.06, 0.012), bisel=0.004), "#2c9ae8"),
         color(caja((0, 0.19, 0.19), (0.012, 0.06, 0.1), bisel=0.004), "#ee3b33"),
         color(caja((0, -0.265, 0.12), (0.2, 0.008, 0.025)), "#333333"),
         color(caja((0, -0.04, 0.17), (0.07, 0.08, 0.04), bisel=0.015), "#bfe6ff")]
    for l in (-1, 1):
        p.append(color(cilindro((l * 0.08, -0.04, 0.03), 0.025, 0.02, rot=(0, math.pi / 2, 0)), "#222222"))
        p.append(color(cilindro((l * 0.08, -0.04, 0.06), 0.005, 0.06), "#888888"))
    return unir(p, "Avion")


def barquito():
    c = caja((0, 0, 0.06), (0.16, 0.36, 0.1), bisel=0.04)
    for v in c.data.vertices:
        if v.co.z < 0.05:
            v.co.x *= 0.65
            v.co.y *= 0.85
        if v.co.y < -0.1:
            v.co.x *= 0.45 + 0.55 * max(0, (v.co.y + 0.18) / 0.08)
    pintar(c, lambda co, n: lineal("#ffffff") if co.z > 0.09 else lineal("#ee3b33"))
    me = bpy.data.meshes.new("Vela")
    me.from_pydata([(0, -0.02, 0.13), (0, 0.13, 0.14), (0, -0.01, 0.46)], [], [(0, 1, 2)])
    vela = objeto("Vela", me)
    s = vela.modifiers.new("S", 'SOLIDIFY')
    s.thickness = 0.01
    aplicar(vela)
    p = [c, color(cilindro((0, -0.03, 0.28), 0.008, 0.36), "#c8955a"), color(vela, "#2c9ae8"),
         color(caja((0, 0.1, 0.13), (0.08, 0.08, 0.05), bisel=0.01), "#ffd21f")]
    return unir(p, "Barquito")


def cubo_magico():
    caras = {(0, 1): "#ee3b33", (0, -1): "#ff8c1a", (1, 1): "#3dbe4a", (1, -1): "#2c7be8", (2, 1): "#ffffff", (2, -1): "#ffd21f"}
    s = 0.24
    p = [color(caja((0, 0, s / 2), (s, s, s), bisel=0.012), "#1a1a1a")]
    for (eje, signo), c in caras.items():
        for i in range(3):
            for j in range(3):
                otros = [a for a in range(3) if a != eje]
                loc = [0, 0, s / 2]
                loc[eje] += signo * (s / 2 + 0.002)
                loc[otros[0]] += (i - 1) * s / 3
                loc[otros[1]] += (j - 1) * s / 3
                esc = [s / 3 * 0.84] * 3
                esc[eje] = 0.006
                p.append(color(caja(tuple(loc), tuple(esc), bisel=0.002, seg=1), c))
    return unir(p, "CuboMagico")


def trofeo():
    p = [cilindro((0, 0, 0.03), 0.09, 0.06, v=24), cilindro((0, 0, 0.1), 0.02, 0.1, v=16),
         cilindro((0, 0, 0.24), 0.04, 0.2, r2=0.11, v=28), toro((0, 0, 0.34), 0.11, 0.012)]
    for l in (-1, 1):
        a = toro((l * 0.11, 0, 0.25), 0.05, 0.011, rot=(math.pi / 2, 0, 0))
        p.append(a)
    p.append(cilindro((0, 0, 0.42), 0.04, 0.05, r2=0.0, v=5))
    for o in p:
        color(o, "#ffc21a", VC_ORO)
    suave(p[2])
    return unir(p, "Trofeo")


# ---------- REGALO Y CARRITO ----------
def regalo():
    caja_r = color(caja((0, 0, 0.17), (0.34, 0.34, 0.32), bisel=0.01), "#ffffff")
    caja_r.name = caja_r.data.name = "RegaloCaja"
    tapa = color(caja((0, 0, 0.35), (0.38, 0.38, 0.07), bisel=0.012), "#ffffff")
    cinta = [caja((0, 0, 0.355), (0.39, 0.07, 0.075)), caja((0, 0, 0.355), (0.07, 0.39, 0.075))]
    for l in (-1, 1):
        cinta.append(toro((l * 0.07, 0, 0.43), 0.06, 0.02, rot=(math.pi / 2, 0, 0)))
    cinta.append(esfera((0, 0, 0.42), 0.035, 12))
    for o in cinta:
        color(o, "#ffffff")
    lazo = unir(cinta, "RegaloLazo")
    tapa.name = tapa.data.name = "RegaloTapa"
    lados = [caja((0, 0, 0.16), (0.345, 0.07, 0.3)), caja((0, 0, 0.16), (0.07, 0.345, 0.3))]
    for o in lados:
        color(o, "#ffffff")
    cinta_caja = unir(lados, "RegaloCinta")
    return [caja_r, tapa, lazo, cinta_caja]


def carrito():
    # Cajón rojo con borde blanco, como los carritos de juguetes
    cajon = caja((0, 0, 0.32), (0.62, 0.95, 0.26), bisel=0.04)
    bm = bmesh.new()
    bm.from_mesh(cajon.data)
    arriba = [f for f in bm.faces if f.normal.z > 0.9]
    bmesh.ops.inset_region(bm, faces=arriba, thickness=0.04)
    bmesh.ops.translate(bm, verts=list({v for f in arriba for v in f.verts}), vec=(0, 0, -0.2))
    bm.to_mesh(cajon.data)
    bm.free()
    pintar(cajon, lambda co, n: lineal("#ffffff") if co.z > 0.42 else lineal("#e8322a"))
    p = [cajon, color(caja((0, 0, 0.17), (0.5, 0.82, 0.04)), "#3a3a3a")]
    for y in (-0.33, 0.33):
        p.append(color(cilindro((0, y, 0.11), 0.018, 0.62, rot=(0, math.pi / 2, 0)), "#555555"))
    # Lanza para tirar del carrito (hacia delante, -Y)
    p.append(color(cilindro((0, -0.63, 0.25), 0.016, 0.34, rot=(math.radians(-62), 0, 0)), "#3a3a3a"))
    p.append(color(cilindro((0, -0.795, 0.33), 0.022, 0.18, rot=(0, math.pi / 2, 0)), "#1f1f1f"))
    o = unir(p, "Carrito")
    rueda = cilindro((0, 0, 0), 0.11, 0.06, rot=(0, math.pi / 2, 0), v=24)
    pintar(rueda, lambda co, n: lineal("#ffffff") if (co.y ** 2 + co.z ** 2) < 0.05 ** 2 else lineal("#222222"))
    suave(rueda)
    rueda.name = rueda.data.name = "CarritoRueda"
    return [o, rueda]


# ---------- DECORACIÓN DEL PUEBLO ----------
def dado():
    s = 1.0
    d = color(caja((0, 0, s / 2), (s, s, s), bisel=0.12, seg=3), "#ffffff")
    puntos = {(2, 1): [(0, 0)], (2, -1): [(-1, -1), (1, 1), (-1, 1), (1, -1), (0, 0), (0, 0)],
              (1, -1): [(-1, -1), (1, 1)], (1, 1): [(-1, -1), (0, 0), (1, 1)], (0, 1): [(-1, -1), (1, 1), (-1, 1), (1, -1)],
              (0, -1): [(-1, -1), (1, 1), (-1, 1), (1, -1), (0, 0)]}
    p = [d]
    for (eje, signo), lista in puntos.items():
        for i, j in set(lista):
            otros = [a for a in range(3) if a != eje]
            loc = [0, 0, s / 2]
            loc[eje] += signo * s / 2
            loc[otros[0]] += i * 0.27
            loc[otros[1]] += j * 0.27
            esc = [0.09, 0.09, 0.09]
            esc[eje] = 0.03
            p.append(color(esfera(tuple(loc), tuple(esc), 8), "#e8322a" if (eje, signo) == (2, 1) else "#1a1d24"))
    return unir(p, "Dado")


def abaco():
    p = [color(caja((-1.1, 0, 0.9), (0.12, 0.2, 1.8), bisel=0.03), "#c8955a"),
         color(caja((1.1, 0, 0.9), (0.12, 0.2, 1.8), bisel=0.03), "#c8955a"),
         color(caja((0, 0, 1.78), (2.4, 0.22, 0.12), bisel=0.03), "#a36d3a"),
         color(caja((0, 0, 0.1), (2.6, 0.5, 0.2), bisel=0.03), "#a36d3a")]
    for k in range(5):
        z = 0.45 + k * 0.28
        p.append(color(cilindro((0, 0, z), 0.02, 2.1, rot=(0, math.pi / 2, 0)), "#dddddd"))
        for b in range(10):
            x = -0.95 + b * 0.13 + (0.0 if b < 5 + k % 3 else 0.55)
            bola = esfera((x, 0, z), (0.065, 0.11, 0.11), 10)
            color(bola, ARCOIRIS[k] if b < 5 else ARCOIRIS[(k + 3) % 7])
            p.append(bola)
    return unir(p, "Abaco")


def arbol_piruleta():
    palo = color(cilindro((0, 0, 1.2), 0.07, 2.4), "#ffffff")
    pintar(palo, lambda co, n: lineal("#ee3b33") if int((co.z + math.atan2(co.y, co.x) * 0.08) / 0.18) % 2 else lineal("#ffffff"))
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=36, radius=1, location=(0, 0, 3.0), rotation=(math.pi / 2, 0, 0))
    disco = bpy.context.object
    bpy.ops.object.transform_apply(location=False, rotation=True)
    disco.scale = (0.9, 0.2, 0.9)
    bpy.ops.object.transform_apply(location=True, scale=True)
    suave(disco)

    def espiral(co, n):
        x, z = co.x, co.z - 3.0
        r = math.hypot(x, z)
        a = math.atan2(z, x)
        k = int((r * 7 + a / (2 * math.pi) * 2) % 2)
        return lineal("#ffffff") if k else lineal("#ff5fa2")
    pintar(disco, espiral)
    # El disco necesita más vértices para la espiral
    return unir([palo, disco], "ArbolPiruleta")


def subdividir(o, cortes):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cortes, use_grid_fill=True)
    bm.to_mesh(o.data)
    bm.free()
    return o


def puesto():
    """Puesto de juego: mostrador y postes; el toldo de rayas va aparte (PuestoToldo, blanco para teñirlo)."""
    p = [color(caja((0, 0.2, 0.5), (2.6, 0.8, 1.0), bisel=0.05), "#fff6e0"),
         color(caja((0, -0.22, 1.02), (2.75, 0.2, 0.06), bisel=0.02), "#c8955a")]
    for x in (-1.3, 1.3):
        for y in (-0.15, 0.55):
            p.append(color(cilindro((x, y, 1.45), 0.05, 2.9), "#ffffff"))
    base = unir(p, "Puesto")
    # Toldo: rayas, las pares blancas y las impares de color (se tiñen en la web)
    blancas, de_color = [], []
    for k in range(10):
        x = -1.45 + 0.29 * k + 0.145
        r = caja((x, 0.2, 2.95), (0.29, 1.3, 0.05))
        for v in r.data.vertices:
            v.co.z += -(v.co.y - 0.2) * 0.22
        (blancas if k % 2 == 0 else de_color).append(r)
        fleco = recortar(cilindro((x, -0.5, 2.98), 0.145, 0.02, rot=(math.pi / 2, 0, 0), v=16), lambda co: co.z > 2.99)
        (blancas if k % 2 == 0 else de_color).append(fleco)
    for o in blancas:
        color(o, "#ffffff")
    for o in de_color:
        color(o, "#ffffff")
    b = unir(blancas, "PuestoToldoBlanco")
    t = unir(de_color, "PuestoToldo")
    return [base, t, b]


def globo():
    g = esfera((0, 0, 0.0), (0.32, 0.32, 0.4), 22)
    nudo = cilindro((0, 0, -0.42), 0.02, 0.06, r2=0.05, v=10)
    o = unir([color(g, "#ffffff"), color(nudo, "#ffffff")], "Globo")
    return o


def estanteria():
    p = []
    for z in (0.02, 0.55, 1.08, 1.6):
        p.append(caja((0, 0, z + 0.02), (1.8, 0.4, 0.04)))
    for x in (-0.9, 0.9):
        p.append(caja((x, 0, 0.82), (0.05, 0.4, 1.64)))
    p.append(caja((0, 0.19, 0.82), (1.8, 0.02, 1.64)))
    for o in p:
        color(o, "#f3e3c4")
    return unir(p, "Estanteria")


def baul():
    b = caja((0, 0, 0.25), (0.9, 0.55, 0.5), bisel=0.03)
    pintar(b, lambda co, n: lineal("#4a8fe0") if abs(co.z - 0.25) < 0.14 else lineal("#ffd21f"))
    t = caja((0, -0.285, 0.05), (0.92, 0.57, 0.1), bisel=0.03)
    pintar(t, lambda co, n: lineal("#ee3b33"))
    # La tapa gira sobre la bisagra de atrás (+Y): su origen queda en la bisagra
    t.name = t.data.name = "BaulTapa"
    return [unir([b], "Baul"), t]


def arco():
    """Arco de la entrada hecho con bloques de colores."""
    p = []
    k = 0
    for x in (-3.0, 3.0):
        for f in range(8):
            c = ARCOIRIS[k % 7]
            k += 1
            p += bloque(x, 0.25 + f * 0.5 + 0.0, c, None, [])
    for i in range(13):
        x = -3.0 + i * 0.5
        p += bloque(x, 4.25, ARCOIRIS[i % 7], None, [])
    o = unir(p, "Arco")
    for v in o.data.vertices:
        v.co.z -= 0.0
    return o


proto = [personaje(n) for n in range(1, 11)]
proto += [osito(), robot(), cohete(), dinosaurio(), tren(), cochecito(), pelota(), patito(), tambor(), xilofono(),
          peonza(), avion(), barquito(), cubo_magico(), trofeo()]
proto += regalo() + carrito() + [dado(), abaco(), arbol_piruleta(), globo(), estanteria()] + baul() + puesto() + [arco()]
for o in proto:
    if o.name in ("RegaloCaja", "RegaloTapa", "RegaloLazo", "RegaloCinta", "CarritoRueda", "BaulTapa"):
        continue
    o.location = (0, 0, 0)
for o in proto:
    print(f"{o.name}: {len(o.data.polygons)} caras")
bpy.ops.object.select_all(action='DESELECT')
for o in proto:
    o.select_set(True)
bpy.ops.export_scene.gltf(filepath=os.path.abspath(os.environ.get("SALIDA", "numeros.glb")), export_format='GLB', use_selection=True)
print("Exportado numeros.glb")

if os.environ.get("SIN_RENDER") == "1":
    raise SystemExit

# ---------- MUESTRA ----------
por = {o.name: o for o in proto}
for o in proto:
    o.hide_render = True


def copia(nombre, loc, rz=0.0, esc=1.0):
    o = bpy.data.objects.new(nombre + "_c", por[nombre].data)
    bpy.context.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (0, 0, rz)
    o.scale = (esc,) * 3
    return o


x = -9.0
for n in range(1, 11):
    cols = FORMAS[n][0]
    x += cols * CUBO / 2 + 0.35
    copia(f"Bloque{n}", (x, 0, 0), 0)
    x += cols * CUBO / 2 + 0.35
juguetes = ["Osito", "Robot", "Cohete", "Dinosaurio", "Tren", "Cochecito", "Pelota", "Patito", "Tambor", "Xilofono", "Peonza", "Avion", "Barquito", "CuboMagico", "Trofeo"]
for k, n in enumerate(juguetes):
    copia(n, (-6.3 + k * 0.9, -2.4, 0), 0.3, 1.6)
copia("Carrito", (5.2, -1.2, 0), 0.6)
copia("Dado", (-9.6, 2.5, 0), 0.4)
copia("ArbolPiruleta", (8.6, 2.5, 0))
copia("Abaco", (-4, 4.5, 0))
bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 10, 0))
s = bpy.context.object
m = bpy.data.materials.new("Suelo")
m.use_nodes = True
m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*lineal("#9ad66a"), 1)
s.data.materials.append(m)
bpy.ops.object.camera_add(location=(0, -15, 4.2), rotation=(math.radians(80), 0, 0))
bpy.context.scene.camera = bpy.context.object
bpy.context.object.data.lens = 30
bpy.ops.object.light_add(type='SUN', rotation=(math.radians(45), math.radians(10), math.radians(-25)))
bpy.context.object.data.energy = 3.5
w = bpy.data.worlds.new("Mundo")
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.6, 0.8, 1.0, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 0.8
bpy.context.scene.world = w
esc = bpy.context.scene
esc.render.engine = 'CYCLES'
esc.cycles.samples = int(os.environ.get("MUESTRAS", "48"))
esc.cycles.use_denoising = False
esc.view_settings.view_transform = 'AgX'
esc.view_settings.look = 'AgX - Punchy'
esc.render.resolution_x = 1400
esc.render.resolution_y = 700
esc.render.filepath = os.path.abspath(os.environ.get("IMAGEN", "numeros.png"))
bpy.ops.render.render(write_still=True)
