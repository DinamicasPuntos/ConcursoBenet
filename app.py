from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify
)

import pymysql
import os
import uuid
import csv
import io
import hashlib
from datetime import date
from itsdangerous import URLSafeTimedSerializer, BadSignature

from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix

import config


# ==========================================================
# CONFIGURACIÓN
# ==========================================================

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_prefix=1)

app.secret_key = config.SECRET_KEY
app.config.update(SESSION_COOKIE_SECURE=True, SESSION_COOKIE_SAMESITE="Lax")

app.config["MAX_CONTENT_LENGTH"] = (
    config.MAX_FILE_SIZE_MB * 1024 * 1024
)


# ==========================================================
# CARPETA DE FOTOGRAFÍAS
# ==========================================================

UPLOAD_FOLDER = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "uploads"
)

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# ==========================================================
# EXTENSIONES PERMITIDAS
# ==========================================================

EXTENSIONES_PERMITIDAS = {
    "jpg",
    "jpeg",
    "png",
    "webp"
}


def archivo_permitido(nombre):

    if "." not in nombre:
        return False

    extension = nombre.rsplit(".", 1)[1].lower()

    return extension in EXTENSIONES_PERMITIDAS


# ==========================================================
# CONEXIÓN MYSQL
# ==========================================================

def conectar_mysql():

    return pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor
    )



# ==========================================================
# AUTENTICACIÓN ADMINISTRATIVA
# ==========================================================

def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def admin_logueado():
    return session.get("admin_id") is not None


def exigir_admin():
    if not admin_logueado():
        return redirect(url_for("admin_login"))
    return None


def destino_por_rol():
    if session.get("admin_rol") == "LABORATORIO":
        return redirect(url_for("laboratorio_dashboard"))
    return redirect(url_for("admin_dashboard"))


def exigir_rol(rol):
    if not admin_logueado():
        return redirect(url_for("admin_login"))
    if session.get("admin_rol") != rol:
        return destino_por_rol()
    return None


def fecha_concurso(nombre_configuracion):
    return date(*getattr(config, nombre_configuracion))


def concurso_abierto():
    hoy = date.today()
    return fecha_concurso("CONCURSO_FECHA_INICIO") <= hoy <= fecha_concurso("CONCURSO_FECHA_FIN")


def estado_concurso():
    inicio = fecha_concurso("CONCURSO_FECHA_INICIO")
    fin = fecha_concurso("CONCURSO_FECHA_FIN")
    hoy = date.today()
    return {
        "inicio": inicio,
        "fin": fin,
        "abierto": inicio <= hoy <= fin,
        "finalizado": hoy > fin,
    }


def token_laboratorio():
    return URLSafeTimedSerializer(app.secret_key, salt="benet-laboratorio")


def laboratorio_api_autorizado():
    encabezado = request.headers.get("Authorization", "")
    if not encabezado.startswith("Bearer "):
        return None
    try:
        datos = token_laboratorio().loads(encabezado[7:], max_age=60 * 60 * 12)
        return datos if datos.get("rol") == "LABORATORIO" else None
    except BadSignature:
        return None


@app.after_request
def permitir_frontend_externo(respuesta):
    origen = request.headers.get("Origin")
    if origen == "https://dinamicaspuntos.github.io":
        respuesta.headers["Access-Control-Allow-Origin"] = origen
        respuesta.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        respuesta.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return respuesta


# ==========================================================
# PÁGINA PRINCIPAL
# ==========================================================

