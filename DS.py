import csv
import os
import re
from collections import deque
import urllib.request
from bs4 import BeautifulSoup
import matplotlib.pyplot as plt
from sqlalchemy import (create_engine, MetaData, Table, Column, String, Integer, ForeignKey, select, update, delete, func)

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

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
            return grupo
    nuevo_grupo = crear_nodo_grupo(codigo, nombre, area)
    multilista_grupos.append(nuevo_grupo)
    return nuevo_grupo

def agregar_o_buscar_investigador_ml(grupo_codigo, inv_codigo, nombre="Sin Nombre", correo="correo@unicesar.edu.co"):
    grupo = agregar_o_buscar_grupo_ml(grupo_codigo)
    for inv in grupo["investigadores"]:
        if inv["codigo"] == inv_codigo:
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
        registros = conn.execute(
            select(
                productos.c.codigo,
                productos.c.nombre,
                productos.c.categoria,
                productos.c.anio,
                productos.c.validacion,
                productos.c.investigador_codigo,
                productos.c.grupo_codigo
            )
        ).mappings().all()

    for p in registros:
        pila_productos.append(p["codigo"])
        cola_productos.append(p["codigo"])
        g_cod = p["grupo_codigo"] if p["grupo_codigo"] else "G-BASE"
        inv_cod = p["investigador_codigo"] if p["investigador_codigo"] else "INV-BASE"

        agregar_producto_ml(
            grupo_codigo=g_cod,
            inv_codigo=inv_cod,
            prod_codigo=p["codigo"],
            nombre=p["nombre"],
            categoria=p["categoria"],
            anio=p["anio"],
            validacion=p["validacion"]
        )

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
        contador = 1
        registros_extraidos = []

        with engine.begin() as conn:
            if not buscar_grupo("G-001"):
                conn.execute(grupos.insert().values(codigo="G-001", nombre="Grupo Scraping MinCiencias", area="Investigación", estado="Activo"))
            if not buscar_investigador("INV-001"):
                conn.execute(investigadores.insert().values(codigo="INV-001", nombre="Investigador Principal", correo="investigador@unicesar.edu.co", estado="Activo"))

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
                agregar_producto_ml("G-001", "INV-001", codigo_prod, nombre_prod, categoria, anio, "Validado")
                contador += 1

            registros_extraidos.append([codigo_prod, nombre_prod, categoria, anio, "Validado", "G-001"])

        with open("datos_scraping.csv", mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["codigo", "nombre", "categoria", "anio", "validacion", "grupo_codigo"])
            writer.writerows(registros_extraidos)

        messagebox.showinfo("Éxito", f"Se importaron {contador - 1} productos directamente a la BD, Pila, Cola y Multilista.")
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
                    investigador_codigo = fila.get("investigador", "INV-001")
                    producto_codigo = fila["codigo"]

                    if not conn.execute(select(grupos.c.codigo).where(grupos.c.codigo == grupo_codigo)).scalar():
                        conn.execute(grupos.insert().values(codigo=grupo_codigo, nombre="Grupo Base", area="Sistemas", estado="Activo"))

                    if not conn.execute(select(investigadores.c.codigo).where(investigadores.c.codigo == investigador_codigo)).scalar():
                        conn.execute(investigadores.insert().values(codigo=investigador_codigo, nombre="Investigador Base", correo="inv@unicesar.edu.co", estado="Activo"))

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

def estadisticas():
    with engine.connect() as conn:
        categorias = conn.execute(
            select(productos.c.categoria, func.count().label("cantidad")).group_by(productos.c.categoria)
        ).mappings().all()

        anios = conn.execute(
            select(productos.c.anio, func.count().label("cantidad")).group_by(productos.c.anio)
        ).mappings().all()

    if not categorias and not anios:
        messagebox.showwarning("Sin Datos", "No hay datos suficientes para generar el Dashboard.")
        return

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))
    fig.canvas.manager.set_window_title('PEA-i - Dashboard Estadístico')
    fig.suptitle('DASHBOARD ESTADÍSTICO DE INVESTIGACIÓN (UPC)', fontsize=13, fontweight='bold')

    cats = [c['categoria'] for c in categorias]
    c_cants = [c['cantidad'] for c in categorias]
    ax1.bar(cats, c_cants, color='#0056b3', edgecolor='black')
    ax1.set_title('Productos por Categoría')
    ax1.set_xlabel('Categorías')
    ax1.set_ylabel('Cantidad')
    ax1.tick_params(axis='x', rotation=25)
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

def refrescar_tabla_grupos(tree):
    for item in tree.get_children():
        tree.delete(item)
    with engine.connect() as conn:
        registros = conn.execute(select(grupos)).mappings().all()
    for g in registros:
        tree.insert("", "end", values=(g["codigo"], g["nombre"], g["area"], g["estado"]))

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
    for inv in registros:
        tree.insert("", "end", values=(inv["codigo"], inv["nombre"], inv["correo"], inv["grupos"] or "Sin grupo", inv["estado"]))

