import csv
import os
import re
import json
import subprocess
from collections import deque
import urllib.request
from bs4 import BeautifulSoup
from sqlalchemy import (create_engine, MetaData, Table, Column, String, Integer, ForeignKey, select, update, delete, func)
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

# CONFIGURACIÓN Y PERSISTENCIA (SQLAlchemy)


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
    Column("grupo_codigo", String(50), ForeignKey("grupos.codigo"), primary_key=True),
    Column("investigador_codigo", String(50), ForeignKey("investigadores.codigo"), primary_key=True)
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
    Column("investigador_codigo", String(50), ForeignKey("investigadores.codigo"), nullable=False),
    Column("grupo_codigo", String(50), ForeignKey("grupos.codigo"))
)

metadata.create_all(engine)

# ==========================================
# ESTRUCTURAS DE DATOS EN MEMORIA (No-POO)
# ==========================================

pila_productos = []
cola_productos = deque()
multilista_grupos = []

def vaciar_multilista():
    multilista_grupos.clear()

def crear_nodo_producto(codigo, nombre, categoria, anio, validacion, estado="Activo"):
    return {
        "codigo": codigo,
        "nombre": nombre,
        "categoria": categoria,
        "anio": anio,
        "validacion": validacion,
        "estado": estado
    }

def crear_nodo_investigador(codigo, nombre, correo, estado="Activo"):
    return {
        "codigo": codigo,
        "nombre": nombre,
        "correo": correo,
        "estado": estado,
        "productos": []
    }

def crear_nodo_grupo(codigo, nombre, area, estado="Activo"):
    return {
        "codigo": codigo,
        "nombre": nombre,
        "area": area,
        "estado": estado,
        "investigadores": []
    }

def agregar_o_buscar_grupo_ml(codigo, nombre="Sin Nombre", area="General"):
    for grupo in multilista_grupos:
        if grupo["codigo"] == codigo:
            grupo["nombre"] = nombre
            grupo["area"] = area
            return grupo
    nuevo_grupo = crear_nodo_grupo(codigo, nombre, area)
    multilista_grupos.append(nuevo_grupo)
    return nuevo_grupo

def agregar_o_buscar_investigador_ml(grupo_codigo, inv_codigo, nombre="Sin Nombre", correo="correo@unicesar.edu.co"):
    grupo = agregar_o_buscar_grupo_ml(grupo_codigo)
    for inv in grupo["investigadores"]:
        if inv["codigo"] == inv_codigo:
            inv["nombre"] = nombre
            inv["correo"] = correo
            return inv
    nuevo_inv = crear_nodo_investigador(inv_codigo, nombre, correo)
    grupo["investigadores"].append(nuevo_inv)
    return nuevo_inv

def agregar_producto_ml(grupo_codigo, inv_codigo, prod_codigo, nombre, categoria, anio, validacion="Validado"):
    investigador = agregar_o_buscar_investigador_ml(grupo_codigo, inv_codigo)
    for prod in investigador["productos"]:
        if prod["codigo"] == prod_codigo:
            return
    nuevo_prod = crear_nodo_producto(prod_codigo, nombre, categoria, anio, validacion)
    investigador["productos"].append(nuevo_prod)

# ==========================================
# FUNCIONES DE BASE DE DATOS Y SINCRONIZACIÓN
# ==========================================


def generar_reporte_pandas_gui(ventana_padre):
    # 1. Cargar los datos desde SQLite a un DataFrame de pandas
    with engine.connect() as conn:
        df = pd.read_sql("SELECT * FROM productos", conn)

    if df.empty:
        messagebox.showwarning("Atención", "No hay productos registrados para analizar.")
        return

    # 2. Crear ventana emergente Tkinter
    top = tk.Toplevel(ventana_padre)
    top.title("Análisis Estadístico e Histogramas (Pandas + Matplotlib)")
    top.geometry("800x600")
    top.configure(bg="#f8fafc")

    # 3. Crear figura de Matplotlib con 2 subgráficos (Histogramas/Barras)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 4), dpi=100)
    fig.patch.set_facecolor('#f8fafc')

    # Gráfico 1: Conteo por Categoría
    conteo_cat = df['categoria'].value_counts()
    conteo_cat.plot(kind='bar', ax=ax1, color='#0284c7', edgecolor='black')
    ax1.set_title('Productos por Categoría', fontsize=10, fontweight='bold')
    ax1.set_xlabel('Categoría')
    ax1.set_ylabel('Cantidad')
    ax1.grid(axis='y', linestyle='--', alpha=0.7)

    # Gráfico 2: Histograma por Año
    df['anio'].plot(kind='hist', ax=ax2, bins=len(df['anio'].unique()), color='#16a34a', edgecolor='black')
    ax2.set_title('Distribución Cronológica (Años)', fontsize=10, fontweight='bold')
    ax2.set_xlabel('Año de Publicación')
    ax2.set_ylabel('Frecuencia')
    ax2.grid(axis='y', linestyle='--', alpha=0.7)

    plt.tight_layout()

    # 4. Embeber la gráfica de Matplotlib dentro de la ventana de Tkinter
    canvas = FigureCanvasTkAgg(fig, master=top)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

def crear_tablas():
    metadata.create_all(engine)

def buscar_grupo(codigo):
    with engine.connect() as conn:
        return conn.execute(select(grupos).where(grupos.c.codigo == codigo)).mappings().first()

def buscar_investigador(codigo):
    with engine.connect() as conn:
        return conn.execute(select(investigadores).where(investigadores.c.codigo == codigo)).mappings().first()

def buscar_producto(codigo):
    with engine.connect() as conn:
        return conn.execute(select(productos).where(productos.c.codigo == codigo)).mappings().first()

def limpiar_base_datos():
    with engine.begin() as conn:
        conn.execute(delete(productos))
        conn.execute(delete(grupo_investigador))
        conn.execute(delete(investigadores))
        conn.execute(delete(grupos))
    pila_productos.clear()
    cola_productos.clear()
    vaciar_multilista()

