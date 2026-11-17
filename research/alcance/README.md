# Alcance — ¿la pieza abre la puerta al objeto?

La etapa 0 del embudo. Las otras cuatro (candidato, ruptura, consumidor, recepción)
suponen algo que nadie medía: que el lector **pueda llegar**. Una pieza puede
describir un objeto con precisión perfecta y no ofrecer ninguna puerta.

## El hallazgo que creó este instrumento

Medido el 17-Nov-2026 sobre el artículo `dev.to/5059635`:

| momento | superficie | huella | estado | detalle | veredicto |
|---|---|---|---|---|---|
| 19:56 | `devto/5059635` (vivo) | `287e6b023274` | `SOLO_TEXTO` | `code_span` | **SIN_ALCANCE** |
| 19:56 | `archivo:devto-articulo-final.md` (original) | `ab0eff5a1ab9` | `ENLACE` | `markdown` | **ALCANZABLE** |
| 20:05 | `devto/5059635` (vivo, corregido) | `868e951fcee2` | `ENLACE` | `markdown` | **ALCANZABLE** |
| 20:05 | `devto/5059635#render` (lo que la plataforma sirve) | `a1ad5a7718f1` | `ENLACE` | `html` | **ALCANZABLE** |

`ORIGEN_DIVERGE: 1` — el original enlaza el repositorio y la pieza publicada **no**.
En el cuerpo vivo, `github.com` aparece **0 veces** y el repositorio se nombra una
sola vez, entre acentos graves: `` `auditor-toolkit` ``.

El defecto no fue de cifras. El autor había auditado las cifras de esa pieza tres
veces. Nunca auditó si era alcanzable. **Un instrumento puede medir el objeto con
precisión y no medir su puerta.**

La tabla es **append-only**: la corrección añade la fila de las 20:05 y no borra la
de las 19:56. Una fila que se reescribe convierte la historia de la medición en
una opinión sobre el presente.

## La plataforma es inocente (medido, no supuesto)

Antes de publicar la corrección se midió el render del artículo huérfano:

```bash
--pieza devto:5059635 --render --origen devto:5059635   # SOLO_TEXTO · sin_divergencia
```

El `body_html` decía exactamente lo mismo que el `body_markdown`: **la plataforma
no había borrado ningún enlace, porque nunca hubo ninguno que borrar.** La puerta
se perdió al pegar el texto, no al servirlo. Sin ese control, el diagnóstico
habría sido "dev.to sanea enlaces" — falso, y habría mandado a arreglar el sitio
equivocado.

La plataforma **sí reescribe** algo al guardar: los bloques de código sin lenguaje
se guardan como ```` ```plaintext ````. El markdown enviado y el almacenado difieren
en 9 bytes (`ab0eff5a1ab9` → `868e951fcee2`). **La copia no es el objeto**: por eso
lo que se publica en la tabla es la huella del texto *leído*, y por eso el veredicto
se toma del render cuando se pide `--render`.

## Los cuatro estados

| estado | significado | se arregla con |
|---|---|---|
| `ENLACE` | hay URL en posición de enlace | nada: la puerta está abierta |
| `SOLO_TEXTO` | el objeto está nombrado, sin puerta | corchetes alrededor de la URL |
| `HUERFANO` | el objeto no aparece ni nombrado | escribir el objeto en la pieza |
| `NO_MEDIDO` | la pieza no se pudo leer | reintentar; **nunca** se lee como huérfano |

`SOLO_TEXTO` lleva el **detalle** de la causa, porque "falta el enlace" es un
diagnóstico y no una causa: `url_desnuda` (la dirección está escrita, sin
corchetes), `code_span`, `fence`, `imagen` (la URL pinta un pixel y no una
puerta), `referencia_sin_uso` (definida y nunca usada: el lector no la ve),
`mencion` (solo el nombre).

## Cuatro trampas que el instrumento no negocia

1. **URL desnuda no es `ENLACE`.** Se reporta `url_desnuda`. Un falso rojo se
   corrige añadiendo corchetes; un falso verde autoriza publicar una pieza
   huérfana creyendo que tiene puerta. La asimetría es deliberada.
2. **Nombrar no es enlazar.** `` `auditor-toolkit` `` describe el objeto y no lo
   alcanza. Es el defecto medido, con nombre propio.
3. **Una imagen no es una puerta.** `![portada](url)` no se pincha hacia el
   objeto, y su URL no la ve el lector. Mismo criterio que `cover_image: None`
   frente a `social_image`: una portada no es un enlace.
4. **La página servida no es la pieza.** La barra del sitio, el perfil del autor y
   la barra lateral enlazan a GitHub por su cuenta. Contar `<a href>` en el HTML
   público daría verde a cualquier artículo, incluso a uno que no menciona el
   objeto: es un **falso verde de fábrica**. Por eso `--render` lee `body_html` —
   el cuerpo que la plataforma renderizó— y no el documento completo.

## Reproducir

```bash
# reproducir
python3 research/alcance/instruments/medir_alcance.py --pieza 5059635 \
  --debe https://github.com/alexisromtz-lab/auditor-toolkit \
  --origen case_studies/devto/encontre-2-bugs-reales-en-django-20261117.md