@app.route("/")
@app.route("/concurso-exhibicion-nutresa")
def inicio():

    try:

        conexion = conectar_mysql()

        with conexion.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    id,
                    codigo,
                    nombre,
                    comercial,
                    zona_supervision,
                    regional
                FROM pdv
                WHERE activo = 1
                ORDER BY nombre ASC
                """
            )

            pdvs = cursor.fetchall()

        conexion.close()

    except Exception as error:

        return render_template(
            "error.html",
            error=error
        )


    return render_template(
        "index.html",
        pdvs=pdvs
    )


# ==========================================================
# BUSCAR PDV
# ==========================================================

@app.route("/api/pdv/<int:pdv_id>", methods=["GET", "OPTIONS"])
def api_pdv(pdv_id):
    if request.method == "OPTIONS":
        return "", 204
    try:
        conexion = conectar_mysql()
        with conexion.cursor() as cursor:
            cursor.execute("SELECT id, codigo, nombre, comercial, zona_supervision, regional FROM pdv WHERE id = %s AND activo = 1", (pdv_id,))
            pdv = cursor.fetchone()
            cursor.execute("SELECT id, archivo, intento, fecha_hora, seleccionada, confirmada FROM fotos WHERE pdv_id = %s ORDER BY intento", (pdv_id,))
            fotos = cursor.fetchall()
        conexion.close()
        if not pdv:
            return jsonify({"error": "PDV no encontrado"}), 404
        for foto in fotos:
            foto["fecha_hora"] = foto["fecha_hora"].isoformat()
            foto["url"] = f"{config.API_PUBLIC_BASE}/foto/{foto['archivo']}"
        return jsonify({"pdv": pdv, "fotos": fotos, "oportunidades": max(0, config.MAX_INTENTOS - len(fotos)), "concurso": estado_concurso()})
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@app.route("/api/laboratorio/login", methods=["POST", "OPTIONS"])
def api_laboratorio_login():
    if request.method == "OPTIONS":
        return "", 204
    datos = request.get_json(silent=True) or {}
    try:
        conexion = conectar_mysql()
        with conexion.cursor() as cursor:
            cursor.execute("SELECT id, nombre, password_hash, rol FROM usuarios_admin WHERE usuario = %s AND activo = 1 AND rol = 'LABORATORIO' LIMIT 1", (datos.get("usuario", "").strip(),))
            usuario = cursor.fetchone()
        conexion.close()
        if not usuario or usuario["password_hash"] != hash_password(datos.get("password", "")):
            return jsonify({"error": "Credenciales incorrectas"}), 401
        token = token_laboratorio().dumps({"id": usuario["id"], "nombre": usuario["nombre"], "rol": usuario["rol"]})
        return jsonify({"token": token, "nombre": usuario["nombre"]})
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@app.route("/api/laboratorio/participantes", methods=["GET", "OPTIONS"])
def api_laboratorio_participantes():
    if request.method == "OPTIONS":
        return "", 204
    if not laboratorio_api_autorizado():
        return jsonify({"error": "No autorizado"}), 401
    try:
        conexion = conectar_mysql()
        with conexion.cursor() as cursor:
            cursor.execute("SELECT f.id AS foto_id, f.archivo, p.codigo, p.nombre, p.regional, g.posicion AS posicion_ganadora FROM fotos f INNER JOIN pdv p ON p.id=f.pdv_id LEFT JOIN ganadores_concurso g ON g.foto_id=f.id WHERE p.activo=1 AND f.confirmada=1 ORDER BY g.posicion IS NULL, g.posicion, p.nombre")
            filas = cursor.fetchall()
        conexion.close()
        for fila in filas:
            fila["url"] = f"{config.API_PUBLIC_BASE}/foto/{fila['archivo']}"
        return jsonify({"participantes": filas})
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@app.route("/api/laboratorio/ganadores/<int:foto_id>", methods=["POST", "OPTIONS"])
def api_laboratorio_ganador(foto_id):
    if request.method == "OPTIONS":
        return "", 204
    usuario = laboratorio_api_autorizado()
    if not usuario:
        return jsonify({"error": "No autorizado"}), 401
    datos = request.get_json(silent=True) or {}
    try:
        posicion = int(datos.get("posicion", 0))
        if posicion not in range(1, 6):
            raise ValueError
    except ValueError:
        return jsonify({"error": "El puesto debe estar entre 1 y 5"}), 400
    try:
        conexion = conectar_mysql()
        with conexion.cursor() as cursor:
            cursor.execute("SELECT f.pdv_id FROM fotos f INNER JOIN pdv p ON p.id=f.pdv_id WHERE f.id=%s AND f.confirmada=1 AND p.activo=1", (foto_id,))
            foto = cursor.fetchone()
            if not foto:
                conexion.close()
                return jsonify({"error": "Participación no válida"}), 404
            cursor.execute("DELETE FROM ganadores_concurso WHERE posicion=%s OR foto_id=%s OR pdv_id=%s", (posicion, foto_id, foto["pdv_id"]))
            cursor.execute("INSERT INTO ganadores_concurso (pdv_id, foto_id, posicion, seleccionado_por) VALUES (%s,%s,%s,%s)", (foto["pdv_id"], foto_id, posicion, usuario["id"]))
            conexion.commit()
        conexion.close()
        return jsonify({"ok": True})
    except Exception as error:
        return jsonify({"error": str(error)}), 500

@app.route("/buscar-pdv")
def buscar_pdv():

    termino = request.args.get(
        "q",
        ""
    ).strip()


    if not termino:

        return {
            "pdvs": []
        }


    try:

        conexion = conectar_mysql()

        with conexion.cursor() as cursor:

            busqueda = f"%{termino}%"

            cursor.execute(
                """
                SELECT
                    id,
                    codigo,
                    nombre,
                    comercial,
                    zona_supervision,
                    regional
                FROM pdv

                WHERE activo = 1

                AND (
                    codigo LIKE %s
                    OR nombre LIKE %s
                    OR comercial LIKE %s
                )

                ORDER BY nombre ASC

                LIMIT 20
                """,
                (
                    busqueda,
                    busqueda,
                    busqueda
                )
            )

            pdvs = cursor.fetchall()

        conexion.close()

        return {
            "pdvs": pdvs
        }


    except Exception as error:

        return {
            "pdvs": [],
            "error": str(error)
        }, 500


# ==========================================================
# ENTRAR AL PDV
# ==========================================================

@app.route("/pdv/<int:pdv_id>")
def ingresar_pdv(pdv_id):

    try:

        conexion = conectar_mysql()

        with conexion.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    id,
                    codigo,
                    nombre,
                    comercial,
                    zona_supervision,
                    regional
                FROM pdv
                WHERE id = %s
                AND activo = 1
                """,
                (pdv_id,)
            )

            pdv = cursor.fetchone()

        conexion.close()


    except Exception as error:

        return render_template(
            "error.html",
            error=error
        )


    if not pdv:

        return "PDV no encontrado", 404


    session["pdv_id"] = pdv["id"]

    return redirect(
        url_for(
            "pagina_pdv",
            pdv_id=pdv["id"]
        )
    )


