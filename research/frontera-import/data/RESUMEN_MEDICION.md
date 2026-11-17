# Contrato de frontera 01 — veredicto de la línea

**Fecha:** 16-Nov-2026 · **Sujeto:** `<esta-carpeta>` · **`platino-labs`: 0 escrituras.**

## Hipótesis evaluada

> Un sistema maduro acumula invariantes implícitos (orden de carga, estado global) que sus propias
> pruebas nunca violan; cruzar el grafo de importaciones del núcleo contra el AST de sus consumidores
> externos permitiría *predecir* qué ruptura de acoplamiento ocurrirá en producción.

Dos mitades, evaluadas por separado. La mitad **estática** (predecir) y la mitad **ejecutiva** (medir).

## Medición

`escrutar_instalado.py` reconstruye el grafo de módulos de un paquete **instalado**, enumera sus
componentes fuertemente conexas (SCC) y ejecuta **un `import` por miembro** en un intérprete limpio,
clasificando cada fallo por causa (`ORDEN` vs `DEPENDENCIA`).

| paquete | versión | módulos | SCC≥2 | con arista viva | ruptura ORDEN | ruptura DEPENDENCIA | miembros importados |
|---|---|---|---|---|---|---|---|
| django | 6.1.3 | 909 | 10 | 9 | 0 | 3 | 71 |
| pydantic | 2.14.3 | 106 | 1 | 1 | 0 | 0 | 15 |
| sqlalchemy | 2.1.9 | 258 | 5 | 5 | 0 | 0 | 52 |
| celery | 5.7.0 | 161 | 0 | 0 | 0 | 0 | 0 |
| django-filter | 26.2 | 15 | 1 | 1 | 0 | 0 | 5 |
| **TOTAL** | | **1449** | **17** | **16** | **0** | **3** | **143** |

- **0 rupturas por orden de importación en 1449 módulos.** Diecisiete ciclos reales, dieciséis con
  arista estáticamente "viva", ninguno detona al importarse.
- Las **3 rupturas por DEPENDENCIA** son drivers opcionales ausentes (`GDAL`, `oracledb`, `psycopg2`),
  no acoplamiento. Sin la separación de causas, la tabla habría contado **3 falsos positivos**.
- Coste: **143 imports** en lugar de 1449. El ejecutor es exacto y reutilizable sobre cualquier árbol
  instalado.

## El predictor estático: precisión 0/16

`censar_forma.py` etiqueta cada ciclo como `VIVO_RAIZ` / `VIVO_HOJA` / `INERTE`. Contrastado contra
la ejecución: **16 predicciones `VIVO`, 16 ejecuciones `PASA`** → precisión **0/16**. Además un
**falso negativo** en el ciclo de libro de texto (`p.a` ↔ `p.b`), que etiqueta `INERTE` y **sí** rompe
con `ImportError: cannot import name ... partially initialized module`.

Causa raíz, en el propio instrumento: `arista_viva()` exigía `local in usados` — que el nombre se
**reutilice** después. Pero `from X import v` **es** una lectura en tiempo de importación aunque `v`
no se vuelva a mencionar. El requisito es infundado.

## Control positivo (obligatorio)

`control_orden/p/{a,b}.py` reproduce el ciclo canónico. `import p.a` →
`ImportError: cannot import name 'A' from partially initialized module 'p.a'`. Sin este control,
"cero rupturas por orden" es indistinguible de **un ejecutor ciego** — y es justo el control el que
expuso el falso negativo del predictor. Sellado en `escrutar_instalado.py::self_test()` (3/3 exigiendo
que el predictor **falle** en este caso).

## Corrección de un hallazgo anterior

"El módulo GIS de Django rompe al importarse" era **esta máquina sin GDAL**
(`django.contrib.gis.db.backends.spatialite.features` → `ImproperlyConfigured: Could not find the GDAL
library`), no un hallazgo de acoplamiento. Retirado.

