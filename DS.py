import csv
import os
import re
from collections import deque
import urllib.request
from bs4 import BeautifulSoup
import matplotlib.pyplot as plt
from sqlalchemy import (create_engine, MetaData, Table, Column, String, Integer, ForeignKey, select, update, delete, func)

RUTA_BD = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "pea.db"
)

engine = create_engine(f"sqlite:///{RUTA_BD}")
metadata = MetaData()


grupos = Table(
    "grupos",
    metadata,

    Column("codigo", String(50), primary_key=True),
    Column("nombre", String(100), nullable=False),
    Column("area", String(100), nullable=False),
    Column("estado", String(20), default="Activo")
)


investigadores = Table(
    "investigadores",
    metadata,

    Column("codigo", String(50), primary_key=True),
    Column("nombre", String(100), nullable=False),
    Column("correo", String(100), nullable=False),
    Column("estado", String(20), default="Activo")
)


grupo_investigador = Table(
    "grupo_investigador",
    metadata,

    Column(
        "grupo_codigo",
        String(50),
        ForeignKey("grupos.codigo"),
        primary_key=True
    ),

    Column(
        "investigador_codigo",
        String(50),
        ForeignKey("investigadores.codigo"),
        primary_key=True
    )
)


productos = Table(
    "productos",
    metadata,

    Column("codigo", String(50), primary_key=True),
    Column("nombre", String(150), nullable=False),
    Column("categoria", String(100), nullable=False),
    Column("anio", Integer, nullable=False),
    Column("validacion", String(50), nullable=False),
    Column("estado", String(20), default="Activo"),

    Column(
        "investigador_codigo",
        String(50),
        ForeignKey("investigadores.codigo"),
        nullable=False
    ),

    Column(
        "grupo_codigo",
        String(50),
        ForeignKey("grupos.codigo")
    )
)


metadata.create_all(engine)


pila_productos = []
cola_productos = deque()

def crear_tablas():
    metadata.create_all(engine)

def buscar_grupo(codigo):

    with engine.connect() as conn:

        resultado = conn.execute(
            select(grupos).where(
                grupos.c.codigo == codigo
            )
        ).mappings().first()

        return resultado


def buscar_investigador(codigo):

    with engine.connect() as conn:

        resultado = conn.execute(
            select(investigadores).where(
                investigadores.c.codigo == codigo
            )
        ).mappings().first()

        return resultado


def buscar_producto(codigo):

    with engine.connect() as conn:

        resultado = conn.execute(
            select(productos).where(
                productos.c.codigo == codigo
            )
        ).mappings().first()

        return resultado


def limpiar_base_datos():

    with engine.begin() as conn:

        conn.execute(delete(productos))
        conn.execute(delete(grupo_investigador))
        conn.execute(delete(investigadores))
        conn.execute(delete(grupos))

    pila_productos.clear()
    cola_productos.clear()

    print("\n[BD] Se eliminaron todos los registros.")


def cargar_estructuras_en_memoria():

    pila_productos.clear()
    cola_productos.clear()

    with engine.connect() as conn:

        registros = conn.execute(
            select(productos.c.codigo)
        ).scalars().all()

    for codigo in registros:

        pila_productos.append(codigo)
        cola_productos.append(codigo)

    if registros:

        print(
            f"\n[Persistencia] "
            f"Se cargaron {len(registros)} producto(s) "
            f"en la pila y la cola."
        )

def gestionar_persistencia():

    crear_tablas()

    with engine.connect() as conn:

        total_grupos = conn.execute(
            select(func.count()).select_from(grupos)
        ).scalar()

        total_productos = conn.execute(
            select(func.count()).select_from(productos)
        ).scalar()

    if total_grupos > 0 or total_productos > 0:

        print("\n================ CONFIGURACIÓN DE DATOS ================")

        print(
            "\nSe encontraron datos guardados "
            "de sesiones anteriores en SQLite."
        )

        print("\n1. Mantener los datos anteriores")
        print("2. Borrar todos los datos")

        opcion = input(
            "\nSeleccione una opción (1/2) [Por defecto 1]: "
        ).strip()

        if opcion == "2":

            limpiar_base_datos()

        else:

            cargar_estructuras_en_memoria()

            print(
                "\n[Persistencia] "
                "Continuando con la base de datos existente."
            )


