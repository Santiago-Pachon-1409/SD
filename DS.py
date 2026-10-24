import csv
import os
import re
import json
import subprocess
from collections import deque
import urllib.request
from bs4 import BeautifulSoup
from sqlalchemy import (create_engine, MetaData, Table, Column, String, Integer, ForeignKey, select, update, delete, func)

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from datetime import datetime
import math


RUTA_BD = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "pea.db"
)

engine = create_engine(f"sqlite:///{RUTA_BD}")
metadata = MetaData()

VENTANAS = {
    "Todos": None,
    "Últimos 2 años": 2,
    "Últimos 5 años": 5,
    "Últimos 7 años": 7,
    "Últimos 10 años": 10,
}

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

def calcular_indicador_oficial(productos_lista, num_autores=1, num_grupos_externos=1):
    conteo = {"Nc.Top": 0, "Nc.A": 0, "Nc.B": 0, "AP": 0, "DPC": 0, "Fr.A": 0, "Fr.B": 0}
    total_activos = 0

    for prod in productos_lista:
        estado = str(prod.get("estado", "Activo")).strip().lower()
        activo = prod.get("activo", estado == "activo")
        if not activo:
            continue

        total_activos += 1
        cat = str(prod.get("categoria", "")).upper().replace(" ", "_")

        if any(x in cat for x in ("OPEN_A1", "ART_A1", "NC.TOP", "TOP", "PATENTE")):
            conteo["Nc.Top"] += 1
        elif any(x in cat for x in ("OPEN_A2", "ART_A2", "NC.A")):
            conteo["Nc.A"] += 1
        elif any(x in cat for x in ("ART_B", "ART_C", "NC.B")):
            conteo["Nc.B"] += 1
        elif "APROPIACION" in cat or cat == "AP" or "APROPIACION_SOCIAL" in cat:
            conteo["AP"] += 1
        elif "DIVULGACION" in cat or "DPC" in cat:
            conteo["DPC"] += 1
        elif any(x in cat for x in ("FR_A", "TESIS_DOC", "TESIS_MAE", "FORMACION_POSGRADO")):
            conteo["Fr.A"] += 1
        else:
            conteo["Fr.B"] += 1

    denominador = total_activos - 1 if total_activos > 1 else 1.0
    cohe = num_autores / denominador
    coop = num_grupos_externos / denominador
    resultado = (
        3.7 * conteo["Nc.Top"] + 2.3 * conteo["Nc.A"] +
        0.4 * conteo["Nc.B"] + 1.5 * conteo["AP"] +
        0.5 * conteo["DPC"] + conteo["Fr.A"] +
        0.2 * conteo["Fr.B"] + 0.1 * cohe + 0.3 * coop
    )
    return round(resultado, 4), conteo

def validar_requisitos_existencia_minciencias(grupo_dict: dict) -> tuple[bool, str]:
    """
    Valida el Capítulo II (Numeral 2.1.1) del modelo Minciencias 2024.
    Criterios: Mínimo 2 integrantes, >=1 año de existencia, >=1 proyecto en ejecución.
    """
    integrantes = grupo_dict.get("num_integrantes", 0)
    edad_anos = grupo_dict.get("edad_anos", 1)
    proyectos_ejecucion = grupo_dict.get("proyectos_ejecucion", 1)
    
    if integrantes < 2:
        return False, f"Incumple Requisito: El grupo cuenta con {integrantes} integrante(s) (Mínimo requerido: 2)[cite: 51]."
    if edad_anos < 1:
        return False, f"Incumple Requisito: Edad del grupo de {edad_anos} año(s) (Mínimo requerido: 1)[cite: 51]."
    if proyectos_ejecucion < 1:
        return False, "Incumple Requisito: No registra proyectos de I+D+i en ejecución (Mínimo: 1)[cite: 51]."
        
    return True, "Cumple con los requisitos de existencia del Modelo Minciencias 2024[cite: 51]."

def filtrar_por_ventana_observacion_minciencias(productos_lista: list, tipo_producto: str) -> list:
    """
    Filtra los productos según las Ventanas de Observación oficiales (Tabla 5 - Minciencias 2024):
    - Artículos A1, A2, B, C, Libros de investigación: 7 años
    - Artículos D y productos generales: 5 años
    - Patentes, Variedades vegetales, AAD: 10 años
    """
    anho_actual = datetime.now().year
    filtrados = []

    for p in productos_lista:
        anho_pub = p.get("anio", anho_actual)
        diff = anho_actual - anho_pub
        
        if tipo_producto in ["A1", "A2", "B", "C", "Libro_Investigacion"] and diff <= 7:
            filtrados.append(p)
        elif tipo_producto in ["D", "General"] and diff <= 5:
            filtrados.append(p)
        elif tipo_producto in ["Patente", "AAD", "Variedad_Vegetal"] and diff <= 10:
            filtrados.append(p)
        elif tipo_producto == "Todas":
            if diff <= 7:
                filtrados.append(p)
                
    return filtrados

def calcular_itp_minciencias(num_productos: int, periodo_observacion: int) -> float:
    """
    Calcula el indicador de productos (I_TP) aplicando la fórmula logarítmica oficial:
    lambda = ln((Productos / Periodo) + 1)
    """
    if periodo_observacion <= 0:
        return 0.0
    valor = (num_productos / periodo_observacion) + 1
    return math.log(valor)

def evaluar_grupo_seleccionado():
    sel = tree_grupos.selection()
    if sel:
        codigo = tree_grupos.item(sel[0])["values"][0]
    else:
        codigo = simpledialog.askstring("Evaluación Minciencias", "Código del grupo a evaluar:", parent=root)
        if not codigo:
            return
    abrir_reporte_minciencias_gui(root, codigo.strip())
    
def abrir_reporte_minciencias_gui(root, grupo_codigo="G-001"):
    try:
        with engine.connect() as conn:
            g_info = conn.execute(select(grupos).where(grupos.c.codigo == grupo_codigo)).mappings().first()
            investigadores_grupo = conn.execute(
                select(investigadores.c.codigo, investigadores.c.nombre)
                .select_from(investigadores.join(
                    grupo_investigador,
                    investigadores.c.codigo == grupo_investigador.c.investigador_codigo
                ))
                .where(grupo_investigador.c.grupo_codigo == grupo_codigo)
                .order_by(investigadores.c.nombre)
            ).mappings().all()
            prods_grupo = conn.execute(
                select(productos).where(productos.c.grupo_codigo == grupo_codigo)
            ).mappings().all()

        if not g_info:
            messagebox.showwarning("Atención", f"No se encontró el grupo '{grupo_codigo}' en la base de datos.")
            return

        lista_prods = [dict(p) for p in prods_grupo]
        ind_total, conteo = calcular_indicador_oficial(
            lista_prods, num_autores=len(investigadores_grupo), num_grupos_externos=1
        )

        lineas_individuales = []
        for inv in investigadores_grupo:
            prods_inv = [
                p for p in lista_prods
                if p.get("investigador_codigo") == inv["codigo"]
            ]
            ind_inv, conteo_inv = calcular_indicador_oficial(
                prods_inv, num_autores=1, num_grupos_externos=1
            )
            activos_inv = sum(
                1 for p in prods_inv
                if str(p.get("estado", "Activo")).strip().lower() == "activo"
            )
            lineas_individuales.append(
                f"Investigador: {inv['nombre']} ({inv['codigo']})\\n"
                f"  Productos activos: {activos_inv}\\n"
                f"  Indicador individual: {ind_inv}\\n"
            )

        top = tk.Toplevel(root)
        top.title(f"Indicador de producción científica - {g_info['nombre']}")
        top.geometry("760x620")

        reporte_texto = f"""INDICADOR DE PRODUCCIÓN CIENTÍFICA

GRUPO: {g_info['nombre']}
Código: {g_info['codigo']}
Investigadores asociados: {len(investigadores_grupo)}
Productos registrados en el grupo: {len(lista_prods)}

DETALLE DEL INDICADOR DEL GRUPO
Nc.Top (peso 3.7): {conteo['Nc.Top']}
Nc.A   (peso 2.3): {conteo['Nc.A']}
Nc.B   (peso 0.4): {conteo['Nc.B']}
AP     (peso 1.5): {conteo['AP']}
DPC    (peso 0.5): {conteo['DPC']}
Fr.A   (peso 1.0): {conteo['Fr.A']}
Fr.B   (peso 0.2): {conteo['Fr.B']}

INDICADOR FINAL DEL GRUPO: {ind_total}

INDICADORES POR INVESTIGADOR
{chr(10).join(lineas_individuales) if lineas_individuales else 'No hay investigadores asociados a este grupo.'}

Nota: solo se ponderan productos con estado Activo.
"""
        txt = tk.Text(top, wrap="word", font=("Consolas", 10))
        txt.pack(expand=True, fill="both", padx=10, pady=10)
        txt.insert(tk.END, reporte_texto)
        txt.config(state="disabled")
    except Exception as e:
        messagebox.showerror("Error", f"Ocurrió un error al generar el reporte: {e}")

