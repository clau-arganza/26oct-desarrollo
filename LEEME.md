# Ejercicio del 21 de octubre adaptado a la nueva tarea

## Ejecutar en VS Code

Descomprime el ZIP completo y abre esta nueva carpeta Registro_Login, que es
independiente de la versión anterior. Ejecuta login.py.

En la terminal de esa carpeta:

```bash
python3 -m pip install Pillow
python3 login.py
```

Pillow es la misma dependencia que ya usaba este proyecto para el meme WebP y
el GIF. Si ya lo tenías instalado para ese Python, no necesitas instalarlo otra vez.
No instales paquetes llamados sqlite3, hashlib o tkinter con pip.

## Qué conserva de tu proyecto

- Fondo turquesa y el mismo diseño de campos, botones y enlaces.
- Ventana de tamaño fijo, con barra de desplazamiento.
- Meme del perrito debajo de «He olvidado mi contraseña» en el login.
- GIF animado debajo de la bienvenida al iniciar sesión.
- Ojito para ver u ocultar la contraseña.
- Indicador de seguridad y requisitos de contraseña.
- Recuperación mediante pregunta y respuesta secreta.
- Cancelación de la animación al cambiar de pantalla o cerrar.

## Qué se ha cambiado para la nueva tarea

1. Se reemplazan users_dict.py y el almacenamiento JSON por sqlite3.
2. Los datos se guardan en data/db_user.db, en la tabla users.
3. El registro incorpora nacimiento en formato AAAA-MM-DD.
4. El nombre de usuario es el identificador único (sin distinguir mayúsculas).
5. Tras el registro, el usuario queda conectado y ve la bienvenida con el GIF.
6. La bienvenida añade «Acceder al contenido».
7. Solo al pulsarlo se comprueban edad y bloqueo, con excepciones propias.
8. Si no puede entrar, se muestra la causa y se mantiene su sesión abierta.
9. La recuperación también utiliza SQLite: pregunta en texto y respuesta hasheada.

Las contraseñas usan hashlib.pbkdf2_hmac (SHA-256, sal aleatoria y 600000
iteraciones). El login comprueba el hash, sin almacenar contraseñas en claro.
La recuperación entrega un permiso temporal de cinco minutos y un solo uso
tras comprobar la respuesta; cambiar la contraseña no quita un bloqueo.

## Datos que pide el registro

Usuario (3 a 30 caracteres, letras, números, guion o guion bajo), nacimiento,
contraseña, confirmación, pregunta y respuesta secreta.
La contraseña conserva las reglas de tu ejercicio: al menos 10 caracteres,
mayúscula, minúscula, número y símbolo. Ejemplo ficticio: Prueba2026!

## Usuarios de demostración

La BD incluida contiene los seis ejemplos del material, con contraseñas hasheadas.

| Usuario | Contraseña | Resultado al acceder al contenido en octubre de 2026 |
| --- | --- | --- |
| sarauser | sarapassw | Acceso permitido |
| lolauser | lolapassw | Acceso permitido |
| pepeuser | pepepassw | Denegado por minoría de edad |
| mariouser | mariopassw | Denegado por minoría de edad |
| jorgeuser | jorgepassw | Denegado por bloqueo |
| alejauser | alejopassw | Denegado por bloqueo y minoría de edad |

Se conservan las claves originales de estos ejemplos para entrar fácilmente;
la política más estricta se aplica al crear una cuenta o cambiar su contraseña.
Estos ejemplos no tienen pregunta de recuperación; para mostrar esa función,
registra una cuenta nueva.

El ZIP original no contiene usuarios_registrados.json, así que no hay cuentas
registradas de aquel archivo que se puedan trasladar. Las nuevas cuentas quedan
almacenadas solo en esta base de datos.

## Pruebas para presentar en clase

1. Intentar entrar con una contraseña incorrecta: error.
2. Entrar con sarauser: bienvenida con GIF; pulsar «Acceder al contenido».
3. Entrar con pepeuser: login correcto, contenido denegado por edad.
4. Entrar con jorgeuser: login correcto, contenido denegado por bloqueo.
5. Crear un adulto nuevo, nacido por ejemplo el 2000-05-15: conexión automática.
6. Cerrar y abrir el programa: puede entrar con la cuenta que acaba de crear.
7. Intentar repetir el nombre: duplicado rechazado.
8. Registrar un menor: conexión automática, contenido denegado.
9. Recuperar la contraseña de la nueva cuenta con su pregunta; comprobar que
   funciona la nueva clave y que la anterior deja de funcionar.
10. Probar campos vacíos, fecha imposible, fecha futura y confirmación distinta.

## Archivos

- login.py: tu interfaz anterior adaptada.
- login_db.py: operaciones con SQLite, hashes, fechas y recuperación.
- excepciones.py: MenorDeEdadError y UsuarioBloqueadoError heredan de
  AccesoNoPermitidoError; también incluye errores de credenciales y duplicados.
- data/db_user.db: base SQLite. No se abre como texto ni se edita copiando código.
- meme.webp y saludo.gif: los archivos originales, sin cambiarlos.
- login.png y user.png: imágenes originales conservadas.
- requirements.txt: dependencia Pillow.
- test_login.py: pruebas de la lógica, sin abrir ventanas ni alterar la BD real.

Python puede crear __pycache__ al ejecutar: es normal y no necesita abrirse.

## Utilidades para preparar casos de clase

Desde la terminal de la carpeta:

```bash
python3 login_db.py --bloquear sarauser
python3 login_db.py --desbloquear sarauser
python3 -m unittest -v test_login.py
```

El bloqueo solo se cambia con esa utilidad local, no desde el registro.
Si borras la BD, la aplicación crea otra vacía. Para añadir los usuarios de ejemplo:

```bash
python3 login_db.py --demo
```

Ese comando no modifica cuentas existentes. La BD está en una ruta relativa al
código, de modo que siempre se usa la misma aunque se ejecute desde otra carpeta.
