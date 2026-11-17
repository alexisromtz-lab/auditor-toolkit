"""Ajustes minimos de django para que `contrib.gis` se pueda importar sin un
GDAL del sistema. Las dos rutas se declaran por entorno:

    GDAL_LIBRARY_PATH=<ruta a libgdal.*.dylib o .so>
    GEOS_LIBRARY_PATH=<ruta a libgeos_c.*>

Medido el 17-Nov-2026: `brew install gdal` arrastra 44 formulas (incluida
python@3.15). Un `pip download rasterio` trae la MISMA libgdal real embebida en
el wheel (3.12.2), enlazada por @loader_path. Eso no es un stub: el sujeto de la
medicion se conserva. GEOS viene de `brew install geos`, que no tiene
dependencias.
"""
import os

SECRET_KEY = "probe"
INSTALLED_APPS = []
DATABASES = {}

if os.environ.get("GDAL_LIBRARY_PATH"):
    GDAL_LIBRARY_PATH = os.environ["GDAL_LIBRARY_PATH"]
if os.environ.get("GEOS_LIBRARY_PATH"):
    GEOS_LIBRARY_PATH = os.environ["GEOS_LIBRARY_PATH"]