## Plataformas de recompensa — medidas el 16-Nov-2026

| plataforma | descripción circulante | estado real medido | veredicto |
|---|---|---|---|
| Algora | issues con recompensa en USD, pago al mergear PR | `algora.io/bounties` → **404**; `algora.io/api/v1/bounties` → **404**; el sitio se presenta como *"Hire your competitors' best engineers"* (reclutamiento defensa/aeroespacial/robótica/energía) | **el producto de bounties no existe** |
| Huntr | subir reporte → CVE → bounty | `huntr.com/challenges` → **200**, **1** challenge ("The Quiet Part: Govware Training Grounds 2026") y ya publica `View Results` (cerrado) | **0 challenges abiertos** |

Conclusión: **no se construye buscador de bounties.** Escribirlo hoy es un lector para un catálogo vacío.

## Veredicto

1. **La mitad estática se cierra como medición negativa.** No se publica ningún predictor de ruptura
   de acoplamiento: precisión 0/16 y un falso negativo sobre el caso canónico.
2. **Sobrevive el ejecutor con clasificación de causa.** Veredicto exacto, 143 imports sobre 1449
   módulos, reutilizable sobre cualquier árbol instalado. Es un instrumento de **triaje y reporte**,
   no un buscador: dado un fallo, dice *por qué*. No promete encontrar fallos.
3. **La clase "ciclo de importación ⇒ rotura" está vacía** en 5 ecosistemas maduros. Es esperable:
   Django, pydantic, sqlalchemy y celery importan cada módulo en su propia CI, así que la clase está
   drenada por construcción.

## Qué refutaría esta conclusión

- Un SCC con `causa=ORDEN` en cualquier paquete instalado. El ejecutor ya lo reportaría; basta una fila.
- Un paquete donde la clase no esté drenada: sin CI que importe todos los módulos, o con `__getattr__`
  de módulo / carga perezosa que difiera la lectura. **No medido.**
- Que un ciclo se rompa solo bajo una **secuencia** de imports (no un import aislado). El ejecutor mide
  cada miembro por separado; la clase "secuencia" queda **NO_MEDIDA** y no se lee como cero.

## Límites declarados

- `NO_MEDIDO`: consumidores externos **con sus dependencias** más allá de django-filter; rupturas por
  secuencia; paquetes sin CI de importación.
- Versiones fijadas arriba; el veredicto es de esas versiones, no de esos proyectos.
- El predictor conserva dos defectos estructurales conocidos y sin arreglar (resolución
  distribución→módulo; hack del prefijo `src/`). Irrelevantes para esta decisión, fatales para
  publicar un porcentaje.

---

## Corrección 2026-11-17 — el cero era artefacto, y la cifra que se publica es 2

**Lo que dijo la corrida anterior:** 0 rupturas por ORDEN sobre 1 449 módulos, 17 SCC.
**Lo que dice la medición corregida:** 2 SCC rompen de verdad. La corrida anterior no
midió: 3 de sus 17 SCC tenían driver opcional ausente y estaban marcados `NO_MEDIDO`
—`oracle`, `postgresql`, `gis.geos`—. Al instalar `oracledb 26.1.0` y `psycopg2 2.9.13`,
dos de esos tres rompen con la clase exacta que el ejecutor buscaba.

| punto de entrada (import aislado) | veredicto | causa |
|---|---|---|
| `django.db.backends.oracle.utils` | **ROMPE** | `ImportError: cannot import name 'BoundVar' from partially initialized module` |
| `django.db.backends.oracle.operations` | **ROMPE** | `ImportError: cannot import name 'DatabaseOperations' from partially initialized module` |
| `django.db.backends.postgresql.introspection` | **ROMPE** | `ImportError: cannot import name 'DatabaseIntrospection' from partially initialized module` |
| `django.contrib.gis.*` (24 módulos) | `NO_MEDIDO` | falta GDAL |
| `django.db.backends.mysql.*` (4) | `DEPENDENCIA` | falta mysqlclient |

