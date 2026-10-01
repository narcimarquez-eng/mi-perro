# mi-perro

Drako, un perro bretón español hecho con Blender (Python), y una playa de agua cristalina para pasearlo con Manuel.

- `Perro.py`: crea el perro (un bretón español blanco y negro, con el hocico moteado y ojos color miel), renderiza `perro.png` y exporta `perro.glb`. Los colores del pelaje van pintados en los vértices para que también se vean en la web.
- `Playa.py`: crea la playa (arena, dunas, agua, palmeras, rocas, sombrilla, muelle) con una explanada en las dunas para el parque acuático y sus piscinas; renderiza `playa.png` y exporta `playa.glb`.
- `Nino.py`: prepara el modelo 3D de Manuel: le quita el balón de la mano, baja el brazo derecho y rehace sus animaciones en espejo del izquierdo, añade las animaciones `kick` (chutar) y `pickup` (agacharse), crea un balón aparte y reduce las texturas. Exporta `nino.glb`.
- `Padres.py`: crea a papá y mamá en estilo de dibujo (papá con pelo rizado, barba y chaqueta de cuero; mamá con melena ondulada color miel, blusa blanca y pendientes rosas), con esqueleto y animaciones (reposo, hablar, andar, llevar el plato y saludar); exporta `papa.glb` y `mama.glb` y renderiza `padres.png`.
- `Arrecife.py`: crea las piezas del arrecife de coral (coral cerebro, cuerno de ciervo, arbustos azules, dedos, corales mesa, gorgonias, esponjas de tubo, coliflor, anémonas, algas, rocas, estrellas y erizos), seis peces con su dibujo (anthias, payaso, cirujano, ángel, mariposa y loro), una tortuga, un cofre del tesoro, la barca, un barco pirata hundido, una cueva, una morena, un tiburón y un delfín; las exporta en `arrecife.glb` y renderiza una escena submarina en `arrecife.png`.
- `Coches.py`: crea el coche de carreras de Manuel (un GT blanco y negro con franjas azul claro, azul oscuro y rojo y el número 1, pintado en una textura), sus ruedas, un kart, un bólido de fórmula, un buggy todoterreno, una nave futurista que flota y el casco de Manuel; exporta `coches.glb` y renderiza `coches.png`. Con `FICHAS=1` renderiza también las fichas del menú de coches (`vehiculos.png`).
- `Pistas.py`: crea las piezas de los escenarios de los circuitos: rascacielos, farolas, semáforos y árboles de la ciudad; palmeras, faro, casetas, veleros, sombrillas y rocas de la playa; árboles retorcidos, setas gigantes que brillan, cristales, ruinas, helechos, troncos y farolillos del bosque misterioso; y los objetos de las cajas sorpresa (plátano, caparazón y seta turbo). Exporta `pistas.glb` y renderiza `pistas.png`.
- `Amigos.py`: crea cuatro amigos de Manuel (Lucía, Hugo, Martina y Leo) con el creador de personas de `Padres.py`, con proporciones de niño, esqueleto, casco y animaciones (reposo, saludar, conducir, celebrar y andar); exporta `amigo1.glb` a `amigo4.glb`.
- `Numeros.py`: crea el pueblo de los números: diez personajes hechos de bloques (del 1 al 10, cada uno con su color, cara, brazos y piernas), quince juguetes (pelota, patito, peonza, tambor, xilófono, cochecito, osito, tren, barquito, avión, cubo mágico, robot, cohete, dinosaurio y una copa de oro), el regalo, el carrito de Manuel, la estantería y el baúl de su cuarto, y la decoración (arco de bloques, puestos con toldo, dados, ábaco, piruletas gigantes y globos). Exporta `numeros.glb` y renderiza `numeros.png`.
- `PistasJuguete.py`: crea dieciséis cochecitos de juguete distintos (deportivo con llamas, fórmula, monstruo, tiburón, dinocoche, cohete, policía, bomberos, furgoneta, escarabajo y los que se desbloquean: todoterreno, buggy, camión de helados, ovni, dragón y coche de oro), el lanzador de muelle, la caja de pistas del cuarto de Manuel y el set de pistas de regalo; exporta `cochesjuguete.glb` y renderiza `pistasjuguete.png`. Con `FICHAS=1` renderiza las fichas del menú de coches (`cochesjuguete.png`).
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
- **Barca y arrecife de coral**: al final del muelle hay una barca. Con «Bucear», Manuel se pone el equipo de buzo (botella, gafas, tubo y aletas) y la barca le lleva mar adentro con Drako. Bajo el agua hay corales de colores, miles de peces que se apartan a su paso, tortugas, un tiburón de puntas negras que patrulla el arrecife, un grupo de delfines, rayos de sol, cáusticas y burbujas. Hay que descubrir 7 zonas, cada una marcada con una columna de luz y señalada por una brújula: el jardín de corales, el bosque de gorgonias, las anémonas de los peces payaso, la bahía de las tortugas, el barco pirata hundido, la cueva de las morenas y el cofre del tesoro (dorado, con monedas y destellos). «Subir»/«Bajar» lleva a Manuel a la superficie o al fondo, y junto a la barca «A la barca» le devuelve al muelle.
- **Coche de carreras y circuitos de karts**: el coche de Manuel está aparcado en la playa. Con «Conducir» Manuel lo lleva (joystick: girar y acelerar) hasta el arco del circuito, al final de la playa. En la puerta le esperan cuatro amigos; con «¡A correr!» se abre el menú para elegir coche y circuito:
  - Coches: kart (buen giro), coche GT, bólido (el más rápido), buggy (va bien fuera de la pista) y nave futurista (flota y acelera mucho). Cada uno tiene su velocidad, aceleración y giro.
  - Circuitos: **Circuito Verde**; **Gran Ciudad**, entre rascacielos al atardecer, con puente, pasos de cebra y semáforos; **Costa Soleada**, junto al mar con olas, palmeras, faro y un arroyo que frena; y **Bosque Misterioso**, de noche con niebla, colinas, setas y cristales que brillan, ruinas y luciérnagas. Todos son más largos, con turbos, rampas de salto y seis filas de cajas sorpresa.
  - Mandos: botón **Acelerar** (o `W`/↑), botón **Frenar** (o `S`/↓), joystick o `A`/`D` para girar y el botón del objeto (o `Espacio`/`E`) para usarlo. Arriba a la derecha hay un minimapa.
  - Objetos de las cajas: seta turbo, tres setas, plátano (se deja detrás), caparazón verde (sale recto), caparazón rojo (persigue al de delante), estrella (invencible y más rápido) y rayo (encoge a los demás). Los amigos también los usan.
  - La carrera es de 3 vueltas. Hay que quedar entre los 3 primeros para subir al podio; cada circuito ganado da una copa 🏆, y la prueba final es conseguir las 4.
