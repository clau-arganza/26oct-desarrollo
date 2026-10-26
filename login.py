import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk, ImageSequence
from pathlib import Path
import sqlite3

from login_db import BaseDatos, requisitos_password
from excepciones import (
    CredencialesIncorrectasError, UsuarioExistenteError,
    MenorDeEdadError, UsuarioBloqueadoError,
)

# Diseño e imágenes del ejercicio anterior.
FONDO = "#3DE3C9"
BLANCO = "#FFFFFF"
NEGRO = "#000000"
BASE = Path(__file__).resolve().parent
ARCHIVO_MEME = BASE / "meme.webp"
ARCHIVO_GIF = BASE / "saludo.gif"


class Login:
    def __init__(self, ventana):
        self.window = ventana
        self.window.title("Acceso al programa")
        self.window.configure(bg=FONDO)

        # Tamaño fijo para todas las pantallas.
        ancho = min(
            490,
            self.window.winfo_screenwidth() - 60
        )
        alto = min(
            740,
            self.window.winfo_screenheight() - 100
        )

        self.window.geometry(f"{ancho}x{alto}")

        # Impide ampliar o reducir la ventana.
        self.window.resizable(False, False)

        self.ancho = ancho
        self.animacion = None
        self.frames_gif = []
        self.duraciones_gif = []
        self.imagen_meme = None

        self.db = BaseDatos()
        self.usuario_actual = None

        self.window.protocol(
            "WM_DELETE_WINDOW",
            self.cerrar
        )

        self.mostrar_login()

    def detener_animacion(self):
        if self.animacion is not None:
            self.window.after_cancel(self.animacion)
            self.animacion = None

    def cerrar(self):
        self.detener_animacion()
        self.window.destroy()

    def limpiar(self):
        self.detener_animacion()

        for elemento in self.window.winfo_children():
            elemento.destroy()

        self.frames_gif = []
        self.duraciones_gif = []
        self.imagen_meme = None

    def pantalla(self, titulo, subtitulo=""):
        self.limpiar()

        # Barra para desplazarse si el contenido no cabe.
        contenedor = tk.Frame(self.window, bg=FONDO)
        contenedor.pack(fill="both", expand=True)

        barra = tk.Scrollbar(contenedor)
        barra.pack(side="right", fill="y")

        canvas = tk.Canvas(
            contenedor,
            bg=FONDO,
            highlightthickness=0,
            yscrollcommand=barra.set
        )
        canvas.pack(
            side="left",
            fill="both",
            expand=True
        )

        barra.configure(command=canvas.yview)

        pagina = tk.Frame(canvas, bg=FONDO)

        ventana_canvas = canvas.create_window(
            (0, 0),
            window=pagina,
            anchor="nw"
        )

        pagina.bind(
            "<Configure>",
            lambda event: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(
                ventana_canvas,
                width=event.width
            )
        )

        tk.Label(
            pagina,
            text=titulo,
            font=("Arial", 20, "bold"),
            bg=FONDO,
            fg=NEGRO,
            wraplength=self.ancho - 70
        ).pack(pady=(25, 8))

        if subtitulo:
            tk.Label(
                pagina,
                text=subtitulo,
                font=("Arial", 11),
                bg=FONDO,
                fg=NEGRO,
                wraplength=self.ancho - 80,
                justify="center"
            ).pack(pady=(0, 12))

        contenido = tk.Frame(pagina, bg=FONDO)
        contenido.pack(
            fill="x",
            padx=25,
            pady=(0, 25)
        )

        # Desplazamiento con rueda o trackpad.
        def rueda(event):
            if event.delta:
                paso = -1 if event.delta > 0 else 1
                canvas.yview_scroll(paso, "units")
            return "break"

        def enlazar_rueda(widget):
            widget.bind("<MouseWheel>", rueda, add="+")

            widget.bind(
                "<Button-4>",
                lambda event: canvas.yview_scroll(-1, "units"),
                add="+"
            )

            widget.bind(
                "<Button-5>",
                lambda event: canvas.yview_scroll(1, "units"),
                add="+"
            )

            for hijo in widget.winfo_children():
                enlazar_rueda(hijo)

        # Se enlaza cuando ya están creados todos los campos.
        pagina.after_idle(
            lambda: enlazar_rueda(contenedor)
        )

        return contenido

    def etiqueta(self, padre, texto):
        tk.Label(
            padre,
            text=texto,
            font=("Arial", 11),
            bg=FONDO,
            fg=NEGRO
        ).pack(anchor="w", pady=(10, 4))

    def campo(self, padre, texto, variable=None):
        self.etiqueta(padre, texto)

        entrada = tk.Entry(
            padre,
            textvariable=variable,
            font=("Arial", 12),
            bg=BLANCO,
            fg=NEGRO,
            insertbackground=NEGRO,
            selectbackground=NEGRO,
            selectforeground=BLANCO,
            relief="solid",
            bd=1
        )
        entrada.pack(fill="x", ipady=6)

        return entrada

    def campo_password(self, padre, texto, variable=None):
        self.etiqueta(padre, texto)

        fila = tk.Frame(padre, bg=FONDO)
        fila.pack(fill="x")

        entrada = tk.Entry(
            fila,
            textvariable=variable,
            show="•",
            font=("Arial", 12),
            bg=BLANCO,
            fg=NEGRO,
            insertbackground=NEGRO,
            selectbackground=NEGRO,
            selectforeground=BLANCO,
            relief="solid",
            bd=1
        )
        entrada.pack(
            side="left",
            fill="x",
            expand=True,
            ipady=6
        )

        # Ojito para mostrar y ocultar la contraseña.
        ojo = tk.Canvas(
            fila,
            width=32,
            height=30,
            bg=FONDO,
            highlightthickness=0,
            cursor="hand2",
            takefocus=True
        )
        ojo.pack(side="right", padx=(6, 0))

        def dibujar_ojo(visible):
            ojo.delete("all")

            ojo.create_oval(
                3, 8, 29, 23,
                outline=NEGRO,
                width=2
            )

            ojo.create_oval(
                12, 11, 20, 20,
                fill=NEGRO,
                outline=NEGRO
            )

            if visible:
                ojo.create_line(
                    4, 27, 28, 4,
                    fill=NEGRO,
                    width=2
                )

        def alternar(event=None):
            estaba_visible = entrada.cget("show") == ""

            entrada.configure(
                show="•" if estaba_visible else ""
            )

            dibujar_ojo(not estaba_visible)

        dibujar_ojo(False)

        ojo.bind("<Button-1>", alternar)
        ojo.bind("<Return>", alternar)
        ojo.bind("<space>", alternar)

        return entrada

    def boton(self, padre, texto, accion):
        tk.Button(
            padre,
            text=texto,
            command=accion,
            font=("Arial", 12, "bold"),
            bg=BLANCO,
            fg=NEGRO,
            activebackground=BLANCO,
            activeforeground=NEGRO,
            highlightbackground=FONDO,
            pady=8,
            cursor="hand2"
        ).pack(fill="x", pady=(18, 5))

    def enlace(self, padre, texto, accion):
        enlace = tk.Label(
            padre,
            text=texto,
            font=("Arial", 10, "underline"),
            fg=NEGRO,
            bg=FONDO,
            cursor="hand2",
            takefocus=True
        )
        enlace.pack(pady=5)

        enlace.bind(
            "<Button-1>",
            lambda event: accion()
        )

        enlace.bind(
            "<Return>",
            lambda event: accion()
        )

        enlace.bind(
            "<space>",
            lambda event: accion()
        )

    def indicador_seguridad(self, padre, variable):
        estado = tk.Label(
            padre,
            text="Seguridad: sin contraseña",
            font=("Arial", 11, "bold"),
            bg=FONDO,
            fg=NEGRO
        )
        estado.pack(anchor="w", pady=(10, 4))

        etiquetas = {}

        for texto in requisitos_password(""):
            etiqueta = tk.Label(
                padre,
                text=f"○ {texto}",
                font=("Arial", 10),
                bg=FONDO,
                fg=NEGRO
            )
            etiqueta.pack(anchor="w")
            etiquetas[texto] = etiqueta

        def actualizar(*args):
            password = variable.get()
            requisitos = requisitos_password(password)
            puntos = sum(requisitos.values())

            if not password:
                nivel = "Sin contraseña"
            elif puntos <= 2:
                nivel = "Débil"
            elif puntos < 5:
                nivel = "Media"
            else:
                nivel = "Fuerte"

            estado.configure(
                text=f"Seguridad: {nivel}"
            )

            for requisito, cumple in requisitos.items():
                simbolo = "✓" if cumple else "○"

                etiquetas[requisito].configure(
                    text=f"{simbolo} {requisito}"
                )

        variable.trace_add("write", actualizar)
        actualizar()

    def mostrar_meme(self, padre):
        try:
            with Image.open(ARCHIVO_MEME) as original:
                imagen = original.convert("RGB")

            # Recorta los márgenes del meme enviado.
            ancho, alto = imagen.size

            imagen = imagen.crop((
                int(ancho * 0.25),
                int(alto * 0.17),
                int(ancho * 0.75),
                int(alto * 0.83)
            ))

            imagen.thumbnail(
                (160, 230),
                Image.Resampling.LANCZOS
            )

            self.imagen_meme = ImageTk.PhotoImage(imagen)

            tk.Label(
                padre,
                image=self.imagen_meme,
                bg=FONDO
            ).pack(pady=(20, 5))

        except OSError:
            tk.Label(
                padre,
                text="No se pudo abrir meme.webp.",
                font=("Arial", 10),
                bg=FONDO,
                fg=NEGRO
            ).pack(pady=20)

    def mostrar_gif(self, padre):
        etiqueta_gif = tk.Label(
            padre,
            bg=FONDO,
            fg=NEGRO
        )
        etiqueta_gif.pack(pady=25)

        try:
            with Image.open(ARCHIVO_GIF) as gif:
                for frame in ImageSequence.Iterator(gif):
                    duracion = frame.info.get(
                        "duration", 100
                    )

                    imagen = frame.convert("RGBA")

                    imagen.thumbnail(
                        (330, 300),
                        Image.Resampling.LANCZOS
                    )

                    self.frames_gif.append(
                        ImageTk.PhotoImage(imagen)
                    )

                    self.duraciones_gif.append(
                        max(20, int(duracion or 100))
                    )

        except (OSError, ValueError):
            self.frames_gif = []
            self.duraciones_gif = []

            etiqueta_gif.configure(
                text="No se pudo abrir saludo.gif.",
                font=("Arial", 12)
            )

        def reproducir(indice=0):
            etiqueta_gif.configure(
                image=self.frames_gif[indice]
            )

            siguiente = (
                indice + 1
            ) % len(self.frames_gif)

            self.animacion = self.window.after(
                self.duraciones_gif[indice],
                reproducir,
                siguiente
            )

        if self.frames_gif:
            reproducir()

    def mostrar_login(self):
        self.usuario_actual = None
        marco = self.pantalla(
            "INICIAR SESIÓN",
            "Introduce tu usuario y contraseña."
        )

        self.usuario = self.campo(
            marco,
            "Usuario"
        )

        self.password = self.campo_password(
            marco,
            "Contraseña"
        )

        self.usuario.focus_set()

        self.password.bind(
            "<Return>",
            lambda event: self.iniciar_sesion()
        )

        self.boton(
            marco,
            "Acceder",
            self.iniciar_sesion
        )

        self.enlace(
            marco,
            "Crear una cuenta",
            self.mostrar_registro
        )

        self.enlace(
            marco,
            "He olvidado mi contraseña",
            self.mostrar_recuperacion
        )

    def iniciar_sesion(self):
        try:
            usuario = self.db.autenticar(self.usuario.get().strip(), self.password.get())
        except CredencialesIncorrectasError as error:
            messagebox.showerror("Acceso incorrecto", str(error), parent=self.window)
            return
        except sqlite3.Error as error:
            self.error_bd(error)
            return
        self.usuario_actual = usuario
        self.mostrar_bienvenida(usuario["nickname"])

    def mostrar_bienvenida(self, nombre):
        marco = self.pantalla(
            "¡Bienvenido!", f"Has iniciado sesión como {nombre}."
        )
        # Se mantiene el GIF bajo la bienvenida, también después del registro.
        self.mostrar_gif(marco)
        self.boton(marco, "Acceder al contenido", self.acceder_contenido)
        self.boton(marco, "Cerrar sesión", self.mostrar_login)

    def mostrar_registro(self):
        marco = self.pantalla("CREAR CUENTA")
        usuario = self.campo(marco, "Nombre de usuario único")
        nacimiento = self.campo(marco, "Fecha de nacimiento (AAAA-MM-DD)")
        password_var = tk.StringVar()
        self.campo_password(marco, "Contraseña", password_var)
        self.indicador_seguridad(marco, password_var)
        confirmacion = self.campo_password(marco, "Repite la contraseña")
        pregunta = self.campo(marco, "Escribe una pregunta de recuperación")
        respuesta = self.campo_password(marco, "Respuesta secreta")

        def registrar():
            if not pregunta.get().strip() or not respuesta.get().strip():
                messagebox.showwarning("Faltan datos", "Completa la pregunta y respuesta de recuperación.")
                return
            try:
                nuevo = self.db.registrar_usuario(
                    usuario.get(), nacimiento.get().strip(), password_var.get(),
                    confirmacion.get(), pregunta.get(), respuesta.get(),
                )
            except (ValueError, UsuarioExistenteError) as error:
                messagebox.showerror("No se ha podido registrar", str(error), parent=self.window)
                return
            except sqlite3.Error as error:
                self.error_bd(error)
                return
            self.usuario_actual = nuevo
            # Cambia el antiguo final del registro: ahora queda conectado.
            self.mostrar_registro_correcto(nuevo["nickname"])

        self.boton(marco, "Registrarme", registrar)
        self.enlace(marco, "Volver al inicio", self.mostrar_login)
        usuario.focus_set()

    def mostrar_registro_correcto(self, nombre):
        messagebox.showinfo("Cuenta creada", "Te has registrado y has iniciado sesión automáticamente.", parent=self.window)
        self.mostrar_bienvenida(nombre)

    def mostrar_recuperacion(self):
        marco = self.pantalla(
            "RECUPERAR ACCESO", "Introduce tu usuario para recuperar la contraseña mediante tu pregunta de seguridad."
        )
        usuario = self.campo(marco, "Usuario")

        def continuar():
            nombre = usuario.get().strip()
            try:
                pregunta = self.db.pregunta_recuperacion(nombre)
            except ValueError as error:
                messagebox.showerror("Recuperación no disponible", str(error), parent=self.window)
                return
            except sqlite3.Error as error:
                self.error_bd(error)
                return
            self.mostrar_pregunta(nombre, pregunta)

        self.boton(marco, "Continuar", continuar)
        self.enlace(marco, "Volver al inicio", self.mostrar_login)
        usuario.focus_set()

    def mostrar_pregunta(self, nombre, pregunta):
        marco = self.pantalla("PREGUNTA DE SEGURIDAD", pregunta)
        respuesta = self.campo_password(marco, "Tu respuesta")

        def verificar():
            try:
                token = self.db.verificar_respuesta(nombre, respuesta.get())
            except ValueError as error:
                messagebox.showerror("Respuesta incorrecta", str(error), parent=self.window)
                return
            except sqlite3.Error as error:
                self.error_bd(error)
                return
            self.mostrar_nueva_password(token)

        self.boton(marco, "Verificar respuesta", verificar)
        self.enlace(marco, "Volver al inicio", self.mostrar_login)
        respuesta.focus_set()

    def mostrar_nueva_password(self, token):
        marco = self.pantalla("NUEVA CONTRASEÑA", "Elige una nueva contraseña para tu cuenta.")
        password_var = tk.StringVar()
        entrada = self.campo_password(marco, "Nueva contraseña", password_var)
        self.indicador_seguridad(marco, password_var)
        confirmacion = self.campo_password(marco, "Repite la nueva contraseña")

        def cambiar():
            try:
                self.db.restablecer_password(token, password_var.get(), confirmacion.get())
            except ValueError as error:
                messagebox.showerror("No se ha podido cambiar", str(error), parent=self.window)
                return
            except sqlite3.Error as error:
                self.error_bd(error)
                return
            messagebox.showinfo("Contraseña actualizada", "Ya puedes acceder con tu nueva contraseña.", parent=self.window)
            self.mostrar_login()

        self.boton(marco, "Guardar contraseña", cambiar)
        self.enlace(marco, "Volver al inicio", self.mostrar_login)
        entrada.focus_set()

    def acceder_contenido(self):
        if self.usuario_actual is None:
            self.mostrar_login()
            return
        try:
            usuario = self.db.comprobar_acceso(self.usuario_actual["codigo"])
        except (MenorDeEdadError, UsuarioBloqueadoError) as error:
            # La sesión sigue abierta; únicamente se deniega el contenido.
            messagebox.showwarning("Acceso no permitido", str(error), parent=self.window)
            return
        except CredencialesIncorrectasError as error:
            messagebox.showerror("Sesión no válida", str(error), parent=self.window)
            self.mostrar_login()
            return
        except sqlite3.Error as error:
            self.error_bd(error)
            return
        self.usuario_actual = usuario
        marco = self.pantalla("CONTENIDO DEL PROGRAMA", f"Hola, {usuario['nickname']}.")
        tk.Label(
            marco, text="Has accedido al contenido protegido.\n\n"
            "Tu cuenta no está bloqueada y eres mayor de edad.",
            bg=FONDO, fg=NEGRO, font=("Arial", 12),
            wraplength=self.ancho - 80, justify="center",
        ).pack(pady=25)
        self.boton(marco, "Volver a la bienvenida", lambda: self.mostrar_bienvenida(usuario["nickname"]))
        self.boton(marco, "Cerrar sesión", self.mostrar_login)

    def error_bd(self, error):
        messagebox.showerror("Error de base de datos", f"No se ha podido completar la operación:\n{error}", parent=self.window)

if __name__ == "__main__":
    ventana = tk.Tk()
    try:
        aplicacion = Login(ventana)
    except (OSError, ValueError, sqlite3.Error) as error:
        messagebox.showerror("Error al cargar usuarios", f"No se pudo abrir la base de datos:\n{error}")
        ventana.destroy()
    else:
        ventana.mainloop()