pila_productos = []
cola_productos = deque()
multilista_grupos = []

def vaciar_multilista():
    multilista_grupos.clear()

def crear_nodo_producto(codigo, nombre, categoria, anio, validacion, estado="Activo"):
    return {"codigo": codigo, "nombre": nombre, "categoria": categoria, "anio": anio, "validacion": validacion, "estado": estado}

def crear_nodo_investigador(codigo, nombre, correo, estado="Activo"):
    return {"codigo": codigo, "nombre": nombre, "correo": correo, "estado": estado, "productos": []}

def crear_nodo_grupo(codigo, nombre, area, estado="Activo"):
    return {"codigo": codigo, "nombre": nombre, "area": area, "estado": estado, "investigadores": []}

def agregar_o_buscar_grupo_ml(codigo, nombre=None, area=None):
    for grupo in multilista_grupos:
        if grupo["codigo"] == codigo:
            if nombre and nombre != "Sin Nombre":
                grupo["nombre"] = nombre
            if area and area != "General":
                grupo["area"] = area
            return grupo
    nom_final = nombre if (nombre and nombre != "Sin Nombre") else "Grupo de Investigación"
    area_final = area if (area and area != "General") else "Ingeniería y Sistemas"
    nuevo_grupo = crear_nodo_grupo(codigo, nom_final, area_final)
    multilista_grupos.append(nuevo_grupo)
    return nuevo_grupo

def agregar_o_buscar_investigador_ml(grupo_codigo, inv_codigo, nombre=None, correo=None):
    grupo = agregar_o_buscar_grupo_ml(grupo_codigo)
    for inv in grupo["investigadores"]:
        if inv["codigo"] == inv_codigo:
            if nombre and nombre != "Sin Nombre":
                inv["nombre"] = nombre
            if correo and correo != "correo@unicesar.edu.co":
                inv["correo"] = correo
            return inv
    nom_final = nombre if (nombre and nombre != "Sin Nombre") else "Investigador Principal"
    cor_final = correo if (correo and correo != "correo@unicesar.edu.co") else "inv@unicesar.edu.co"
    nuevo_inv = crear_nodo_investigador(inv_codigo, nom_final, cor_final)
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
    
def existe_producto_duplicado(nombre, anio, grupo_codigo, excluir_codigo=None):
    with engine.connect() as conn:
        stmt = select(productos.c.codigo).where(
            (func.lower(productos.c.nombre) == nombre.strip().lower())
            & (productos.c.anio == anio)
            & (productos.c.grupo_codigo == grupo_codigo)
        )
        if excluir_codigo:
            stmt = stmt.where(productos.c.codigo != excluir_codigo)
        return conn.execute(stmt).first() is not None
    
def limpiar_base_datos():
    with engine.begin() as conn:
        conn.execute(delete(productos))
        conn.execute(delete(grupo_investigador))
        conn.execute(delete(investigadores))
        conn.execute(delete(grupos))
    pila_productos.clear()
    cola_productos.clear()
    vaciar_multilista()

def siguiente_codigo(tabla, prefijo):
    with engine.connect() as conn:
        codigos = conn.execute(select(tabla.c.codigo).where(tabla.c.codigo.like(f"{prefijo}%"))).scalars().all()
    nums = [int(m.group(1)) for c in codigos if (m := re.search(r"(\d+)$", c))]
    return f"{prefijo}{(max(nums) + 1 if nums else 1):03d}"

codigo_prod = siguiente_codigo(productos, "PROD-WEB-")    

def cargar_estructuras_guardadas():
    pila_productos.clear()
    cola_productos.clear()
    vaciar_multilista()

    with engine.connect() as conn:
        reg_grupos = conn.execute(select(grupos)).mappings().all()
        for g in reg_grupos:
            agregar_o_buscar_grupo_ml(g["codigo"], g["nombre"], g["area"])

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

        registros = conn.execute(select(productos)).mappings().all()

    for p in registros:
        pila_productos.append(p["codigo"])
        cola_productos.append(p["codigo"])
        g_cod = p["grupo_codigo"] if p["grupo_codigo"] else "G-001"
        inv_cod = p["investigador_codigo"] if p["investigador_codigo"] else "INV-001"
        agregar_producto_ml(g_cod, inv_cod, p["codigo"], p["nombre"], p["categoria"], p["anio"], p["validacion"])

def exportar_todo_a_json(ruta_salida="datos_entrada.json"):
    with engine.connect() as conn:
        registros = conn.execute(select(productos)).mappings().all()

    lista_productos = []
    for r in registros:
        lista_productos.append({
            "codigo": r["codigo"],
            "nombre": r["nombre"],
            "categoria": r["categoria"],
            "anio": r["anio"],
            "validacion": r["validacion"],
            "estado": r["estado"],
            "grupo_codigo": r["grupo_codigo"] if r["grupo_codigo"] else "G-001",
            "investigador_codigo": r["investigador_codigo"] if r["investigador_codigo"] else "INV-001"
        })

    with open(ruta_salida, mode='w', encoding='utf-8') as f:
        json.dump(lista_productos, f, indent=4, ensure_ascii=False)

