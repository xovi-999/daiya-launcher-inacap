-- Esquema de la base de datos local de Daiya Launcher (SQLite).
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS instancia (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre            TEXT    NOT NULL UNIQUE,
    version_minecraft TEXT    NOT NULL,
    loader            TEXT    NOT NULL CHECK (loader IN ('vanilla', 'fabric')),
    version_loader    TEXT,
    ram_mb            INTEGER NOT NULL DEFAULT 4096 CHECK (ram_mb BETWEEN 1024 AND 32768),
    ruta_java         TEXT,
    ruta              TEXT    NOT NULL,
    ultima_vez        TEXT
);

CREATE TABLE IF NOT EXISTS addon (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    instancia_id INTEGER NOT NULL REFERENCES instancia(id) ON DELETE CASCADE,
    tipo         TEXT    NOT NULL CHECK (tipo IN ('mod', 'shader', 'resourcepack')),
    nombre       TEXT    NOT NULL,
    version      TEXT    NOT NULL DEFAULT '',
    id_externo   TEXT    NOT NULL DEFAULT '',
    archivo      TEXT    NOT NULL,
    hash_sha1    TEXT    NOT NULL,
    activo       INTEGER NOT NULL DEFAULT 1,
    UNIQUE (instancia_id, archivo)
);

CREATE INDEX IF NOT EXISTS idx_addon_instancia ON addon(instancia_id);

CREATE TABLE IF NOT EXISTS configuracion (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);