# ==========================================================
# PÁGINA DEL PDV
# ==========================================================

@app.route("/pdv/<int:pdv_id>/participar")
def pagina_pdv(pdv_id):

    try:

        conexion = conectar_mysql()

        with conexion.cursor() as cursor:

            # ----------------------------------------------
            # DATOS PDV
            # ----------------------------------------------

            cursor.execute(
                """
                SELECT
                    id,
                    codigo,
                    nombre,
                    comercial,
                    zona_supervision,
                    regional
                FROM pdv
                WHERE id = %s
                AND activo = 1
                """,
                (pdv_id,)
            )

            pdv = cursor.fetchone()


            if not pdv:

                conexion.close()

                return "PDV no encontrado", 404


            # ----------------------------------------------
            # FOTOGRAFÍAS
            # ----------------------------------------------

            cursor.execute(
                """
                SELECT
                    id,
                    archivo,
                    intento,
                    fecha_hora,
                    seleccionada,
                    confirmada
                FROM fotos
                WHERE pdv_id = %s
                ORDER BY intento ASC
                """,
                (pdv_id,)
            )

            fotos = cursor.fetchall()


        conexion.close()


    except Exception as error:

        return render_template(
            "error.html",
            error=error
        )


    intentos_usados = len(fotos)

    oportunidades = max(
        0,
        config.MAX_INTENTOS - intentos_usados
    )


    foto_confirmada = next(
        (
            foto
            for foto in fotos
            if foto["confirmada"] == 1
        ),
        None
    )


    return render_template(
        "pdv.html",
        pdv=pdv,
        fotos=fotos,
        oportunidades=oportunidades,
        foto_confirmada=foto_confirmada,
        concurso=estado_concurso()
    )