def descargar_desde_url_gui(ventana_padre):
    url = simpledialog.askstring("Web Scraping MinCiencias", "Ingrese la URL a procesar (GrupLAC/CvLAC):", parent=ventana_padre)
    if not url:
        return

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        req = urllib.request.Request(url, headers=headers)
        try:
            html = urllib.request.urlopen(req).read().decode('utf-8')
        except UnicodeDecodeError:
            html = urllib.request.urlopen(req).read().decode('iso-8859-1')

        soup = BeautifulSoup(html, 'html.parser')
        m = re.search(r"nro=0*(\d+)", url)
        g_cod = f"G-{int(m.group(1)):03d}" if m else "G-001"
        g_nom = "Grupo de Investigación en Sistemas y Computación"
        
        header_grupo = soup.find(
            lambda tag: tag.name in ['td', 'b', 'span', 'h2', 'h3', 'a', 'font'] and 
            "GRUPO DE INVESTIGACION" in tag.get_text().upper() and len(tag.get_text().strip()) < 150
        )
        if header_grupo:
            g_nom = re.sub(r'\s+', ' ', header_grupo.get_text(strip=True))[:100]

        with engine.begin() as conn:
            if not conn.execute(select(grupos).where(grupos.c.codigo == g_cod)).first():
                conn.execute(grupos.insert().values(codigo=g_cod, nombre=g_nom, area="Ingeniería y Sistemas", estado="Activo"))
            else:
                conn.execute(update(grupos).where(grupos.c.codigo == g_cod).values(nombre=g_nom))
        
        agregar_o_buscar_grupo_ml(g_cod, g_nom, "Ingeniería y Sistemas")

        lista_investigadores = []
        mapa_investigadores = {}
        inv_contador = int(siguiente_codigo(investigadores, "INV-").split("-")[1])

        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href'].lower()
            if 'cvlac' in href or 'evaluador' in href or 'investigador' in href:
                nombre_inv = a_tag.get_text(strip=True)
                nombre_inv = re.sub(r'^\d+\s*[-\.]\s*', '', nombre_inv).strip()
                if len(nombre_inv.split()) >= 2 and len(nombre_inv) < 50 and not any(char.isdigit() for char in nombre_inv):
                    if nombre_inv.lower() not in mapa_investigadores:
                        with engine.connect() as conn:
                            existente = conn.execute(
                                select(investigadores.c.codigo).where(func.lower(investigadores.c.nombre) == nombre_inv.lower())
                                ).scalar()
                        # Cada investigador nuevo necesita un código diferente.
                        # No se usa siguiente_codigo() dentro de este ciclo porque
                        # todavía no se han guardado los investigadores en la BD.
                        cod_inv = existente or f"INV-{inv_contador:03d}"
                        lista_investigadores.append((cod_inv, nombre_inv, f"inv{inv_contador}@unicesar.edu.co"))
                        mapa_investigadores[nombre_inv.lower()] = cod_inv
                        inv_contador += 1

        if not lista_investigadores:
            cod_inv = "INV-001"
            nombre_def = "Investigador Principal"
            lista_investigadores.append((cod_inv, nombre_def, "investigador@unicesar.edu.co"))
            mapa_investigadores[nombre_def.lower()] = cod_inv

        with engine.begin() as conn:
            for cod, nom, cor in lista_investigadores:
                if not conn.execute(select(investigadores.c.codigo).where(investigadores.c.codigo == cod)).first():
                    conn.execute(investigadores.insert().values(codigo=cod, nombre=nom, correo=cor, estado="Activo"))

                # Asociar al grupo también a investigadores que ya existían.
                asociacion = conn.execute(
                    select(grupo_investigador.c.grupo_codigo).where(
                        (grupo_investigador.c.grupo_codigo == g_cod)
                        & (grupo_investigador.c.investigador_codigo == cod)
                    )
                ).first()
                if not asociacion:
                    conn.execute(grupo_investigador.insert().values(
                        grupo_codigo=g_cod, investigador_codigo=cod
                    ))

                agregar_o_buscar_investigador_ml(g_cod, cod, nom, cor)

        nuevos = 0
        registros_extraidos = []
        categoria_actual = "Artículo"

        for tr in soup.find_all('tr'):
            texto_tr = tr.get_text(strip=True)
            texto_lower = texto_tr.lower()

            if "artículo" in texto_lower or "articulo" in texto_lower:
                categoria_actual = "Artículo"
            elif "libro" in texto_lower or "capítulo" in texto_lower or "capitulo" in texto_lower:
                categoria_actual = "Libro / Capítulo"
            elif "software" in texto_lower:
                categoria_actual = "Software"

            celdas = tr.find_all(['td', 'th'])
            if len(celdas) >= 1:
                texto_completo = " ".join([c.get_text(strip=True) for c in celdas])
                if len(texto_completo) < 30 or "autores" in texto_completo.lower() or "referencia" in texto_completo.lower():
                    continue

                match_anio = re.search(r'\b(19\d\d|20[0-3]\d)\b', texto_completo)
                if not match_anio:
                    continue

                anio = int(match_anio.group(1))
                
                nombre_prod = texto_completo.replace(',', ' ').replace('"', '')
                nombre_prod = re.sub(r'^\d+[\.\-\s]+[A-ZÁÉÍÓÚÑa-záéíóúñ\s\.]+?(?:Integrante|Profesor|Autor|Estudiante|Coinvestigador|Director|Líder|\d{4}/\d).*?[\-\–\—\.]\s*', '', nombre_prod, flags=re.IGNORECASE)
                nombre_prod = re.sub(r'^\d+[\.\-\s]+[A-ZÁÉÍÓÚÑa-záéíóúñ\s\.]+?(?:\d{4}/\d).*?[\-\–\—\.]\s*', '', nombre_prod, flags=re.IGNORECASE)
                nombre_prod = re.sub(r'^\d+[\.\-\s]+[A-ZÁÉÍÓÚÑa-záéíóúñ\s\.-]+(?:[\-\–\—]|\bde\b|\bpiso\b).*?\.\s*', '', nombre_prod, flags=re.IGNORECASE)
                nombre_prod = re.sub(r'^\d+[\.\-\s]+', '', nombre_prod)
                nombre_prod = nombre_prod[:120].strip()
                if existe_producto_duplicado(nombre_prod, anio, g_cod):
                    continue

                codigo_prod = siguiente_codigo(productos, "PROD-WEB-")

                with engine.connect() as conn:
                    dup = conn.execute(
                        select(productos.c.codigo).where(
                            (productos.c.nombre == nombre_prod)
                            & (productos.c.anio == anio)
                            & (productos.c.grupo_codigo == g_cod)
                        )
                    ).first()
                if dup:
                    continue

                codigo_prod = siguiente_codigo(productos, "PROD-WEB-")

                inv_asociado_cod = lista_investigadores[0][0]
                for nom_inv, cod_inv in mapa_investigadores.items():
                    partes_nombre = [p for p in nom_inv.lower().split() if len(p) > 3]
                    if partes_nombre:
                        coincidencias = sum(1 for p in partes_nombre if p in texto_lower)
                        umbral = 2 if len(partes_nombre) >= 2 else 1
                        if coincidencias >= umbral:
                            inv_asociado_cod = cod_inv
                            break

                if not buscar_producto(codigo_prod):
                    with engine.begin() as conn:
                        conn.execute(
                            productos.insert().values(
                                codigo=codigo_prod, nombre=nombre_prod, categoria=categoria_actual,
                                anio=anio, validacion="Validado", estado="Activo",
                                investigador_codigo=inv_asociado_cod, grupo_codigo=g_cod
                            )
                        )

                    pila_productos.append(codigo_prod)
                    cola_productos.append(codigo_prod)
                    agregar_producto_ml(g_cod, inv_asociado_cod, codigo_prod, nombre_prod, categoria_actual, anio, "Validado")
                    nuevos += 1
                    registros_extraidos.append([codigo_prod, nombre_prod, categoria_actual, anio, "Validado", g_cod, inv_asociado_cod])

        with open("datos_scraping.csv", mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["codigo", "nombre", "categoria", "anio", "validacion", "grupo_codigo", "investigador_codigo"])
            writer.writerows(registros_extraidos)

        cargar_estructuras_guardadas()
        refrescar_todas_las_tablas()

        messagebox.showinfo("Éxito", f"Web Scraping completado:\n• Grupo: {g_nom}\n• {len(lista_investigadores)} Investigadores.\n• {nuevos} Productos limpios procesados.")

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
                    g_cod = fila.get("grupo_codigo", "G-001")
                    i_cod = fila.get("investigador_codigo", "INV-001")
                    p_cod = fila["codigo"]
                    if existe_producto_duplicado(fila["nombre"], int(fila["anio"]), g_cod):
                        continue
                    if not conn.execute(select(productos.c.codigo).where(productos.c.codigo == p_cod)).scalar():
                        conn.execute(productos.insert().values(
                            codigo=p_cod, nombre=fila["nombre"], categoria=fila["categoria"],
                            anio=int(fila["anio"]), validacion=fila["validacion"], estado="Activo",
                            investigador_codigo=i_cod, grupo_codigo=g_cod
                        ))
                        pila_productos.append(p_cod)
                        cola_productos.append(p_cod)
                        agregar_producto_ml(g_cod, i_cod, p_cod, fila["nombre"], fila["categoria"], int(fila["anio"]), fila["validacion"])
                        registros_nuevos += 1
        messagebox.showinfo("Éxito", f"Se importaron {registros_nuevos} productos.")
        refrescar_todas_las_tablas()
    except Exception as e:
        messagebox.showerror("Error", f"Error al importar CSV: {e}")