Mecanismo, en líneas: `oracle/utils.py:4` hace `from .base import Database`; `base.py:61-66`
importa `client · creation · features · introspection · operations · schema`; uno de ellos
lee `BoundVar` de `utils`. Entrando por `utils`, el módulo está a medio ejecutar y
`BoundVar` —definido más abajo— no existe todavía. Entrando por `base` o por el paquete,
`Database` ya está ligado antes de L61 y todo pasa. **La ruptura existe; lo que no existe es
quien la alcance.**

## El embudo, con las tres etapas medidas por instrumentos distintos

| etapa | instrumento | resultado |
|---|---|---|
| 1 · candidatos sintácticos | `censar_forma.py` (+ `mecanismo_ciclos.py`) | 9 SCC con arista o lectura candidata · 625 lecturas de nombre |
| 2 · ruptura real | `escrutar_instalado.py` (ejecución) | **2 SCC · 3 puntos de entrada** |
| 3 · consumidor publicado | `gh api search/code` (3 consultas literales) | **0 · 0 · 0** |

Precisión del paso 1 sobre el paso 2: **0/11**. Accionables tras el paso 3: **0**.

> **Corrección 2026-11-17 (esta línea se publica).** La frase anterior decía `2/11 = 18 %`, y esa
> cifra no compara identidad: cuenta las 2 rupturas reales sobre 11 predicciones `ROMPE` como si
> alguna cayera dentro. Medido SCC a SCC por miembros —no por número, porque `mecanismo` y
> `escrutinio` numeran distinto—: los **11** SCC predichos `ROMPE` ejecutaron **`PASA`** (django
> scc 1, 4, 5, 6 y los 7 restantes de los otros cuatro paquetes), y las **2** rupturas reales viven
> en `django` scc **8** (tam 3) y scc **10** (tam 2), que el modelo declaró **`NO_MEDIDO`**.
> Verificación: `awk -F'\t' '$1=="django"&&$4=="ROMPE"' mec_django.tsv` contra
> `escrutinio_django_v3.tsv`, columna `ejecucion`. El modelo no sólo sobre-predijo: **falló por
> abstención justo donde había hecho falta**. `2/11` era un techo generoso disfrazado de precisión.

## Qué significa, sin adornos

- El cribador estático **no** es un detector: los **11** SCC que marcó `ROMPE` ejecutaron `PASA`,
  incluso después de codificar la regla padre-primero, y las 2 únicas rupturas reales cayeron en
  SCC que declaró `NO_MEDIDO`. Se publica como **cota superior y ranking**, no como veredicto.
- El ejecutor **sí** encuentra rupturas que nadie más mide, y esta corrida lo demuestra con
  1 hallazgo real por cada 1 449 módulos auditados.
- El filtro que convierte ruptura en hallazgo **no es el análisis, es la búsqueda de consumidor**.
  Sin la etapa 3, estos tres casos habrían sido tres tickets rechazados con razón —el mismo
  `wontfix` de #37504— y el método habría quedado desacreditado por segunda vez.
- **`NO_MEDIDO` no es cero.** Costó una conclusión entera: una noche midiendo un nulo que
  fabricaba la ausencia de dos drivers.

---

## Corrección de la etapa 3 (2026-11-16 22:20) — el «0 consumidores» también era artefacto

La tabla del embudo de arriba decía `gh api search/code → 0 · 0 · 0`. **Ese cero no era
un cero**, y se descubrió aplicando al propio instrumento la regla que el instrumento
aplicaba a Django:

| intento | consulta | resultado | veredicto |
|---|---|---|---|
| 1 | `from+django.db.backends.postgresql.introspection+import` | 0 | **instrumento roto**: control positivo con la misma forma (`…postgresql.base…`) da 0; con espacio da 11 696 |
| 2 | con espacios | 19 520 / 9 872 / 14 080 | **inservible al revés**: la API legacy empareja tokens, no sentencias; los hits caen en el propio `postgresql/base.py` de Django |
| 3 | censo del sdist 6.1.3, población declarada | 6 ocurrencias, 0 documentadas | **exacto y localizable** |

