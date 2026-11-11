# Daiya Launcher

Launcher de escritorio para **Minecraft Java Edition** que permite al jugador crear instancias y
agregar sus propios **mods, shaders y resource packs** arrastrando el archivo a la ventana. Antes de
instalar, el launcher valida la compatibilidad con la versión de la instancia y avisa si falta una
dependencia (por ejemplo, Fabric API o Iris).

Proyecto académico de la asignatura **TI3043 Ingeniería de Software** (INACAP). No está afiliado a
Mojang Studios ni a Microsoft. Requiere una cuenta legítima de Minecraft.

## Requisitos

- Python 3.11 o superior (probado con 3.12 y 3.13)
- Windows 10/11 o Linux

## Instalación y ejecución

```bash
python -m venv .venv
.venv\Scripts\activate          # en Linux: source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Para iniciar sesión con Microsoft se debe registrar una aplicación en Azure, solicitar el permiso de
la API de Minecraft y definir la variable de entorno `DAIYA_AZURE_CLIENT_ID`.

Al crear una instancia se ofrecen todas las versiones publicadas por Mojang (releases y, si se
marca, snapshots, beta y alpha). La lista se descarga al iniciar y se guarda en `versiones.json`
para usarla sin internet; con Fabric solo aparecen las versiones que Fabric soporta (1.14 o superior).

Mientras ese permiso no se obtiene, el botón **Iniciar sesión → Jugar sin conexión** crea un perfil
local (nombre de 3 a 16 caracteres: letras, números o guion bajo). Ese perfil sirve para un jugador
y LAN, no entra a servidores oficiales ni a Realms y no guarda ningún secreto. Es una decisión
académica documentada en el informe: el EULA de Minecraft exige haber comprado el juego, por lo que
se recomienda usarlo solo si se tiene Minecraft Java Edition.

## Pruebas

```bash
pip install -r requirements-dev.txt
pytest --cov=daiya                      # pruebas unitarias, de integración y de interfaz
python -m herramientas.benchmark        # métricas de rendimiento -> reportes/metricas.json
python -m herramientas.capturas         # capturas de la interfaz con datos de prueba
```

## Estructura

```
daiya/
  core/        modelos, add-ons (Mod, Shader, ResourcePack), validación, gestores
  datos/       repositorio SQLite y esquema
  servicios/   cuenta Microsoft (OAuth + PKCE), lanzamiento, cliente Modrinth
  ui/          interfaz PySide6
  util/        hashing, rutas seguras, log con redacción de secretos
tests/         pytest
herramientas/  datos de prueba, benchmark y capturas
```

## Empaquetado

```bash
pyinstaller --name Daiya --windowed --add-data "daiya/datos/esquema.sql;daiya/datos" main.py
```
