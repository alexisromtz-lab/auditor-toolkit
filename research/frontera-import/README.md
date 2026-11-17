<!-- HUELLA-FRONTERA-IMPORT-RESEARCH-20261117 -->
# Fronteras de importación: de un predictor refutado a un invariante medido

Esta carpeta es una línea de investigación completa, con sus fracasos incluidos.
La pregunta inicial era **«¿un ciclo de importación predice una ruptura en
producción?»**. La respuesta, medida dos veces, es **no**. Pero al cambiar la
unidad de medida apareció otra pregunta, y esa sí tiene respuesta con números:
**«¿qué le permite a un paquete tener ciclos y no romperse?»**

Respuesta medida: **una convención de entrada**. En Django, cuatro módulos se
rompen si se importan primero, y los cuatro se reparan entrando por `.base` —
una regla de una línea que su propia API impone.

## El resultado

Población: **1 449 módulos** ejecutados en intérprete limpio sobre django 6.1.3,
pydantic 2.14.3, sqlalchemy 2.1.9, celery 5.7.0 y django-filter 26.2, Python
3.14.8. De esa ejecución salen **17 componentes fuertemente conexas (SCC)**, con
**625 lecturas** de importación registradas.

| celda | qué significa | cuántas |
|---|---|---|
| `INERTE` | ningún módulo de fuera entra por el ciclo | **13** |
| `INMUNE_CONSTRUCCION` | entra alguien y rompe, pero hay una entrada que lo salva | **4** |
| `MINA_VIVA` | entra alguien, rompe, y ninguna entrada lo salva | **0** |

Cinco pares (ciclo, lector) rompen, sobre **cuatro módulos distintos**, todos en
Django:

| lector que rompe al importarse primero | rompe en el SCC |
|---|---|
| `django.db.backends.oracle.operations` | 1 y 8 |
| `django.db.backends.postgresql.introspection` | 1 |
| `django.contrib.gis.db.backends.oracle.operations` | 2 y 8 |
| `django.contrib.gis.db.backends.postgis.introspection` | 10 |

Los cinco se reparan con **dos** módulos: `django.db.backends.oracle.base` y
`django.db.backends.postgresql.base`. El invariante **no vive en el ciclo, vive
en el paquete**: entra por `.base`. La API pública lo impone en
`django/db/utils.py:116` (`import_module("%s.base" % backend_name)`), razón por
la cual el fallo no ocurre en uso normal.

En pydantic, sqlalchemy y django-filter, sus **7** ciclos no tienen ni un lector
que rompa.

## Lo que quedó refutado

`instruments/mecanismo_ciclos.py` nació como **predictor**: dado un SCC, predecir
si rompe. Sus **11 candidatos salieron limpios en ejecución real**: precisión
**0/11**, no el 18 % de una versión anterior del cálculo. El archivo lo declara
`REFUTADO COMO PREDICTOR` en su docstring y se conserva como **generador de
candidatos de etapa 1**, no como oráculo.

Un predictor estático no puede ver la pila de importación. Esa es toda la
lección, y costó tres intentos.

## Cómo reproducir

```bash
python instruments/verificar_invariante_orden.py --self-test   # RC 0 esperado
```

El auto-test construye un paquete sintético con la forma del backend `oracle` de
Django y verifica cinco cosas: que el control positivo rompe, que el control
negativo pasa, que un lector inseguro se detecta **y** se repara, que un lector
seguro no se marca, y que un `ImportError` por dependencia nativa ausente **no**
cuenta como ciclo.

La corrida sobre Django necesita las dos bibliotecas nativas de `contrib.gis`.
`bench/settings_probe.py` las toma del entorno:

```bash
export GDAL_LIBRARY_PATH=<ruta a libgdal.*>     # ver nota en bench/settings_probe.py
export GEOS_LIBRARY_PATH=<ruta a libgeos_c.*>
export DJANGO_SETTINGS_MODULE=settings_probe
export PYTHONPATH=$PWD/bench

python instruments/verificar_invariante_orden.py --paquete django \
  --escrutinio data/escrutinio_django_v3.tsv --salida /tmp/invariante_django.tsv \
  --preludio "import django; django.setup()" \
  --env DJANGO_SETTINGS_MODULE=settings_probe --env PYTHONPATH=$PWD/bench \
  --cargador "from django.db.utils import load_backend; load_backend('django.db.backends.oracle')"
```

## Qué hay en `data/`

| archivo | qué es |
|---|---|
| `escrutinio_*.tsv` | verdad de ejecución por paquete; columna `miembros` = pertenencia al SCC |
| `mecanismo_total.tsv` | salida del predictor refutado (17 filas) |
| `invariante_total.tsv` | la medición de nivel 7 (17 filas): `rompen`, `reparan`, `reparan_global`, `celda` |
| `PREREGISTRO_invariante.txt` | las 17 predicciones, escritas **antes** del instrumento, y el resultado medido con sus dos desvíos |
| `PREREGISTRO_mecanismo.txt` | predicciones del mecanismo y la prueba de dependencia de orden A/B/C/D |
| `RESUMEN_MEDICION.md` | la línea completa: agregado, hallazgo, embudo de tres etapas, correcciones |

## Límites declarados

- **El consumidor externo es `NO_MEDIDO`.** Cuántos paquetes de terceros
  importan `...oracle.operations` como punto de entrada no se midió, y no se
  rellena con un número de búsqueda de código que no se distingue de un
  instrumento roto.
- Sólo se miden lectores **dentro** del paquete censado.
- El reparador **no** tiene por qué vivir en el ciclo que se rompe: para SCC 1 y
  SCC 2 ningún miembro del propio ciclo repara. De ahí las dos columnas,
  `reparan` (vecindario propio) y `reparan_global` (todo el censo).
- El pre-registro de nivel 7 **falló en dos de diecisiete** predicciones (SCC 1 y
  SCC 2 también rompen) y su desglose de población estaba mal. Se registra sin
  corregirlo hacia atrás.
- `NO_MEDIDO` no es cero. Tres veces en esta línea un cero resultó ser un
  instrumento ciego: drivers ausentes, un `+` en una consulta, y GDAL/GEOS
  enmascarando el import entero.

## Herramientas

| archivo | papel |
|---|---|
| `instruments/censar_forma.py` | forma estática del árbol: SCC, aristas, sospechas |
| `instruments/escrutar_instalado.py` | ejecuta cada módulo en intérprete limpio y clasifica la causa |
| `instruments/mecanismo_ciclos.py` | **refutado como predictor**; generador de candidatos y prueba A/B/C/D |
| `instruments/verificar_invariante_orden.py` | la medición de nivel 7, con auto-test propio |