# el render que sirve la plataforma, contra el markdown que la plataforma guarda:
# la misma pieza, tres objetos (markdown · body_html · pagina servida)
python3 research/alcance/instruments/medir_alcance.py --pieza 5059635 --render \
  --debe https://github.com/alexisromtz-lab/auditor-toolkit \
  --origen devto:5059635

# control positivo: el original corregido debe dar RC 0
python3 research/alcance/instruments/medir_alcance.py \
  --pieza case_studies/devto/encontre-2-bugs-reales-en-django-20261117.md \
  --debe https://github.com/alexisromtz-lab/auditor-toolkit

# control negativo: pieza ilegible => NO_MEDIDO, RC 2, nunca HUERFANO
python3 research/alcance/instruments/medir_alcance.py --pieza 999999999 \
  --debe https://github.com/alexisromtz-lab/auditor-toolkit

# 74 reglas del instrumento, sin red
python3 research/alcance/instruments/medir_alcance.py --self-test
```

El código de salida **es** el veredicto, porque esto es una compuerta y no un
medidor: `0` ALCANZABLE · `1` PARCIAL o SIN_ALCANCE · `2` NO_MEDIDO · `20`
argumentos mal formados.

Los vocabularios de estado y de veredicto son **disjuntos a propósito**: `estado`
habla de un objeto (`ENLACE` · `SOLO_TEXTO` · `HUERFANO` · `NO_MEDIDO`) y
`veredicto` de la pieza entera (`ALCANZABLE` · `PARCIAL` · `SIN_ALCANCE` ·
`NO_MEDIDO`). Reutilizar una palabra en los dos fue el error que este instrumento
cometió en su primer borrador y que solo se vio al escribir su prueba.

## La columna `origen`, y por qué no dice `coincide`

`origen` compara la pieza con el original declarado. Tiene cuatro etiquetas y
ninguna es "coincide", aunque el caso normal lo parezca: lo que se mide es **"la
pieza no perdió ninguna puerta que el original tuviera"**, no "las dos dicen lo
mismo". Si la plataforma *añade* un enlace (autolink de una URL desnuda), el render
sale `ENLACE` y el markdown `SOLO_TEXTO`: los dos objetos **no** coinciden, y sin
embargo no se perdió nada. Se llama `sin_divergencia` porque es lo que se midió.

| etiqueta | significado |
|---|---|
| `divergente` | el original enlazaba y la pieza no: **se perdió la puerta** |
| `sin_divergencia` | la pieza no perdió ninguna puerta del original |
| `sin_origen` | no se declaró original |
| `origen_ilegible` | se declaró y no se pudo leer |

## Publicar: lo que la API escribe y lo que solo lee

Cuatro hechos medidos el 17-Nov-2026 publicando la corrección del `5059635`. Ninguno
se deduce de la documentación; los cuatro costaron una medición.

1. **`cover_image` es de lectura.** `PUT` con `cover_image` devuelve **HTTP 200** y
   el campo sigue en `None`. El parámetro de escritura es **`main_image`**: con él,
   `cover_image` pasa a ser la URL del CDN a `width=1000,height=420`, el aspecto
   exacto que dev.to recomienda.
2. **Un 200 no es un efecto.** La primera escritura devolvió 200 y el cuerpo no
   cambió. Se verifica con un `GET` posterior *y* con la huella del texto, nunca con
   el código de estado: el mismo «verde sin efecto» que este corpus persigue en sus
   propias compuertas.
3. **La página pública responde 403 a agentes y 200 a un navegador.** Un 403 en el
   peldaño de la página es `NO_MEDIDO`, jamás «0 enlaces»: medir el bloqueo y
   llamarlo cero es el defecto que esta tabla existe para no repetir.
4. **El locus se toma de `canonical_url`, no de la memoria.** Un slug compuesto a
   mano devolvió 404 sobre una pieza que existía: se midió una URL inexistente y se
   habría diagnosticado «el artículo desapareció».

## Tres superficies, y los peldaños que cada una tiene

Una superficie sin delimitador declarado no se mide. Por eso `--pieza` no adivina lo
que recibe: lo declara. Lo que sigue se midió el 17-Nov-2026 contra el mundo, no
contra la documentación.

| superficie | especificación | peldaños | delimitador |
|---|---|---|---|
| dev.to | `5059635` · `devto:5059635` | **dos**: `body_markdown` y `body_html` | `<a href>`, y `<a href>` escapado dentro de `<code>` |
| release de GitHub | `gh:<owner>/<repo>[@tag]` | **uno**: `body` | `<a href>` |
| Zenodo | `zenodo:<registro>` | **uno**: `metadata.description` | `<a href>` |
| archivo local | ruta | el que pida `--render` | el mismo |
| URL cruda | `https://…` | ninguno | aviso en stderr, `NO_MEDIDO` |