# ==========================================================
# SUBIR FOTOGRAFÍA
# ==========================================================

@app.route(
    "/pdv/<int:pdv_id>/subir",
    methods=["POST"]
)
def subir_foto(pdv_id):

    if not concurso_abierto():
        flash(
            "La carga de fotografías está disponible únicamente del 25 de agosto al 15 de septiembre.",
            "error"
        )
        return redirect(url_for("pagina_pdv", pdv_id=pdv_id))

    archivo = request.files.get(
        "foto"
    )


    if not archivo:

        flash(
            "Debes seleccionar una fotografía.",
            "error"
        )

        return redirect(
            url_for(
                "pagina_pdv",
                pdv_id=pdv_id
            )
        )


    if archivo.filename == "":

        flash(
            "No seleccionaste ninguna fotografía.",
            "error"
        )

        return redirect(
            url_for(
                "pagina_pdv",
                pdv_id=pdv_id
            )
        )


    if not archivo_permitido(
        archivo.filename
    ):

        flash(
            "Formato no permitido. Usa JPG, PNG o WEBP.",
            "error"
        )

        return redirect(
            url_for(
                "pagina_pdv",
                pdv_id=pdv_id
            )
        )


    try:

        conexion = conectar_mysql()

        with conexion.cursor() as cursor:

            # ----------------------------------------------
            # VERIFICAR PDV
            # ----------------------------------------------

            cursor.execute(
                """
                SELECT id, codigo
                FROM pdv
                WHERE id = %s
                AND activo = 1
                """,
                (pdv_id,)
            )

            pdv = cursor.fetchone()


            if not pdv:

                conexion.close()

                return "PDV no encontrado", 404


            # ----------------------------------------------
            # VERIFICAR PARTICIPACIÓN
            # ----------------------------------------------

            cursor.execute(
                """
                SELECT
                    COUNT(*) AS total
                FROM fotos
                WHERE pdv_id = %s
                """,
                (pdv_id,)
            )

            resultado = cursor.fetchone()

            total_fotos = resultado["total"]


            # ----------------------------------------------
            # MÁXIMO 5
            # ----------------------------------------------

            if total_fotos >= config.MAX_INTENTOS:

                conexion.close()

                flash(
                    "Ya utilizaste las 5 oportunidades.",
                    "error"
                )

                return redirect(
                    url_for(
                        "pagina_pdv",
                        pdv_id=pdv_id
                    )
                )


            # ----------------------------------------------
            # NÚMERO DE INTENTO
            # ----------------------------------------------

            intento = total_fotos + 1


            # ----------------------------------------------
            # NOMBRE ÚNICO
            # ----------------------------------------------

            extension = archivo.filename.rsplit(
                ".",
                1
            )[1].lower()


            codigo_archivo = secure_filename(
                str(pdv["codigo"])
            ).lower()

            if not codigo_archivo:
                codigo_archivo = str(pdv_id)

            nombre_archivo = (
                f"pdv_{codigo_archivo}"
                f"_intento_{intento}"
                f"_{uuid.uuid4().hex}"
                f".{extension}"
            )


            nombre_archivo = secure_filename(
                nombre_archivo
            )


            ruta = os.path.join(
                app.config["UPLOAD_FOLDER"],
                nombre_archivo
            )


            archivo.save(
                ruta
            )


            # ----------------------------------------------
            # GUARDAR MYSQL
            # ----------------------------------------------

            cursor.execute(
                """
                INSERT INTO fotos
                (
                    pdv_id,
                    archivo,
                    intento
                )

                VALUES
                (
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    pdv_id,
                    nombre_archivo,
                    intento
                )
            )


            conexion.commit()


        conexion.close()


        flash(
            f"¡Fotografía {intento} subida correctamente! 📸",
            "success"
        )


    except Exception as error:

        try:
            conexion.rollback()
            conexion.close()
        except:
            pass


        flash(
            f"Ocurrió un error: {error}",
            "error"
        )


    return redirect(
        url_for(
            "pagina_pdv",
            pdv_id=pdv_id
        )
    )


# ==========================================================
# SELECCIONAR FAVORITA
# ==========================================================

@app.route(
    "/pdv/<int:pdv_id>/seleccionar/<int:foto_id>",
    methods=["POST"]
)
def seleccionar_foto(
    pdv_id,
    foto_id
):

    if not concurso_abierto():
        flash("La selección de la fotografía cerró el 15 de septiembre.", "error")
        return redirect(url_for("pagina_pdv", pdv_id=pdv_id))

    try:

        conexion = conectar_mysql()

        with conexion.cursor() as cursor:

            # ----------------------------------------------
            # VERIFICAR FOTO
            # ----------------------------------------------

            cursor.execute(
                """
                SELECT id
                FROM fotos
                WHERE id = %s
                AND pdv_id = %s
                """,
                (
                    foto_id,
                    pdv_id
                )
            )

            foto = cursor.fetchone()


            if not foto:

                conexion.close()

                flash(
                    "Fotografía no encontrada.",
                    "error"
                )

                return redirect(
                    url_for(
                        "pagina_pdv",
                        pdv_id=pdv_id
                    )
                )


            # ----------------------------------------------
            # QUITAR SELECCIÓN ANTERIOR
            # ----------------------------------------------

            cursor.execute(
                """
                UPDATE fotos

                SET seleccionada = 0

                WHERE pdv_id = %s
                """,
                (pdv_id,)
            )


            # ----------------------------------------------
            # SELECCIONAR FOTO
            # ----------------------------------------------

            cursor.execute(
                """
                UPDATE fotos

                SET seleccionada = 1

                WHERE id = %s
                AND pdv_id = %s
                """,
                (
                    foto_id,
                    pdv_id
                )
            )


            conexion.commit()


        conexion.close()


        flash(
            "⭐ Esta es tu fotografía favorita.",
            "success"
        )


    except Exception as error:

        flash(
            f"Error seleccionando fotografía: {error}",
            "error"
        )


    return redirect(
        url_for(
            "pagina_pdv",
            pdv_id=pdv_id
        )
    )


# ==========================================================
# CONFIRMAR PARTICIPACIÓN
# ==========================================================

@app.route(
    "/pdv/<int:pdv_id>/confirmar",
    methods=["POST"]
)
def confirmar_participacion(pdv_id):

    if not concurso_abierto():
        flash("La selección final cerró el 15 de septiembre.", "error")
        return redirect(url_for("pagina_pdv", pdv_id=pdv_id))

    try:

        conexion = conectar_mysql()

        with conexion.cursor() as cursor:

            # ----------------------------------------------
            # BUSCAR FOTO FAVORITA
            # ----------------------------------------------

            cursor.execute(
                """
                SELECT id
                FROM fotos

                WHERE pdv_id = %s
                AND seleccionada = 1

                LIMIT 1
                """,
                (pdv_id,)
            )

            foto = cursor.fetchone()


            if not foto:

                conexion.close()

                flash(
                    "Primero debes seleccionar tu fotografía favorita.",
                    "error"
                )

                return redirect(
                    url_for(
                        "pagina_pdv",
                        pdv_id=pdv_id
                    )
                )


            # ----------------------------------------------
            # CONFIRMAR
            # ----------------------------------------------

            cursor.execute(
                """
                UPDATE fotos

                SET confirmada = 0

                WHERE pdv_id = %s
                """,
                (pdv_id,)
            )


            cursor.execute(
                """
                UPDATE fotos

                SET confirmada = 1

                WHERE id = %s
                AND pdv_id = %s
                """,
                (
                    foto["id"],
                    pdv_id
                )
            )


            conexion.commit()


        conexion.close()


        flash(
            "🎉 ¡Fotografía participante actualizada exitosamente!",
            "success"
        )


    except Exception as error:

        flash(
            f"Error confirmando participación: {error}",
            "error"
        )


    return redirect(
        url_for(
            "pagina_pdv",
            pdv_id=pdv_id
        )
    )



# ==========================================================
# ADMINISTRACIÓN - LOGIN
# ==========================================================

@app.route("/administracion", methods=["GET", "POST"])
def admin_login():

    if admin_logueado():
        return redirect(url_for("admin_dashboard"))

    error = None

    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        password = request.form.get("password", "")

        if not usuario or not password:
            error = "Ingresa usuario y contraseña."
        else:
            try:
                conexion = conectar_mysql()
                with conexion.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT id, usuario, nombre, rol, password_hash
                        FROM usuarios_admin
                        WHERE usuario = %s
                        AND activo = 1
                        LIMIT 1
                        """,
                        (usuario,)
                    )
                    admin = cursor.fetchone()
                conexion.close()

                if admin and admin["password_hash"] == hash_password(password):
                    session["admin_id"] = admin["id"]
                    session["admin_nombre"] = admin["nombre"]
                    session["admin_rol"] = admin["rol"]
                    return destino_por_rol()

                error = "Usuario o contraseña incorrectos."

            except Exception as e:
                return render_template("error.html", error=e)

    return render_template("admin_login.html", error=error)