def crear_grupo():

    codigo = input("Código del grupo: ").strip()

    if buscar_grupo(codigo):

        print("Ese grupo ya existe.")
        return

    nombre = input("Nombre del grupo: ").strip()
    area = input("Área de investigación: ").strip()

    with engine.begin() as conn:

        conn.execute(
            grupos.insert().values(
                codigo=codigo,
                nombre=nombre,
                area=area,
                estado="Activo"
            )
        )

    print("Grupo creado correctamente.")


def crear_investigador():

    codigo = input(
        "Código del investigador: "
    ).strip()

    if buscar_investigador(codigo):

        print("Ese investigador ya existe.")
        return

    nombre = input(
        "Nombre completo: "
    ).strip()

    correo = input(
        "Correo: "
    ).strip()

    grupo_codigo = input(
        "Código del grupo al que pertenece: "
    ).strip()

    if not buscar_grupo(grupo_codigo):

        print("El grupo especificado no existe.")
        return

    with engine.begin() as conn:

        conn.execute(
            investigadores.insert().values(
                codigo=codigo,
                nombre=nombre,
                correo=correo,
                estado="Activo"
            )
        )

        conn.execute(
            grupo_investigador.insert().values(
                grupo_codigo=grupo_codigo,
                investigador_codigo=codigo
            )
        )

    print("Investigador creado correctamente.")


def crear_producto():

    codigo = input(
        "Código del producto: "
    ).strip()

    if buscar_producto(codigo):

        print("Ese producto ya existe.")
        return

    nombre = input(
        "Nombre del producto: "
    ).strip()

    categoria = input(
        "Categoría: "
    ).strip()

    try:

        anio = int(
            input("Año: ")
        )

    except ValueError:

        print("El año debe ser un número.")
        return

    validacion = input(
        "Validación (Validado/No validado): "
    ).strip()

    investigador_codigo = input(
        "Código del investigador asociado: "
    ).strip()

    if not buscar_investigador(
        investigador_codigo
    ):

        print("El investigador no existe.")
        return

    with engine.connect() as conn:

        grupo_codigo = conn.execute(
            select(
                grupo_investigador.c.grupo_codigo
            ).where(
                grupo_investigador.c.investigador_codigo
                == investigador_codigo
            )
        ).scalars().first()

    with engine.begin() as conn:

        conn.execute(
            productos.insert().values(
                codigo=codigo,
                nombre=nombre,
                categoria=categoria,
                anio=anio,
                validacion=validacion,
                estado="Activo",
                investigador_codigo=investigador_codigo,
                grupo_codigo=grupo_codigo
            )
        )

    pila_productos.append(codigo)
    cola_productos.append(codigo)

    print(
        "Producto registrado correctamente "
        "en la BD, pila y cola."
    )


def consultar_grupos():

    print("\n--- GRUPOS DE INVESTIGACIÓN ---")

    with engine.connect() as conn:

        registros = conn.execute(
            select(grupos)
        ).mappings().all()

    if not registros:

        print("No hay grupos registrados.")
        return

    for grupo in registros:

        print(
            f"{grupo['codigo']} | "
            f"{grupo['nombre']} | "
            f"{grupo['area']} | "
            f"{grupo['estado']}"
        )


def consultar_investigadores():

    print("\n--- INVESTIGADORES ---")

    consulta = (
        select(
            investigadores.c.codigo,
            investigadores.c.nombre,
            investigadores.c.correo,
            investigadores.c.estado,
            func.group_concat(
                grupo_investigador.c.grupo_codigo,
                ", "
            ).label("grupos")
        )
        .select_from(
            investigadores.outerjoin(
                grupo_investigador,
                investigadores.c.codigo
                == grupo_investigador.c.investigador_codigo
            )
        )
        .group_by(
            investigadores.c.codigo
        )
    )

    with engine.connect() as conn:

        registros = conn.execute(
            consulta
        ).mappings().all()

    if not registros:

        print("No hay investigadores registrados.")
        return

    for investigador in registros:

        grupos_str = (
            investigador["grupos"]
            or "Sin grupo"
        )

        print(
            f"{investigador['codigo']} | "
            f"{investigador['nombre']} | "
            f"{investigador['correo']} | "
            f"Grupos: [{grupos_str}] | "
            f"{investigador['estado']}"
        )