def cargar_estructuras_guardadas():
    pila_productos.clear()
    cola_productos.clear()
    vaciar_multilista()

    with engine.connect() as conn:
        # 1. Cargar Grupos
        reg_grupos = conn.execute(select(grupos)).mappings().all()
        for g in reg_grupos:
            agregar_o_buscar_grupo_ml(g["codigo"], g["nombre"], g["area"])

        # 2. Cargar Investigadores
        consulta_inv = (
            select(
                investigadores.c.codigo,
                investigadores.c.nombre,
                investigadores.c.correo,
                grupo_investigador.c.grupo_codigo
            )
            .select_from(
                investigadores.outerjoin(grupo_investigador, investigadores.c.codigo == grupo_investigador.c.investigador_codigo)
            )
        )
        reg_inv = conn.execute(consulta_inv).mappings().all()
        for inv in reg_inv:
            g_cod = inv["grupo_codigo"] if inv["grupo_codigo"] else "G-001"
            agregar_o_buscar_investigador_ml(g_cod, inv["codigo"], inv["nombre"], inv["correo"])

        # 3. Cargar Productos
        registros = conn.execute(select(productos)).mappings().all()

    for p in registros:
        pila_productos.append(p["codigo"])
        cola_productos.append(p["codigo"])
        g_cod = p["grupo_codigo"] if p["grupo_codigo"] else "G-001"
        inv_cod = p["investigador_codigo"] if p["investigador_codigo"] else "INV-001"

        agregar_producto_ml(
            grupo_codigo=g_cod,
            inv_codigo=inv_cod,
            prod_codigo=p["codigo"],
            nombre=p["nombre"],
            categoria=p["categoria"],
            anio=p["anio"],
            validacion=p["validacion"]
        )

def exportar_todo_a_json(ruta_salida="datos_entrada.json"):
    with engine.connect() as conn:
        registros = conn.execute(
            select(
                productos.c.codigo,
                productos.c.nombre,
                productos.c.categoria,
                productos.c.anio,
                productos.c.validacion,
                productos.c.grupo_codigo,
                productos.c.investigador_codigo
            )
        ).mappings().all()

    lista_productos = []
    for r in registros:
        lista_productos.append({
            "codigo": r["codigo"],
            "nombre": r["nombre"],
            "categoria": r["categoria"],
            "anio": r["anio"],
            "validacion": r["validacion"],
            "grupo_codigo": r["grupo_codigo"] if r["grupo_codigo"] else "G-001",
            "investigador_codigo": r["investigador_codigo"] if r["investigador_codigo"] else "INV-001"
        })

    with open(ruta_salida, mode='w', encoding='utf-8') as f:
        json.dump(lista_productos, f, indent=4, ensure_ascii=False)

def ejecutar_procesador_cpp_gui():
    exportar_todo_a_json("datos_entrada.json")
    
    ejecutable = "./DS" if os.name != "nt" else "DS.exe"
    
    if not os.path.exists(ejecutable) and os.path.exists("DS.cpp"):
        os.system("g++ -o DS DS.cpp")

    if not os.path.exists(ejecutable):
        messagebox.showerror("Error C++", "No se encontró el ejecutable 'DS.exe' ni el archivo fuente 'DS.cpp'.")
        return

    try:
        # 1. Ejecutar C++ para procesar Multilista en RAM y generar 'resultados_cpp.json'
        resultado = subprocess.run(
            [ejecutable, "datos_entrada.json"], 
            capture_output=True, 
            text=True, 
            encoding="utf-8", 
            errors="replace"
        )

        if not os.path.exists("resultados_cpp.json"):
            messagebox.showerror("Error C++", "C++ no generó el archivo de intercambio 'resultados_cpp.json'.")
            return

        # 2. Cargar el JSON producido por C++ dentro de un DataFrame de Pandas
        df_resultados = pd.read_json("resultados_cpp.json")

        # 3. Renderizar ventana en Tkinter con gráfico de Matplotlib/Pandas
        top = tk.Toplevel()
        top.title("Análisis Estadístico - C++ + Pandas Interoperabilidad")
        top.geometry("680x480")
        top.configure(bg="#f8fafc")

        lbl_titulo = tk.Label(top, text="RESULTADOS PROCESADOS EN C++ (GRAFICADO CON PANDAS)", font=("Segoe UI", 11, "bold"), bg="#f8fafc", fg="#0f172a")
        lbl_titulo.pack(pady=(10, 5))

        # Crear figura de Matplotlib
        fig, ax = plt.subplots(figsize=(6, 3.5), dpi=100)
        fig.patch.set_facecolor('#f8fafc')

        # Graficar usando la integración nativa de Pandas con Matplotlib
        bars = ax.bar(df_resultados['categoria'], df_resultados['cantidad'], color='#0284c7', edgecolor='#0f172a')
        
        # Agregar etiquetas de valor sobre cada barra
        ax.bar_label(bars, padding=3, fontproperties={'weight': 'bold'})

        ax.set_title("Distribución de Productos por Categoría", fontsize=10, fontweight='bold', pad=10)
        ax.set_xlabel("Categoría", fontsize=9)
        ax.set_ylabel("Cantidad de Productos", fontsize=9)
        ax.grid(axis='y', linestyle='--', alpha=0.5)
        plt.tight_layout()

        # Incrustar en la ventana de Tkinter
        canvas = FigureCanvasTkAgg(fig, master=top)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=12, pady=12)

    except Exception as e:
        messagebox.showerror("Error", f"Fallo al ejecutar integración C++ / Pandas: {e}")
# ==========================================
# MÓDULOS DE IMPORTACIÓN Y WEB SCRAPING
# ==========================================