@app.route("/administracion/salir")
def admin_logout():
    session.pop("admin_id", None)
    session.pop("admin_nombre", None)
    session.pop("admin_rol", None)
    return redirect(url_for("admin_login"))


# ==========================================================
# ADMINISTRACIÓN - DASHBOARD
# ==========================================================

@app.route("/administracion/panel")
def admin_dashboard():

    guard = exigir_rol("ADMIN")
    if guard:
        return guard

    try:
        conexion = conectar_mysql()

        with conexion.cursor() as cursor:

            cursor.execute("SELECT COUNT(*) AS total FROM pdv WHERE activo = 1")
            total_pdvs = cursor.fetchone()["total"]

            cursor.execute(
                """
                SELECT COUNT(DISTINCT pdv_id) AS total
                FROM fotos
                """
            )
            pdvs_con_fotos = cursor.fetchone()["total"]

            cursor.execute("SELECT COUNT(*) AS total FROM fotos")
            total_fotos = cursor.fetchone()["total"]

            cursor.execute(
                """
                SELECT COUNT(DISTINCT pdv_id) AS total
                FROM fotos
                WHERE confirmada = 1
                """
            )
            confirmados = cursor.fetchone()["total"]

            cursor.execute(
                """
                SELECT
                    p.id,
                    p.codigo,
                    p.nombre,
                    p.ciudad,
                    p.regional,
                    COUNT(f.id) AS total_fotos,
                    MAX(f.fecha_hora) AS ultima_foto,
                    MAX(f.confirmada) AS confirmado
                FROM pdv p
                LEFT JOIN fotos f ON f.pdv_id = p.id
                WHERE p.activo = 1
                GROUP BY
                    p.id, p.codigo, p.nombre,
                    p.ciudad, p.regional
                HAVING total_fotos > 0
                ORDER BY
                    confirmado DESC,
                    ultima_foto DESC,
                    p.nombre ASC
                """
            )
            participaciones = cursor.fetchall()

        conexion.close()

    except Exception as e:
        return render_template("error.html", error=e)

    return render_template(
        "admin_dashboard.html",
        total_pdvs=total_pdvs,
        pdvs_con_fotos=pdvs_con_fotos,
        total_fotos=total_fotos,
        confirmados=confirmados,
        participaciones=participaciones,
        admin_nombre=session.get("admin_nombre"),
        admin_rol=session.get("admin_rol")
    )


