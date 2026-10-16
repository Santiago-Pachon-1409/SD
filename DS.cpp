#include <iostream>
#include <fstream>
#include <string>
#include <sstream>
#include <cstring>
#include <cstdlib>
#include <algorithm>
#include <cmath>
#include <cctype>

using namespace std;

// =========================================================================
// ARQUITECTURA C++ - MOTOR DE DATOS PROCEDIMENTAL (SIN POO)
// Multilista enlazada dinámica: Grupo -> Investigador -> Producto
// Adaptado al Modelo Minciencias 2024 (Ventanas y Cálculo I_TP)
// =========================================================================

struct NodoProducto {
    char codigo[50];
    char nombre[150];
    char categoria[50];
    int anio;
    char validacion[50];
    char estado[20];
    NodoProducto* sig;
};

struct NodoInvestigador {
    char codigo[50];
    NodoProducto* productos;
    NodoInvestigador* sig;
};

struct NodoGrupo {
    char codigo[50];
    NodoInvestigador* investigadores;
    NodoGrupo* sig;
};

NodoGrupo* buscarOAgregarGrupo(NodoGrupo** cabeza, const char* g_cod) {
    NodoGrupo* act = *cabeza;
    while (act != NULL) {
        if (strcmp(act->codigo, g_cod) == 0) return act;
        act = act->sig;
    }
    NodoGrupo* nuevo = new NodoGrupo();
    strncpy(nuevo->codigo, g_cod, 49); nuevo->codigo[49] = '\0';
    nuevo->investigadores = NULL;
    nuevo->sig = *cabeza;
    *cabeza = nuevo;
    return nuevo;
}

NodoInvestigador* buscarOAgregarInvestigador(NodoInvestigador** cabeza, const char* inv_cod) {
    NodoInvestigador* act = *cabeza;
    while (act != NULL) {
        if (strcmp(act->codigo, inv_cod) == 0) return act;
        act = act->sig;
    }
    NodoInvestigador* nuevo = new NodoInvestigador();
    strncpy(nuevo->codigo, inv_cod, 49); nuevo->codigo[49] = '\0';
    nuevo->productos = NULL;
    nuevo->sig = *cabeza;
    *cabeza = nuevo;
    return nuevo;
}

void agregarProductoML(NodoGrupo** multilista, const char* g_cod, const char* inv_cod, 
                       const char* p_cod, const char* nom, const char* cat, int anio, const char* val, const char* estado) {
    NodoGrupo* grp = buscarOAgregarGrupo(multilista, g_cod);
    NodoInvestigador* inv = buscarOAgregarInvestigador(&(grp->investigadores), inv_cod);

    NodoProducto* nuevo = new NodoProducto();
    strncpy(nuevo->codigo, p_cod, 49); nuevo->codigo[49] = '\0';
    strncpy(nuevo->nombre, nom, 149); nuevo->nombre[149] = '\0';
    strncpy(nuevo->categoria, cat, 49); nuevo->categoria[49] = '\0';
    nuevo->anio = anio;
    strncpy(nuevo->validacion, val, 49); nuevo->validacion[49] = '\0';
    strncpy(nuevo->estado, estado, 19); nuevo->estado[19] = '\0';

    // Evita duplicar un producto si el archivo contiene el mismo código más de una vez.
    NodoProducto* existente = inv->productos;
    while (existente != NULL) {
        if (strcmp(existente->codigo, p_cod) == 0) {
            delete nuevo;
            return;
        }
        existente = existente->sig;
    }

    nuevo->sig = inv->productos;
    inv->productos = nuevo;
}

void liberarMultilista(NodoGrupo* cabezaGrupo) {
    while (cabezaGrupo != NULL) {
        NodoInvestigador* actInv = cabezaGrupo->investigadores;
        while (actInv != NULL) {
            NodoProducto* actProd = actInv->productos;
            while (actProd != NULL) {
                NodoProducto* tmpP = actProd;
                actProd = actProd->sig;
                delete tmpP;
            }
            NodoInvestigador* tmpI = actInv;
            actInv = actInv->sig;
            delete tmpI;
        }
        NodoGrupo* tmpG = cabezaGrupo;
        cabezaGrupo = cabezaGrupo->sig;
        delete tmpG;
    }
}