def descargar_desde_url_gui(ventana_padre):
    url = simpledialog.askstring("Web Scraping MinCiencias", "Ingrese la URL a procesar (GrupLAC/CvLAC):", parent=ventana_padre)
    if not url:
        return

    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        req = urllib.request.Request(url, headers=headers)
        try:
            html = urllib.request.urlopen(req).read().decode('utf-8')
        except UnicodeDecodeError:
            html = urllib.request.urlopen(req).read().decode('iso-8859-1')

        soup = BeautifulSoup(html, 'html.parser')
        filas = soup.find_all('tr')

        # 1. Extracción del Nombre Real del Grupo
        g_cod = "G-001"
        g_nom = "Grupo de Investigación"
        
        header_grupo = soup.find(
            lambda tag: tag.name in ['td', 'b', 'span', 'h2', 'h3', 'a'] and 
            "GRUPO DE INVESTIGACION" in tag.get_text().upper() and 
            len(tag.get_text().strip()) < 150
        )
        
        if header_grupo:
            g_nom = re.sub(r'\s+', ' ', header_grupo.get_text(strip=True))[:100]

        with engine.begin() as conn:
            if not buscar_grupo(g_cod):
                conn.execute(grupos.insert().values(codigo=g_cod, nombre=g_nom, area="Sistemas y Computación", estado="Activo"))
            else:
                conn.execute(update(grupos).where(grupos.c.codigo == g_cod).values(nombre=g_nom))
        
        agregar_o_buscar_grupo_ml(g_cod, g_nom, "Sistemas y Computación")

        # 2. Extracción de Integrantes Reales
        lista_investigadores = []
        mapa_investigadores = {}
        inv_contador = 1

        for fila in filas:
            texto_fila = fila.get_text(strip=True)
            if "Líder" in texto_fila or "Lider" in texto_fila:
                celdas = fila.find_all(['td', 'th'])
                if len(celdas) >= 2:
                    nombre_lider = celdas[1].get_text(strip=True)
                    if nombre_lider and len(nombre_lider) > 3:
                        cod_inv = f"INV-{inv_contador:03d}"
                        lista_investigadores.append((cod_inv, nombre_lider, f"inv{inv_contador}@unicesar.edu.co"))
                        mapa_investigadores[nombre_lider.lower()] = cod_inv
                        inv_contador += 1
                break

        en_seccion_integrantes = False
        for fila in filas:
            texto_fila = fila.get_text(strip=True)
            texto_lower = texto_fila.lower()

            if "integrantes del grupo" in texto_lower:
                en_seccion_integrantes = True
                continue

            if en_seccion_integrantes and any(sec in texto_lower for sec in ["líneas de investigación", "lineas de investigacion", "productos", "artículos", "proyectos"]):
                en_seccion_integrantes = False

            if en_seccion_integrantes:
                match_member = re.search(r'^\d+\s*\.-\s*([A-Za-zÁÉÍÓÚáéíóúñÑ\s]+)', texto_fila)
                if match_member:
                    nombre_member = match_member.group(1).strip()
                    if nombre_member and nombre_member.lower() not in mapa_investigadores and len(nombre_member) > 3:
                        cod_inv = f"INV-{inv_contador:03d}"
                        lista_investigadores.append((cod_inv, nombre_member, f"inv{inv_contador}@unicesar.edu.co"))
                        mapa_investigadores[nombre_member.lower()] = cod_inv
                        inv_contador += 1

        if not lista_investigadores:
            cod_inv = "INV-001"
            lista_investigadores.append((cod_inv, "Investigador Principal", "investigador@unicesar.edu.co"))
            mapa_investigadores["investigador principal"] = cod_inv

        with engine.begin() as conn:
            for cod, nom, cor in lista_investigadores:
                if not buscar_investigador(cod):
                    conn.execute(investigadores.insert().values(codigo=cod, nombre=nom, correo=cor, estado="Activo"))
                    conn.execute(grupo_investigador.insert().values(grupo_codigo=g_cod, investigador_codigo=cod))
                agregar_o_buscar_investigador_ml(g_cod, cod, nom, cor)

        # 3. Extracción y Asociación de Productos
        descartar = [
            "datos básicos", "datos basicos", "año y mes de formación", "departamento - ciudad",
            "líder", "lider", "página web", "clasificación", "área de conocimiento",
            "programa nacional", "instituciones", "plan estratégico", "plan estrategico",
            "plan de trabajo", "estado del arte", "objetivos",
            "integrantes del grupo", "líneas de investigación", "lineas de investigacion"
        ]

        contador_prod = 1
        registros_extraidos = []

        for fila in filas:
            celdas = fila.find_all(['td', 'th'])
            textos = [c.get_text(strip=True) for c in celdas if c.get_text(strip=True)]
            if not textos:
                continue

            texto_completo = " ".join(textos)
            if len(texto_completo) < 20:
                continue

            texto_lower = texto_completo.lower()

            if any(pilar in texto_lower for pilar in descartar) or re.match(r'^\d+\s*\.-\s*[A-Za-zÁÉÍÓÚáéíóúñÑ\s]+$', texto_completo.strip()):
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

            inv_asociado_cod = lista_investigadores[0][0]
            for nom_inv, cod_inv in mapa_investigadores.items():
                partes_nombre = [p for p in nom_inv.split() if len(p) > 3]
                if any(parte in texto_lower for parte in partes_nombre):
                    inv_asociado_cod = cod_inv
                    break

            nombre_prod = texto_completo.replace(',', ' ').replace('"', '')[:100]
            codigo_prod = f"PROD-WEB-{contador_prod:03d}"

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
                            investigador_codigo=inv_asociado_cod,
                            grupo_codigo=g_cod
                        )
                    )
                pila_productos.append(codigo_prod)
                cola_productos.append(codigo_prod)
                agregar_producto_ml(g_cod, inv_asociado_cod, codigo_prod, nombre_prod, categoria, anio, "Validado")
                contador_prod += 1

            registros_extraidos.append([codigo_prod, nombre_prod, categoria, anio, "Validado", g_cod, inv_asociado_cod])

        with open("datos_scraping.csv", mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["codigo", "nombre", "categoria", "anio", "validacion", "grupo_codigo", "investigador_codigo"])
            writer.writerows(registros_extraidos)

        messagebox.showinfo("Éxito", f"Web Scraping completado:\n• Grupo: {g_nom}\n• {len(lista_investigadores)} Investigadores vinculados.\n• {contador_prod - 1} Productos clasificados.")
        refrescar_todas_las_tablas()

    except Exception as e:
        messagebox.showerror("Error", f"Error en Web Scraping: {e}")

