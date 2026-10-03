"""Poses de atletismo para los personajes de dibujo hechos con Padres.py (Carlos, Miguel, papá y los amigos).

No se ejecuta solo: lo importan Primos.py y Amigos.py y lo añaden a la lista de animaciones.
  correr    carrera de velocista, con los brazos doblados y el cuerpo inclinado (en bucle, 0,6 s)
  correr_pertiga  igual, pero agarrando la pértiga con las dos manos delante de la cadera
  agachado  «¡En sus marcas!»: agachado en el taco de salida, respirando
  lanzar    tomar impulso con el brazo derecho hacia atrás y lanzar (jabalina o peso)
  saltar    en el aire: brazos arriba y las rodillas recogidas
  cansado   con las manos en las rodillas, resoplando, después de la carrera
Los signos son los de Padres.py: en las piernas y los brazos, X negativo es hacia delante; en la columna, X
positivo inclina el cuerpo hacia delante.
"""
import math

import Padres as P

X, Y, Z, S2 = P.X, P.Y, P.Z, P.S2


def _suave(a, b, t):
    """0 antes de a, 1 después de b, con curva suave entre los dos."""
    k = max(0.0, min(1.0, (t - a) / (b - a)))
    return k * k * (3 - 2 * k)


def correr(t):
    a = 0.95 * S2(t)
    rod = lambda fase: 0.35 + 1.55 * max(0.0, S2(t + fase))
    return {
        "raiz": [(Z, 0.1 * S2(t))],
        "columna": [(X, 0.3), (Z, -0.2 * S2(t))],
        "cabeza": [(X, -0.28)],
        "pierna_L": [(X, -a)], "pierna_R": [(X, a)],
        "espinilla_L": [(X, rod(0.25))], "espinilla_R": [(X, rod(0.75))],
        "pie_L": [(X, -0.3 * S2(t + 0.1))], "pie_R": [(X, 0.3 * S2(t + 0.1))],
        "brazo_L": [(X, 0.95 * S2(t)), (Y, -0.12)], "brazo_R": [(X, -0.95 * S2(t)), (Y, 0.12)],
        "antebrazo_L": [(X, -1.45)], "antebrazo_R": [(X, -1.45)],
    }


def correr_pertiga(t):
    p = correr(t)
    for l in ("L", "R"):
        p["brazo_" + l] = [(X, -0.55), (Y, -0.1 if l == "L" else 0.1)]
        p["antebrazo_" + l] = [(X, -0.9), (Z, 0.3 if l == "L" else -0.3)]
    return p


def agachado(t):
    # Una rodilla casi en el suelo, la otra doblada, el cuerpo inclinado y las manos en la línea
    r = 0.025 * S2(t)
    return {
        "columna": [(X, 0.85 + r)],
        "cabeza": [(X, -0.55)],
        "pierna_L": [(X, -1.25)], "pierna_R": [(X, -0.55)],
        "espinilla_L": [(X, 1.95)], "espinilla_R": [(X, 1.35)],
        "pie_L": [(X, 0.3)], "pie_R": [(X, 0.5)],
        "brazo_L": [(X, -0.55), (Y, -0.1)], "brazo_R": [(X, -0.55), (Y, 0.1)],
        "antebrazo_L": [(X, -0.15)], "antebrazo_R": [(X, -0.15)],
    }


def lanzar(t):
    # 0-0,42 toma impulso; 0,42-0,6 lanza; 0,6-1 se queda con el brazo estirado y vuelve a la postura de salida
    w = _suave(0.0, 0.42, t)
    l = _suave(0.42, 0.6, t)
    v = _suave(0.78, 1.0, t)
    brazo = 2.3 * w - 4.7 * l + 2.4 * v      # atrás (+), delante (−) y de nuevo a la postura inicial
    giro = 0.5 * w - 0.9 * l + 0.4 * v
    return {
        "columna": [(Z, giro), (X, 0.05 + 0.25 * l * (1 - v))],
        "cabeza": [(Z, -0.3 * giro)],
        "brazo_R": [(X, brazo), (Y, 0.45 * w * (1 - l))],
        "antebrazo_R": [(X, -0.5 - 0.7 * w * (1 - l))],
        "brazo_L": [(X, -1.3 * w * (1 - l)), (Y, -0.25 * w * (1 - l))],
        "pierna_L": [(X, -0.45 * l * (1 - v))], "pierna_R": [(X, 0.35 * w * (1 - l))],
        "espinilla_R": [(X, 0.25 * w)],
    }


def saltar(t):
    s = 0.08 * S2(t, 2)
    return {
        "columna": [(X, 0.1)],
        "cabeza": [(X, -0.2)],
        "brazo_L": [(X, -2.75 + s), (Y, -0.2)], "brazo_R": [(X, -2.75 - s), (Y, 0.2)],
        "antebrazo_L": [(X, -0.15)], "antebrazo_R": [(X, -0.15)],
        "pierna_L": [(X, -1.15 + s)], "pierna_R": [(X, -0.3 - s)],
        "espinilla_L": [(X, 1.25)], "espinilla_R": [(X, 0.55)],
    }


def cansado(t):
    r = 0.045 * S2(t, 2)
    return {
        "columna": [(X, 0.95 + r)],
        "cabeza": [(X, 0.25)],
        "pierna_L": [(X, -0.28)], "pierna_R": [(X, -0.28)],
        "espinilla_L": [(X, 0.35)], "espinilla_R": [(X, 0.35)],
        "brazo_L": [(X, -0.35), (Y, -0.15)], "brazo_R": [(X, -0.35), (Y, 0.15)],
        "antebrazo_L": [(X, -0.2)], "antebrazo_R": [(X, -0.2)],
    }


# nombre, segundos que dura la vuelta completa, pose
ANIMS_ATLETISMO = (("correr", 0.6, correr), ("correr_pertiga", 0.6, correr_pertiga), ("agachado", 2.0, agachado),
                   ("lanzar", 1.4, lanzar), ("saltar", 1.0, saltar), ("cansado", 1.6, cansado))