string extraerValor(const string& bloque, const string& clave) {
    const string buscado = "\"" + clave + "\"";
    size_t pos = bloque.find(buscado);
    if (pos == string::npos) return "";
    pos = bloque.find(':', pos + buscado.size());
    if (pos == string::npos) return "";
    pos++;
    while (pos < bloque.size() && isspace(static_cast<unsigned char>(bloque[pos]))) pos++;
    if (pos >= bloque.size()) return "";

    string valor;
    if (bloque[pos] == '\"') {
        pos++;
        while (pos < bloque.size()) {
            char c = bloque[pos++];
            if (c == '\"') break;
            if (c == '\\' && pos < bloque.size()) {
                char escapado = bloque[pos++];
                if (escapado == 'n') valor += '\n';
                else if (escapado == 't') valor += '\t';
                else if (escapado == 'r') valor += '\r';
                else valor += escapado;
            } else valor += c;
        }
    } else {
        size_t inicio = pos;
        while (pos < bloque.size() && bloque[pos] != ',' && bloque[pos] != '}' && !isspace(static_cast<unsigned char>(bloque[pos]))) pos++;
        valor = bloque.substr(inicio, pos - inicio);
    }
    return valor;
}

void cargarJSONEnMultilista(const char* rutaArchivo, NodoGrupo** multilista) {
    ifstream archivo(rutaArchivo);
    if (!archivo.is_open()) {
        cout << "[Error C++] No se pudo abrir el archivo de entrada JSON: " << rutaArchivo << endl;
        return;
    }
    string contenido((istreambuf_iterator<char>(archivo)), istreambuf_iterator<char>());
    archivo.close();

    size_t pos = 0;
    while ((pos = contenido.find('{', pos)) != string::npos) {
        size_t finObj = pos;
        bool dentroCadena = false;
        bool escape = false;
        int profundidad = 0;
        for (; finObj < contenido.size(); finObj++) {
            char c = contenido[finObj];
            if (escape) { escape = false; continue; }
            if (dentroCadena && c == '\\') { escape = true; continue; }
            if (c == '\"') { dentroCadena = !dentroCadena; continue; }
            if (!dentroCadena && c == '{') profundidad++;
            if (!dentroCadena && c == '}') {
                profundidad--;
                if (profundidad == 0) break;
            }
        }
        if (finObj >= contenido.size()) break;
        string bloque = contenido.substr(pos, finObj - pos + 1);

        string cod = extraerValor(bloque, "codigo");
        string nom = extraerValor(bloque, "nombre");
        string cat = extraerValor(bloque, "categoria");
        string anioStr = extraerValor(bloque, "anio");
        string val = extraerValor(bloque, "validacion");
        string g_cod = extraerValor(bloque, "grupo_codigo");
        string inv_cod = extraerValor(bloque, "investigador_codigo");
        string estado = extraerValor(bloque, "estado");
        if (estado.empty()) estado = "Activo";

        int anio = anioStr.empty() ? 0 : atoi(anioStr.c_str());
        if (g_cod.empty()) g_cod = "G-001";
        if (inv_cod.empty()) inv_cod = "INV-001";

        if (!cod.empty()) {
            agregarProductoML(multilista, g_cod.c_str(), inv_cod.c_str(), 
                              cod.c_str(), nom.c_str(), cat.c_str(), anio, val.c_str(), estado.c_str());
        }
        pos = finObj + 1;
    }
}

void imprimirBarraHistograma(int valor, int maxValor, int anchoMax = 20) {
    int barras = (maxValor > 0) ? (valor * anchoMax / maxValor) : 0;
    if (valor > 0 && barras == 0) barras = 1;
    for (int i = 0; i < barras; i++) cout << "#";
    cout << " (" << valor << ")" << endl;
}

double calcularItpCplusplus(int numProductos, int periodo) {
    if (periodo <= 0) return 0.0;
    return log(((double)numProductos / periodo) + 1.0);
}

