import csv
import os
from collections import deque
import pymysql

# Configuración de conexión a la base de datos
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "dannydaza29",
    "database": "pea_db",
    "cursorclass": pymysql.cursors.DictCursor,
}

pila_productos = []
cola_productos = deque()

def obtener_conexion():
    return pymysql.connect(**DB_CONFIG)

def limpiar_base_datos():
    conn = obtener_conexion()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
            cursor.execute("TRUNCATE TABLE productos;")
            cursor.execute("TRUNCATE TABLE grupo_investigador;")
            cursor.execute("TRUNCATE TABLE investigadores;")
            cursor.execute("TRUNCATE TABLE grupos;")
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
        conn.commit()
        print("\n[BD] Se han eliminado todos los registros guardados anteriormente.")
    finally:
        conn.close()
        
def cargar_estructuras_en_memoria():
    global pila_productos, cola_productos
    pila_productos.clear()
    cola_productos.clear()

    conn = obtener_conexion()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT codigo FROM productos")
            registros = cursor.fetchall()
            for r in registros:
                pila_productos.append(r["codigo"])
                cola_productos.append(r["codigo"])
        if registros:
            print(f"\n[Persistencia] Se cargaron {len(registros)} producto(s) previos en Pila/Cola.")
    finally:
        conn.close()

def gestionar_persistencia():
    crear_tablas()
    # Verificar si hay datos previos

    conn = obtener_conexion()
    hay_datos = False
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS total FROM grupos")
            tot_g = cursor.fetchone()["total"]
            cursor.execute("SELECT COUNT(*) AS total FROM productos")
            tot_p = cursor.fetchone()["total"]
            if tot_g > 0 or tot_p > 0:
                hay_datos = True
    finally:
        conn.close()

    if hay_datos:
        print("\n================ CONFIGURACIÓN DE DATOS ================")
        print("\nSe encontraron datos guardados de sesiones anteriores en MySQL.")
        print("\n1. Mantener los datos anteriores y continuar con ellos")
        print("\n2. Borrar todos los datos y empezar una base de datos limpia")
        op = input("Seleccione una opción (1/2) [Por defecto 1]: ").strip()

        if op == "2":
            limpiar_base_datos()
        else:
            cargar_estructuras_en_memoria()
            print("\n[Persistencia] Continuando con la base de datos existente.")

def crear_tablas():
    conn = obtener_conexion()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS grupos (
                    codigo VARCHAR(50) PRIMARY KEY,
                    nombre VARCHAR(100) NOT NULL,
                    area VARCHAR(100) NOT NULL,
                    estado VARCHAR(20) DEFAULT 'Activo'
                )
            """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS investigadores (
                    codigo VARCHAR(50) PRIMARY KEY,
                    nombre VARCHAR(100) NOT NULL,
                    correo VARCHAR(100) NOT NULL,
                    estado VARCHAR(20) DEFAULT 'Activo'
                )
            """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS grupo_investigador (
                    grupo_codigo VARCHAR(50),
                    investigador_codigo VARCHAR(50),
                    PRIMARY KEY (grupo_codigo, investigador_codigo),
                    FOREIGN KEY (grupo_codigo) REFERENCES grupos(codigo),
                    FOREIGN KEY (investigador_codigo) REFERENCES investigadores(codigo)
                )
            """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS productos (
                    codigo VARCHAR(50) PRIMARY KEY,
                    nombre VARCHAR(150) NOT NULL,
                    categoria VARCHAR(100) NOT NULL,
                    anio INT NOT NULL,
                    validacion VARCHAR(50) NOT NULL,
                    estado VARCHAR(20) DEFAULT 'Activo',
                    investigador_codigo VARCHAR(50) NOT NULL,
                    grupo_codigo VARCHAR(50),
                    FOREIGN KEY (investigador_codigo) REFERENCES investigadores(codigo),
                    FOREIGN KEY (grupo_codigo) REFERENCES grupos(codigo)
                )
            """
            )
        conn.commit()
    finally:
        conn.close()


def buscar_grupo(codigo):
    conn = obtener_conexion()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM grupos WHERE codigo = %s", (codigo,))
            return cursor.fetchone()
    finally:
        conn.close()


def buscar_investigador(codigo):
    conn = obtener_conexion()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM investigadores WHERE codigo = %s", (codigo,)
            )
            return cursor.fetchone()
    finally:
        conn.close()