def importar_csv_gui(ventana_padre):
    archivo_csv = simpledialog.askstring("Importar CSV", "Nombre del archivo CSV [Por defecto: datos_scraping.csv]:", parent=ventana_padre)
    if not archivo_csv:
        archivo_csv = "datos_scraping.csv"

    if not os.path.exists(archivo_csv):
        messagebox.showerror("Error", f"El archivo '{archivo_csv}' no existe.")
        return

    try:
        with open(archivo_csv, "r", encoding="utf-8-sig", newline="") as archivo:
            lector = csv.DictReader(archivo)
            registros_nuevos = 0

            with engine.begin() as conn:
                for fila in lector:
                    grupo_codigo = fila.get("grupo_codigo", fila.get("grupo", "G-001"))
                    investigador_codigo = fila.get("investigador_codigo", fila.get("investigador", "INV-001"))
                    producto_codigo = fila["codigo"]

                    if not conn.execute(select(grupos.c.codigo).where(grupos.c.codigo == grupo_codigo)).scalar():
                        conn.execute(grupos.insert().values(codigo=grupo_codigo, nombre="Grupo Base", area="Sistemas", estado="Activo"))

                    if not conn.execute(select(investigadores.c.codigo).where(investigadores.c.codigo == investigador_codigo)).scalar():
                        conn.execute(investigadores.insert().values(codigo=investigador_codigo, nombre="Investigador Base", correo="inv@unicesar.edu.co", estado="Activo"))
                        conn.execute(grupo_investigador.insert().values(grupo_codigo=grupo_codigo, investigador_codigo=investigador_codigo))

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
                        agregar_producto_ml(grupo_codigo, investigador_codigo, producto_codigo, fila["nombre"], fila["categoria"], int(fila["anio"]), fila["validacion"])
                        registros_nuevos += 1

        messagebox.showinfo("Éxito", f"Se importaron {registros_nuevos} productos desde '{archivo_csv}'.")
        refrescar_todas_las_tablas()

    except Exception as e:
        messagebox.showerror("Error", f"Error al importar CSV: {e}")

# ==========================================
# FUNCIONES DE REFRESCO Y BÚSQUEDA EN TABLAS
# ==========================================

def refrescar_tabla_grupos(tree):
    for item in tree.get_children():
        tree.delete(item)
    with engine.connect() as conn:
        registros = conn.execute(select(grupos)).mappings().all()
    for i, g in enumerate(registros):
        tag = "evenrow" if i % 2 == 0 else "oddrow"
        tree.insert("", "end", values=(g["codigo"], g["nombre"], g["area"], g["estado"]), tags=(tag,))

def refrescar_tabla_investigadores(tree):
    for item in tree.get_children():
        tree.delete(item)
    consulta = (
        select(
            investigadores.c.codigo,
            investigadores.c.nombre,
            investigadores.c.correo,
            investigadores.c.estado,
            func.group_concat(grupo_investigador.c.grupo_codigo, ", ").label("grupos")
        )
        .select_from(
            investigadores.outerjoin(grupo_investigador, investigadores.c.codigo == grupo_investigador.c.investigador_codigo)
        )
        .group_by(investigadores.c.codigo)
    )
    with engine.connect() as conn:
        registros = conn.execute(consulta).mappings().all()
    for i, inv in enumerate(registros):
        tag = "evenrow" if i % 2 == 0 else "oddrow"
        tree.insert("", "end", values=(inv["codigo"], inv["nombre"], inv["correo"], inv["grupos"] or "Sin grupo", inv["estado"]), tags=(tag,))

def refrescar_tabla_productos(tree, filtro=""):
    for item in tree.get_children():
        tree.delete(item)
    
    with engine.connect() as conn:
        stmt = select(productos)
        if filtro.strip():
            f = f"%{filtro.strip()}%"
            stmt = stmt.where(
                (productos.c.codigo.like(f)) | 
                (productos.c.nombre.like(f)) | 
                (productos.c.categoria.like(f))
            )
        registros = conn.execute(stmt).mappings().all()

    for i, p in enumerate(registros):
        tag = "evenrow" if i % 2 == 0 else "oddrow"
        tree.insert("", "end", values=(p["codigo"], p["nombre"], p["categoria"], p["anio"], p["validacion"], p["investigador_codigo"], p["estado"]), tags=(tag,))

def refrescar_arbol_multilista(tree):
    for item in tree.get_children():
        tree.delete(item)
    
    for g in multilista_grupos:
        node_g = tree.insert("", "end", text=f" 📂 Grupo: {g['codigo']} - {g['nombre']}", values=(g['codigo'], "Grupo", g['area']), open=True, tags=("grupo",))
        
        for inv in g["investigadores"]:
            node_inv = tree.insert(node_g, "end", text=f"   👤 Investigador: {inv['codigo']} - {inv['nombre']}", values=(inv['codigo'], "Investigador", inv['correo']), open=True, tags=("investigador",))
            
            for prod in inv["productos"]:
                tree.insert(node_inv, "end", text=f"      📄 Producto: {prod['codigo']} - {prod['nombre']}", values=(prod['codigo'], f"Cat: {prod['categoria']} ({prod['anio']})", prod['validacion']), tags=("producto",))

def refrescar_todas_las_tablas():
    refrescar_tabla_grupos(tree_grupos)
    refrescar_tabla_investigadores(tree_inv)
    refrescar_tabla_productos(tree_prod, ent_buscar.get() if 'ent_buscar' in globals() else "")
    if 'tree_multi' in globals():
        refrescar_arbol_multilista(tree_multi)