def consultar_productos():

    print("\n--- PRODUCTOS DE INVESTIGACIÓN ---")

    with engine.connect() as conn:

        registros = conn.execute(
            select(productos)
        ).mappings().all()

    if not registros:

        print("No hay productos registrados.")
        return

    for producto in registros:

        print(
            f"{producto['codigo']} | "
            f"{producto['nombre']} | "
            f"{producto['categoria']} | "
            f"{producto['anio']} | "
            f"{producto['validacion']} | "
            f"{producto['estado']}"
        )


def modificar_producto():

    codigo = input(
        "Código del producto a modificar: "
    ).strip()

    producto = buscar_producto(codigo)

    if not producto:

        print("Producto no encontrado.")
        return

    print(
        "\nDeje vacío un campo para conservar "
        "su valor actual."
    )

    nombre = input(
        f"Nombre [{producto['nombre']}]: "
    ).strip()

    if not nombre:
        nombre = producto["nombre"]

    categoria = input(
        f"Categoría [{producto['categoria']}]: "
    ).strip()

    if not categoria:
        categoria = producto["categoria"]

    anio_texto = input(
        f"Año [{producto['anio']}]: "
    ).strip()

    if anio_texto:

        try:
            anio = int(anio_texto)

        except ValueError:

            print("El año debe ser un número.")
            return

    else:

        anio = producto["anio"]

    validacion = input(
        f"Validación [{producto['validacion']}]: "
    ).strip()

    if not validacion:
        validacion = producto["validacion"]

    with engine.begin() as conn:

        conn.execute(
            update(productos)
            .where(productos.c.codigo == codigo)
            .values(
                nombre=nombre,
                categoria=categoria,
                anio=anio,
                validacion=validacion
            )
        )

    print("Producto modificado correctamente.")

def eliminar_producto():

    codigo = input(
        "Código del producto a eliminar: "
    ).strip()

    if not buscar_producto(codigo):

        print("Producto no encontrado.")
        return

    with engine.begin() as conn:

        conn.execute(
            delete(productos).where(
                productos.c.codigo == codigo
            )
        )

    if codigo in pila_productos:

        pila_productos.remove(codigo)

    if codigo in cola_productos:

        cola_productos.remove(codigo)

    print("Producto eliminado correctamente.")


def desactivar_producto():

    codigo = input(
        "Código del producto: "
    ).strip()

    if not buscar_producto(codigo):

        print("Producto no encontrado.")
        return

    with engine.begin() as conn:

        conn.execute(
            update(productos)
            .where(productos.c.codigo == codigo)
            .values(
                estado="Inactivo"
            )
        )

    print("Producto marcado como Inactivo.")

def desactivar_grupo():

    codigo = input(
        "Código del grupo a desactivar: "
    ).strip()

    if not buscar_grupo(codigo):

        print("Grupo no encontrado.")
        return

    with engine.begin() as conn:

        conn.execute(
            update(grupos)
            .where(grupos.c.codigo == codigo)
            .values(
                estado="Inactivo"
            )
        )

    print("Grupo desactivado.")

def filtrar_por_anio():

    try:

        desde = int(
            input("Año inicial: ")
        )

        hasta = int(
            input("Año final: ")
        )

    except ValueError:

        print("Los años deben ser números.")
        return

    consulta = (
        select(productos)
        .where(
            productos.c.anio.between(
                desde,
                hasta
            )
        )
    )

    with engine.connect() as conn:

        registros = conn.execute(
            consulta
        ).mappings().all()

    print(
        f"\nProductos entre {desde} y {hasta}:"
    )

    if not registros:

        print(
            "No se encontraron productos "
            "en ese rango."
        )

        return

    for producto in registros:

        print(
            f"{producto['codigo']} | "
            f"{producto['nombre']} | "
            f"Año: {producto['anio']} | "
            f"{producto['categoria']}"
        )