def buscar_producto(codigo):
    conn = obtener_conexion()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM productos WHERE codigo = %s", (codigo,))
            return cursor.fetchone()
    finally:
        conn.close()


def crear_grupo():
    codigo = input("Código del grupo: ")
    if buscar_grupo(codigo):
        print("Ese grupo ya existe.")
        return

    nombre = input("Nombre del grupo: ")
    area = input("Área de investigación: ")

    conn = obtener_conexion()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO grupos (codigo, nombre, area) VALUES (%s, %s, %s)",
                (codigo, nombre, area),
            )
        conn.commit()
        print("Grupo creado y guardado en la BD correctamente.")
    finally:
        conn.close()


def crear_investigador():
    codigo = input("Código del investigador: ")
    if buscar_investigador(codigo):
        print("Ese investigador ya existe.")
        return

    nombre = input("Nombre completo: ")
    correo = input("Correo: ")
    grupo_codigo = input("Código del grupo al que pertenece: ")

    if not buscar_grupo(grupo_codigo):
        print("El grupo especificado no existe.")
        return

    conn = obtener_conexion()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO investigadores (codigo, nombre, correo) VALUES (%s, %s, %s)",
                (codigo, nombre, correo),
            )
            cursor.execute(
                "INSERT INTO grupo_investigador (grupo_codigo, investigador_codigo) VALUES (%s, %s)",
                (grupo_codigo, codigo),
            )
        conn.commit()
        print("Investigador creado correctamente en la BD.")
    finally:
        conn.close()


def crear_producto():
    codigo = input("Código del producto: ")
    if buscar_producto(codigo):
        print("Ese producto ya existe.")
        return

    nombre = input("Nombre del producto: ")
    categoria = input("Categoría: ")
    anio = int(input("Año: "))
    validacion = input("Validación (Validado/No validado): ")
    investigador_codigo = input("Código del investigador asociado: ")

    investigador = buscar_investigador(investigador_codigo)
    if not investigador:
        print("El investigador no existe.")
        return

    # Obtener el primer grupo del investigador
    conn = obtener_conexion()
    try:
        grupo_codigo = None
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT grupo_codigo FROM grupo_investigador WHERE investigador_codigo = %s LIMIT 1",
                (investigador_codigo,),
            )
            res = cursor.fetchone()
            if res:
                grupo_codigo = res["grupo_codigo"]

            cursor.execute(
                """
                INSERT INTO productos (codigo, nombre, categoria, anio, validacion, investigador_codigo, grupo_codigo)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
                (
                    codigo,
                    nombre,
                    categoria,
                    anio,
                    validacion,
                    investigador_codigo,
                    grupo_codigo,
                ),
            )
        conn.commit()

        pila_productos.append(codigo)
        cola_productos.append(codigo)
        print("Producto registrado en BD, Pila y Cola correctamente.")
    finally:
        conn.close()


def consultar_grupos():
    print("\n--- GRUPOS DE INVESTIGACIÓN (BD) ---")
    conn = obtener_conexion()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM grupos")
            grupos = cursor.fetchall()
            if not grupos:
                print("No hay grupos registrados.")
                return
            for g in grupos:
                print(
                    f"{g['codigo']} | {g['nombre']} | {g['area']} | {g['estado']}"
                )
    finally:
        conn.close()


def consultar_investigadores():
    print("\n--- INVESTIGADORES (BD) ---")
    conn = obtener_conexion()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT i.codigo, i.nombre, i.correo, i.estado, 
                       GROUP_CONCAT(gi.grupo_codigo SEPARATOR ', ') AS grupos
                FROM investigadores i
                LEFT JOIN grupo_investigador gi ON i.codigo = gi.investigador_codigo
                GROUP BY i.codigo
            """
            )
            investigadores = cursor.fetchall()
            if not investigadores:
                print("No hay investigadores registrados.")
                return
            for i in investigadores:
                grupos_str = i["grupos"] or "Sin grupo"
                print(
                    f"{i['codigo']} | {i['nombre']} | {i['correo']} | Grupos: [{grupos_str}] | {i['estado']}"
                )
    finally:
        conn.close()


def consultar_productos():
    print("\n--- PRODUCTOS DE INVESTIGACIÓN (BD) ---")
    conn = obtener_conexion()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM productos")
            productos = cursor.fetchall()
            if not productos:
                print("No hay productos registrados.")
                return
            for p in productos:
                print(
                    f"{p['codigo']} | {p['nombre']} | {p['categoria']} | {p['anio']} | {p['validacion']} | {p['estado']}"
                )
    finally:
        conn.close()