# ==========================================
# OPERACIONES DE PILA (LIFO) Y COLA (FIFO)
# ==========================================

def deshacer_ultimo_pila_gui():
    if not pila_productos:
        messagebox.showinfo("Pila Vacía", "La Cima de la Pila (LIFO) está vacía.")
        return

    ultimo_codigo = pila_productos.pop() # Operación POP en Cima de Pila
    
    if messagebox.askyesno("Pila (LIFO) - Deshacer Registro", f"¿Desea eliminar de la BD el último producto ingresado a la Cima de la Pila: '{ultimo_codigo}'?"):
        with engine.begin() as conn:
            conn.execute(delete(productos).where(productos.c.codigo == ultimo_codigo))
        if ultimo_codigo in cola_productos:
            cola_productos.remove(ultimo_codigo)
        cargar_estructuras_guardadas()
        refrescar_todas_las_tablas()
        messagebox.showinfo("Éxito Pila", f"Producto '{ultimo_codigo}' deshecho correctamente desde la Cima de la Pila.")
    else:
        pila_productos.append(ultimo_codigo) # Recomponer si cancela

def ver_estado_pila_cola_gui(root):
    top = tk.Toplevel(root)
    top.title("Estado de Memoria RAM: Pila (LIFO) & Cola (FIFO)")
    top.geometry("480x320")
    top.configure(bg="#0f172a")

    lbl_t = tk.Label(top, text="ESTRUCTURAS DE MEMORIA LINEALES", font=("Segoe UI", 11, "bold"), bg="#0f172a", fg="#38bdf8")
    lbl_t.pack(pady=10)

    txt = tk.Text(top, font=("Consolas", 9), bg="#1e293b", fg="#f8fafc", bd=0, padx=10, pady=10)
    txt.pack(fill="both", expand=True, padx=10, pady=10)

    pila_str = " -> ".join(reversed(pila_productos)) if pila_productos else "[VACÍA]"
    cola_str = " -> ".join(cola_productos) if cola_productos else "[VACÍA]"

    info = f"--- PILA (LIFO - Cima a Fondo) ---\nTotal elementos: {len(pila_productos)}\n[{pila_str}]\n\n"
    info += f"--- COLA (FIFO - Frente a Final) ---\nTotal elementos: {len(cola_productos)}\n[{cola_str}]"

    txt.insert(tk.END, info)
    txt.config(state="disabled")

# ==========================================
# FORMULARIOS Y ACCIONES DE LA GUI
# ==========================================

def abrir_formulario_grupo(root):
    top = tk.Toplevel(root)
    top.title("Crear Grupo")
    top.geometry("320x240")
    top.configure(bg="#f8fafc")
    top.grab_set()

    tk.Label(top, text="Código del Grupo:", bg="#f8fafc", fg="#0f172a", font=("Segoe UI", 9, "bold")).pack(pady=(10, 2))
    ent_cod = tk.Entry(top, font=("Segoe UI", 9), relief="solid", bd=1)
    ent_cod.pack(ipadx=4, ipady=2)

    tk.Label(top, text="Nombre:", bg="#f8fafc", fg="#0f172a", font=("Segoe UI", 9, "bold")).pack(pady=(6, 2))
    ent_nom = tk.Entry(top, font=("Segoe UI", 9), relief="solid", bd=1)
    ent_nom.pack(ipadx=4, ipady=2)

    tk.Label(top, text="Área:", bg="#f8fafc", fg="#0f172a", font=("Segoe UI", 9, "bold")).pack(pady=(6, 2))
    ent_area = tk.Entry(top, font=("Segoe UI", 9), relief="solid", bd=1)
    ent_area.pack(ipadx=4, ipady=2)

    def guardar():
        c, n, a = ent_cod.get().strip(), ent_nom.get().strip(), ent_area.get().strip()
        if not c or not n or not a:
            messagebox.showwarning("Atención", "Todos los campos son obligatorios.", parent=top)
            return
        if buscar_grupo(c):
            messagebox.showerror("Error", "Ese grupo ya existe.", parent=top)
            return

        with engine.begin() as conn:
            conn.execute(grupos.insert().values(codigo=c, nombre=n, area=a, estado="Activo"))
        agregar_o_buscar_grupo_ml(c, n, a)
        messagebox.showinfo("Éxito", "Grupo creado correctamente.", parent=top)
        top.destroy()
        refrescar_todas_las_tablas()

    tk.Button(top, text="Guardar Grupo", command=guardar, bg="#16a34a", fg="white", font=("Segoe UI", 9, "bold"), activebackground="#15803d", activeforeground="white", relief="flat", cursor="hand2").pack(pady=15)

