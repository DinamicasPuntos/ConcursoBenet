# ==========================================
# CONFIGURACIÓN CONCURSO EXHIBICIÓN NUTRESA
# ==========================================

# ------------------------------------------
# CONEXIÓN MYSQL
# ------------------------------------------

import os


def cargar_entorno_local():
    ruta = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(ruta):
        return
    with open(ruta, encoding="utf-8") as archivo:
        for linea in archivo:
            if "=" not in linea or linea.lstrip().startswith("#"):
                continue
            clave, valor = linea.strip().split("=", 1)
            os.environ.setdefault(clave, valor)


cargar_entorno_local()

DB_HOST = os.getenv("BENET_DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("BENET_DB_PORT", "3306"))
DB_USER = os.getenv("BENET_DB_USER", "benet_app")
DB_PASSWORD = os.getenv("BENET_DB_PASSWORD", "")
DB_NAME = os.getenv("BENET_DB_NAME", "concurso_benet")


# ------------------------------------------
# SEGURIDAD FLASK
# ------------------------------------------

SECRET_KEY = os.getenv("BENET_SECRET_KEY", "cambia-esta-clave-en-produccion")
API_PUBLIC_BASE = os.getenv("BENET_API_PUBLIC_BASE", "http://127.0.0.1:5000")


# ------------------------------------------
# CONFIGURACIÓN DEL CONCURSO
# ------------------------------------------

MAX_FILE_SIZE_MB = 10
MAX_INTENTOS = 5
CONCURSO_FECHA_INICIO = (2026, 8, 25)
CONCURSO_FECHA_FIN = (2026, 9, 15)


# ------------------------------------------
# ADMINISTRACIÓN
# ------------------------------------------

ADMIN_DEFAULT_USER = "admin"
