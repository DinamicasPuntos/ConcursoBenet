import pandas as pd
import pymysql
import config


ARCHIVO_EXCEL = "PDV PARTICIPANTES.xlsx"


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


def importar_pdvs():

    print()
    print("=" * 60)
    print("       IMPORTADOR DE PDV - CONCURSO BENET")
    print("=" * 60)
    print()

    # =====================================================
    # LEER EXCEL
    # =====================================================

    try:

        df = pd.read_excel(ARCHIVO_EXCEL)

    except Exception as error:

        print("❌ No se pudo leer el archivo Excel.")
        print(error)

        return

    print("Columnas encontradas:")

    for columna in df.columns:

        print(f"   - {columna}")

    print()

    # =====================================================
    # VALIDAR COLUMNAS
    # =====================================================

    columnas_necesarias = [
        "NOMBRE",
        "CODIGO",
        "COMERCIAL",
        "ZONA DE SUPERVISION",
        "REGION"
    ]

    faltantes = [
        columna
        for columna in columnas_necesarias
        if columna not in df.columns
    ]

    if faltantes:

        print("❌ Faltan estas columnas:")

        for columna in faltantes:

            print(f"   - {columna}")

        return

    # =====================================================
    # LIMPIAR DATOS
    # =====================================================

    for columna in columnas_necesarias:

        df[columna] = (
            df[columna]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    # =====================================================
    # ELIMINAR FILAS SIN CÓDIGO
    # =====================================================

    df = df[df["CODIGO"] != ""]

    # =====================================================
    # ELIMINAR CÓDIGOS DUPLICADOS
    # =====================================================

    df = df.drop_duplicates(
        subset=["CODIGO"]
    )

    print(
        f"📊 PDV encontrados en Excel: {len(df)}"
    )

    print()

    # =====================================================
    # CONECTAR A MYSQL
    # =====================================================

    try:

        conexion = conectar_mysql()

        print("✅ Conexión a MySQL correcta.")

    except Exception as error:

        print("❌ Error conectando a MySQL.")
        print(error)

        return

    nuevos = 0
    actualizados = 0

    try:

        with conexion.cursor() as cursor:

            for _, fila in df.iterrows():

                codigo = fila["CODIGO"]
                nombre = fila["NOMBRE"]
                comercial = fila["COMERCIAL"]
                zona = fila["ZONA DE SUPERVISION"]
                regional = fila["REGION"]

                # =========================================
                # BUSCAR PDV
                # =========================================

                cursor.execute(
                    """
                    SELECT id
                    FROM pdv
                    WHERE codigo = %s
                    """,
                    (codigo,)
                )

                existente = cursor.fetchone()

                # =========================================
                # SI EXISTE → ACTUALIZAR
                # =========================================

                if existente:

                    cursor.execute(
                        """
                        UPDATE pdv

                        SET
                            nombre = %s,
                            comercial = %s,
                            zona_supervision = %s,
                            regional = %s,
                            activo = 1

                        WHERE codigo = %s
                        """,
                        (
                            nombre,
                            comercial,
                            zona,
                            regional,
                            codigo
                        )
                    )

                    actualizados += 1

                # =========================================
                # SI NO EXISTE → CREAR
                # =========================================

                else:

                    cursor.execute(
                        """
                        INSERT INTO pdv
                        (
                            codigo,
                            nombre,
                            comercial,
                            zona_supervision,
                            regional,
                            activo
                        )

                        VALUES
                        (
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            1
                        )
                        """,
                        (
                            codigo,
                            nombre,
                            comercial,
                            zona,
                            regional
                        )
                    )

                    nuevos += 1

            conexion.commit()

        print()
        print("=" * 60)
        print("       ✅ IMPORTACIÓN COMPLETADA")
        print("=" * 60)
        print()

        print(f"🆕 PDV nuevos: {nuevos}")
        print(f"🔄 PDV actualizados: {actualizados}")
        print(f"📊 Total procesados: {len(df)}")
        print()

    except Exception as error:

        conexion.rollback()

        print()
        print("❌ Error durante la importación:")
        print(error)

    finally:

        conexion.close()


if __name__ == "__main__":

    importar_pdvs()