def refrescar_tabla_productos(tree):
    for item in tree.get_children():
        tree.delete(item)
    with engine.connect() as conn:
        registros = conn.execute(select(productos)).mappings().all()
    for p in registros:
        tree.insert("", "end", values=(p["codigo"], p["nombre"], p["categoria"], p["anio"], p["validacion"], p["investigador_codigo"], p["estado"]))

def refrescar_tree_multilista(tree):
    for item in tree.get_children():
        tree.delete(item)
    for g in multilista_grupos:
        g_node = tree.insert("", "end", text=f"Grupo: {g['codigo']} - {g['nombre']} ({g['area']})", open=True)
        for inv in g["investigadores"]:
            inv_node = tree.insert(g_node, "end", text=f"Investigador: {inv['codigo']} - {inv['nombre']}", open=True)
            for prod in inv["productos"]:
                tree.insert(inv_node, "end", text=f"Producto: {prod['codigo']} | {prod['nombre']} | {prod['categoria']} | {prod['anio']}")

def refrescar_estructuras_memoria(txt_pila, txt_cola):
    txt_pila.config(state="normal")
    txt_cola.config(state="normal")
    txt_pila.delete("1.0", tk.END)
    txt_cola.delete("1.0", tk.END)

    txt_pila.insert(tk.END, " -> ".join(reversed(pila_productos)) if pila_productos else "Pila vacía")
    txt_cola.insert(tk.END, " -> ".join(cola_productos) if cola_productos else "Cola vacía")

    txt_pila.config(state="disabled")
    txt_cola.config(state="disabled")

def refrescar_todas_las_tablas():
    refrescar_tabla_grupos(tree_grupos)
    refrescar_tabla_investigadores(tree_inv)
    refrescar_tabla_productos(tree_prod)
    refrescar_tree_multilista(tree_ml)
    refrescar_estructuras_memoria(txt_pila_gui, txt_cola_gui)

def abrir_formulario_grupo(root):
    top = tk.Toplevel(root)
    top.title("Crear Grupo")
    top.geometry("300x200")
    top.grab_set()

    tk.Label(top, text="Código:").pack(pady=2)
    ent_cod = tk.Entry(top)
    ent_cod.pack()

    tk.Label(top, text="Nombre:").pack(pady=2)
    ent_nom = tk.Entry(top)
    ent_nom.pack()

    tk.Label(top, text="Área:").pack(pady=2)
    ent_area = tk.Entry(top)
    ent_area.pack()

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

    tk.Button(top, text="Guardar", command=guardar, bg="#28a745", fg="white").pack(pady=10)

def abrir_formulario_investigador(root):
    top = tk.Toplevel(root)
    top.title("Crear Investigador")
    top.geometry("300x250")
    top.grab_set()

    tk.Label(top, text="Código:").pack(pady=2)
    ent_cod = tk.Entry(top)
    ent_cod.pack()

    tk.Label(top, text="Nombre:").pack(pady=2)
    ent_nom = tk.Entry(top)
    ent_nom.pack()

    tk.Label(top, text="Correo:").pack(pady=2)
    ent_correo = tk.Entry(top)
    ent_correo.pack()

    tk.Label(top, text="Código de Grupo Asociado:").pack(pady=2)
    ent_grupo = tk.Entry(top)
    ent_grupo.pack()

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

    tk.Button(top, text="Guardar", command=guardar, bg="#28a745", fg="white").pack(pady=10)

def abrir_formulario_producto(root):
    top = tk.Toplevel(root)
    top.title("Crear Producto")
    top.geometry("320x330")
    top.grab_set()

    tk.Label(top, text="Código:").pack(pady=1)
    ent_cod = tk.Entry(top)
    ent_cod.pack()

    tk.Label(top, text="Nombre:").pack(pady=1)
    ent_nom = tk.Entry(top)
    ent_nom.pack()

    tk.Label(top, text="Categoría:").pack(pady=1)
    ent_cat = tk.Entry(top)
    ent_cat.pack()

    tk.Label(top, text="Año:").pack(pady=1)
    ent_anio = tk.Entry(top)
    ent_anio.pack()

    tk.Label(top, text="Validación (Validado/No validado):").pack(pady=1)
    ent_val = tk.Entry(top)
    ent_val.pack()

    tk.Label(top, text="Código Investigador:").pack(pady=1)
    ent_inv = tk.Entry(top)
    ent_inv.pack()

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

        g_final = g_cod if g_cod else "G-BASE"

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

    tk.Button(top, text="Guardar", command=guardar, bg="#28a745", fg="white").pack(pady=10)

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

