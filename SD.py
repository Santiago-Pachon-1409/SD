import csv
import os
from collections import deque
from sqlalchemy import (Column,ForeignKey,Integer,String,Table,create_engine,func,)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

DB_URL = "mysql+pymysql://root:tu_contraseña@localhost:3306/pea_db"
engine = create_engine(DB_URL, echo=False)
Base = declarative_base()
Session = sessionmaker(bind=engine)
session = Session()
                                                                                 
grupo_investigador_m2m = Table(
    "grupo_investigador",
    Base.metadata,
    Column("grupo_codigo", String, ForeignKey("grupos.codigo"), primary_key=True),
    Column(
        "investigador_codigo",
        String,
        ForeignKey("investigadores.codigo"),
        primary_key=True,
    ),
)


class Grupo(Base):
    __tablename__ = "grupos"

    codigo = Column(String, primary_key=True)
    nombre = Column(String, nullable=False)
    area = Column(String, nullable=False)
    estado = Column(String, default="Activo")

                                                   
    investigadores = relationship(
        "Investigador", secondary=grupo_investigador_m2m, back_populates="grupos"
    )
    productos = relationship("Producto", back_populates="grupo_rel")


class Investigador(Base):
    __tablename__ = "investigadores"

    codigo = Column(String, primary_key=True)
    nombre = Column(String, nullable=False)
    correo = Column(String, nullable=False)
    estado = Column(String, default="Activo")

                
    grupos = relationship(
        "Grupo", secondary=grupo_investigador_m2m, back_populates="investigadores"
    )
    productos = relationship("Producto", back_populates="investigador_rel")


class Producto(Base):
    __tablename__ = "productos"

    codigo = Column(String, primary_key=True)
    nombre = Column(String, nullable=False)
    categoria = Column(String, nullable=False)
    anio = Column(Integer, nullable=False)
    validacion = Column(String, nullable=False)
    estado = Column(String, default="Activo")

    investigador_codigo = Column(
        String, ForeignKey("investigadores.codigo"), nullable=False
    )
    grupo_codigo = Column(String, ForeignKey("grupos.codigo"), nullable=True)

                                
    investigador_rel = relationship("Investigador", back_populates="productos")
    grupo_rel = relationship("Grupo", back_populates="productos")
                    
Base.metadata.create_all(engine)                                        
pila_productos = []        
cola_productos = deque()        

def buscar_grupo(codigo):
    return session.query(Grupo).filter_by(codigo=codigo).first()


def buscar_investigador(codigo):
    return session.query(Investigador).filter_by(codigo=codigo).first()


def buscar_producto(codigo):
    return session.query(Producto).filter_by(codigo=codigo).first()


def crear_grupo():
    codigo = input("Código del grupo: ")
    if buscar_grupo(codigo):
        print("Ese grupo ya existe.")
        return

    nombre = input("Nombre del grupo: ")
    area = input("Área de investigación: ")

    nuevo_grupo = Grupo(codigo=codigo, nombre=nombre, area=area)
    session.add(nuevo_grupo)
    session.commit()
    print("Grupo creado y guardado en la BD correctamente.")


def crear_investigador():
    codigo = input("Código del investigador: ")
    if buscar_investigador(codigo):
        print("Ese investigador ya existe.")
        return

    nombre = input("Nombre completo: ")
    correo = input("Correo: ")
    grupo_codigo = input("Código del grupo al que pertenece: ")

    grupo = buscar_grupo(grupo_codigo)
    if not grupo:
        print("El grupo especificado no existe.")
        return

    nuevo_inv = Investigador(codigo=codigo, nombre=nombre, correo=correo)
    nuevo_inv.grupos.append(grupo)

    session.add(nuevo_inv)
    session.commit()
    print("Investigador creado correctamente en la BD.")


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

                                                          
    grupo_codigo = investigador.grupos[0].codigo if investigador.grupos else None

    nuevo_producto = Producto(
        codigo=codigo,
        nombre=nombre,
        categoria=categoria,
        anio=anio,
        validacion=validacion,
        investigador_codigo=investigador_codigo,
        grupo_codigo=grupo_codigo,
    )

    session.add(nuevo_producto)
    session.commit()

                                       
    pila_productos.append(codigo)
    cola_productos.append(codigo)

    print("Producto registrado en BD, Pila y Cola correctamente.")


def consultar_grupos():
    print("\n--- GRUPOS DE INVESTIGACIÓN (BD) ---")
    grupos = session.query(Grupo).all()
    if not grupos:
        print("No hay grupos registrados.")
        return
    for g in grupos:
        print(f"{g.codigo} | {g.nombre} | {g.area} | {g.estado}")


def consultar_investigadores():
    print("\n--- INVESTIGADORES (BD) ---")
    investigadores = session.query(Investigador).all()
    if not investigadores:
        print("No hay investigadores registrados.")
        return
    for i in investigadores:
        grupos_str = ", ".join([g.codigo for g in i.grupos])
        print(
            f"{i.codigo} | {i.nombre} | {i.correo} | Grupos: [{grupos_str}] | {i.estado}"
        )