def refrescar_tabla_grupos(tree):
    for item in tree.get_children(): tree.delete(item)
    with engine.connect() as conn:
        registros = conn.execute(select(grupos)).mappings().all()
    for i, g in enumerate(registros):
        tree.insert("", "end", values=(g["codigo"], g["nombre"], g["area"], g["estado"]), tags=("evenrow" if i%2==0 else "oddrow",))

def refrescar_tabla_investigadores(tree):
    for item in tree.get_children(): tree.delete(item)
    consulta = (
        select(
            investigadores.c.codigo,
            investigadores.c.nombre,
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
        tree.insert("", "end", values=(inv["codigo"], inv["nombre"], inv["grupos"] or "Sin grupo", inv["estado"]), tags=("evenrow" if i%2==0 else "oddrow",))

def refrescar_tabla_productos(tree, texto_filtro="", cat_filtro="Todas", est_filtro="Todos", anio_filtro="Todos", ventana="Todos"):
    for item in tree.get_children(): tree.delete(item)
    n = VENTANAS.get(ventana)
    with engine.connect() as conn:
        stmt = select(productos)
        if n:
            stmt = stmt.where(productos.c.anio >= datetime.now().year - n)
        if texto_filtro.strip():
            f = f"%{texto_filtro.strip()}%"
            stmt = stmt.where((productos.c.codigo.like(f)) | (productos.c.nombre.like(f)) | (productos.c.categoria.like(f)))
        if cat_filtro != "Todas": 
            stmt = stmt.where(productos.c.categoria == cat_filtro)
        if est_filtro != "Todos": 
            stmt = stmt.where(productos.c.estado == est_filtro)
        if anio_filtro.strip() and anio_filtro.strip().lower() != "todos":
            try:
                stmt = stmt.where(productos.c.anio == int(anio_filtro.strip()))
            except ValueError:
                pass

        registros = conn.execute(stmt).mappings().all()
    for i, p in enumerate(registros):
        tree.insert("", "end", values=(p["codigo"], p["nombre"], p["categoria"], p["anio"], p["validacion"], p["investigador_codigo"], p["estado"]), tags=("evenrow" if i%2==0 else "oddrow",))

def refrescar_arbol_multilista(tree):
    for item in tree.get_children(): tree.delete(item)
    for g in multilista_grupos:
        node_g = tree.insert("", "end", text=f" 📂 Grupo: {g['codigo']} - {g['nombre']}", values=(g['codigo'], "Grupo", g['area']), open=True, tags=("grupo",))
        for inv in g["investigadores"]:
            node_inv = tree.insert(node_g, "end", text=f"   👤 Investigador: {inv['codigo']} - {inv['nombre']}", values=(inv['codigo'], "Investigador", inv['correo']), open=True, tags=("investigador",))
            for prod in inv["productos"]:
                tree.insert(node_inv, "end", text=f"      📄 Producto: {prod['codigo']} - {prod['nombre']}", values=(prod['codigo'], f"Cat: {prod['categoria']} ({prod['anio']})", prod['validacion']), tags=("producto",))

def refrescar_dashboard_sigiip():
    if 'panel_der_dash' not in globals(): return
    for widget in panel_der_dash.winfo_children(): widget.destroy()

    tk.Label(panel_der_dash, text="Métricas e Indicadores de Producción Científica", font=("Segoe UI", 11, "bold"), bg="#f8fafc", fg="#0f172a").pack(anchor="w", pady=(5, 10))

    with engine.connect() as conn:
        df_prod = pd.read_sql("SELECT * FROM productos", conn)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 4.5), dpi=100)
    fig.patch.set_facecolor('#f8fafc')

    if not df_prod.empty:
        conteo_anios = df_prod['anio'].value_counts().sort_index()
        conteo_anios.plot(kind='bar', ax=ax1, color='#0284c7', edgecolor='#0f172a', width=0.6)
        ax1.set_title("Participación en Proyectos / Años", fontsize=10, fontweight='bold')
        ax1.set_xlabel("Año", fontsize=9)
        ax1.set_ylabel("Cantidad", fontsize=9)
        ax1.grid(axis='y', linestyle='--', alpha=0.6)

        conteo_cat = df_prod['categoria'].value_counts()
        colores = ['#f97316', '#0284c7', '#16a34a', '#dc2626']
        conteo_cat.plot(kind='pie', ax=ax2, autopct='%1.1f%%', startangle=90, colors=colores[:len(conteo_cat)], wedgeprops=dict(width=0.6, edgecolor='w'))
        ax2.set_title("Tipología de Productos Reportados", fontsize=10, fontweight='bold')
        ax2.set_ylabel("")
    else:
        ax1.text(0.5, 0.5, "Sin datos", ha='center', va='center')
        ax2.text(0.5, 0.5, "Sin datos", ha='center', va='center')

    plt.tight_layout()
    canvas_dash = FigureCanvasTkAgg(fig, master=panel_der_dash)
    canvas_dash.draw()
    plt.close(fig)
    canvas_dash.get_tk_widget().pack(fill="both", expand=True)

def refrescar_todas_las_tablas():
    refrescar_tabla_grupos(tree_grupos)
    refrescar_tabla_investigadores(tree_inv)
    refrescar_tabla_productos(
        tree_prod, 
        ent_buscar.get() if 'ent_buscar' in globals() else "", 
        combo_cat.get() if 'combo_cat' in globals() else "Todas", 
        combo_est.get() if 'combo_est' in globals() else "Todos", 
        ent_anio.get() if 'ent_anio' in globals() else "Todos"
    )
    if 'tree_multi' in globals(): refrescar_arbol_multilista(tree_multi)
    refrescar_dashboard_sigiip()

def deshacer_ultimo_pila_gui():
    if not pila_productos:
        messagebox.showinfo("Pila Vacía", "La Cima de la Pila está vacía.")
        return
    ultimo_codigo = pila_productos.pop()
    if messagebox.askyesno("Pila (LIFO)", f"¿Eliminar de la BD el último producto: '{ultimo_codigo}'?"):
        with engine.begin() as conn:
            conn.execute(delete(productos).where(productos.c.codigo == ultimo_codigo))
        if ultimo_codigo in cola_productos: cola_productos.remove(ultimo_codigo)
        cargar_estructuras_guardadas()
        refrescar_todas_las_tablas()
    else:
        pila_productos.append(ultimo_codigo)