def abrir_formulario_investigador(root):
    top = tk.Toplevel(root)
    top.title("Crear Investigador")
    top.geometry("320x290")
    top.configure(bg="#f8fafc")
    top.grab_set()

    tk.Label(top, text="Código:", bg="#f8fafc", fg="#0f172a", font=("Segoe UI", 9, "bold")).pack(pady=(8, 2))
    ent_cod = tk.Entry(top, font=("Segoe UI", 9), relief="solid", bd=1)
    ent_cod.pack(ipadx=4, ipady=2)

    tk.Label(top, text="Nombre:", bg="#f8fafc", fg="#0f172a", font=("Segoe UI", 9, "bold")).pack(pady=(4, 2))
    ent_nom = tk.Entry(top, font=("Segoe UI", 9), relief="solid", bd=1)
    ent_nom.pack(ipadx=4, ipady=2)

    tk.Label(top, text="Correo:", bg="#f8fafc", fg="#0f172a", font=("Segoe UI", 9, "bold")).pack(pady=(4, 2))
    ent_correo = tk.Entry(top, font=("Segoe UI", 9), relief="solid", bd=1)
    ent_correo.pack(ipadx=4, ipady=2)

    tk.Label(top, text="Código de Grupo Asociado:", bg="#f8fafc", fg="#0f172a", font=("Segoe UI", 9, "bold")).pack(pady=(4, 2))
    ent_grupo = tk.Entry(top, font=("Segoe UI", 9), relief="solid", bd=1)
    ent_grupo.pack(ipadx=4, ipady=2)

    def guardar():
        c, n, cor, g_cod = ent_cod.get().strip(), ent_nom.get().strip(), ent_correo.get().strip(), ent_grupo.get().strip()
        if not c or not n or not cor or not g_cod:
            messagebox.showwarning("Atención", "Todos los campos son obligatorios.", parent=top)
            return
        if buscar_investigador(c):
            messagebox.showerror("Error", "El investigador ya existe.", parent=top)
            return
        if not buscar_grupo(g_cod):
            messagebox.showerror("Error", "El grupo especificado no existe.", parent=top)
            return

        with engine.begin() as conn:
            conn.execute(investigadores.insert().values(codigo=c, nombre=n, correo=cor, estado="Activo"))
            conn.execute(grupo_investigador.insert().values(grupo_codigo=g_cod, investigador_codigo=c))
        agregar_o_buscar_investigador_ml(g_cod, c, n, cor)
        messagebox.showinfo("Éxito", "Investigador registrado correctamente.", parent=top)
        top.destroy()
        refrescar_todas_las_tablas()

    tk.Button(top, text="Guardar Investigador", command=guardar, bg="#16a34a", fg="white", font=("Segoe UI", 9, "bold"), activebackground="#15803d", activeforeground="white", relief="flat", cursor="hand2").pack(pady=12)

def abrir_formulario_producto(root):
    top = tk.Toplevel(root)
    top.title("Crear Producto")
    top.geometry("340x380")
    top.configure(bg="#f8fafc")
    top.grab_set()

    tk.Label(top, text="Código:", bg="#f8fafc", fg="#0f172a", font=("Segoe UI", 8, "bold")).pack(pady=(6, 1))
    ent_cod = tk.Entry(top, font=("Segoe UI", 9), relief="solid", bd=1)
    ent_cod.pack(ipadx=4)

    tk.Label(top, text="Nombre:", bg="#f8fafc", fg="#0f172a", font=("Segoe UI", 8, "bold")).pack(pady=(4, 1))
    ent_nom = tk.Entry(top, font=("Segoe UI", 9), relief="solid", bd=1)
    ent_nom.pack(ipadx=4)

    tk.Label(top, text="Categoría:", bg="#f8fafc", fg="#0f172a", font=("Segoe UI", 8, "bold")).pack(pady=(4, 1))
    ent_cat = tk.Entry(top, font=("Segoe UI", 9), relief="solid", bd=1)
    ent_cat.pack(ipadx=4)

    tk.Label(top, text="Año:", bg="#f8fafc", fg="#0f172a", font=("Segoe UI", 8, "bold")).pack(pady=(4, 1))
    ent_anio = tk.Entry(top, font=("Segoe UI", 9), relief="solid", bd=1)
    ent_anio.pack(ipadx=4)

    tk.Label(top, text="Validación (Validado/No validado):", bg="#f8fafc", fg="#0f172a", font=("Segoe UI", 8, "bold")).pack(pady=(4, 1))
    ent_val = tk.Entry(top, font=("Segoe UI", 9), relief="solid", bd=1)
    ent_val.pack(ipadx=4)

    tk.Label(top, text="Código Investigador:", bg="#f8fafc", fg="#0f172a", font=("Segoe UI", 8, "bold")).pack(pady=(4, 1))
    ent_inv = tk.Entry(top, font=("Segoe UI", 9), relief="solid", bd=1)
    ent_inv.pack(ipadx=4)

    def guardar():
        c, n, cat, val, inv_cod = ent_cod.get().strip(), ent_nom.get().strip(), ent_cat.get().strip(), ent_val.get().strip(), ent_inv.get().strip()
        try:
            a = int(ent_anio.get().strip())
        except ValueError:
            messagebox.showerror("Error", "El año debe ser numérico.", parent=top)
            return

        if not c or not n or not cat or not val or not inv_cod:
            messagebox.showwarning("Atención", "Todos los campos son requeridos.", parent=top)
            return

        if buscar_producto(c):
            messagebox.showerror("Error", "Ese producto ya existe.", parent=top)
            return

        if not buscar_investigador(inv_cod):
            messagebox.showerror("Error", "El investigador no existe.", parent=top)
            return

        with engine.connect() as conn:
            g_cod = conn.execute(select(grupo_investigador.c.grupo_codigo).where(grupo_investigador.c.investigador_codigo == inv_cod)).scalars().first()

        g_final = g_cod if g_cod else "G-001"

        with engine.begin() as conn:
            conn.execute(
                productos.insert().values(
                    codigo=c, nombre=n, categoria=cat, anio=a, validacion=val, estado="Activo", investigador_codigo=inv_cod, grupo_codigo=g_final
                )
            )

        pila_productos.append(c)
        cola_productos.append(c)
        agregar_producto_ml(g_final, inv_cod, c, n, cat, a, val)

        messagebox.showinfo("Éxito", "Producto registrado en BD, Pila, Cola y Multilista.", parent=top)
        top.destroy()
        refrescar_todas_las_tablas()

    tk.Button(top, text="Guardar Producto", command=guardar, bg="#16a34a", fg="white", font=("Segoe UI", 9, "bold"), activebackground="#15803d", activeforeground="white", relief="flat", cursor="hand2").pack(pady=12)

def eliminar_producto_gui():
    selected = tree_prod.selection()
    if not selected:
        messagebox.showwarning("Selección", "Seleccione un producto de la tabla.")
        return
    codigo = tree_prod.item(selected[0])['values'][0]

    if messagebox.askyesno("Confirmar", f"¿Eliminar el producto '{codigo}'?"):
        with engine.begin() as conn:
            conn.execute(delete(productos).where(productos.c.codigo == codigo))
        if codigo in pila_productos:
            pila_productos.remove(codigo)
        if codigo in cola_productos:
            cola_productos.remove(codigo)
        cargar_estructuras_guardadas()
        refrescar_todas_las_tablas()