def modificar_producto():
    codigo = input("Código del producto a modificar: ")
    producto = buscar_producto(codigo)
    if not producto:
        print("Producto no encontrado.")
        return

    print("Deje vacío un campo para conservar su valor actual.")
    nombre = input(f"Nombre [{producto['nombre']}]: ") or producto["nombre"]
    categoria = (
        input(f"Categoría [{producto['categoria']}]: ") or producto["categoria"]
    )
    anio_in = input(f"Año [{producto['anio']}]: ")
    anio = int(anio_in) if anio_in else producto["anio"]
    validacion = (
        input(f"Validación [{producto['validacion']}]: ")
        or producto["validacion"]
    )

    conn = obtener_conexion()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE productos 
                SET nombre = %s, categoria = %s, anio = %s, validacion = %s 
                WHERE codigo = %s
            """,
                (nombre, categoria, anio, validacion, codigo),
            )
        conn.commit()
        print("Producto modificado correctamente.")
    finally:
        conn.close()


def eliminar_producto():
    codigo = input("Código del producto a eliminar: ")
    if not buscar_producto(codigo):
        print("Producto no encontrado.")
        return

    conn = obtener_conexion()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM productos WHERE codigo = %s", (codigo,))
        conn.commit()
        print("Producto eliminado físicamente de la BD.")
    finally:
        conn.close()


def desactivar_producto():
    codigo = input("Código del producto: ")
    if not buscar_producto(codigo):
        print("Producto no encontrado.")
        return

    conn = obtener_conexion()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE productos SET estado = 'Inactivo' WHERE codigo = %s",
                (codigo,),
            )
        conn.commit()
        print("Producto marcado como Inactivo.")
    finally:
        conn.close()


def filtrar_por_anio():
    desde = int(input("Año inicial: "))
    hasta = int(input("Año final: "))

    conn = obtener_conexion()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM productos WHERE anio BETWEEN %s AND %s",
                (desde, hasta),
            )
            productos = cursor.fetchall()
            print(f"\nProductos entre {desde} y {hasta}:")
            if not productos:
                print("No se encontraron productos en ese rango.")
                return
            for p in productos:
                print(
                    f"{p['codigo']} | {p['nombre']} | Año: {p['anio']} | {p['categoria']}"
                )
    finally:
        conn.close()


def estadisticas():
    conn = obtener_conexion()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS total FROM grupos")
            cant_grupos = cursor.fetchone()["total"]

            cursor.execute("SELECT COUNT(*) AS total FROM investigadores")
            cant_inv = cursor.fetchone()["total"]

            cursor.execute("SELECT COUNT(*) AS total FROM productos")
            cant_prod = cursor.fetchone()["total"]

            cursor.execute(
                "SELECT COUNT(*) AS total FROM productos WHERE estado = 'Activo'"
            )
            activos = cursor.fetchone()["total"]

            cursor.execute(
                "SELECT COUNT(*) AS total FROM productos WHERE LOWER(validacion) = 'validado'"
            )
            validados = cursor.fetchone()["total"]

            print("\n--- ESTADÍSTICAS DEL SISTEMA (PEA-i) ---")
            print(f"Total Grupos: {cant_grupos}")
            print(f"Total Investigadores: {cant_inv}")
            print(f"Total Productos: {cant_prod}")
            print(f"Productos Activos: {activos}")
            print(f"Productos Validados: {validados}")

            print("\nProductos por Categoría:")
            cursor.execute(
                "SELECT categoria, COUNT(*) AS cantidad FROM productos GROUP BY categoria"
            )
            categorias = cursor.fetchall()
            for c in categorias:
                print(f" - {c['categoria']}: {c['cantidad']}")
    finally:
        conn.close()


def importar_csv():
    archivo_csv = input("Nombre del archivo CSV a importar: ")
    if not os.path.exists(archivo_csv):
        print("El archivo especificado no existe.")
        return

    conn = obtener_conexion()
    try:
        with open(
            archivo_csv, "r", encoding="utf-8-sig", newline=""
        ) as f, conn.cursor() as cursor:
            lector = csv.DictReader(f)
            for fila in lector:
                # 1. Crear Grupo si no existe
                if not buscar_grupo(fila["grupo"]):
                    cursor.execute(
                        "INSERT INTO grupos (codigo, nombre, area) VALUES (%s, %s, %s)",
                        (
                            fila["grupo"],
                            fila.get("grupo_nombre", "Sin Nombre"),
                            fila.get("area", "Sin Área"),
                        ),
                    )

                # 2. Crear Investigador si no existe
                if not buscar_investigador(fila["investigador"]):
                    cursor.execute(
                        "INSERT INTO investigadores (codigo, nombre, correo) VALUES (%s, %s, %s)",
                        (
                            fila["investigador"],
                            fila.get("investigador_nombre", "Sin Nombre"),
                            fila.get("correo", "correo@unicesar.edu.co"),
                        ),
                    )
                    cursor.execute(
                        "INSERT INTO grupo_investigador (grupo_codigo, investigador_codigo) VALUES (%s, %s)",
                        (fila["grupo"], fila["investigador"]),
                    )

                # 3. Crear Producto si no existe
                if not buscar_producto(fila["codigo"]):
                    cursor.execute(
                        """
                        INSERT INTO productos (codigo, nombre, categoria, anio, validacion, investigador_codigo, grupo_codigo)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                        (
                            fila["codigo"],
                            fila["nombre"],
                            fila["categoria"],
                            int(fila["anio"]),
                            fila["validacion"],
                            fila["investigador"],
                            fila["grupo"],
                        ),
                    )
                    pila_productos.append(fila["codigo"])
                    cola_productos.append(fila["codigo"])

        conn.commit()
        print("Datos de CSV importados con éxito a la Base de Datos.")
    finally:
        conn.close()


