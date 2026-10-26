"""Persistencia SQLite y comprobaciones de usuarios, sin depender de Tkinter."""
import argparse
import hashlib
import hmac
import secrets
import sqlite3
import re
import time
from contextlib import closing
from datetime import date
from pathlib import Path

from excepciones import (
    CredencialesIncorrectasError, MenorDeEdadError,
    UsuarioBloqueadoError, UsuarioExistenteError,
)

# La ruta depende del archivo, no de la carpeta desde la que se ejecuta.
DB_FILE = Path(__file__).resolve().parent / "data" / "db_user.db"
ITERACIONES = 600_000


def crear_hash(password):
    """Hash PBKDF2 con una sal aleatoria diferente para cada contraseña."""
    sal = secrets.token_hex(16)
    resumen = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(sal), ITERACIONES
    ).hex()
    return f"pbkdf2_sha256${ITERACIONES}${sal}${resumen}"


def comprobar_password(password, guardado):
    """Repite el hash con la sal guardada; no descifra la contraseña."""
    try:
        algoritmo, iteraciones, sal, resumen = guardado.split("$")
        if algoritmo != "pbkdf2_sha256":
            return False
        calculado = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(sal), int(iteraciones)
        ).hex()
        return hmac.compare_digest(calculado, resumen)
    except (ValueError, TypeError):
        return False


def validar_nacimiento(texto, hoy=None):
    """Valida una fecha real con formato AAAA-MM-DD y que no sea futura."""
    hoy = hoy or date.today()
    try:
        nacimiento = date.fromisoformat(texto)
    except (ValueError, TypeError):
        raise ValueError("La fecha debe ser válida y tener formato AAAA-MM-DD.") from None
    if nacimiento.isoformat() != texto:
        raise ValueError("Utiliza el formato AAAA-MM-DD, por ejemplo 2002-05-18.")
    if nacimiento > hoy:
        raise ValueError("La fecha de nacimiento no puede ser futura.")
    return nacimiento


def calcular_edad(nacimiento, hoy=None):
    hoy = hoy or date.today()
    fecha = validar_nacimiento(nacimiento, hoy)
    return hoy.year - fecha.year - ((hoy.month, hoy.day) < (fecha.month, fecha.day))


def normalizar_respuesta(texto):
    return texto.strip().casefold()

def requisitos_password(password):
    return {
        "Al menos 10 caracteres": len(password) >= 10,
        "Una letra mayúscula": bool(
            re.search(r"[A-Z]", password)
        ),
        "Una letra minúscula": bool(
            re.search(r"[a-z]", password)
        ),
        "Un número": bool(
            re.search(r"\d", password)
        ),
        "Un símbolo, por ejemplo ! @ #": any(
            not caracter.isalnum()
            and not caracter.isspace()
            for caracter in password
        )
    }