def iniciar_interfaz_grafica():
    global tree_grupos, tree_inv, tree_prod, tree_ml, txt_pila_gui, txt_cola_gui

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
    root.geometry("850x600")

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=10, pady=10)

    frame_p = ttk.Frame(notebook)
    notebook.add(frame_p, text="Productos")

    cols_p = ("Código", "Nombre", "Categoría", "Año", "Validación", "Investigador", "Estado")
    tree_prod = ttk.Treeview(frame_p, columns=cols_p, show="headings")
    for col in cols_p:
        tree_prod.heading(col, text=col)
        tree_prod.column(col, width=110)
    tree_prod.pack(fill="both", expand=True, padx=5, pady=5)

    btn_bar_p = ttk.Frame(frame_p)
    btn_bar_p.pack(fill="x", pady=5)
    ttk.Button(btn_bar_p, text="Crear Producto", command=lambda: abrir_formulario_producto(root)).pack(side="left", padx=5)
    ttk.Button(btn_bar_p, text="Eliminar Producto", command=eliminar_producto_gui).pack(side="left", padx=5)
    ttk.Button(btn_bar_p, text="Desactivar", command=desactivar_producto_gui).pack(side="left", padx=5)
    ttk.Button(btn_bar_p, text="Web Scraping (URL)", command=lambda: descargar_desde_url_gui(root)).pack(side="left", padx=5)
    ttk.Button(btn_bar_p, text="Importar CSV", command=lambda: importar_csv_gui(root)).pack(side="left", padx=5)

    frame_gi = ttk.Frame(notebook)
    notebook.add(frame_gi, text="Grupos e Investigadores")

    lbl_g = ttk.Label(frame_gi, text="Grupos de Investigación", font=("Arial", 10, "bold"))
    lbl_g.pack(anchor="w", padx=5, pady=2)
    cols_g = ("Código", "Nombre", "Área", "Estado")
    tree_grupos = ttk.Treeview(frame_gi, columns=cols_g, show="headings", height=5)
    for col in cols_g:
        tree_grupos.heading(col, text=col)
    tree_grupos.pack(fill="both", expand=True, padx=5, pady=2)

    lbl_i = ttk.Label(frame_gi, text="Investigadores", font=("Arial", 10, "bold"))
    lbl_i.pack(anchor="w", padx=5, pady=2)
    cols_i = ("Código", "Nombre", "Correo", "Grupos", "Estado")
    tree_inv = ttk.Treeview(frame_gi, columns=cols_i, show="headings", height=5)
    for col in cols_i:
        tree_inv.heading(col, text=col)
    tree_inv.pack(fill="both", expand=True, padx=5, pady=2)

    btn_bar_gi = ttk.Frame(frame_gi)
    btn_bar_gi.pack(fill="x", pady=5)
    ttk.Button(btn_bar_gi, text="Crear Grupo", command=lambda: abrir_formulario_grupo(root)).pack(side="left", padx=5)
    ttk.Button(btn_bar_gi, text="Crear Investigador", command=lambda: abrir_formulario_investigador(root)).pack(side="left", padx=5)

    frame_ml = ttk.Frame(notebook)
    notebook.add(frame_ml, text="Multilista (Grupo -> Inv -> Prod)")

    tree_ml = ttk.Treeview(frame_ml)
    tree_ml.heading("#0", text="Estructura Jerárquica en Memoria", anchor="w")
    tree_ml.pack(fill="both", expand=True, padx=5, pady=5)

    frame_pc = ttk.Frame(notebook)
    notebook.add(frame_pc, text="Pila (LIFO) y Cola (FIFO)")

    ttk.Label(frame_pc, text="Pila de Productos (LIFO - Último en entrar, primero en salir):", font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=5)
    txt_pila_gui = tk.Text(frame_pc, height=4, wrap="word")
    txt_pila_gui.pack(fill="x", padx=10, pady=5)

    ttk.Label(frame_pc, text="Cola de Productos (FIFO - Primero en entrar, primero en salir):", font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=5)
    txt_cola_gui = tk.Text(frame_pc, height=4, wrap="word")
    txt_cola_gui.pack(fill="x", padx=10, pady=5)

    frame_dash = ttk.Frame(notebook)
    notebook.add(frame_dash, text="Dashboard Estadístico")

    lbl_d = ttk.Label(frame_dash, text="Visualización de Gráficos Estadísticos (Matplotlib)", font=("Arial", 11, "bold"))
    lbl_d.pack(pady=20)
    ttk.Button(frame_dash, text="Abrir Dashboard Gráfico (Barras / Histograma)", command=estadisticas).pack(pady=10)

    refrescar_todas_las_tablas()

    root.mainloop()

if __name__ == "__main__":
    iniciar_interfaz_grafica()