def desactivar_producto_gui():
    selected = tree_prod.selection()
    if not selected:
        messagebox.showwarning("Selección", "Seleccione un producto de la tabla.")
        return
    codigo = tree_prod.item(selected[0])['values'][0]

    with engine.begin() as conn:
        conn.execute(update(productos).where(productos.c.codigo == codigo).values(estado="Inactivo"))
    refrescar_todas_las_tablas()

def activar_producto_gui():
    selected = tree_prod.selection()
    if not selected:
        messagebox.showwarning("Selección", "Seleccione un producto de la tabla.")
        return
    codigo = tree_prod.item(selected[0])['values'][0]

    with engine.begin() as conn:
        conn.execute(update(productos).where(productos.c.codigo == codigo).values(estado="Activo"))
    refrescar_todas_las_tablas()

# ==========================================
# ESTILOS Y VENTANA PRINCIPAL (Tkinter)
# ==========================================

def aplicar_estilos_gui(root):
    style = ttk.Style(root)
    style.theme_use("clam")

    color_fondo = "#f8fafc"
    color_header = "#0f172a"
    color_texto = "#334155"

    root.configure(bg=color_fondo)

    style.configure("TNotebook", background=color_fondo, borderwidth=0)
    style.configure("TNotebook.Tab", background="#e2e8f0", foreground=color_texto, font=("Segoe UI", 9, "bold"), padding=[12, 6])
    style.map("TNotebook.Tab", background=[("selected", color_header)], foreground=[("selected", "#ffffff")])

    style.configure("TFrame", background=color_fondo)
    style.configure("TLabel", background=color_fondo, foreground=color_texto, font=("Segoe UI", 9))

    style.configure("Treeview", background="#ffffff", foreground=color_texto, fieldbackground="#ffffff", rowheight=26, font=("Segoe UI", 9), borderwidth=1, relief="solid")
    style.configure("Treeview.Heading", background=color_header, foreground="#ffffff", font=("Segoe UI", 9, "bold"), relief="flat")
    style.map("Treeview.Heading", background=[("active", "#1e293b")])

    style.configure("TButton", font=("Segoe UI", 9, "bold"), padding=5, background="#cbd5e1", foreground=color_header)
    style.map("TButton", background=[("active", "#94a3b8")])

    style.configure("Success.TButton", background="#16a34a", foreground="#ffffff")
    style.map("Success.TButton", background=[("active", "#15803d")])

    style.configure("Primary.TButton", background="#0284c7", foreground="#ffffff")
    style.map("Primary.TButton", background=[("active", "#0369a1")])

    style.configure("Danger.TButton", background="#dc2626", foreground="#ffffff")
    style.map("Danger.TButton", background=[("active", "#b91c1c")])

