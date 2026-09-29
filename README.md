# mi-perro

Drako, un perro bretón español hecho con Blender (Python), y una playa de agua cristalina para pasearlo con Manuel.

- `Perro.py`: crea el perro (un bretón español blanco y negro, con el hocico moteado y ojos color miel), renderiza `perro.png` y exporta `perro.glb`. Los colores del pelaje van pintados en los vértices para que también se vean en la web.
- `Playa.py`: crea la playa (arena, dunas, agua, palmeras, rocas, sombrilla, muelle) con una explanada en las dunas para el parque acuático y sus piscinas; renderiza `playa.png` y exporta `playa.glb`.
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

Con el botón **Manuel** (tecla `C`) cambias de personaje. Con Manuel:

- **Pesca** en el final del muelle: eliges cebo, apuntas y eliges la fuerza del lanzamiento, tiras cuando pica y recoges controlando la tensión del sedal. Cada especie (sardina, dorada, pulpo, lubina, caballa, pez espada) vive a una distancia y quiere un cebo.
- **Parque acuático** en las dunas: salta las 3 vallas para abrir la puerta, recoge los 5 patitos de la piscina infantil en 45 s para desbloquear el tobogán espiral y cruza la piscina saltando por las colchonetas para desbloquear el kamikaze (si te caes, vuelves a la última colchoneta). También hay piscina de olas con un **barco pirata** (se sube por una pasarela con chorros de agua, tiene un cubo gigante que se vuelca y dos toboganes) y un **tobogán de salto** que lanza a Manuel por el aire con una voltereta.

- **Casa de Manuel y Drako** en las dunas: casa blanca con terraza, porche, piscina de arena y jardín. Junto a la mesa del porche pueden **descansar** juntos.
- **Parque de bolas gigante** junto a la casa, con 11 atracciones: piscina de bolas (se apartan al pasar), muro de escalada, tobogán de tubo, puente colgante, tobogán ondulado, camas elásticas, columpios, tiovivo, balancín (Drako se sube al otro lado), cañón de bolas y sacos blandos. La prueba es probar 10.
- **Dentro de casa**: por la puerta se entra en la casa, con cocina (azulejo blanco con cenefa azul, suelo de barro, mesa blanca de cristal), salón con sofá y tele, y la habitación de Manuel con su cama y juguetes. Papá y mamá están en la cocina y le dan de comer; en el salón ve los dibujos con Drako, en su cuarto juega y duerme.
- **Llamar a Drako**: con el botón «¡Drako!» Manuel silba y le llama; Drako viene corriendo aunque esté lejos.

Si Manuel está cerca, Drako le sigue y va a por el balón; si está lejos, se queda curioseando hasta que le llaman. Suena una música alegre (más tranquila en casa) que se quita con el botón ♪ o la tecla `M`. Los botones reaccionan al tocarlos, así que se puede saltar con un dedo mientras el otro mueve el joystick.

Con `#prueba` al final de la dirección se activa un modo de pruebas (`window.prueba`) con piloto automático.

Si cambias `Perro.py` o `Playa.py`, copia los `.glb` nuevos a `web/`. La forma del terreno (`altura()`, con el parque, la casa y sus piscinas) y el rectángulo del muelle están duplicados en `Playa.py` y `web/index.html`: si los cambias, cámbialos en los dos.