class BaseDatos:
    def __init__(self, ruta=DB_FILE):
        self.ruta = Path(ruta)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.crear_tabla()
        self.tokens_recuperacion = {}

    def conectar(self):
        conexion = sqlite3.connect(self.ruta)
        conexion.row_factory = sqlite3.Row
        return conexion

    def crear_tabla(self):
        # UNIQUE protege el identificador también desde la propia base de datos.
        # NOCASE evita duplicar SaraUser y sarauser.
        with closing(self.conectar()) as conexion, conexion:
            conexion.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    codigo INTEGER PRIMARY KEY AUTOINCREMENT,
                    nickname TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    birthday TEXT NOT NULL,
                    passw TEXT NOT NULL,
                    blocked INTEGER NOT NULL DEFAULT 0 CHECK(blocked IN (0, 1)),
                    pregunta TEXT,
                    respuesta TEXT
                )
            """)

    def registrar_usuario(self, nickname, birthday, password, confirmar, pregunta="", respuesta=""):
        nickname = nickname.strip()
        if not nickname or not birthday or not password or not confirmar:
            raise ValueError("Completa todos los campos.")
        if not 3 <= len(nickname) <= 30:
            raise ValueError("El nombre de usuario debe tener entre 3 y 30 caracteres.")
        if not all(c.isalnum() or c in "_-" for c in nickname):
            raise ValueError("El usuario solo admite letras, números, guion y guion bajo.")
        validar_nacimiento(birthday)
        if not all(requisitos_password(password).values()):
            raise ValueError("La contraseña debe cumplir todos los requisitos de seguridad.")
        if password != confirmar:
            raise ValueError("Las contraseñas no coinciden.")
        if bool(pregunta.strip()) != bool(respuesta.strip()):
            raise ValueError("Completa la pregunta y la respuesta de recuperación.")
        # Ser menor no impide registrarse: se controla el acceso al contenido.
        with closing(self.conectar()) as conexion, conexion:
            if conexion.execute(
                "SELECT codigo FROM users WHERE nickname = ?", (nickname,)
            ).fetchone():
                raise UsuarioExistenteError("Ese nombre de usuario ya está registrado.")
            try:
                cursor = conexion.execute(
                    "INSERT INTO users(nickname, birthday, passw, pregunta, respuesta) VALUES (?, ?, ?, ?, ?)",
                    (nickname, birthday, crear_hash(password), pregunta.strip() or None,
                     crear_hash(normalizar_respuesta(respuesta)) if respuesta.strip() else None),
                )
            except sqlite3.IntegrityError:
                raise UsuarioExistenteError("Ese nombre de usuario ya está registrado.") from None
            return dict(conexion.execute(
                "SELECT codigo, nickname, birthday, blocked FROM users WHERE codigo = ?",
                (cursor.lastrowid,),
            ).fetchone())

    def autenticar(self, nickname, password):
        with closing(self.conectar()) as conexion:
            fila = conexion.execute(
                "SELECT * FROM users WHERE nickname = ?", (nickname.strip(),)
            ).fetchone()
        if fila is None or not comprobar_password(password, fila["passw"]):
            raise CredencialesIncorrectasError("Usuario o contraseña incorrectos.")
        # La sesión nunca necesita almacenar ni devolver la contraseña o su hash.
        return {clave: fila[clave] for clave in ("codigo", "nickname", "birthday", "blocked")}

    def obtener_usuario(self, codigo):
        with closing(self.conectar()) as conexion:
            fila = conexion.execute(
                "SELECT codigo, nickname, birthday, blocked FROM users WHERE codigo = ?",
                (codigo,),
            ).fetchone()
        if fila is None:
            raise CredencialesIncorrectasError("El usuario ya no existe. Inicia sesión otra vez.")
        return dict(fila)

    def comprobar_acceso(self, codigo):
        # Consulta de nuevo para detectar bloqueos posteriores al login.
        usuario = self.obtener_usuario(codigo)
        motivos = []
        if usuario["blocked"]:
            motivos.append("tu cuenta está bloqueada")
        if calcular_edad(usuario["birthday"]) < 18:
            motivos.append("eres menor de 18 años")
        if usuario["blocked"]:
            raise UsuarioBloqueadoError("No puedes acceder al contenido porque " + " y ".join(motivos) + ".")
        if motivos:
            raise MenorDeEdadError("No puedes acceder al contenido porque " + motivos[0] + ".")
        return usuario

    def cambiar_bloqueo(self, nickname, bloqueado):
        with closing(self.conectar()) as conexion, conexion:
            cursor = conexion.execute(
                "UPDATE users SET blocked = ? WHERE nickname = ?", (int(bloqueado), nickname.strip())
            )
            if cursor.rowcount == 0:
                raise ValueError("No existe ese usuario.")

    def crear_usuarios_demo(self):
        # Son los mismos ejemplos del material, con contraseñas ahora hasheadas.
        ejemplos = [
            ("pepeuser", "2020-11-15", "pepepassw", 0),
            ("sarauser", "2000-11-15", "sarapassw", 0),
            ("mariouser", "2010-11-15", "mariopassw", 0),
            ("lolauser", "2005-11-15", "lolapassw", 0),
            ("jorgeuser", "2000-11-15", "jorgepassw", 1),
            ("alejauser", "2015-11-15", "alejopassw", 1),
        ]
        with closing(self.conectar()) as conexion, conexion:
            for nombre, fecha, password, bloqueo in ejemplos:
                if not conexion.execute("SELECT 1 FROM users WHERE nickname = ?", (nombre,)).fetchone():
                    conexion.execute(
                        "INSERT INTO users(nickname,birthday,passw,blocked) VALUES (?,?,?,?)",
                        (nombre, fecha, crear_hash(password), bloqueo),
                    )


    def pregunta_recuperacion(self, nickname):
        with closing(self.conectar()) as conexion:
            fila = conexion.execute(
                "SELECT pregunta, respuesta FROM users WHERE nickname = ?", (nickname.strip(),)
            ).fetchone()
        if fila is None or not fila["pregunta"] or not fila["respuesta"]:
            raise ValueError("Este usuario no existe o no tiene pregunta de recuperación.")
        return fila["pregunta"]

    def verificar_respuesta(self, nickname, respuesta):
        with closing(self.conectar()) as conexion:
            fila = conexion.execute(
                "SELECT codigo, respuesta FROM users WHERE nickname = ?", (nickname.strip(),)
            ).fetchone()
        if fila is None or not fila["respuesta"] or not comprobar_password(
            normalizar_respuesta(respuesta), fila["respuesta"]
        ):
            raise ValueError("La respuesta secreta no es correcta.")
        # Permiso temporal de un solo uso para el siguiente formulario.
        ahora = time.monotonic()
        self.tokens_recuperacion = {
            t: datos for t, datos in self.tokens_recuperacion.items() if datos[1] > ahora
        }
        token = secrets.token_urlsafe(32)
        self.tokens_recuperacion[token] = (fila["codigo"], ahora + 300)
        return token

    def restablecer_password(self, token, password, confirmar):
        datos = self.tokens_recuperacion.get(token)
        if datos is None or datos[1] <= time.monotonic():
            self.tokens_recuperacion.pop(token, None)
            raise ValueError("La verificación ha caducado. Responde de nuevo a la pregunta.")
        if not all(requisitos_password(password).values()):
            raise ValueError("Cumple todos los requisitos de seguridad de la contraseña.")
        if password != confirmar:
            raise ValueError("Las contraseñas no coinciden.")
        with closing(self.conectar()) as conexion, conexion:
            cursor = conexion.execute(
                "UPDATE users SET passw = ? WHERE codigo = ?", (crear_hash(password), datos[0])
            )
            if cursor.rowcount != 1:
                raise ValueError("El usuario ya no existe.")
        self.tokens_recuperacion.pop(token, None)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gestión local de la base de datos para la práctica")
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--demo", action="store_true", help="Añade ejemplos sin sobrescribir usuarios")
    grupo.add_argument("--bloquear", metavar="USUARIO")
    grupo.add_argument("--desbloquear", metavar="USUARIO")
    args = parser.parse_args()
    try:
        db = BaseDatos()
        if args.demo:
            db.crear_usuarios_demo()
        else:
            db.cambiar_bloqueo(args.bloquear or args.desbloquear, bool(args.bloquear))
        print("Operación realizada correctamente.")
    except (ValueError, sqlite3.Error) as error:
        parser.exit(1, f"Error: {error}\n")