Portar el lector de `dev.to` a las otras dos superficies midió cuatro cosas que
ninguna de ellas declara:

1. **La API de releases de GitHub no publica `body_html`.** Verificado con
   `'body_html' in d` → `False`. Pedir el segundo peldaño ahí **no es** `NO_MEDIDO`:
   es `RC 20`. Un `NO_MEDIDO` promete una medición que no puede llegar nunca, y este
   corpus ya pagó ese defecto. `--render` sobre un release es un error de uso, no un
   estado del objeto.
2. **Una copia servida antes de corregir la pieza se lee como si siguiera rota.**
   Mismo endpoint, dos segundos de diferencia: 94 B y 515 B. Desde entonces el lector
   pide `Cache-Control: no-cache`; sin eso el instrumento producía un rojo falso
   sobre una pieza que ya estaba arreglada, y el rojo venía del transporte.
3. **El depósito declara puertas en dos sitios que no son el cuerpo.** Además de
   `related_identifiers`, el registro lleva `custom["code:codeRepository"]`. Los dos
   se pintan en la barra lateral. **No se suman al veredicto** (sería sumar dos
   superficies en un veredicto) y **no se ignoran** (daría un rojo falso sobre la
   página): se publican aparte con las dos líneas `RELACIONES` y `CODIGO DECLARADO`.
   No son columnas de la tabla, que conserva sus ocho.
4. **Editar un DOI publicado con la forma vieja pierde campos en silencio.** El
   registro se creó con `related_identifiers[].relation`; el flujo de borrador
   espera `relation_type`. Un `PUT` al borrador devolvió **HTTP 200** y dejó
   `creators`, `resource_type`, `license` y `custom` en `null`, además de recortar
   `related_identifiers`. **La publicación está fail-closed** —la validación rechazó
   el borrador con 400— y el borrador se descartó (`DELETE` → 204) verificando los
   catorce campos contra la copia previa: los catorce, idénticos. El `200` no era
   prueba de que el campo hubiera entrado.

### Dos hallazgos sobre piezas ya publicadas

Las dos se midieron **antes** de tocarlas, y las filas de antes y después están en
`data/ALCANCE.tsv` (append-only: la corrección agrega fila, no edita la vieja).

| pieza | antes | después |
|---|---|---|
| `gh:alexisromtz-lab/auditor-toolkit@v0.2.0` | `fd3f50b02eae` · repo `SOLO_TEXTO/url_desnuda`, DOI `HUERFANO/ausente` · **0/2** · `SIN_ALCANCE` | `795886a32837` · repo `ENLACE`, DOI `ENLACE` · **2/2** · `ALCANZABLE` |
| `zenodo/24323318` | `bdd5b6455029` · repo `SOLO_TEXTO/mencion` · **0/1** · `SIN_ALCANCE` | sin cambio: `mencion` en el cuerpo, `CODIGO DECLARADO: 1 … 1 hacia los objetos pedidos` |

La nota del release `v0.2.0` era la línea que GitHub autogenera: 94 bytes, un
`**Full Changelog**` y ni una puerta al repositorio ni al DOI. La página del DOI
nombra `auditor-toolkit` **sólo** dentro de la URL de Pages, y su descripción no
enlaza el código. La diferencia entre las dos: el release no tenía ninguna puerta y
se arregló; el registro ya tenía la de la barra lateral, así que su rojo es de
cuerpo, no de página. Corregir el cuerpo de un DOI publicado a cambio de arriesgar
sus metadatos es un mal cambio: la puerta ya está abierta.

## Límites declarados

- No es un parser CommonMark: mide presencia de URL en posición de enlace. Los
  enlaces por referencia se resuelven (definición + uso); los construidos por
  otra extensión de la plataforma no se ven.
- Mide la pieza que se le entrega. Si dev.to reescribe el cuerpo al guardar, la
  copia que se midió no es la copia que se publicó: por eso `--origen` existe y
  por eso la tabla publica la **huella** del texto leído.
- No mide si el objeto destino responde: mide si existe una puerta, no si está
  abierta al otro lado.
- No corrige la pieza. Es un lector; publicar exige un acto humano.
- Si se pide `--origen` y no se puede leer, la fila dice `origen_ilegible`, no
  `sin_origen`: "no me dieron original" y "no pude leerlo" son estados distintos.
- El release de GitHub tiene **un** peldaño: no hay HTML servido que contrastar. La
  página renderizada autolinkea las URL desnudas, así que `SOLO_TEXTO/url_desnuda`
  sobre un release es un **falso rojo deliberado y barato**: el arreglo es un enlace
  markdown explícito, no un cambio en el instrumento.