def menu_grupos():
    opcion = input(
        "\n--- MENÚ GRUPOS ---\n1. Crear\n2. Consultar\n3. Desactivar\nOpción: "
    )
    if opcion == "1":
        crear_grupo()
    elif opcion == "2":
        consultar_grupos()
    elif opcion == "3":
        codigo = input("Código del grupo a desactivar: ")
        if buscar_grupo(codigo):
            conn = obtener_conexion()
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "UPDATE grupos SET estado = 'Inactivo' WHERE codigo = %s",
                        (codigo,),
                    )
                conn.commit()
                print("Grupo desactivado.")
            finally:
                conn.close()


def menu_investigadores():
    opcion = input(
        "\n--- MENÚ INVESTIGADORES ---\n1. Crear\n2. Consultar\nOpción: "
    )
    if opcion == "1":
        crear_investigador()
    elif opcion == "2":
        consultar_investigadores()


def menu_productos():
    opcion = input(
        "\n--- MENÚ PRODUCTOS ---\n1. Crear\n2. Consultar\n3. Modificar\n4. Eliminar\n5. Desactivar\n6. Filtrar por año\n7. Importar CSV\nOpción: "
    )
    if opcion == "1":
        crear_producto()
    elif opcion == "2":
        consultar_productos()
    elif opcion == "3":
        modificar_producto()
    elif opcion == "4":
        eliminar_producto()
    elif opcion == "5":
        desactivar_producto()
    elif opcion == "6":
        filtrar_por_anio()
    elif opcion == "7":
        importar_csv()


def menu():
    crear_tablas()  # Asegura que las tablas existan al iniciar
    gestionar_persistencia()  # Maneja la persistencia de datos al iniciar
    opcion = ""
    while opcion != "0":
        print("\n========== PEA-i (PyMySQL Directo / UPC) ==========")
        print("1. Grupos de investigación")
        print("2. Investigadores")
        print("3. Productos de investigación")
        print("4. Estadísticas")
        print("5. Ver pila de productos (LIFO)")
        print("6. Ver cola de productos (FIFO)")
        print("0. Salir")

        opcion = input("Seleccione una opción: ")

        if opcion == "1":
            menu_grupos()
        elif opcion == "2":
            menu_investigadores()
        elif opcion == "3":
            menu_productos()
        elif opcion == "4":
            estadisticas()
        elif opcion == "5":
            print(
                "\nPila de productos registrados reciente (LIFO):",
                pila_productos,
            )
        elif opcion == "6":
            print(
                "\nCola de productos registrados reciente (FIFO):",
                list(cola_productos),
            )
        elif opcion == "0":
            print("Programa finalizado.")
        else:
            print("Opción no válida.")


if __name__ == "__main__":
    menu()