# ==========================================================
# ADMINISTRACIÓN - FOTOGRAFÍAS DE UN PDV
# ==========================================================

@app.route("/administracion/pdv/<int:pdv_id>")
def admin_pdv(pdv_id):

    guard = exigir_rol("ADMIN")
    if guard:
        return guard

    try:
        conexion = conectar_mysql()

        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id, codigo, nombre, comercial,
                    zona_supervision, ciudad, regional
                FROM pdv
                WHERE id = %s
                """,
                (pdv_id,)
            )
            pdv = cursor.fetchone()

            if not pdv:
                conexion.close()
                return "PDV no encontrado", 404

            cursor.execute(
                """
                SELECT
                    id, archivo, intento,
                    fecha_hora, seleccionada, confirmada
                FROM fotos
                WHERE pdv_id = %s
                ORDER BY intento ASC
                """,
                (pdv_id,)
            )
            fotos = cursor.fetchall()

        conexion.close()

    except Exception as e:
        return render_template("error.html", error=e)

    return render_template(
        "admin_pdv.html",
        pdv=pdv,
        fotos=fotos
    )


# ==========================================================
# ADMINISTRACIÓN - EXPORTAR CSV
# ==========================================================

@app.route("/administracion/exportar")
def admin_exportar():

    guard = exigir_rol("ADMIN")
    if guard:
        return guard

    try:
        conexion = conectar_mysql()

        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    p.codigo,
                    p.nombre,
                    p.comercial,
                    p.zona_supervision,
                    p.ciudad,
                    p.regional,
                    f.intento,
                    f.archivo,
                    f.fecha_hora,
                    f.seleccionada,
                    f.confirmada
                FROM fotos f
                INNER JOIN pdv p ON p.id = f.pdv_id
                ORDER BY p.nombre, f.intento
                """
            )
            filas = cursor.fetchall()

        conexion.close()

        salida = io.StringIO()
        salida.write("\ufeff")
        escritor = csv.writer(salida, delimiter=";")

        escritor.writerow([
            "Código PDV",
            "Nombre PDV",
            "Comercial",
            "Zona Supervisión",
            "Ciudad",
            "Regional",
            "Intento",
            "Archivo",
            "Fecha y hora",
            "Favorita",
            "Confirmada"
        ])

        for fila in filas:
            escritor.writerow([
                fila["codigo"],
                fila["nombre"],
                fila["comercial"] or "",
                fila["zona_supervision"] or "",
                fila["ciudad"] or "",
                fila["regional"] or "",
                fila["intento"],
                fila["archivo"],
                fila["fecha_hora"],
                "SI" if fila["seleccionada"] else "NO",
                "SI" if fila["confirmada"] else "NO"
            ])

        respuesta = salida.getvalue()
        from flask import Response
        return Response(
            respuesta,
            mimetype="text/csv; charset=utf-8",
            headers={
                "Content-Disposition":
                    "attachment; filename=participaciones_benet.csv"
            }
        )

    except Exception as e:
        return render_template("error.html", error=e)