def descargar_desde_url():
    url = input("\nIngrese la URL a procesar (GrupLAC/CvLAC): ").strip()
    if not url:
        return

    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        print(f"\n[Scraping] Conectando a {url}...")
        req = urllib.request.Request(url, headers=headers)
        try:
            html = urllib.request.urlopen(req).read().decode('utf-8')
        except UnicodeDecodeError:
            html = urllib.request.urlopen(req).read().decode('iso-8859-1')

        soup = BeautifulSoup(html, 'html.parser')
        filas = soup.find_all('tr')
        contador = 1
        registros_extraidos = []

        with engine.begin() as conn:
            if not buscar_grupo("G-001"):
                conn.execute(
                    grupos.insert().values(
                        codigo="G-001", 
                        nombre="Grupo Scraping MinCiencias", 
                        area="Investigación", 
                        estado="Activo"
                    )
                )
            if not buscar_investigador("INV-001"):
                conn.execute(
                    investigadores.insert().values(
                        codigo="INV-001", 
                        nombre="Investigador Principal", 
                        correo="investigador@unicesar.edu.co", 
                        estado="Activo"
                    )
                )

        for fila in filas:
            celdas = fila.find_all(['td', 'th'])
            textos = [c.get_text(strip=True) for c in celdas if c.get_text(strip=True)]
            if not textos:
                continue

            texto_completo = " ".join(textos)
            if len(texto_completo) < 20:
                continue

            match_anio = re.search(r'\b(19\d\d|20[0-2]\d)\b', texto_completo)
            anio = int(match_anio.group(1)) if match_anio else 2024

            categoria = "Generica"
            if re.search(r'art[ií]culo|journal', texto_completo, re.IGNORECASE):
                categoria = "Artículo"
            elif re.search(r'cap[ií]tulo|libro', texto_completo, re.IGNORECASE):
                categoria = "Libro / Capítulo"
            elif re.search(r'software|app', texto_completo, re.IGNORECASE):
                categoria = "Software"

            nombre_prod = texto_completo.replace(',', ' ').replace('"', '')[:100]
            codigo_prod = f"PROD-WEB-{contador:03d}"

            if not buscar_producto(codigo_prod):
                with engine.begin() as conn:
                    conn.execute(
                        productos.insert().values(
                            codigo=codigo_prod,
                            nombre=nombre_prod,
                            categoria=categoria,
                            anio=anio,
                            validacion="Validado",
                            estado="Activo",
                            investigador_codigo="INV-001",
                            grupo_codigo="G-001"
                        )
                    )
                pila_productos.append(codigo_prod)
                cola_productos.append(codigo_prod)
                contador += 1

            registros_extraidos.append([codigo_prod, nombre_prod, categoria, anio, "Validado", "G-001"])

        with open("datos_scraping.csv", mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["codigo", "nombre", "categoria", "anio", "validacion", "grupo_codigo"])
            writer.writerows(registros_extraidos)

        print(f"\n[Scraping] Se importaron {contador - 1} productos directamente a la BD y Pila/Cola.")
        print("[Respaldo] Se actualizó el archivo auxiliar 'datos_scraping.csv'.")

    except Exception as e:
        print(f"\nError en Web Scraping: {e}")

def estadisticas():
    with engine.connect() as conn:
        categorias = conn.execute(
            select(
                productos.c.categoria,
                func.count().label("cantidad")
            ).group_by(productos.c.categoria)
        ).mappings().all()

        anios = conn.execute(
            select(
                productos.c.anio,
                func.count().label("cantidad")
            ).group_by(productos.c.anio)
        ).mappings().all()

    if not categorias and not anios:
        print("\n[Estadísticas] No hay datos suficientes para generar el Dashboard.")
        return

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.canvas.manager.set_window_title('PEA-i - Dashboard Estadístico')
    fig.suptitle('DASHBOARD ESTADÍSTICO DE INVESTIGACIÓN (UPC)', fontsize=14, fontweight='bold')

    cats = [c['categoria'] for c in categorias]
    c_cants = [c['cantidad'] for c in categorias]
    ax1.bar(cats, c_cants, color='#0056b3', edgecolor='black')
    ax1.set_title('Productos por Categoría')
    ax1.set_xlabel('Categorías')
    ax1.set_ylabel('Cantidad')
    ax1.tick_params(axis='x', rotation=30)
    ax1.grid(axis='y', linestyle='--', alpha=0.7)

    a_anios = [str(a['anio']) for a in anios]
    a_cants = [a['cantidad'] for a in anios]
    ax2.bar(a_anios, a_cants, color='#28a745', edgecolor='black')
    ax2.set_title('Distribución por Año de Publicación')
    ax2.set_xlabel('Año')
    ax2.set_ylabel('Cantidad')
    ax2.grid(axis='y', linestyle='--', alpha=0.7)

    plt.tight_layout()
    plt.show()