def consultar_productos():
    print("\n--- PRODUCTOS DE INVESTIGACIÓN (BD) ---")
    productos = session.query(Producto).all()
    if not productos:
        print("No hay productos registrados.")
        return
    for p in productos:
        print(
            f"{p.codigo} | {p.nombre} | {p.categoria} | {p.anio} | {p.validacion} | {p.estado}"
        )


def modificar_producto():
    codigo = input("Código del producto a modificar: ")
    producto = buscar_producto(codigo)
    if not producto:
        print("Producto no encontrado.")
        return

    print("Deje vacío un campo para conservar su valor actual.")
    nombre = input(f"Nombre [{producto.nombre}]: ")
    categoria = input(f"Categoría [{producto.categoria}]: ")
    anio = input(f"Año [{producto.anio}]: ")
    validacion = input(f"Validación [{producto.validacion}]: ")

    if nombre:
        producto.nombre = nombre
    if categoria:
        producto.categoria = categoria
    if anio:
        producto.anio = int(anio)
    if validacion:
        producto.validacion = validacion

    session.commit()
    print("Producto modificado correctamente.")


def eliminar_producto():
    codigo = input("Código del producto a eliminar: ")
    producto = buscar_producto(codigo)
    if not producto:
        print("Producto no encontrado.")
        return

    session.delete(producto)
    session.commit()
    print("Producto eliminado físicamente de la BD.")


def desactivar_producto():
    codigo = input("Código del producto: ")
    producto = buscar_producto(codigo)
    if producto:
        producto.estado = "Inactivo"
        session.commit()
        print("Producto marcado como Inactivo.")
    else:
        print("Producto no encontrado.")


def filtrar_por_anio():
    desde = int(input("Año inicial (Ventana de observación): "))
    hasta = int(input("Año final: "))

    productos = (
        session.query(Producto).filter(Producto.anio.between(desde, hasta)).all()
    )

    print(f"\nProductos entre {desde} y {hasta}:")
    if not productos:
        print("No se encontraron productos en ese rango.")
        return

    for p in productos:
        print(f"{p.codigo} | {p.nombre} | Año: {p.anio} | {p.categoria}")


def estadisticas():
    cant_grupos = session.query(Grupo).count()
    cant_inv = session.query(Investigador).count()
    cant_prod = session.query(Producto).count()

    activos = session.query(Producto).filter_by(estado="Activo").count()
    validados = (
        session.query(Producto)
        .filter(func.lower(Producto.validacion) == "validado")
        .count()
    )

    print("\n--- ESTADÍSTICAS DEL SISTEMA (PEA-i) ---")
    print(f"Total Grupos: {cant_grupos}")
    print(f"Total Investigadores: {cant_inv}")
    print(f"Total Productos: {cant_prod}")
    print(f"Productos Activos: {activos}")
    print(f"Productos Validados: {validados}")

    print("\nProductos por Categoría:")
    categorias = (
        session.query(Producto.categoria, func.count(Producto.codigo))
        .group_by(Producto.categoria)
        .all()
    )
    for cat, cantidad in categorias:
        print(f" - {cat}: {cantidad}")


def importar_csv():
    archivo_csv = input("Nombre del archivo CSV a importar: ")
    if not os.path.exists(archivo_csv):
        print("El archivo especificado no existe.")
        return

    with open(archivo_csv, "r", encoding="utf-8-sig", newline="") as f:
        lector = csv.DictReader(f)
        for fila in lector:
                                  
            grupo = buscar_grupo(fila["grupo"])
            if not grupo:
                grupo = Grupo(
                    codigo=fila["grupo"],
                    nombre=fila.get("grupo_nombre", "Sin Nombre"),
                    area=fila.get("area", "Sin Área"),
                )
                session.add(grupo)

                                         
            investigador = buscar_investigador(fila["investigador"])
            if not investigador:
                investigador = Investigador(
                    codigo=fila["investigador"],
                    nombre=fila.get("investigador_nombre", "Sin Nombre"),
                    correo=fila.get("correo", "correo@unicesar.edu.co"),
                )
                investigador.grupos.append(grupo)
                session.add(investigador)

                                     
            if not buscar_producto(fila["codigo"]):
                producto = Producto(
                    codigo=fila["codigo"],
                    nombre=fila["nombre"],
                    categoria=fila["categoria"],
                    anio=int(fila["anio"]),
                    validacion=fila["validacion"],
                    investigador_codigo=investigador.codigo,
                    grupo_codigo=grupo.codigo,
                )
                session.add(producto)
                pila_productos.append(producto.codigo)
                cola_productos.append(producto.codigo)

        session.commit()
        print("Datos de CSV importados con éxito a la Base de Datos.")


                                                                        
                               
                                                                        


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
        g = buscar_grupo(codigo)
        if g:
            g.estado = "Inactivo"
            session.commit()
            print("Grupo desactivado.")


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
    opcion = ""
    while opcion != "0":
        print("\n========== PEA-i (SQLAlchemy / UPC) ==========")
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
            print("\nPila de productos registrados reciente (LIFO):", pila_productos)
        elif opcion == "6":
            print(
                "\nCola de productos registrados reciente (FIFO):", list(cola_productos)
            )
        elif opcion == "0":
            session.close()
            print("Sesión de Base de Datos cerrada. Programa finalizado.")
        else:
            print("Opción no válida.")


if __name__ == "__main__":
    menu()