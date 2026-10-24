#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <sstream>
#include <cstdlib>
#include <cctype>
#include <cmath>
#include <algorithm>

using namespace std;

struct Producto {
    string codigo, nombre, categoria, validacion, estado, grupo_codigo, investigador_codigo;
    int anio = 0;
};

struct Investigador {
    string codigo;
    vector<Producto> productos;
};

struct Grupo {
    string codigo;
    vector<Investigador> investigadores;
};

string extraerValor(const string& bloque, const string& clave) {
    string buscado = "\"" + clave + "\"";
    size_t pos = bloque.find(buscado);
    if (pos == string::npos) return "";
    pos = bloque.find(':', pos + buscado.size());
    if (pos == string::npos) return "";
    pos++;
    while (pos < bloque.size() && isspace((unsigned char)bloque[pos])) pos++;
    if (pos >= bloque.size()) return "";

    string valor;
    if (bloque[pos] == '"') {
        pos++;
        while (pos < bloque.size()) {
            char c = bloque[pos++];
            if (c == '"') break;
            if (c == '\\' && pos < bloque.size()) {
                char e = bloque[pos++];
                if (e == 'n') valor += '\n';
                else if (e == 't') valor += '\t';
                else if (e == 'r') valor += '\r';
                else valor += e;
            } else valor += c;
        }
    } else {
        size_t inicio = pos;
        while (pos < bloque.size() && bloque[pos] != ',' && bloque[pos] != '}' &&
               !isspace((unsigned char)bloque[pos])) pos++;
        valor = bloque.substr(inicio, pos - inicio);
    }
    return valor;
}

bool estaActivo(const Producto& p) {
    string estado = p.estado;
    transform(estado.begin(), estado.end(), estado.begin(),
              [](unsigned char c){ return (char)tolower(c); });
    return estado.empty() || estado == "activo";
}

struct Conteo {
    int top = 0, a = 0, b = 0, ap = 0, dpc = 0, fra = 0, frb = 0, activos = 0;
    double indicador = 0.0;
};

Conteo calcularIndicador(const vector<Producto>& productos, int numAutores, int numGrupos) {
    Conteo c;
    for (const Producto& p : productos) {
        if (!estaActivo(p)) continue;
        c.activos++;
        string cat = p.categoria;
        transform(cat.begin(), cat.end(), cat.begin(),
                  [](unsigned char x){ return (char)toupper(x); });
        replace(cat.begin(), cat.end(), ' ', '_');

        if (cat.find("OPEN_A1") != string::npos || cat.find("ART_A1") != string::npos ||
            cat.find("NC.TOP") != string::npos || cat.find("PATENTE") != string::npos ||
            cat == "TOP") c.top++;
        else if (cat.find("OPEN_A2") != string::npos || cat.find("ART_A2") != string::npos ||
                 cat.find("NC.A") != string::npos) c.a++;
        else if (cat.find("ART_B") != string::npos || cat.find("ART_C") != string::npos ||
                 cat.find("NC.B") != string::npos) c.b++;
        else if (cat == "AP" || cat.find("APROPIACION") != string::npos) c.ap++;
        else if (cat.find("DPC") != string::npos || cat.find("DIVULGACION") != string::npos) c.dpc++;
        else if (cat.find("FR_A") != string::npos || cat.find("TESIS_DOC") != string::npos ||
                 cat.find("TESIS_MAE") != string::npos || cat.find("FORMACION_POSGRADO") != string::npos) c.fra++;
        else c.frb++;
    }

    double denominador = c.activos > 1 ? (double)(c.activos - 1) : 1.0;
    double cohe = numAutores / denominador;
    double coop = numGrupos / denominador;
    c.indicador = 3.7*c.top + 2.3*c.a + 0.4*c.b + 1.5*c.ap +
                  0.5*c.dpc + 1.0*c.fra + 0.2*c.frb + 0.1*cohe + 0.3*coop;
    return c;
}

void imprimirDetalle(const Conteo& c) {
    cout << "  Nc.Top (peso 3.7): " << c.top << "\n";
    cout << "  Nc.A   (peso 2.3): " << c.a << "\n";
    cout << "  Nc.B   (peso 0.4): " << c.b << "\n";
    cout << "  AP     (peso 1.5): " << c.ap << "\n";
    cout << "  DPC    (peso 0.5): " << c.dpc << "\n";
    cout << "  Fr.A   (peso 1.0): " << c.fra << "\n";
    cout << "  Fr.B   (peso 0.2): " << c.frb << "\n";
}