def importar_csv():
    archivo_csv = input("Nombre del archivo CSV a importar [Por defecto: datos_scraping.csv]: ").strip()
    if not archivo_csv:
        archivo_csv = "datos_scraping.csv"

    if not os.path.exists(archivo_csv):
        print("El archivo especificado no existe.")
        return

    try:
        with open(archivo_csv, "r", encoding="utf-8-sig", newline="") as archivo:
            lector = csv.DictReader(archivo)
            registros_nuevos = 0

            with engine.begin() as conn:
                for fila in lector:
                    grupo_codigo = fila.get("grupo_codigo", fila.get("grupo", "G-001"))
                    investigador_codigo = fila.get("investigador", "INV-001")
                    producto_codigo = fila["codigo"]

                    # Crear Grupo e Investigador base si no existen en SQLite
                    if not conn.execute(select(grupos.c.codigo).where(grupos.c.codigo == grupo_codigo)).scalar():
                        conn.execute(grupos.insert().values(codigo=grupo_codigo, nombre="Grupo Base", area="Sistemas", estado="Activo"))

                    if not conn.execute(select(investigadores.c.codigo).where(investigadores.c.codigo == investigador_codigo)).scalar():
                        conn.execute(investigadores.insert().values(codigo=investigador_codigo, nombre="Investigador Base", correo="inv@unicesar.edu.co", estado="Activo"))

                    # Insertar el producto en SQLite
                    if not conn.execute(select(productos.c.codigo).where(productos.c.codigo == producto_codigo)).scalar():
                        conn.execute(
                            productos.insert().values(
                                codigo=producto_codigo,
                                nombre=fila["nombre"],
                                categoria=fila["categoria"],
                                anio=int(fila["anio"]),
                                validacion=fila["validacion"],
                                estado="Activo",
                                investigador_codigo=investigador_codigo,
                                grupo_codigo=grupo_codigo
                            )
                        )
                        pila_productos.append(producto_codigo)
                        cola_productos.append(producto_codigo)
                        registros_nuevos += 1

        print(f"\n[CSV] Se importaron {registros_nuevos} productos a la BD desde '{archivo_csv}'.")

    except Exception as e:
        print(f"\nError al importar CSV: {e}")
        
def menu_grupos():

    opcion = input(
        "\n--- MENÚ GRUPOS ---\n"
        "1. Crear\n"
        "2. Consultar\n"
        "3. Desactivar\n"
        "Opción: "
    )

    if opcion == "1":

        crear_grupo()

    elif opcion == "2":

        consultar_grupos()

    elif opcion == "3":

        desactivar_grupo()

    else:

        print("Opción no válida.")

def menu_investigadores():

    opcion = input(
        "\n--- MENÚ INVESTIGADORES ---\n"
        "1. Crear\n"
        "2. Consultar\n"
        "Opción: "
    )

    if opcion == "1":

        crear_investigador()

    elif opcion == "2":

        consultar_investigadores()

    else:

        print("Opción no válida.")

def menu_productos():

    opcion = input(
        "\n--- MENÚ PRODUCTOS ---\n"
        "1. Crear\n"
        "2. Consultar\n"
        "3. Modificar\n"
        "4. Eliminar\n"
        "5. Desactivar\n"
        "6. Filtrar por año\n"
        "7. Importar CSV\n"
        "8. Web Scraping (URL)\n"
        "Opción: "
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

    elif opcion == "8":

        descargar_desde_url()

    else:

        print("Opción no válida.")

def menu():

    gestionar_persistencia()

    opcion = ""

    while opcion != "0":

        print(
            "\n========== PEA-i "
            "(SQLAlchemy + SQLite) =========="
        )

        print("1. Grupos de investigación")
        print("2. Investigadores")
        print("3. Productos de investigación")
        print("4. Estadísticas")
        print("5. Ver pila de productos (LIFO)")
        print("6. Ver cola de productos (FIFO)")
        print("0. Salir")

        opcion = input(
            "\nSeleccione una opción: "
        ).strip()

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
                "\nPila de productos (LIFO):"
            )

            print(pila_productos)

        elif opcion == "6":

            print(
                "\nCola de productos (FIFO):"
            )

            print(list(cola_productos))

        elif opcion == "0":

            print(
                "\nPrograma finalizado."
            )

        else:

            print(
                "\nOpción no válida."
            )

if __name__ == "__main__":

    menu()