- **Pueblo de los números**: en las dunas, al lado de la casa, hay un arco de bloques que lleva al pueblo. Allí Manuel recibe un carrito y juega con los personajes de bloques a 11 juegos de matemáticas para niños de 5 a 7 años, cada uno con tres niveles (fácil, hasta 5; medio, hasta 10; difícil, hasta 20):
  - Cuenta conmigo (contar cosas), ¿Quién soy? (reconocer el número por sus bloques), Juntamos bloques (sumas), Se van bloques (restas), Amigos del 10 (cuántos faltan para 5, 10 o 20), ¿Cuál es más grande?, ¿Qué número falta? (series, también de 2 en 2, de 5 en 5 y de 10 en 10), Dobles y mitades, Pares y nones, La tienda de monedas (contar dinero) y Salta al número (una rayuela gigante en la plaza: hay que saltar a la baldosa con la respuesta).
  - Cada ronda tiene 5 preguntas, que se leen en voz alta (botón 🔊). Con 3 fallos o menos se supera y se ganan estrellas (⭐⭐⭐ sin fallos) y un regalo: se abre y el juguete salta al carrito. Cuanto más difícil el nivel, mejores juguetes.
  - En el carrito caben 3 juguetes. Cuando está lleno hay que llevarlo a casa y, en el cuarto de Manuel, pulsar «Guardar» junto a las estanterías; luego se vuelve a por más. Caben 60 juguetes en las estanterías y el resto va al baúl. Los juguetes, las estrellas y el carrito se quedan guardados en el navegador.