bool cargarJSON(const string& ruta, vector<Producto>& productos) {
    ifstream archivo(ruta, ios::binary);
    if (!archivo) {
        cerr << "Error: no se pudo abrir " << ruta << "\n";
        return false;
    }
    string contenido((istreambuf_iterator<char>(archivo)), istreambuf_iterator<char>());
    size_t pos = 0;
    while ((pos = contenido.find('{', pos)) != string::npos) {
        size_t fin = pos;
        bool enCadena = false, escape = false;
        int profundidad = 0;
        for (; fin < contenido.size(); ++fin) {
            char ch = contenido[fin];
            if (escape) { escape = false; continue; }
            if (enCadena && ch == '\\') { escape = true; continue; }
            if (ch == '"') { enCadena = !enCadena; continue; }
            if (!enCadena && ch == '{') profundidad++;
            if (!enCadena && ch == '}') {
                profundidad--;
                if (profundidad == 0) break;
            }
        }
        if (fin >= contenido.size()) break;
        string bloque = contenido.substr(pos, fin-pos+1);
        Producto p;
        p.codigo = extraerValor(bloque, "codigo");
        p.nombre = extraerValor(bloque, "nombre");
        p.categoria = extraerValor(bloque, "categoria");
        p.validacion = extraerValor(bloque, "validacion");
        p.estado = extraerValor(bloque, "estado");
        p.grupo_codigo = extraerValor(bloque, "grupo_codigo");
        p.investigador_codigo = extraerValor(bloque, "investigador_codigo");
        string anio = extraerValor(bloque, "anio");
        p.anio = anio.empty() ? 0 : atoi(anio.c_str());
        if (p.estado.empty()) p.estado = "Activo";
        if (p.grupo_codigo.empty()) p.grupo_codigo = "G-001";
        if (p.investigador_codigo.empty()) p.investigador_codigo = "INV-001";
        if (!p.codigo.empty()) productos.push_back(p);
        pos = fin + 1;
    }
    return true;
}

int main(int argc, char* argv[]) {
    string ruta = argc > 1 ? argv[1] : "datos_entrada.json";
    vector<Producto> productos;
    if (!cargarJSON(ruta, productos)) return 1;

    vector<Grupo> grupos;
    for (const Producto& p : productos) {
        auto itG = find_if(grupos.begin(), grupos.end(), [&](const Grupo& g){ return g.codigo == p.grupo_codigo; });
        if (itG == grupos.end()) {
            Grupo nuevo;
            nuevo.codigo = p.grupo_codigo;
            grupos.push_back(nuevo);
            itG = grupos.end() - 1;
        }
        auto itI = find_if(itG->investigadores.begin(), itG->investigadores.end(),
                           [&](const Investigador& i){ return i.codigo == p.investigador_codigo; });
        if (itI == itG->investigadores.end()) {
            Investigador nuevo;
            nuevo.codigo = p.investigador_codigo;
            itG->investigadores.push_back(nuevo);
            itI = itG->investigadores.end() - 1;
        }
        itI->productos.push_back(p);
    }

    cout << "============================================================\n";
    cout << " INDICADOR DE PRODUCCION CIENTIFICA - PARCIAL EdD\n";
    cout << "============================================================\n";
    cout << "Productos leidos del JSON: " << productos.size() << "\n";

    for (const Grupo& g : grupos) {
        vector<Producto> productosGrupo;
        for (const Investigador& inv : g.investigadores)
            productosGrupo.insert(productosGrupo.end(), inv.productos.begin(), inv.productos.end());

        Conteo cg = calcularIndicador(productosGrupo, (int)g.investigadores.size(), 1);
        cout << "\n------------------------------------------------------------\n";
        cout << "GRUPO: " << g.codigo << "\n";
        cout << "Investigadores asociados: " << g.investigadores.size() << "\n";
        cout << "Productos registrados: " << productosGrupo.size() << "\n";
        cout << "DETALLE DEL INDICADOR DEL GRUPO\n";
        imprimirDetalle(cg);
        cout << "INDICADOR FINAL DEL GRUPO: " << cg.indicador << "\n";

        cout << "\nINDICADOR POR INVESTIGADOR\n";
        for (const Investigador& inv : g.investigadores) {
            Conteo ci = calcularIndicador(inv.productos, 1, 1);
            cout << "\nInvestigador: " << inv.codigo << "\n";
            cout << "Productos registrados: " << inv.productos.size()
                 << " | Productos activos: " << ci.activos << "\n";
            imprimirDetalle(ci);
            cout << "INDICADOR INDIVIDUAL: " << ci.indicador << "\n";
        }
    }

    cout << "\nNota: solo se ponderan productos activos. Cohesión y cooperación usan los valores disponibles en los datos.\n";
    return 0;
}