### Etapa 3, medida exacta

Población: árbol fuente de Django 6.1.3 (`pip download --no-binary :all:`). Sin rate
limit, sin tokens, cada ocurrencia localizable por archivo y línea.

- **6 imports de módulo** de los tres módulos rotos — todos en `contrib.gis`:
  `postgis/base.py:8` y `:11`, `postgis/introspection.py:2`, `postgis/operations.py:13`,
  `gis/oracle/operations.py:20`, `gis/oracle/introspection.py:3`.
- **5 de las 6** cargan `postgresql.base` en una línea anterior: `postgis/base.py:4` es
  `from django.db.backends.postgresql.base import DatabaseWrapper`. Cuando llega su línea 8,
  el ciclo ya se resolvió.
- **La única sin esa cobertura** es `postgis/introspection.py:2`, y su línea 1 importa
  GDAL, que falla antes de llegar. Enmascarada, no segura.
- **5 imports dentro de función** (zona segura), incluido `tests/gis_tests/tests.py:105`,
  el único sitio donde Django ejecuta literalmente la sentencia rota — después de que la
  conexión ya está construida.
- **0 documentados** en `docs/ref/`.

**Predicción abierta, pre-registrada:** con GDAL instalado, `postgis/introspection.py`
pasa de `NO_MEDIDO` a `ROMPE`. Falsador: instalar GDAL y ver `PASA`.

### Corrección del censo de consumidores (2026-11-17) — la población era otra

El recuento de arriba **no se reproduce** con población declarada. Se hizo contra los *tres
módulos rotos más dos hermanos* (`postgresql.operations`, `oracle.introspection`), no contra
los miembros de los dos SCC. Recuento con la población correcta —los **5 módulos** de los SCC 8
y 10— separando las aristas internas del ciclo, que no son consumidores:

| clase | cuenta | detalle |
|---|---|---|
| aristas internas del ciclo | **7** | p. ej. `oracle/base.py:65`, `postgresql/introspection.py:6`; son el ciclo, no quien lo alcanza |
| **consumidores a nivel módulo** | **5** | `gis/oracle/base.py:1`, `gis/oracle/operations.py:20`, `postgis/base.py:4`, `postgis/base.py:8`, `postgis/introspection.py:2` |
| consumidores dentro de función | **13** | 11 en `tests/`, 1 en `oracle/client.py:12`, 1 en `gis_tests/tests.py:105` |
| documentados en `docs/ref/` | **0** | verificado con `grep -rln` |

Medido ejecutando los 5 módulos como punto de entrada (`./venv/bin/python -c "import …"`):
**4 de 5 fallan por GDAL ausente**, no por el ciclo — `ImproperlyConfigured: Could not find the
GDAL library`. El quinto (`postgis/base.py:8`) no llega a importar nada roto porque su línea 4
ya cargó `postgresql.base`. Es decir: **GDAL no enmascara 1 caso, enmascara 4 de 5**, y es la
variable que decide si la etapa 3 tiene algún consumidor vivo.

**Predicción abierta corregida (pre-registrada, con orden de líneas ya verificado):** con GDAL
instalado, `gis/oracle/operations.py:20` importa `django.db.backends.oracle.operations` —uno de
los tres rotos— y `postgis/introspection.py:2` importa `postgresql.introspection`, también roto;
ambos deben dar **`ROMPE`**. `postgis/base.py` (línea 4 antes de la 8) y `gis/oracle/base.py:1`
(`oracle.base` es entrada segura) deben dar **`PASA`**. Falsadores respectivos: `PASA` en los dos
primeros, `ROMPE` en los dos últimos. `cota_error`: si `django.contrib.gis.geos` carga
`postgresql.base` por su cuenta antes de la línea 20, el primero pasa y la predicción falla.