- **Cuarto de las pistas**: en el cuarto de Manuel hay una caja de pistas de coches; con «Pistas» Manuel entra en un cuarto de juegos gigante (con juguetes enormes alrededor) con 6 pistas naranjas de coches de juguete: La primera rampa, El gran rizo, El salto del cocodrilo, Curvas locas, Doble rizo turbo y La megapista. En cada lanzador se elige uno de los 10 coches (cada uno con su peso y su agarre), se apunta con una flecha que se mueve (la entrada de la pista está un poco girada en cada una) y se elige la fuerza con una barra que sube y baja. Con poca fuerza el coche no sube la rampa, se cae del rizo o no llega al salto; con demasiada se sale en las curvas o se pasa del salto; si se apunta mal, no entra en la pista. Tras cada fallo dice qué ha pasado y marca en la barra la fuerza del último intento. Las pistas son grandes y tienen muchos detalles: semáforo de salida, embudo de entrada, juntas entre piezas, patas con pie y abrazadera, muros con piano en las curvas, luces de colores en los rizos, casetas de turbo con ruedas que giran, avisos antes de los saltos y las curvas, un cocodrilo que abre la boca bajo el salto, un aro de fuego en la megapista, neumáticos, conos, arco de meta y garaje. Cuando el coche hace un rizo o un salto, o llega rápido a una curva peligrosa, la cámara se acerca, va a cámara lenta y aparece un aviso («¡RIZO!», «¡SALTO!», «¡CUIDADO!»). Si el coche se sale, rebota en las paredes y en los juguetes gigantes. Al superar las 6 pistas regalan un set de pistas, que aparece en el cuarto de Manuel.
  - **Cuarto de los paisajes**: por el arco de bloques del fondo se pasa a un segundo cuarto, aún más grande, con 5 pistas largas (de 90 a 200 m, entre el doble y seis veces las otras) que cruzan paisajes de juguete: Dunas del desierto (dunas, cactus y palmeras; si va muy rápido sale volando en la cresta de una duna), El charco gigante (charcos que frenan el coche, patitos y un río con un barquito bajo el salto), Bosque encantado (árboles, setas, helechos y un tronco hueco que hace de túnel), La gran montaña (subida larga, túnel dentro de una montaña nevada, bajada y salto) y El gran tour, que mezcla todo y se abre al superar las otras cuatro. En los túneles la cámara va pegada al coche, y en los charcos salpica.
  - **Coches que se desbloquean**: Todoterreno (al superar las dunas), Buggy (con 12 estrellas), Heladería (el charco gigante), Ovni (el bosque), Dragón (la montaña) y Coche de oro (el gran tour). Los todoterrenos (y el monstruo) apenas frenan en los charcos. En el menú, los coches cerrados salen con candado y dicen cómo conseguirlos.
- **Llamar a Drako**: con el botón «¡Drako!» Manuel silba y le llama; Drako viene corriendo aunque esté lejos.

Si Manuel está cerca, Drako le sigue y va a por el balón; si está lejos, se queda curioseando hasta que le llaman. Suena una música alegre (más tranquila en casa) que se quita con el botón ♪ o la tecla `M`. Los botones reaccionan al tocarlos, así que se puede saltar con un dedo mientras el otro mueve el joystick.

Con `#prueba` al final de la dirección se activa un modo de pruebas (`window.prueba`) con piloto automático.

Si cambias `Perro.py` o `Playa.py`, copia los `.glb` nuevos a `web/`. La forma del terreno (`altura()`, con el parque, la casa y sus piscinas) y el rectángulo del muelle están duplicados en `Playa.py` y `web/index.html`: si los cambias, cámbialos en los dos.
