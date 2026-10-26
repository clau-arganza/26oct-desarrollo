"""Pruebas de SQLite, contraseñas y reglas de acceso sin abrir ventanas."""
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

from excepciones import (
    CredencialesIncorrectasError, MenorDeEdadError,
    UsuarioBloqueadoError, UsuarioExistenteError,
)
from login_db import BaseDatos, calcular_edad, comprobar_password, crear_hash


class PruebasLogin(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.ruta = Path(self.temporal.name) / "prueba.db"
        self.db = BaseDatos(self.ruta)

    def tearDown(self):
        self.temporal.cleanup()

    def alta(self, nombre="prueba", fecha="2000-01-01"):
        return self.db.registrar_usuario(nombre, fecha, "Clave12345!", "Clave12345!")

    def test_registro_persistente_y_login(self):
        nuevo = self.alta()
        otra_conexion = BaseDatos(self.ruta)
        usuario = otra_conexion.autenticar("prueba", "Clave12345!")
        self.assertEqual(nuevo, usuario)
        self.assertNotIn("passw", usuario)
        self.assertEqual(usuario, otra_conexion.comprobar_acceso(usuario["codigo"]))

    def test_hash_con_sal_y_password_incorrecta(self):
        hash1, hash2 = crear_hash("Clave12345!"), crear_hash("Clave12345!")
        self.assertNotEqual(hash1, hash2)
        self.assertTrue(comprobar_password("Clave12345!", hash1))
        self.assertFalse(comprobar_password("otra", hash1))
        self.assertFalse(comprobar_password("otra", "formato invalido"))

    def test_bd_no_guarda_password_en_claro(self):
        self.alta()
        with sqlite3.connect(self.ruta) as conexion:
            guardado = conexion.execute("SELECT passw FROM users").fetchone()[0]
        self.assertNotEqual(guardado, "Clave12345!")
        self.assertTrue(guardado.startswith("pbkdf2_sha256$"))

    def test_identificador_unico_sin_distinguir_mayusculas(self):
        self.alta("SaraUser")
        with self.assertRaises(UsuarioExistenteError):
            self.alta("sarauser")
        self.assertEqual(self.db.autenticar("SARAUSER", "Clave12345!")["nickname"], "SaraUser")

    def test_credenciales_incorrectas(self):
        self.alta()
        for nombre, clave in [("prueba", "mal"), ("nadie", "Clave12345!"), ("' OR 1=1 --", "x")]:
            with self.assertRaises(CredencialesIncorrectasError):
                self.db.autenticar(nombre, clave)

    def test_menor_puede_registrarse_y_autenticarse(self):
        self.alta("menor", date.today().isoformat())
        usuario = self.db.autenticar("menor", "Clave12345!")
        with self.assertRaises(MenorDeEdadError):
            self.db.comprobar_acceso(usuario["codigo"])

    def test_bloqueado_puede_autenticarse_pero_no_acceder(self):
        self.alta()
        self.db.cambiar_bloqueo("prueba", True)
        usuario = self.db.autenticar("prueba", "Clave12345!")
        with self.assertRaises(UsuarioBloqueadoError):
            self.db.comprobar_acceso(usuario["codigo"])
        self.db.cambiar_bloqueo("prueba", False)
        self.db.comprobar_acceso(usuario["codigo"])

    def test_bloqueo_despues_de_login(self):
        usuario = self.alta()
        self.db.cambiar_bloqueo("prueba", True)
        with self.assertRaises(UsuarioBloqueadoError):
            self.db.comprobar_acceso(usuario["codigo"])

    def test_ambas_restricciones_se_explican(self):
        usuario = self.alta("menor", date.today().isoformat())
        self.db.cambiar_bloqueo("menor", True)
        with self.assertRaises(UsuarioBloqueadoError) as resultado:
            self.db.comprobar_acceso(usuario["codigo"])
        self.assertIn("bloqueada", str(resultado.exception))
        self.assertIn("menor", str(resultado.exception))

    def test_validaciones_no_insertan_datos(self):
        casos = [
            ("", "2000-01-01", "Clave12345!", "Clave12345!"),
            ("a", "2000-01-01", "Clave12345!", "Clave12345!"),
            ("abc", "2000-02-30", "Clave12345!", "Clave12345!"),
            ("abc", "2999-01-01", "Clave12345!", "Clave12345!"),
            ("abc", "20000101", "Clave12345!", "Clave12345!"),
            ("abc", "2000-01-01", "corta", "corta"),
            ("abc", "2000-01-01", "Clave12345!", "diferente"),
        ]
        for datos in casos:
            with self.assertRaises(ValueError):
                self.db.registrar_usuario(*datos)
        with sqlite3.connect(self.ruta) as conexion:
            self.assertEqual(conexion.execute("SELECT COUNT(*) FROM users").fetchone()[0], 0)

    def test_edad_en_limite_de_cumpleanos(self):
        self.assertEqual(calcular_edad("2008-10-26", date(2026, 10, 26)), 18)
        self.assertEqual(calcular_edad("2008-10-27", date(2026, 10, 26)), 17)
        self.assertEqual(calcular_edad("2008-02-29", date(2026, 3, 1)), 18)

    def test_demo_no_sobrescribe_cuentas(self):
        self.db.crear_usuarios_demo()
        self.db.cambiar_bloqueo("sarauser", True)
        self.db.crear_usuarios_demo()
        usuario = self.db.autenticar("sarauser", "sarapassw")
        self.assertTrue(usuario["blocked"])
        with sqlite3.connect(self.ruta) as conexion:
            self.assertEqual(conexion.execute("SELECT COUNT(*) FROM users").fetchone()[0], 6)


    def test_recuperacion_completa_y_token_de_un_solo_uso(self):
        self.db.registrar_usuario("recuperar", "2000-01-01", "Clave12345!", "Clave12345!",
                                  "¿Color favorito?", "Azul")
        self.assertEqual(self.db.pregunta_recuperacion("RECUPERAR"), "¿Color favorito?")
        with self.assertRaises(ValueError):
            self.db.verificar_respuesta("recuperar", "rojo")
        token = self.db.verificar_respuesta("recuperar", "  AZUL  ")
        self.db.restablecer_password(token, "NuevaClave123!", "NuevaClave123!")
        self.db.autenticar("recuperar", "NuevaClave123!")
        with self.assertRaises(CredencialesIncorrectasError):
            self.db.autenticar("recuperar", "Clave12345!")
        with self.assertRaises(ValueError):
            self.db.restablecer_password(token, "OtraClave123!", "OtraClave123!")

    def test_respuesta_secreta_guardada_como_hash(self):
        self.db.registrar_usuario("recuperar", "2000-01-01", "Clave12345!", "Clave12345!",
                                  "¿Color favorito?", "Azul")
        with sqlite3.connect(self.ruta) as conexion:
            respuesta = conexion.execute("SELECT respuesta FROM users").fetchone()[0]
        self.assertNotEqual(respuesta, "azul")
        self.assertTrue(comprobar_password("azul", respuesta))

    def test_recuperacion_no_desbloquea_cuenta(self):
        usuario = self.db.registrar_usuario("recuperar", "2000-01-01", "Clave12345!", "Clave12345!",
                                            "¿Color?", "azul")
        self.db.cambiar_bloqueo("recuperar", True)
        token = self.db.verificar_respuesta("recuperar", "azul")
        self.db.restablecer_password(token, "NuevaClave123!", "NuevaClave123!")
        self.db.autenticar("recuperar", "NuevaClave123!")
        with self.assertRaises(UsuarioBloqueadoError):
            self.db.comprobar_acceso(usuario["codigo"])

    def test_token_caducado_y_password_debil(self):
        self.db.registrar_usuario("recuperar", "2000-01-01", "Clave12345!", "Clave12345!",
                                  "¿Color?", "azul")
        token = self.db.verificar_respuesta("recuperar", "azul")
        with self.assertRaises(ValueError):
            self.db.restablecer_password(token, "debil", "debil")
        codigo, _ = self.db.tokens_recuperacion[token]
        self.db.tokens_recuperacion[token] = (codigo, 0)
        with self.assertRaises(ValueError):
            self.db.restablecer_password(token, "NuevaClave123!", "NuevaClave123!")


if __name__ == "__main__":
    unittest.main(verbosity=2)
