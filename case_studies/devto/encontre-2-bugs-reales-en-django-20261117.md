# Encontré 2 bugs reales en Django y decidí no reportarlos. La razón es más interesante que el bug.

*Un embudo de tres etapas para auditar fronteras de acoplamiento, con tres de mis propios instrumentos refutados por la ejecución real.*

---

Pasé una noche midiendo si los ciclos de importación predicen fallos en producción. Al final tenía **1 449 módulos auditados en 5 paquetes, 2 rupturas reales en el backend de base de datos de Django, 0 reportes enviados**. Este artículo es sobre por qué la tercera cifra es la correcta, y sobre los tres instrumentos que tuvieron que romperse para llegar a ella. El código, los datos y los falsadores están en [auditor-toolkit](https://github.com/alexisromtz-lab/auditor-toolkit).

## La premisa

Los proyectos maduros acumulan invariantes implícitos: órdenes de carga, estado global, dependencias no declaradas. Sus propias suites de pruebas nunca los violan, porque las pruebas se escribieron obedeciendo esas reglas. Un consumidor externo —un adaptador, un plugin, un backend de base de datos de terceros— sí puede violarlas, y entonces el sistema falla de una forma que ningún linter detecta.

Los linters responden a «¿existe un ciclo?». La pregunta útil es otra: **¿existe una ruptura alcanzable?**

## Etapa 1 — el candidato: mi primer instrumento, refutado tres veces

Escribí un modelo posicional: una sentencia `from M import n` solo rompe si `n` no existe todavía en `M` en el instante en que la sentencia corre. Suena correcto. Sobre 17 componentes fuertemente conexos (SCC) en django, pydantic, sqlalchemy, celery y django-filter, emitió veredicto en 14 de ellos y predijo **11 rupturas** (los otros 3 los dio por `PASA`, y 3 quedaron `NO_MEDIDO`). La ejecución real, ya con todos los drivers instalados, encontró **2** — y ninguna de las 11 estaba entre ellas.

Lo corregí tres veces, cada vez con evidencia:

| versión | defecto corregido | predice ROMPE | lecturas inseguras |
|---|---|---|---|
| v1 | un submódulo se medía contra el SCC en vez de contra el paquete completo | 14 / 17 | 1 107 |
| v2 | el corte de líneas se leía del módulo **que lee**, no del **leído** | 14 / 17 | 1 050 |
| v3 | regla padre-primero: un submódulo nunca está a medio ejecutar cuando su padre lo importa | 11 / 17 | 625 |

Y la razón por la que ninguna versión funciona no es un bug. Es estructural:

> Dentro de un SCC, todo par de módulos se alcanza mutuamente. Por tanto «¿está `t` a medio ejecutar?» **no es decidible desde el AST**: depende de la pila de importación, es decir, del punto de entrada.

Comparado SCC a SCC contra la ejecución real: **los 11 SCC que el modelo marcó `ROMPE` ejecutaron `PASA`. Las 2 rupturas reales están en los 2 SCC que declaró `NO_MEDIDO`**. No acertó por exceso: falló por abstención justo donde hacía falta. Lo dejé en el código con un `REFUTADO COMO PREDICTOR` en el docstring, porque un instrumento refutado es evidencia de que fue refutado.

## Etapa 2 — la ruptura: aquí sí hay hechos

Un ejecutor independiente importa cada módulo en un intérprete limpio, uno por proceso, y clasifica la causa del fallo (`ORDEN` / `DEPENDENCIA` / `OTRO`). Reduce los 909 módulos de Django a 71 imports con veredicto.

En la primera corrida reportó **0 rupturas por orden**. Ese cero era un artefacto: tres SCC estaban marcados `NO_MEDIDO` porque faltaban drivers opcionales. `NO_MEDIDO` no es cero. Instalé `oracledb 26.1.0` y `psycopg2 2.9.13`, y el resultado cambió de signo:

```python
# intérprete limpio, driver presente
import django.db.backends.postgresql.introspection
# ImportError: cannot import name 'DatabaseIntrospection'
#   from partially initialized module 'django.db.backends.postgresql.introspection'

import django.db.backends.oracle.utils
# ImportError: cannot import name 'BoundVar'
#   from partially initialized module 'django.db.backends.oracle.utils'

import django.db.backends.oracle.operations
# ImportError: cannot import name 'DatabaseOperations'
#   from partially initialized module 'django.db.backends.oracle.operations'
```

El mecanismo, en tres líneas de código ajeno:

```
oracle/operations.py:16   from .utils import BoundVar, ...                  → entra a utils
oracle/utils.py:4         from .base import Database                        → entra a base
oracle/base.py:65         from .operations import DatabaseOperations  ← operations a medio construir
```

Entrando por `base` o por el paquete, `Database` ya está ligado antes de la línea 65 y todo pasa. Entrando por `utils` u `operations`, no. **La ruptura es real. Lo que falta es quién la alcance.**

## Etapa 3 — el consumidor: donde mi instrumento me mintió dos veces

Busqué los tres imports en GitHub. `total_count: 0 · 0 · 0`. Un cero limpio. No abrí el ticket.

Antes de publicarlo corrí un control positivo sobre el buscador, con la misma forma de consulta:

```bash
gh api search/code -f q="from+django.db.backends.postgresql.base+import"   # → 0
gh api search/code -f q="from django.db.backends.postgresql.base import"   # → 11 696
```

**0 contra 11 696 para la misma cadena.** En un parámetro de query, `+` es un signo más literal, no un espacio. Mi instrumento devolvía cero para lo que existe.

Lo rehice con espacios: 19 520 / 9 872 / 14 080. Igual de inservible, ahora en la dirección contraria: la API de búsqueda empareja **tokens, no sentencias**, y los resultados caían en el propio `postgresql/base.py` de Django.

Tercer intento, instrumento distinto y exacto: censo sobre el árbol fuente de Django 6.1.3, población declarada —los **5 módulos** que forman los dos SCC—, separando las aristas internas del ciclo (esas son el ciclo, no quien lo alcanza).

| clase | cuenta | detalle |
|---|---|---|
| aristas internas del ciclo | **7** | `oracle/base.py:65`, `postgresql/introspection.py:6`… |
| **consumidores a nivel módulo** | **5** | los 5 en `contrib.gis`; **2 rompen** al desenmascararlos, 3 están precedidos por su `base` |
| consumidores dentro de función | **13** | 11 en `tests/`, 1 en `oracle/client.py:12` |
| documentados en `docs/ref/` | **0** | |

Ejecuté los 5 como punto de entrada. **Cuatro fallan por GDAL ausente**, no por el ciclo:

```python
import django.contrib.gis.db.backends.oracle.operations
# ImproperlyConfigured: Could not find the GDAL library
```

El quinto no llega al import roto porque su línea 4 ya cargó `postgresql.base`. Es decir: **GDAL no enmascara un caso, enmascara cuatro de cinco**. Y ésa no es una casilla vacía que se pueda dejar abierta: es la variable que decide si esta etapa tiene algún consumidor vivo.

### Así que la desenmascaré

Instalar GDAL por Homebrew son 44 fórmulas. Usé una más barata y sin trampa: el wheel de `rasterio` embarca un `libgdal.38.3.12.2.dylib` **real**, y basta apuntarlo con `GDAL_LIBRARY_PATH`. No es un stub: es la misma biblioteca C que Django enlaza.

Al hacerlo apareció una capa que no había previsto: **no era una máscara, eran dos.** `geos/__init__.py:16` importa `.libgeos`, así que sin GEOS el módulo muere igual, un piso más abajo. Dos bibliotecas C hay que satisfacer antes de que un solo `import` de `contrib.gis` llegue a ejecutar Python propio.

Con las dos presentes, y tras `django.setup()`:

| consumidor | antes | después |
|---|---|---|
| `gis/oracle/operations.py:20` | GDAL ausente | **`ImportError`: `oracle.operations` parcialmente inicializado** |
| `gis/postgis/introspection.py:2` | GDAL ausente | **`ImportError`: `postgresql.introspection` parcialmente inicializado** |
| `gis/oracle/base.py:1` | GDAL ausente | pasa (es la entrada segura) |
| `gis/postgis/base.py:4` y `:8` | cubierto | pasa (la línea 4 precede a la 8) |

**Dos de los cinco consumidores llegan al ciclo y rompen.** El hallazgo cambia de signo: ya no es «cero accionables», es «dos accionables que ninguna biblioteca nativa alcanzaba a mostrar».

### Y aquí está la prueba que hacía falta

Mismo intérprete, misma configuración, mismo módulo. Lo único que cambia es el orden:

```python
import django.contrib.gis.db.backends.oracle.operations
# ImportError: cannot import name 'DatabaseOperations' from partially initialized module

import django.contrib.gis.db.backends.oracle.base      # primero esto
import django.contrib.gis.db.backends.oracle.operations  # y ahora esto
# OK
```

Lo mismo con `postgis.introspection` y `postgis.base`. **El control negativo está dentro de la misma medición**: las dos secuencias «base primero» existen justamente para refutar que la causa sea el entorno. No lo refutan. La causa es el orden.

Esto no es un bug de instalación ni una rareza de mi máquina: es un módulo que se rompe según quién lo importe antes.

**No abrí el ticket** — pero no por lo que creía. El criterio que me dejó el `wontfix` («sin un consumidor nombrado *y alcanzable*, no hay bug: hay texto») se pone a prueba tres párrafos más abajo, y no sale como esperaba: al desenmascarar GDAL, el consumidor aparece. Que aun así no haya ticket tiene otra razón, y es la que vale.

## Las tres reglas que me costaron la noche

**1. `NO_MEDIDO` no es cero.** Dos veces. Los drivers ausentes fabricaron un nulo; el `+` en la consulta fabricó el otro. Un cero con dependencias no declaradas es una mentira estadística.

**2. Un cero que también da cero para lo que existe es un instrumento roto.** El control positivo no es burocracia: es lo único que distingue «no hay» de «no miré». Y un control positivo **no basta**: mi modelo posicional lo pasaba —sabía emitir `ROMPE`— y aun así sus 11 candidatos salieron limpios. Hace falta también el control que debe salir limpio.

**3. La etapa que convierte ruptura en hallazgo no es el análisis: es el consumidor.** Sin ella habría publicado un hallazgo falso por segunda vez.

## El embudo, y lo que queda abierto

| etapa | instrumento | resultado | control positivo | control negativo |
|---|---|---|---|---|
| candidato | AST estático | 17 SCC · 11 predichos `ROMPE` · 625 lecturas | sí | **no: 11/11 falsos** |
| ruptura | ejecución en intérprete limpio | **2 SCC · 3 puntos de entrada** | sí, uno por proceso | sí |
| consumidor | censo del sdist | 5 a nivel módulo · **2 rompen al desenmascararlos** · 13 en función · 0 documentados | sí | sí |

Y el veredicto de la predicción que quedaba abierta. La corrí. **3 de 4 acertadas**, y la que falló es un defecto de mi pre-registro, no del modelo: predije `PASA` para `postgis/base` y sin `django.setup()` da `AppRegistryNotReady`, una tercera clase de fallo que no declaré como precondición. Con `setup()`, pasa, como estaba escrito. La lección no es «acerté»: es que **un pre-registro sin sus precondiciones no es falsable, es una frase**.

Las dos que importan acertaron, y acertaron en la dirección incómoda: el ciclo es alcanzable y rompe de verdad.

## Nivel 7: la pregunta que sí tiene respuesta

Hasta aquí la pregunta era «¿el ciclo predice la ruptura?», y la respuesta es que no: mis once candidatos salieron limpios. Pero hay una pregunta mejor, y esta sí se contesta con números: **¿qué le permite a un paquete tener ciclos y no romperse?**

Cambié la unidad de medida. En vez de contar ciclos, conté **lectores**: módulos fuera del ciclo cuyo `import` a nivel módulo resuelve a un miembro del ciclo. Un lector es la persona que entra por la puerta de atrás. Para cada uno, dos sondas en intérprete limpio: `import R`, y `import <predecesor>; import R`. Si la primera rompe por ciclo y la segunda pasa, la causa es el orden y nada más.

Sobre los mismos 17 ciclos:

| celda | qué significa | cuántos |
|---|---|---|
| `INERTE` | nadie de fuera entra por el ciclo | **13** |
| `INMUNE_CONSTRUCCION` | entra alguien y rompe, pero hay una entrada que lo salva | **4** |
| `MINA_VIVA` | entra alguien, rompe, y ninguna entrada lo salva | **0** |

Cinco pares (ciclo, lector) rompen, sobre **cuatro módulos distintos**, todos en Django: `db.backends.oracle.operations`, `db.backends.postgresql.introspection`, `contrib.gis.db.backends.oracle.operations` y `contrib.gis.db.backends.postgis.introspection`. (Son 4 módulos y no «2 rupturas» como dice la tabla de arriba porque cuento poblaciones distintas: allí, ciclos que rompen; aquí, módulos que rompen al importarse primero.)

Y aquí está el dato que no esperaba. Esos cuatro módulos se reparan con **dos**: `db.backends.oracle.base` y `db.backends.postgresql.base`. El invariante que protege a Django **no vive en el ciclo, vive en el paquete**: entra por `.base`. Es una convención de una línea, y su API pública la impone en `django/db/utils.py:116`. En pydantic, sqlalchemy y django-filter, sus **7** ciclos no tienen ni un lector que rompa: cero convención necesaria.

También me equivoqué aquí, y conviene decirlo. Mi pre-registro afirmaba que sólo dos de los diecisiete ciclos rompían; rompen cuatro. Y el reparador ni siquiera estaba donde lo busqué: para dos de ellos **ningún** miembro del propio ciclo repara — el que repara pertenece a otro ciclo. Por eso la tabla final publica dos columnas, «repara en su vecindario» y «repara en todo el paquete». Quince de diecisiete predicciones correctas: fallé en los dos ciclos del bloque `db.models`.

Lo que cambia para el ticket: no es que Django sea inmune por no tener ciclos —tiene diecisiete—. Es inmune porque tiene **una entrada declarada** y la hace cumplir. Eso no lo arregla un `if`, y no lo descubre un linter. Es exactamente el tipo de invariante implícito que este embudo existe para encontrar.

Entonces, ¿por qué sigo sin abrir el ticket?

Porque medí también el consumidor real, y ese número es pequeño y preciso: `django/db/utils.py:116` hace `import_module("%s.base" % backend_name)` — Django **siempre** carga `base` antes de `operations`. En el uso normal el fallo no puede ocurrir. Vive en el único hueco donde alguien importe `operations` primero: un paquete de terceros que herede `DatabaseOperations` a nivel de módulo. Que ese paquete exista o no lo sigo teniendo en `NO_MEDIDO`.

Es una mina, no un incendio. Y una mina sin denominador medido no se reporta: se documenta.

Y queda una casilla honesta: el consumidor **externo** de terceros es `NO_MEDIDO`. No tengo hoy un instrumento que pruebe una sentencia literal sobre GitHub, y no voy a rellenar esa casilla con un número que no se distingue de un instrumento roto.

---

*Medido el 16 y 17 de noviembre de 2026 sobre django 6.1.3, pydantic 2.14.3, sqlalchemy 2.1.9, celery 5.7.0, django-filter 26.2, Python 3.14.8 en macOS, con GDAL 3.12.2 y GEOS 3.15.0. Los tres instrumentos de esta medición —con su pre-registro, sus datos y sus falsadores ejecutables— están publicados en [auditor-toolkit v0.2.0](https://github.com/alexisromtz-lab/auditor-toolkit), DOI [10.5281/zenodo.24323318](https://doi.org/10.5281/zenodo.24323318), bajo [`research/frontera-import/`](https://github.com/alexisromtz-lab/auditor-toolkit/tree/main/research/frontera-import).*