### La etapa 3 corregida del embudo

| etapa | instrumento | resultado | control positivo |
|---|---|---|---|
| 1 · candidato | AST (`censar_forma` + `mecanismo_ciclos`) | 16 SCC · 11 `ROMPE` → 11 `PASA` · 625 lecturas | sí — `control_orden/p`; **negativo: no** |
| 2 · ruptura | ejecución (`escrutar_instalado`) | **2 SCC · 3 puntos de entrada** | sí — reproducidos uno por proceso |
| 3 · consumidor | censo del sdist, población declarada | **5 a nivel módulo · 4 enmascarados por GDAL · 13 en función · 0 documentados** | sí — `postgis/base.py:4` prueba el patrón de cobertura |

**El embudo no termina en «0 accionables». Termina en `NO_MEDIDO` para el consumidor
externo**, que es una casilla distinta y honesta. La clase externa necesita un instrumento
que pruebe una sentencia literal sobre GitHub; hoy no lo tengo y no lo voy a simular.

Esa es la tesis publicable: **tres etapas, dos instrumentos validados, la tercera sin
instrumento — y la disciplina de no rellenarla con un número.**

## Medición de desenmascaramiento — GDAL y GEOS (17-Nov-2026 12:31 CST)

**Método (sin stub: el sujeto no se sustituyó).** GDAL 3.12.2 real desde
`rasterio-1.5.2-cp314-cp314-macosx_15_0_arm64.whl` (`libgdal.38.3.12.2.dylib`, un
`pip download` frente a las 44 fórmulas de `brew install gdal`), apuntado con
`GDAL_LIBRARY_PATH`. GEOS 3.15.0 por `brew install geos` (cero dependencias),
apuntado con `GEOS_LIBRARY_PATH`. Sonda previa: `gdal_version() -> b'3.12.2'`.

**Hallazgo lateral no previsto:** la máscara no era una capa sino **dos**.
`django/contrib/gis/geos/__init__.py:16` importa `.libgeos`, así que sin GEOS el
módulo muere igual, un piso más abajo. Dos bibliotecas C deben satisfacerse antes
de que un solo `import` de `contrib.gis` ejecute Python propio.

**Resultado (intérprete limpio por módulo, `django.setup()`, `INSTALLED_APPS=[]`):**

| consumidor | antes (sin GDAL) | después (GDAL+GEOS) |
|---|---|---|
| `gis/db/backends/oracle/operations.py:20` | GDAL ausente | **`ImportError`: `oracle.operations` parcialmente inicializado** |
| `gis/db/backends/postgis/introspection.py:2` | GDAL ausente | **`ImportError`: `postgresql.introspection` parcialmente inicializado** |
| `gis/db/backends/oracle/base.py:1` | GDAL ausente | PASA (entrada segura) |
| `gis/db/backends/postgis/base.py:4` y `:8` | cubierto | PASA |

**2 de 5 consumidores a nivel módulo llegan al ciclo y rompen.** La cifra anterior
«4 enmascarados, 0 reales» es falsa y queda sustituida.

**Prueba de que la causa es el orden y no el entorno** (control negativo dentro de la
misma medición, mismo intérprete y configuración):

| secuencia | resultado |
|---|---|
| `import ...oracle.operations` | `ImportError` (circular) |
| `import ...oracle.base` → `import ...oracle.operations` | OK |
| `import ...postgis.introspection` | `ImportError` (circular) |
| `import ...postgis.base` → `import ...postgis.introspection` | OK |

**Veredicto del pre-registro: 3/4 acertadas.** La discrepancia (`postgis/base`
predicho `PASA`, obtenido `AppRegistryNotReady` sin `setup()`) es **defecto del
pre-registro**, no del modelo: omitió `django.setup()` en la `cota_error`. Registrado
en `PREREGISTRO_mecanismo.txt`.