def ver_estado_pila_cola_gui(root):
    top = tk.Toplevel(root)
    top.title("Estado de Memoria RAM: Pila & Cola")
    top.geometry("480x320")
    top.configure(bg="#0f172a")
    tk.Label(top, text="ESTRUCTURAS LINEALES EN RAM", font=("Segoe UI", 11, "bold"), bg="#0f172a", fg="#38bdf8").pack(pady=10)
    txt = tk.Text(top, font=("Consolas", 9), bg="#1e293b", fg="#f8fafc", bd=0, padx=10, pady=10)
    txt.pack(fill="both", expand=True, padx=10, pady=10)
    pila_str = " -> ".join(reversed(pila_productos)) if pila_productos else "[VACÍA]"
    cola_str = " -> ".join(cola_productos) if cola_productos else "[VACÍA]"
    txt.insert(tk.END, f"--- PILA (LIFO) ---\n[{pila_str}]\n\n--- COLA (FIFO) ---\n[{cola_str}]")
    txt.config(state="disabled")

def abrir_formulario_producto(root):
    top = tk.Toplevel(root)
    top.title("Crear Producto")
    top.geometry("340x380")
    top.configure(bg="#f8fafc")
    top.grab_set()

    tk.Label(top, text="Código:", bg="#f8fafc", fg="#0f172a", font=("Segoe UI", 8, "bold")).pack(pady=(6, 1))
    ent_cod = tk.Entry(top, font=("Segoe UI", 9), relief="solid", bd=1); ent_cod.pack(ipadx=4)
    tk.Label(top, text="Nombre:", bg="#f8fafc", fg="#0f172a", font=("Segoe UI", 8, "bold")).pack(pady=(4, 1))
    ent_nom = tk.Entry(top, font=("Segoe UI", 9), relief="solid", bd=1); ent_nom.pack(ipadx=4)
    tk.Label(top, text="Categoría:", bg="#f8fafc", fg="#0f172a", font=("Segoe UI", 8, "bold")).pack(pady=(4, 1))
    ent_cat = tk.Entry(top, font=("Segoe UI", 9), relief="solid", bd=1); ent_cat.pack(ipadx=4)
    tk.Label(top, text="Año:", bg="#f8fafc", fg="#0f172a", font=("Segoe UI", 8, "bold")).pack(pady=(4, 1))
    ent_anio = tk.Entry(top, font=("Segoe UI", 9), relief="solid", bd=1); ent_anio.pack(ipadx=4)
    tk.Label(top, text="Validación:", bg="#f8fafc", fg="#0f172a", font=("Segoe UI", 8, "bold")).pack(pady=(4, 1))
    ent_val = tk.Entry(top, font=("Segoe UI", 9), relief="solid", bd=1); ent_val.pack(ipadx=4)
    tk.Label(top, text="Código Investigador:", bg="#f8fafc", fg="#0f172a", font=("Segoe UI", 8, "bold")).pack(pady=(4, 1))
    ent_inv = tk.Entry(top, font=("Segoe UI", 9), relief="solid", bd=1); ent_inv.pack(ipadx=4)

    def guardar():
        c, n, cat, val, inv_cod = ent_cod.get().strip(), ent_nom.get().strip(), ent_cat.get().strip(), ent_val.get().strip(), ent_inv.get().strip()
        try: a = int(ent_anio.get().strip())
        except ValueError:
            messagebox.showerror("Error", "Año numérico requerido.", parent=top); return
        if not c or not n or not cat or not val or not inv_cod:
            messagebox.showwarning("Atención", "Todos los campos son requeridos.", parent=top); return
        if buscar_producto(c):
            messagebox.showerror("Error", "El producto ya existe.", parent=top); return
        investigador = buscar_investigador(inv_cod)
        if not investigador:
            messagebox.showerror("Error", "El investigador indicado no existe.", parent=top); return
        with engine.connect() as conn:
            g_cod = conn.execute(select(grupo_investigador.c.grupo_codigo).where(grupo_investigador.c.investigador_codigo == inv_cod)).scalars().first()
        g_final = g_cod or "G-001"
        if existe_producto_duplicado(n, a, g_final):
            messagebox.showerror("Error", "Ya existe un producto con ese nombre y año en el grupo.", parent=top)
            return
        if not buscar_grupo(g_final):
            messagebox.showerror("Error", "El investigador debe estar asociado a un grupo existente.", parent=top); return
        with engine.begin() as conn:
            conn.execute(productos.insert().values(codigo=c, nombre=n, categoria=cat, anio=a, validacion=val, estado="Activo", investigador_codigo=inv_cod, grupo_codigo=g_final))
        pila_productos.append(c); cola_productos.append(c)
        agregar_producto_ml(g_final, inv_cod, c, n, cat, a, val)
        messagebox.showinfo("Éxito", "Producto registrado con éxito.", parent=top)
        top.destroy(); refrescar_todas_las_tablas()

    tk.Button(top, text="Guardar Producto", command=guardar, bg="#16a34a", fg="white", font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2").pack(pady=12)

def eliminar_producto_gui():
    selected = tree_prod.selection()
    if not selected: messagebox.showwarning("Selección", "Seleccione un producto."); return
    codigo = tree_prod.item(selected[0])['values'][0]
    if messagebox.askyesno("Confirmar", f"¿Eliminar producto '{codigo}'?"):
        with engine.begin() as conn: conn.execute(delete(productos).where(productos.c.codigo == codigo))
        if codigo in pila_productos: pila_productos.remove(codigo)
        if codigo in cola_productos: cola_productos.remove(codigo)
        cargar_estructuras_guardadas(); refrescar_todas_las_tablas()

def desactivar_producto_gui():
    selected = tree_prod.selection()
    if not selected: return
    codigo = tree_prod.item(selected[0])['values'][0]
    with engine.begin() as conn: conn.execute(update(productos).where(productos.c.codigo == codigo).values(estado="Inactivo"))
    refrescar_todas_las_tablas()

def activar_producto_gui():
    selected = tree_prod.selection()
    if not selected: return
    codigo = tree_prod.item(selected[0])['values'][0]
    with engine.begin() as conn: conn.execute(update(productos).where(productos.c.codigo == codigo).values(estado="Activo"))
    refrescar_todas_las_tablas()

def ejecutar_procesador_cpp_gui():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ruta_json = os.path.join(base_dir, "datos_entrada.json")
    fuente_cpp = os.path.join(base_dir, "DS.cpp")
    ejecutable = os.path.join(base_dir, "programa.exe" if os.name == "nt" else "DS")

    exportar_todo_a_json(ruta_json)

    if not os.path.exists(ejecutable):
        compilador = "g++"
        try:
            compilacion = subprocess.run(
                [compilador, "-std=c++17", fuente_cpp, "-o", ejecutable],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                cwd=base_dir
            )
        except FileNotFoundError:
            messagebox.showerror("Compilador no encontrado", "Instala un compilador C++ (g++) y agrégalo al PATH.")
            return
        if compilacion.returncode != 0:
            messagebox.showerror("Error de compilación", compilacion.stderr or compilacion.stdout)
            return

    try:
        resultado = subprocess.run(
            [ejecutable, ruta_json], capture_output=True, text=True,
            encoding="utf-8", errors="replace", cwd=base_dir, timeout=30
        )
        if resultado.returncode != 0:
            messagebox.showerror("Error C++", resultado.stderr or resultado.stdout or "El proceso C++ terminó con error.")
            return

        top = tk.Toplevel()
        top.title("Reporte estadístico - Motor C++")
        top.geometry("650x460")
        top.configure(bg="#0f172a")
        tk.Label(top, text="RESULTADOS PROCESADOS EN C++", font=("Segoe UI", 10, "bold"), bg="#0f172a", fg="#38bdf8").pack(pady=(12, 5))
        txt = tk.Text(top, wrap="word", font=("Consolas", 10), bg="#1e293b", fg="#f8fafc", bd=0, padx=10, pady=10)
        txt.pack(fill="both", expand=True, padx=12, pady=12)
        txt.insert(tk.END, resultado.stdout)
        txt.config(state="disabled")
    except subprocess.TimeoutExpired:
        messagebox.showerror("Tiempo agotado", "El proceso C++ tardó demasiado en responder.")
    except Exception as e:
        messagebox.showerror("Error", f"Fallo en la interoperabilidad Python-C++: {e}")


def gestionar_grupo_gui(accion):
    seleccionado = tree_grupos.selection()
    registro = None
    if accion != "crear":
        if not seleccionado:
            messagebox.showwarning("Selección", "Seleccione un grupo.")
            return
        codigo = tree_grupos.item(seleccionado[0])["values"][0]
        registro = buscar_grupo(codigo)
        if not registro:
            messagebox.showerror("Error", "No se encontró el grupo seleccionado.")
            return

    if accion == "eliminar":
        if not messagebox.askyesno("Confirmar", f"¿Eliminar el grupo {registro['codigo']} y sus relaciones? "):
            return
        with engine.begin() as conn:
            codigos_inv = conn.execute(select(grupo_investigador.c.investigador_codigo).where(grupo_investigador.c.grupo_codigo == registro["codigo"])).scalars().all()
            conn.execute(delete(productos).where(productos.c.grupo_codigo == registro["codigo"]))
            conn.execute(delete(grupo_investigador).where(grupo_investigador.c.grupo_codigo == registro["codigo"]))
            conn.execute(delete(grupos).where(grupos.c.codigo == registro["codigo"]))
            for cod_inv in codigos_inv:
                pertenece_a_otro = conn.execute(select(grupo_investigador.c.grupo_codigo).where(grupo_investigador.c.investigador_codigo == cod_inv)).first()
                tiene_productos = conn.execute(select(productos.c.codigo).where(productos.c.investigador_codigo == cod_inv)).first()
                if not pertenece_a_otro and not tiene_productos:
                    conn.execute(delete(investigadores).where(investigadores.c.codigo == cod_inv))
        cargar_estructuras_guardadas(); refrescar_todas_las_tablas()
        return

    if accion in ("desactivar", "activar"):
        nuevo_estado = "Inactivo" if accion == "desactivar" else "Activo"
        with engine.begin() as conn:
            conn.execute(update(grupos).where(grupos.c.codigo == registro["codigo"]).values(estado=nuevo_estado))
        cargar_estructuras_guardadas(); refrescar_todas_las_tablas()
        return

    codigo = simpledialog.askstring("Grupo", "Código:", initialvalue=registro["codigo"] if registro else "", parent=root)
    if not codigo: return
    nombre = simpledialog.askstring("Grupo", "Nombre:", initialvalue=registro["nombre"] if registro else "", parent=root)
    if not nombre: return
    area = simpledialog.askstring("Grupo", "Área:", initialvalue=registro["area"] if registro else "Ingeniería y Sistemas", parent=root)
    if not area: return
    if accion == "crear":
        if buscar_grupo(codigo):
            messagebox.showerror("Error", "Ya existe un grupo con ese código."); return
        with engine.begin() as conn:
            conn.execute(grupos.insert().values(codigo=codigo, nombre=nombre, area=area, estado="Activo"))
    else:
        if codigo != registro["codigo"] and buscar_grupo(codigo):
            messagebox.showerror("Error", "El nuevo código ya existe."); return
        with engine.begin() as conn:
            conn.execute(update(grupos).where(grupos.c.codigo == registro["codigo"]).values(codigo=codigo, nombre=nombre, area=area))
            if codigo != registro["codigo"]:
                conn.execute(update(productos).where(productos.c.grupo_codigo == registro["codigo"]).values(grupo_codigo=codigo))
                conn.execute(update(grupo_investigador).where(grupo_investigador.c.grupo_codigo == registro["codigo"]).values(grupo_codigo=codigo))
    cargar_estructuras_guardadas(); refrescar_todas_las_tablas()


def gestionar_investigador_gui(accion):
    seleccionado = tree_inv.selection()
    registro = None
    if accion != "crear":
        if not seleccionado:
            messagebox.showwarning("Selección", "Seleccione un investigador.")
            return
        codigo = tree_inv.item(seleccionado[0])["values"][0]
        registro = buscar_investigador(codigo)
        if not registro:
            messagebox.showerror("Error", "No se encontró el investigador seleccionado.")
            return

    if accion == "eliminar":
        if not messagebox.askyesno("Confirmar", f"¿Eliminar investigador {registro['codigo']} y sus productos? "):
            return
        with engine.begin() as conn:
            conn.execute(delete(productos).where(productos.c.investigador_codigo == registro["codigo"]))
            conn.execute(delete(grupo_investigador).where(grupo_investigador.c.investigador_codigo == registro["codigo"]))
            conn.execute(delete(investigadores).where(investigadores.c.codigo == registro["codigo"]))
        cargar_estructuras_guardadas(); refrescar_todas_las_tablas()
        return

    if accion in ("desactivar", "activar"):
        nuevo_estado = "Inactivo" if accion == "desactivar" else "Activo"
        with engine.begin() as conn:
            conn.execute(update(investigadores).where(investigadores.c.codigo == registro["codigo"]).values(estado=nuevo_estado))
        cargar_estructuras_guardadas(); refrescar_todas_las_tablas()
        return

    codigo = simpledialog.askstring("Investigador", "Código:", initialvalue=registro["codigo"] if registro else "", parent=root)
    if not codigo: return
    nombre = simpledialog.askstring("Investigador", "Nombre completo:", initialvalue=registro["nombre"] if registro else "", parent=root)
    if not nombre: return
    correo = simpledialog.askstring("Investigador", "Correo:", initialvalue=registro["correo"] if registro else "", parent=root)
    if not correo: return
    grupo_actual = ""
    if registro:
        with engine.connect() as conn:
            grupo_actual = conn.execute(select(grupo_investigador.c.grupo_codigo).where(grupo_investigador.c.investigador_codigo == registro["codigo"])).scalars().first() or ""
    grupo_codigo = simpledialog.askstring("Investigador", "Código del grupo al que pertenece:", initialvalue=grupo_actual or "G-001", parent=root)
    if not grupo_codigo: return
    if not buscar_grupo(grupo_codigo):
        messagebox.showerror("Error", "El grupo indicado no existe."); return
    if accion == "crear":
        if buscar_investigador(codigo):
            messagebox.showerror("Error", "Ya existe un investigador con ese código."); return
        with engine.begin() as conn:
            conn.execute(investigadores.insert().values(codigo=codigo, nombre=nombre, correo=correo, estado="Activo"))
            conn.execute(grupo_investigador.insert().values(grupo_codigo=grupo_codigo, investigador_codigo=codigo))
    else:
        if codigo != registro["codigo"] and buscar_investigador(codigo):
            messagebox.showerror("Error", "El nuevo código ya existe."); return
        with engine.begin() as conn:
            conn.execute(update(investigadores).where(investigadores.c.codigo == registro["codigo"]).values(codigo=codigo, nombre=nombre, correo=correo))
            conn.execute(delete(grupo_investigador).where(grupo_investigador.c.investigador_codigo == registro["codigo"]))
            conn.execute(grupo_investigador.insert().values(grupo_codigo=grupo_codigo, investigador_codigo=codigo))
            if codigo != registro["codigo"]:
                conn.execute(update(productos).where(productos.c.investigador_codigo == registro["codigo"]).values(investigador_codigo=codigo))
            conn.execute(update(productos).where(productos.c.investigador_codigo == codigo).values(grupo_codigo=grupo_codigo))
    cargar_estructuras_guardadas(); refrescar_todas_las_tablas()


def modificar_producto_gui():
    seleccionado = tree_prod.selection()
    if not seleccionado:
        messagebox.showwarning("Selección", "Seleccione un producto para modificar.")
        return
    codigo_original = tree_prod.item(seleccionado[0])["values"][0]
    registro = buscar_producto(codigo_original)
    if not registro: return
    top = tk.Toplevel(root)
    top.title("Modificar producto")
    top.geometry("360x430")
    campos = {}
    valores = {"Código": "codigo", "Nombre": "nombre", "Categoría": "categoria", "Año": "anio", "Validación": "validacion", "Código investigador": "investigador_codigo", "Código grupo": "grupo_codigo"}
    for etiqueta, campo in valores.items():
        tk.Label(top, text=etiqueta).pack(pady=(6, 1))
        entrada = tk.Entry(top, width=42)
        entrada.pack()
        entrada.insert(0, str(registro[campo] or ""))
        campos[campo] = entrada

    def guardar_cambios():
        datos_form = {campo: entrada.get().strip() for campo, entrada in campos.items()}
        if any(not datos_form[k] for k in ("codigo", "nombre", "categoria", "anio", "validacion", "investigador_codigo", "grupo_codigo")):
            messagebox.showwarning("Datos incompletos", "Complete todos los campos.", parent=top); return
        try: anio = int(datos_form["anio"])
        except ValueError:
            messagebox.showerror("Año inválido", "El año debe ser numérico.", parent=top); return
        
        if existe_producto_duplicado(datos_form["nombre"], anio, datos_form["grupo_codigo"], excluir_codigo=codigo_original):
            messagebox.showerror("Duplicado", "Ya existe otro producto con ese nombre y año en el grupo.", parent=top); return
        
        if datos_form["codigo"] != codigo_original and buscar_producto(datos_form["codigo"]):
            messagebox.showerror("Código duplicado", "Ya existe un producto con ese código.", parent=top); return
        
        if not buscar_investigador(datos_form["investigador_codigo"]) or not buscar_grupo(datos_form["grupo_codigo"]):
            messagebox.showerror("Relación inválida", "El investigador y el grupo deben existir.", parent=top); return
        
        with engine.begin() as conn:
            conn.execute(update(productos).where(productos.c.codigo == codigo_original).values(
                codigo=datos_form["codigo"], nombre=datos_form["nombre"], categoria=datos_form["categoria"],
                anio=anio, validacion=datos_form["validacion"], investigador_codigo=datos_form["investigador_codigo"],
                grupo_codigo=datos_form["grupo_codigo"]))
        cargar_estructuras_guardadas(); refrescar_todas_las_tablas(); top.destroy()

    tk.Button(top, text="Guardar cambios", command=guardar_cambios).pack(pady=12)

def siguiente_codigo(tabla, prefijo):
    with engine.connect() as conn:
        codigos = conn.execute(select(tabla.c.codigo).where(tabla.c.codigo.like(f"{prefijo}%"))).scalars().all()
    nums = [int(m.group(1)) for c in codigos if (m := re.search(r"(\d+)$", c))]
    return f"{prefijo}{(max(nums) + 1 if nums else 1):03d}"

def iniciar_interfaz_grafica():
    global root, tree_grupos, tree_inv, tree_prod, tree_multi, ent_buscar, combo_cat, combo_est, combo_anio, panel_der_dash, ent_anio, combo_ventana
    
    crear_tablas()
    
    with engine.connect() as conn:
        t_g = conn.execute(select(func.count()).select_from(grupos)).scalar()
        t_p = conn.execute(select(func.count()).select_from(productos)).scalar()

    if t_g > 0 or t_p > 0:
        resp = messagebox.askyesno("Persistencia", "Se encontraron datos de sesiones anteriores.\n\n¿Desea mantener los datos guardados?\n(Seleccione 'No' para iniciar desde cero y limpiar la base de datos)")
        if not resp:
            limpiar_base_datos()

    cargar_estructuras_guardadas()

    root = tk.Tk()
    root.title("PEA-i - Sistema de Gestión de Investigación (UPC)")
    root.geometry("1150x680")

    style = ttk.Style(root); style.theme_use("clam")
    for nombre, bg, hover in [("Primary","#0284c7","#0369a1"),("Success","#16a34a","#15803d"),("Danger","#dc2626","#b91c1c")]:
        style.configure(f"{nombre}.TButton", background=bg, foreground="white", font=("Segoe UI", 9, "bold"), padding=6)
        style.map(f"{nombre}.TButton", background=[("active", hover)])
    root.configure(bg="#f8fafc")
    style.configure("TNotebook", background="#f8fafc", borderwidth=0)
    style.configure("TNotebook.Tab", background="#e2e8f0", foreground="#334155", font=("Segoe UI", 9, "bold"), padding=[12, 6])
    style.map("TNotebook.Tab", background=[("selected", "#0f172a")], foreground=[("selected", "#ffffff")])

    banner = tk.Frame(root, bg="#0f172a", height=50); banner.pack(fill="x", side="top")
    tk.Label(banner, text="PEA-i | GESTIÓN DE INVESTIGACIÓN", font=("Segoe UI", 12, "bold"), bg="#0f172a", fg="#38bdf8").pack(side="left", padx=15, pady=10)

    notebook = ttk.Notebook(root); notebook.pack(fill="both", expand=True, padx=12, pady=12)

    # Pestaña 1: Productos
    frame_p = ttk.Frame(notebook); notebook.add(frame_p, text="Productos")
    frame_search = ttk.Frame(frame_p); frame_search.pack(fill="x", padx=5, pady=(5, 4))

    tk.Label(frame_search, text="Buscar:", font=("Segoe UI", 9, "bold"), bg="#f8fafc", fg="#0f172a").pack(side="left", padx=(2, 2))
    ent_buscar = tk.Entry(frame_search, font=("Segoe UI", 9), relief="solid", bd=1); ent_buscar.pack(side="left", fill="x", expand=True, padx=4, ipady=2)
    ent_buscar.bind("<KeyRelease>", lambda e: refrescar_todas_las_tablas())

    tk.Label(frame_search, text="Categoría:", font=("Segoe UI", 9, "bold"), bg="#f8fafc", fg="#0f172a").pack(side="left", padx=(8, 2))
    combo_cat = ttk.Combobox(frame_search, values=["Todas", "Artículo", "Libro / Capítulo", "Software", "Generica"], state="readonly", width=14)
    combo_cat.current(0); combo_cat.pack(side="left", padx=4)
    combo_cat.bind("<<ComboboxSelected>>", lambda e: refrescar_todas_las_tablas())

    tk.Label(frame_search, text="Ventana:", font=("Segoe UI", 9, "bold"), bg="#f8fafc", fg="#0f172a").pack(side="left", padx=(8, 2))
    combo_ventana = ttk.Combobox(frame_search, values=list(VENTANAS), state="readonly", width=14)
    combo_ventana.current(0)
    combo_ventana.pack(side="left", padx=4)
    combo_ventana.bind("<<ComboboxSelected>>", lambda e: refrescar_todas_las_tablas())

    tk.Label(frame_search, text="Año:", font=("Segoe UI", 9, "bold"), bg="#f8fafc", fg="#0f172a").pack(side="left", padx=(8, 2))
    ent_anio = tk.Entry(frame_search, font=("Segoe UI", 9), relief="solid", bd=1, width=8)
    ent_anio.insert(0, "Todos")
    ent_anio.pack(side="left", padx=4, ipady=2)
    ent_anio.bind("<KeyRelease>", lambda e: refrescar_todas_las_tablas())

    tk.Label(frame_search, text="Estado:", font=("Segoe UI", 9, "bold"), bg="#f8fafc", fg="#0f172a").pack(side="left", padx=(8, 2))
    combo_est = ttk.Combobox(frame_search, values=["Todos", "Activo", "Inactivo"], state="readonly", width=10)
    combo_est.current(0); combo_est.pack(side="left", padx=4)
    combo_est.bind("<<ComboboxSelected>>", lambda e: refrescar_todas_las_tablas())

    cols_p = ("Código", "Nombre", "Categoría", "Año", "Validación", "Investigador", "Estado")
    tree_prod = ttk.Treeview(frame_p, columns=cols_p, show="headings")
    tree_prod.tag_configure("evenrow", background="#ffffff"); tree_prod.tag_configure("oddrow", background="#f1f5f9")
    for col in cols_p:
        tree_prod.heading(col, text=col); tree_prod.column(col, width=115)
    tree_prod.pack(fill="both", expand=True, padx=5, pady=5)

    btn_bar_p = ttk.Frame(frame_p); btn_bar_p.pack(fill="x", pady=6)
    ttk.Button(btn_bar_p, text="Crear Producto", style="Success.TButton", command=lambda: abrir_formulario_producto(root)).pack(side="left", padx=3)
    ttk.Button(btn_bar_p, text="Modificar", command=modificar_producto_gui).pack(side="left", padx=3)
    ttk.Button(btn_bar_p, text="Activar", style="Success.TButton", command=activar_producto_gui).pack(side="left", padx=3)
    ttk.Button(btn_bar_p, text="Desactivar", command=desactivar_producto_gui).pack(side="left", padx=3)
    ttk.Button(btn_bar_p, text="Eliminar", style="Danger.TButton", command=eliminar_producto_gui).pack(side="left", padx=3)
    ttk.Button(btn_bar_p, text="Web Scraping", style="Primary.TButton", command=lambda: descargar_desde_url_gui(root)).pack(side="left", padx=3)
    ttk.Button(btn_bar_p, text="Importar CSV", style="Primary.TButton", command=lambda: importar_csv_gui(root)).pack(side="left", padx=3)
    ttk.Button(btn_bar_p, text="Eval. Minciencias 2024", style="Success.TButton", command=evaluar_grupo_seleccionado).pack(side="left", padx=3)
    ttk.Button(btn_bar_p, text="Deshacer (Pop Pila)", style="Danger.TButton", command=deshacer_ultimo_pila_gui).pack(side="right", padx=3)
    ttk.Button(btn_bar_p, text="Ver Pila/Cola", style="Primary.TButton", command=lambda: ver_estado_pila_cola_gui(root)).pack(side="right", padx=3)

    # Pestaña 2: Dashboard SIGIIP
    frame_dash = ttk.Frame(notebook); notebook.add(frame_dash, text="Dashboard SIGIIP")
    panel_der_dash = tk.Frame(frame_dash, bg="#f8fafc"); panel_der_dash.pack(side="top", fill="both", expand=True, padx=10, pady=10)
    btn_cpp_dash = tk.Frame(frame_dash, bg="#f8fafc"); btn_cpp_dash.pack(side="bottom", fill="x", padx=10, pady=10)
    ttk.Button(btn_cpp_dash, text="Ejecutar Motor C++ (Reporte en Consola)", style="Primary.TButton", command=ejecutar_procesador_cpp_gui).pack(anchor="center")

    # Pestaña 3: Grupos e Investigadores
    frame_gi = ttk.Frame(notebook); notebook.add(frame_gi, text="Grupos e Investigadores")
    tk.Label(frame_gi, text="GRUPOS DE INVESTIGACIÓN", font=("Segoe UI", 10, "bold"), bg="#f8fafc", fg="#0f172a").pack(anchor="w", padx=5, pady=(5, 2))
    tree_grupos = ttk.Treeview(frame_gi, columns=("Código", "Nombre", "Área", "Estado"), show="headings", height=5)
    for col in ("Código", "Nombre", "Área", "Estado"): tree_grupos.heading(col, text=col)
    tree_grupos.pack(fill="both", expand=True, padx=5, pady=2)

    tk.Label(frame_gi, text="INVESTIGADORES", font=("Segoe UI", 10, "bold"), bg="#f8fafc", fg="#0f172a").pack(anchor="w", padx=5, pady=(8, 2))
    cols_i = ("Código", "Nombre", "Grupos", "Estado")
    tree_inv = ttk.Treeview(frame_gi, columns=cols_i, show="headings", height=5)
    for col in cols_i: tree_inv.heading(col, text=col)
    tree_inv.pack(fill="both", expand=True, padx=5, pady=2)

    botones_g = ttk.Frame(frame_gi); botones_g.pack(fill="x", padx=5, pady=4)
    ttk.Button(botones_g, text="Crear grupo", command=lambda: gestionar_grupo_gui("crear")).pack(side="left", padx=2)
    ttk.Button(botones_g, text="Modificar grupo", command=lambda: gestionar_grupo_gui("modificar")).pack(side="left", padx=2)
    ttk.Button(botones_g, text="Desactivar grupo", command=lambda: gestionar_grupo_gui("desactivar")).pack(side="left", padx=2)
    ttk.Button(botones_g, text="Eliminar grupo", command=lambda: gestionar_grupo_gui("eliminar")).pack(side="left", padx=2)
    ttk.Button(botones_g, text="Crear investigador", command=lambda: gestionar_investigador_gui("crear")).pack(side="left", padx=2)
    ttk.Button(botones_g, text="Modificar investigador", command=lambda: gestionar_investigador_gui("modificar")).pack(side="left", padx=2)
    ttk.Button(botones_g, text="Desactivar investigador", command=lambda: gestionar_investigador_gui("desactivar")).pack(side="left", padx=2)
    ttk.Button(botones_g, text="Activar grupo", command=lambda: gestionar_grupo_gui("activar")).pack(side="left", padx=2)
    ttk.Button(botones_g, text="Activar investigador", command=lambda: gestionar_investigador_gui("activar")).pack(side="left", padx=2)
    ttk.Button(botones_g, text="Eliminar investigador", command=lambda: gestionar_investigador_gui("eliminar")).pack(side="left", padx=2)

    # Pestaña 4: Multilista Jerárquica
    frame_m = ttk.Frame(notebook); notebook.add(frame_m, text="Vista de la relacion entre datos")
    tk.Label(frame_m, text="ESTRUCTURA JERÁRQUICA: GRUPO ➔ INVESTIGADOR ➔ PRODUCTO", font=("Segoe UI", 10, "bold"), bg="#f8fafc", fg="#0f172a").pack(anchor="w", padx=5, pady=(8, 4))
    tree_multi = ttk.Treeview(frame_m, columns=("Código / ID", "Tipo / Detalle", "Información Adicional"), show="tree headings")
    tree_multi.heading("#0", text="Jerarquía Multilista")
    tree_multi.heading("Código / ID", text="Código")
    tree_multi.heading("Tipo / Detalle", text="Tipo")
    tree_multi.heading("Información Adicional", text="Info")
    tree_multi.pack(fill="both", expand=True, padx=5, pady=5)

    refrescar_todas_las_tablas()
    root.mainloop()

if __name__ == "__main__":
    iniciar_interfaz_grafica()