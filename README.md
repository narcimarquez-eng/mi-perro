# mi-perro

Un perro beagle hecho con Blender (Python) y una playa de agua cristalina para pasearlo.

- `Perro.py`: crea el perro, renderiza `perro.png` y exporta `perro.glb`.
- `Playa.py`: crea la playa (arena, dunas, agua, palmeras, rocas, sombrilla), renderiza `playa.png` y exporta `playa.glb`.
- `web/index.html`: juego en el navegador (three.js) para mover al perro por la playa.

## Renderizar

En la pestaña **Actions**, ejecuta el workflow **Render Perro**. Deja las imágenes y los modelos en los artefactos `perro-3d` y `playa-web`.

En tu ordenador:

```sh
blender -b --factory-startup --python Perro.py
blender -b --factory-startup --python Playa.py
```

## Jugar

La página necesita un servidor (los navegadores no cargan modelos desde `file://`):

```sh
cd web
python3 -m http.server
```

Abre http://localhost:8000. Controles: WASD o flechas para andar, Shift corre, Espacio salta, B ladra. En el móvil, joystick y botones.

Si cambias `Perro.py` o `Playa.py`, copia los `.glb` nuevos a `web/`. La forma del terreno (`altura()`) está duplicada en `Playa.py` y `web/index.html`: si la cambias, cámbiala en los dos.