def iniciar_interfaz_grafica():
    global tree_grupos, tree_inv, tree_prod, tree_multi, ent_buscar

    crear_tablas()
    with engine.connect() as conn:
        t_g = conn.execute(select(func.count()).select_from(grupos)).scalar()
        t_p = conn.execute(select(func.count()).select_from(productos)).scalar()

    if t_g > 0 or t_p > 0:
        resp = messagebox.askyesno("Persistencia", "Se encontraron datos de sesiones anteriores.\n\n¿Desea mantener los datos guardados?\n(Seleccione 'No' para iniciar desde cero)")
        if not resp:
            limpiar_base_datos()
        else:
            cargar_estructuras_guardadas()

    root = tk.Tk()
    root.title("PEA-i - Sistema de Gestión de Investigación (UPC)")
    root.geometry("960x640")

    aplicar_estilos_gui(root)

    banner = tk.Frame(root, bg="#0f172a", height=50)
    banner.pack(fill="x", side="top")
    lbl_banner = tk.Label(banner, text="PEA-i | GESTIÓN DE INVESTIGACIÓN", font=("Segoe UI", 12, "bold"), bg="#0f172a", fg="#38bdf8")
    lbl_banner.pack(side="left", padx=15, pady=10)

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=12, pady=12)

    # --- Pestaña Productos ---
    frame_p = ttk.Frame(notebook)
    notebook.add(frame_p, text="Productos")

    # Barra de búsqueda y filtrado
    frame_search = ttk.Frame(frame_p)
    frame_search.pack(fill="x", padx=5, pady=(5, 2))

    tk.Label(frame_search, text="🔍 Buscar Producto:", font=("Segoe UI", 9, "bold"), bg="#f8fafc", fg="#0f172a").pack(side="left", padx=(0, 5))
    ent_buscar = tk.Entry(frame_search, font=("Segoe UI", 9), relief="solid", bd=1)
    ent_buscar.pack(side="left", fill="x", expand=True, padx=5, ipady=2)
    ent_buscar.bind("<KeyRelease>", lambda e: refrescar_tabla_productos(tree_prod, ent_buscar.get()))

    cols_p = ("Código", "Nombre", "Categoría", "Año", "Validación", "Investigador", "Estado")
    tree_prod = ttk.Treeview(frame_p, columns=cols_p, show="headings")
    tree_prod.tag_configure("evenrow", background="#ffffff")
    tree_prod.tag_configure("oddrow", background="#f1f5f9")

    for col in cols_p:
        tree_prod.heading(col, text=col)
        tree_prod.column(col, width=115)
    tree_prod.pack(fill="both", expand=True, padx=5, pady=5)

    btn_bar_p = ttk.Frame(frame_p)
    btn_bar_p.pack(fill="x", pady=6)
    ttk.Button(btn_bar_p, text="Crear Producto", style="Success.TButton", command=lambda: abrir_formulario_producto(root)).pack(side="left", padx=3)
    ttk.Button(btn_bar_p, text="Activar", style="Success.TButton", command=activar_producto_gui).pack(side="left", padx=3)
    ttk.Button(btn_bar_p, text="Desactivar", style="TButton", command=desactivar_producto_gui).pack(side="left", padx=3)
    ttk.Button(btn_bar_p, text="Eliminar Producto", style="Danger.TButton", command=eliminar_producto_gui).pack(side="left", padx=3)
    ttk.Button(btn_bar_p, text="Web Scraping (URL)", style="Primary.TButton", command=lambda: descargar_desde_url_gui(root)).pack(side="left", padx=3)
    ttk.Button(btn_bar_p, text="Importar CSV", style="Primary.TButton", command=lambda: importar_csv_gui(root)).pack(side="left", padx=3)
    
    # Botones de demostración Pila/Cola
    ttk.Button(btn_bar_p, text="Deshacer (Pop Pila)", style="Danger.TButton", command=deshacer_ultimo_pila_gui).pack(side="right", padx=3)
    ttk.Button(btn_bar_p, text="Ver Pila/Cola", style="Primary.TButton", command=lambda: ver_estado_pila_cola_gui(root)).pack(side="right", padx=3)

    # --- Pestaña Grupos e Investigadores ---
    frame_gi = ttk.Frame(notebook)
    notebook.add(frame_gi, text="Grupos e Investigadores")

    lbl_g = tk.Label(frame_gi, text="GRUPOS DE INVESTIGACIÓN", font=("Segoe UI", 10, "bold"), bg="#f8fafc", fg="#0f172a")
    lbl_g.pack(anchor="w", padx=5, pady=(5, 2))
    cols_g = ("Código", "Nombre", "Área", "Estado")
    tree_grupos = ttk.Treeview(frame_gi, columns=cols_g, show="headings", height=5)
    tree_grupos.tag_configure("evenrow", background="#ffffff")
    tree_grupos.tag_configure("oddrow", background="#f1f5f9")
    for col in cols_g:
        tree_grupos.heading(col, text=col)
    tree_grupos.pack(fill="both", expand=True, padx=5, pady=2)

    lbl_i = tk.Label(frame_gi, text="INVESTIGADORES", font=("Segoe UI", 10, "bold"), bg="#f8fafc", fg="#0f172a")
    lbl_i.pack(anchor="w", padx=5, pady=(8, 2))
    cols_i = ("Código", "Nombre", "Correo", "Grupos", "Estado")
    tree_inv = ttk.Treeview(frame_gi, columns=cols_i, show="headings", height=5)
    tree_inv.tag_configure("evenrow", background="#ffffff")
    tree_inv.tag_configure("oddrow", background="#f1f5f9")
    for col in cols_i:
        tree_inv.heading(col, text=col)
    tree_inv.pack(fill="both", expand=True, padx=5, pady=2)

    btn_bar_gi = ttk.Frame(frame_gi)
    btn_bar_gi.pack(fill="x", pady=6)
    ttk.Button(btn_bar_gi, text="Crear Grupo", style="Success.TButton", command=lambda: abrir_formulario_grupo(root)).pack(side="left", padx=4)
    ttk.Button(btn_bar_gi, text="Crear Investigador", style="Success.TButton", command=lambda: abrir_formulario_investigador(root)).pack(side="left", padx=4)

    # --- Pestaña Vista Jerárquica (Multilista) ---
    frame_m = ttk.Frame(notebook)
    notebook.add(frame_m, text="Vista Multilista (Jerárquica)")

    lbl_m = tk.Label(frame_m, text="ESTRUCTURA JERÁRQUICA: GRUPO ➔ INVESTIGADOR ➔ PRODUCTO", font=("Segoe UI", 10, "bold"), bg="#f8fafc", fg="#0f172a")
    lbl_m.pack(anchor="w", padx=5, pady=(8, 4))

    cols_m = ("Código / ID", "Tipo / Detalle", "Información Adicional")
    tree_multi = ttk.Treeview(frame_m, columns=cols_m, show="tree headings")
    tree_multi.heading("#0", text="Jerarquía Multilista (Haz clic en ▶ para desplegar)")
    tree_multi.heading("Código / ID", text="Código")
    tree_multi.heading("Tipo / Detalle", text="Tipo")
    tree_multi.heading("Información Adicional", text="Info")

    tree_multi.column("#0", width=380)
    tree_multi.column("Código / ID", width=120)
    tree_multi.column("Tipo / Detalle", width=140)
    tree_multi.column("Información Adicional", width=180)

    tree_multi.tag_configure("grupo", font=("Segoe UI", 9, "bold"), foreground="#0f172a")
    tree_multi.tag_configure("investigador", font=("Segoe UI", 9, "bold"), foreground="#0284c7")
    tree_multi.tag_configure("producto", font=("Segoe UI", 9), foreground="#334155")

    tree_multi.pack(fill="both", expand=True, padx=5, pady=5)

    # --- Pestaña C++ ---
    frame_dash = ttk.Frame(notebook)
    notebook.add(frame_dash, text="Reporte C++")

    lbl_d = tk.Label(frame_dash, text="PROCESAMIENTO DE ESTADÍSTICAS EN C++", font=("Segoe UI", 11, "bold"), bg="#f8fafc", fg="#0f172a")
    lbl_d.pack(pady=(25, 5))
    lbl_sub = tk.Label(frame_dash, text="Genera el archivo de intercambio JSON y ejecuta el motor en C++.", font=("Segoe UI", 9), bg="#f8fafc", fg="#64748b")
    lbl_sub.pack(pady=(0, 15))
    ttk.Button(frame_dash, text="Ejecutar Análisis y Mostrar Reporte (C++)", style="Primary.TButton", command=ejecutar_procesador_cpp_gui).pack(pady=10)

    refrescar_todas_las_tablas()

    root.mainloop()

if __name__ == "__main__":
    iniciar_interfaz_grafica()