void generarReporteEstadistico(NodoGrupo* multilista) {
    int totalArticulos = 0, totalLibros = 0, totalSoftware = 0, totalGenericos = 0;
    int totalProductos = 0;

    NodoGrupo* g = multilista;
    while (g != NULL) {
        NodoInvestigador* inv = g->investigadores;
        while (inv != NULL) {
            NodoProducto* p = inv->productos;
            while (p != NULL) {
                if (string(p->estado) == "Activo") {
                totalProductos++;
                string c = p->categoria;
                if (c.find("Artículo") != string::npos || c.find("Articulo") != string::npos) totalArticulos++;
                else if (c.find("Libro") != string::npos || c.find("Capítulo") != string::npos) totalLibros++;
                else if (c.find("Software") != string::npos) totalSoftware++;
                else totalGenericos++;
                }
                p = p->sig;
            }
            inv = inv->sig;
        }
        g = g->sig;
    }

    int maxCat = totalArticulos;
    if (totalLibros > maxCat) maxCat = totalLibros;
    if (totalSoftware > maxCat) maxCat = totalSoftware;
    if (totalGenericos > maxCat) maxCat = totalGenericos;

    // Cálculo del indicador logarítmico I_TP (Periodo base de 7 años)
    double itpCalculado = calcularItpCplusplus(totalProductos, 7);

    cout << "==================================================" << endl;
    cout << "   REPORTE ESTADISTICO & MINCIENCIAS 2024 (C++)   " << endl;
    cout << "==================================================" << endl << endl;

    cout << "--------------------------------------------------" << endl;
    cout << " 1. HISTOGRAMA DE PRODUCTOS POR CATEGORIA         " << endl;
    cout << "--------------------------------------------------" << endl;
    cout << " Articulos    | "; imprimirBarraHistograma(totalArticulos, maxCat);
    cout << " Libros/Cap.  | "; imprimirBarraHistograma(totalLibros, maxCat);
    cout << " Software     | "; imprimirBarraHistograma(totalSoftware, maxCat);
    cout << " Otr/Generico | "; imprimirBarraHistograma(totalGenericos, maxCat);
    cout << endl;

    cout << "--------------------------------------------------" << endl;
    cout << " 2. HISTOGRAMA DE PRODUCCION POR INVESTIGADOR    " << endl;
    cout << "--------------------------------------------------" << endl;
    
    int maxInvCant = 0;
    g = multilista;
    while (g != NULL) {
        NodoInvestigador* inv = g->investigadores;
        while (inv != NULL) {
            int cnt = 0;
            NodoProducto* p = inv->productos;
            while (p != NULL) { if (string(p->estado) == "Activo") cnt++; p = p->sig; }
            if (cnt > maxInvCant) maxInvCant = cnt;
            inv = inv->sig;
        }
        g = g->sig;
    }

    g = multilista;
    while (g != NULL) {
        NodoInvestigador* inv = g->investigadores;
        while (inv != NULL) {
            int cnt = 0;
            NodoProducto* p = inv->productos;
            while (p != NULL) { if (string(p->estado) == "Activo") cnt++; p = p->sig; }

            string labelInv = inv->codigo;
            while (labelInv.length() < 12) labelInv += " ";
            cout << " " << labelInv << " | ";
            imprimirBarraHistograma(cnt, maxInvCant);
            inv = inv->sig;
        }
        g = g->sig;
    }

    cout << "--------------------------------------------------" << endl;
    cout << " 3. INDICADOR LOGARITMICO MINCIENCIAS (I_TP)      " << endl;
    cout << "--------------------------------------------------" << endl;
    cout << " - Total de Productos Analizados : " << totalProductos << endl;
    cout << " - Periodo de Observacion Base   : 7 Anos" << endl;
    cout << " - Indicador I_TP Calculado      : " << itpCalculado << endl;
    cout << " STATUS: Procesamiento procedural exitoso." << endl;
    cout << "==================================================" << endl;
}

int main(int argc, char* argv[]) {
    const char* rutaJSON = (argc > 1) ? argv[1] : "datos_entrada.json";
    NodoGrupo* multilista = NULL;

    cargarJSONEnMultilista(rutaJSON, &multilista);
    generarReporteEstadistico(multilista);
    liberarMultilista(multilista);

    return 0;
}