# ==========================================================
# SERVIR FOTOGRAFÍAS
# ==========================================================

@app.route("/recursos/<nombre_archivo>")
def recurso_marca(nombre_archivo):

    from flask import send_from_directory

    recursos_publicos = {
        "LOGO BÉNET.png",
        "CONCURSO BENET AGOSTO PDV MOVIL.png",
        "PRODUCTOS PROTAGONISTAS BÉNET.png",
    }

    if nombre_archivo not in recursos_publicos:
        return "Recurso no encontrado", 404

    carpeta_recursos = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "img"
    )

    return send_from_directory(carpeta_recursos, nombre_archivo)

# ==========================================================
# LABORATORIO - FOTOS PARTICIPANTES Y GANADORES
# ==========================================================

@app.route("/laboratorio/panel")
def laboratorio_dashboard():

    guard = exigir_rol("LABORATORIO")
    if guard:
        return guard

    try:
        conexion = conectar_mysql()

        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    f.id AS foto_id, f.archivo, f.fecha_hora,
                    p.id AS pdv_id, p.codigo, p.nombre, p.comercial,
                    p.zona_supervision, p.ciudad, p.regional,
                    g.posicion AS posicion_ganadora
                FROM fotos f
                INNER JOIN pdv p ON p.id = f.pdv_id
                LEFT JOIN ganadores_concurso g ON g.foto_id = f.id
                WHERE p.activo = 1
                AND f.confirmada = 1
                ORDER BY g.posicion IS NULL, g.posicion, p.nombre
                """
            )
            participantes = cursor.fetchall()

            cursor.execute(
                """
                SELECT g.posicion, p.codigo, p.nombre, f.archivo
                FROM ganadores_concurso g
                INNER JOIN pdv p ON p.id = g.pdv_id
                INNER JOIN fotos f ON f.id = g.foto_id
                ORDER BY g.posicion
                """
            )
            ganadores = cursor.fetchall()

        conexion.close()

    except Exception as error:
        return render_template("error.html", error=error)

    return render_template(
        "laboratorio_dashboard.html",
        participantes=participantes,
        ganadores=ganadores,
        concurso=estado_concurso(),
        laboratorio_nombre=session.get("admin_nombre")
    )


@app.route("/laboratorio/ganadores/<int:foto_id>", methods=["POST"])
def guardar_ganador(foto_id):

    guard = exigir_rol("LABORATORIO")
    if guard:
        return guard

    try:
        posicion = int(request.form.get("posicion", "0"))
    except ValueError:
        posicion = 0

    if posicion not in range(1, 6):
        flash("El puesto debe estar entre 1 y 5.", "error")
        return redirect(url_for("laboratorio_dashboard"))

    try:
        conexion = conectar_mysql()

        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT f.id, f.pdv_id
                FROM fotos f
                INNER JOIN pdv p ON p.id = f.pdv_id
                WHERE f.id = %s
                AND f.confirmada = 1
                AND p.activo = 1
                """,
                (foto_id,)
            )
            foto = cursor.fetchone()

            if not foto:
                conexion.close()
                flash("La fotografía seleccionada no es una participación válida.", "error")
                return redirect(url_for("laboratorio_dashboard"))

            cursor.execute(
                """
                DELETE FROM ganadores_concurso
                WHERE posicion = %s OR foto_id = %s OR pdv_id = %s
                """,
                (posicion, foto_id, foto["pdv_id"])
            )
            cursor.execute(
                """
                INSERT INTO ganadores_concurso
                (pdv_id, foto_id, posicion, seleccionado_por)
                VALUES (%s, %s, %s, %s)
                """,
                (foto["pdv_id"], foto_id, posicion, session["admin_id"])
            )
            conexion.commit()

        conexion.close()
        flash(f"Ganador asignado al puesto {posicion}.", "success")

    except Exception as error:
        try:
            conexion.rollback()
            conexion.close()
        except Exception:
            pass
        flash(f"No fue posible guardar el ganador: {error}", "error")

    return redirect(url_for("laboratorio_dashboard"))


@app.route(
    "/foto/<nombre_archivo>"
)
def mostrar_foto(nombre_archivo):

    from flask import send_from_directory

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        nombre_archivo
    )


# ==========================================================
# ERROR DE ARCHIVO GRANDE
# ==========================================================

@app.errorhandler(413)
def archivo_demasiado_grande(error):

    return """
    <h2>La fotografía es demasiado grande.</h2>
    <p>El tamaño máximo permitido es de 10 MB.</p>
    """, 413


# ==========================================================
# EJECUTAR
# ==========================================================

if __name__ == "__main__":

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )
