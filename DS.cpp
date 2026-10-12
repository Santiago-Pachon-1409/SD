#include <iostream>
#include <fstream>
#include <string>
#include <sstream>
#include <cstring>
#include <cstdlib>
#include <algorithm>

using namespace std;

struct NodoProducto {
    char codigo[50];
    char nombre[150];
    char categoria[50];
    int anio;
    char validacion[50];
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

// =========================================================================
// FUNCIONES PROCEDIMENTALES DE MANEJO DE LA MULTILISTA
// =========================================================================

NodoGrupo* buscarOAgregarGrupo(NodoGrupo** cabeza, const char* g_cod) {
    NodoGrupo* act = *cabeza;
    while (act != NULL) {
        if (strcmp(act->codigo, g_cod) == 0) {
            return act;
        }
        act = act->sig;
    }
    NodoGrupo* nuevo = new NodoGrupo();
    strncpy(nuevo->codigo, g_cod, 49);
    nuevo->codigo[49] = '\0';
    nuevo->investigadores = NULL;
    nuevo->sig = *cabeza;
    *cabeza = nuevo;
    return nuevo;
}

NodoInvestigador* buscarOAgregarInvestigador(NodoInvestigador** cabeza, const char* inv_cod) {
    NodoInvestigador* act = *cabeza;
    while (act != NULL) {
        if (strcmp(act->codigo, inv_cod) == 0) {
            return act;
        }
        act = act->sig;
    }
    NodoInvestigador* nuevo = new NodoInvestigador();
    strncpy(nuevo->codigo, inv_cod, 49);
    nuevo->codigo[49] = '\0';
    nuevo->productos = NULL;
    nuevo->sig = *cabeza;
    *cabeza = nuevo;
    return nuevo;
}

void agregarProductoML(NodoGrupo** multilista, const char* g_cod, const char* inv_cod, 
                       const char* p_cod, const char* nom, const char* cat, int anio, const char* val) {
    NodoGrupo* grp = buscarOAgregarGrupo(multilista, g_cod);
    NodoInvestigador* inv = buscarOAgregarInvestigador(&(grp->investigadores), inv_cod);

    NodoProducto* nuevo = new NodoProducto();
    strncpy(nuevo->codigo, p_cod, 49); nuevo->codigo[49] = '\0';
    strncpy(nuevo->nombre, nom, 149); nuevo->nombre[149] = '\0';
    strncpy(nuevo->categoria, cat, 49); nuevo->categoria[49] = '\0';
    nuevo->anio = anio;
    strncpy(nuevo->validacion, val, 49); nuevo->validacion[49] = '\0';
    
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

// =========================================================================
// PARSER PROCEDIMENTAL DE JSON
// =========================================================================

string extraerValor(const string& bloque, const string& clave) {
    size_t posClave = bloque.find("\"" + clave + "\"");
    if (posClave == string::npos) return "";

    size_t posDosPuntos = bloque.find(":", posClave);
    if (posDosPuntos == string::npos) return "";

    size_t inicio = posDosPuntos + 1;
    while (inicio < bloque.size() && (bloque[inicio] == ' ' || bloque[inicio] == '\"')) {
        inicio++;
    }

    size_t fin = inicio;
    if (bloque[posDosPuntos + 1] == ' ' && bloque[posDosPuntos + 2] == '\"') {
        fin = bloque.find("\"", inicio);
    } else {
        while (fin < bloque.size() && (isdigit(bloque[fin]) || bloque[fin] == '-')) {
            fin++;
        }
    }

    if (fin == string::npos) return "";
    return bloque.substr(inicio, fin - inicio);
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
        size_t finObj = contenido.find('}', pos);
        if (finObj == string::npos) break;

        string bloque = contenido.substr(pos, finObj - pos + 1);

        string cod = extraerValor(bloque, "codigo");
        string nom = extraerValor(bloque, "nombre");
        string cat = extraerValor(bloque, "categoria");
        string anioStr = extraerValor(bloque, "anio");
        string val = extraerValor(bloque, "validacion");
        string g_cod = extraerValor(bloque, "grupo_codigo");
        string inv_cod = extraerValor(bloque, "investigador_codigo");

        int anio = anioStr.empty() ? 0 : atoi(anioStr.c_str());
        if (g_cod.empty()) g_cod = "G-001";
        if (inv_cod.empty()) inv_cod = "INV-001";

        if (!cod.empty()) {
            agregarProductoML(multilista, g_cod.c_str(), inv_cod.c_str(), 
                              cod.c_str(), nom.c_str(), cat.c_str(), anio, val.c_str());
        }

        pos = finObj + 1;
    }
}

// =========================================================================
// RENDERIZADO DE HISTOGRAMAS EN FORMATO ASCII
// =========================================================================

void imprimirBarraHistograma(int valor, int maxValor, int anchoMax = 20) {
    int barras = (maxValor > 0) ? (valor * anchoMax / maxValor) : 0;
    if (valor > 0 && barras == 0) barras = 1;

    for (int i = 0; i < barras; i++) {
        cout << "█";
    }
    cout << " (" << valor << ")" << endl;
}

// =========================================================================
// CÁLCULO ESTADÍSTICO Y GENERACIÓN DE REPORTES
// =========================================================================

void generarReporteEstadistico(NodoGrupo* multilista) {
    int totalArticulos = 0, totalLibros = 0, totalSoftware = 0, totalGenericos = 0;
    int totalProductos = 0;

    NodoGrupo* g = multilista;
    while (g != NULL) {
        NodoInvestigador* inv = g->investigadores;
        while (inv != NULL) {
            NodoProducto* p = inv->productos;
            while (p != NULL) {
                totalProductos++;
                
                string c = p->categoria;
                if (c.find("Artículo") != string::npos || c.find("Articulo") != string::npos) totalArticulos++;
                else if (c.find("Libro") != string::npos || c.find("Capítulo") != string::npos) totalLibros++;
                else if (c.find("Software") != string::npos) totalSoftware++;
                else totalGenericos++;

                p = p->sig;
            }
            inv = inv->sig;
        }
        g = g->sig;
    }

  int maxCat = totalArticulos;
  
    if (totalLibros > maxCat) {
        maxCat = totalLibros;
    }
    if (totalSoftware > maxCat) {
        maxCat = totalSoftware;
    }
    if (totalGenericos > maxCat) {
        maxCat = totalGenericos;
    }

    cout << "==================================================" << endl;
    cout << "   REPORTE ESTADÍSTICO CON HISTOGRAMAS (C++)      " << endl;
    cout << "==================================================" << endl << endl;

    // --------------------------------------------------
    // HISTOGRAMA 1: POR CATEGORÍA
    // --------------------------------------------------
    cout << "--------------------------------------------------" << endl;
    cout << " 1. HISTOGRAMA DE PRODUCTOS POR CATEGORÍA         " << endl;
    cout << "--------------------------------------------------" << endl;
    cout << " Artículos    | "; imprimirBarraHistograma(totalArticulos, maxCat);
    cout << " Libros/Cap.  | "; imprimirBarraHistograma(totalLibros, maxCat);
    cout << " Software     | "; imprimirBarraHistograma(totalSoftware, maxCat);
    cout << " Otr/Genérico | "; imprimirBarraHistograma(totalGenericos, maxCat);
    cout << endl;

    // --------------------------------------------------
    // HISTOGRAMA 2: POR INVESTIGADOR
    // --------------------------------------------------
    cout << "--------------------------------------------------" << endl;
    cout << " 2. HISTOGRAMA DE PRODUCCIÓN POR INVESTIGADOR    " << endl;
    cout << "--------------------------------------------------" << endl;
    
    int maxInvCant = 0;
    g = multilista;
    while (g != NULL) {
        NodoInvestigador* inv = g->investigadores;
        while (inv != NULL) {
            int cnt = 0;
            NodoProducto* p = inv->productos;
            while (p != NULL) { cnt++; p = p->sig; }
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
            while (p != NULL) { cnt++; p = p->sig; }

            string labelInv = inv->codigo;
            while (labelInv.length() < 12) labelInv += " ";

            cout << " " << labelInv << " | ";
            imprimirBarraHistograma(cnt, maxInvCant);

            inv = inv->sig;
        }
        g = g->sig;
    }

    // Exportación a JSON para Pandas
    ofstream archivoOut("resultados_cpp.json");
    if (archivoOut.is_open()) {
        archivoOut << "[\n";
        archivoOut << "  {\"categoria\": \"Artículos\", \"cantidad\": " << totalArticulos << "},\n";
        archivoOut << "  {\"categoria\": \"Libros/Capítulos\", \"cantidad\": " << totalLibros << "},\n";
        archivoOut << "  {\"categoria\": \"Software\", \"cantidad\": " << totalSoftware << "},\n";
        archivoOut << "  {\"categoria\": \"Genericos\", \"cantidad\": " << totalGenericos << "}\n";
        archivoOut << "]\n";
        archivoOut.close();
    }

    cout << "--------------------------------------------------" << endl;
    cout << " TOTAL PRODUCTOS ANALIZADOS: " << totalProductos << endl;
    cout << " STATUS: Procesamiento exitoso." << endl;
    cout << "==================================================" << endl;
}

int main(int argc, char* argv[]) {
    const char* rutaJSON = "datos_entrada.json";
    if (argc > 1) {
        rutaJSON = argv[1];
    }

    NodoGrupo* multilista = NULL;

    cargarJSONEnMultilista(rutaJSON, &multilista);
    generarReporteEstadistico(multilista);
    liberarMultilista(multilista);

    return 0;
}