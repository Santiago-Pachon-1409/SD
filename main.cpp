#include <iostream>
#include "sqlite3.h"

int main() {
    sqlite3* db;
    if (sqlite3_open("pea.db", &db) != SQLITE_OK) {
        std::cerr << "Error: " << sqlite3_errmsg(db) << "\n";
        return 1;
    }
    char* err = nullptr;
    const char* sql =
        "CREATE TABLE IF NOT EXISTS grupo("
        "codigo TEXT PRIMARY KEY, nombre TEXT, activo INTEGER DEFAULT 1);";
    if (sqlite3_exec(db, sql, nullptr, nullptr, &err) != SQLITE_OK) {
        std::cerr << "SQL: " << err << "\n";
        sqlite3_free(err);
    } else {
        std::cout << "BD lista: pea.db\n";
    }
    sqlite3_close(db);
    return 0;
}
