# mi-perro

Un perro bretón español hecho con Blender (Python) y una playa de agua cristalina para pasearlo.

- `Perro.py`: crea el perro (un bretón español blanco y negro, con el hocico moteado y ojos color miel), renderiza `perro.png` y exporta `perro.glb`. Los colores del pelaje van pintados en los vértices para que también se vean en la web.
- `Playa.py`: crea la playa (arena, dunas, agua, palmeras, rocas, sombrilla), renderiza `playa.png` y exporta `playa.glb`.
- `Nino.py`: prepara el modelo 3D de Manuel: le quita el balón de la mano, baja el brazo derecho y rehace sus animaciones en espejo del izquierdo, añade las animaciones `kick` (chutar) y `pickup` (agacharse), crea un balón aparte y reduce las texturas. Exporta `nino.glb`.
- `web/index.html`: juego en el navegador (three.js). Manuel juega al balón con el perro y hay seis tareas: traer el balón, recoger conchas, encontrar el hueso, rescatar el balón del mar, saltar desde el muelle y nadar hasta la boya.

## Renderizar

En la pestaña **Actions**, ejecuta el workflow **Render Perro**. Deja las imágenes y los modelos en los artefactos `perro-3d` y `playa-web`.

En tu ordenador:

```sh
blender -b --factory-startup --python Perro.py
blender -b --factory-startup --python Playa.py
```

## Manuel

El modelo de Manuel no está en el repositorio (es público y es una persona real). Para prepararlo:

```sh
blender -b --factory-startup --python Nino.py -- manuel.glb web/nino.glb
```

`.gitignore` evita que `nino.glb` se suba por error.

## Jugar

La página necesita un servidor (los navegadores no cargan modelos desde `file://`):

```sh
cd web
python3 -m http.server
```

Abre http://localhost:8000. Controles: WASD o flechas para andar, Shift corre, Espacio salta, B ladra (cerca de Manuel, le pide que tire el balón; si el perro lleva el balón, lo suelta). En el móvil, joystick y botones.

Con `#prueba` al final de la dirección se activa un modo de pruebas (`window.prueba`) con piloto automático.

Si cambias `Perro.py` o `Playa.py`, copia los `.glb` nuevos a `web/`. La forma del terreno (`altura()`) y el rectángulo del muelle están duplicados en `Playa.py` y `web/index.html`: si los cambias, cámbialos en los dos.