**Por qué no se abre ticket (medido, no supuesto):** `django/db/utils.py:116` hace
`import_module("%s.base" % backend_name)`. Django **siempre** carga `base` antes de
`operations`, así que en uso normal el fallo no puede ocurrir. La mina vive sólo donde
alguien importe `operations` primero (un tercero que herede `DatabaseOperations` a
nivel de módulo). Cuántos terceros lo hacen: **`NO_MEDIDO`**.

**Reproducir:** `DJANGO_SETTINGS_MODULE=settings_probe PYTHONPATH=<esta-carpeta>/bench
<esta-carpeta>/venv/bin/python -c "import django; django.setup();
import django.contrib.gis.db.backends.oracle.operations"`

## Nivel 7 — la invariante de orden, medida sobre los 17 SCC

**Pregunta.** No "¿el ciclo predice la ruptura?" (refutado, 0/11 y luego 0/11
otra vez), sino **"¿qué le permite a un paquete tener ciclos y no romperse?"**

**Instrumento.** `verificar_invariante_orden.py` (13 545 B, auto-test 5/5).
Para cada SCC busca módulos *fuera* del ciclo con import a nivel módulo que
resuelve a un miembro, y hace tres sondas en intérprete limpio: **P** (`import R`),
**N** (`import <predecesor>; import R`, el control negativo dentro del mismo
experimento) y **C** (la ruta canónica del framework). Sólo un `ImportError` con
`partially initialized` o `circular import` cuenta como `ROMPE_CICLO`; un
`ImportError` por dependencia nativa ausente se queda en `OTRO` y nunca es
hallazgo. Esa condición es la lección de GDAL convertida en código.

**Resultado.** 17 SCC: **13 INERTE · 4 INMUNE_CONSTRUCCION · 0 MINA_VIVA**.
5 pares (SCC, lector) rompen, sobre **4 módulos distintos** — todos en django:

| lector que rompe | SCC donde rompe |
|---|---|
| `django.db.backends.oracle.operations` | 1 y 8 |
| `django.db.backends.postgresql.introspection` | 1 |
| `django.contrib.gis.db.backends.oracle.operations` | 2 y 8 |
| `django.contrib.gis.db.backends.postgis.introspection` | 10 |

**El hallazgo.** Los 5 pares se reparan con **dos** módulos:
`django.db.backends.oracle.base` y `django.db.backends.postgresql.base`. El
invariante que protege a django no es del ciclo, **es del paquete**: *entra por
`.base`*. Y su API pública lo impone en `django/db/utils.py:116`
(`import_module("%s.base" % backend_name)`). pydantic, sqlalchemy y
django_filters: 12 SCC, **0 rupturas**, ninguna convención necesaria.

**Lo que corrigió medir.** El pre-registro afirmaba que SCC 8 y 10 rompían y los
otros 15 no. P1 confirmada 2/2; **P2 falsada**: SCC 1 y SCC 2 también rompen. Y
el reparador no vive en el ciclo que se rompe — para SCC 1 y SCC 2 ningún
miembro del propio SCC repara. De ahí las dos columnas de la tabla,
`reparan` (vecindario propio) y `reparan_global` (todo el censo).

**Reproducir.**
```bash
cd <esta-carpeta>
./venv/bin/python verificar_invariante_orden.py --self-test
DJANGO_SETTINGS_MODULE=settings_probe PYTHONPATH=<esta-carpeta>/bench \
  ./venv/bin/python verificar_invariante_orden.py --paquete django \
  --escrutinio escrutinio_django_v3.tsv --salida invariante_django.tsv \
  --preludio "import django; django.setup()" \
  --env DJANGO_SETTINGS_MODULE=settings_probe --env PYTHONPATH=<esta-carpeta>/bench \
  --cargador "from django.db.utils import load_backend; load_backend('django.db.backends.oracle')"
```
Salida completa: `invariante_total.tsv` (17 filas). Sondas de la corrida: 5 pares
roto medidos, 4 módulos, cada uno con su control negativo y su reparador citable.
