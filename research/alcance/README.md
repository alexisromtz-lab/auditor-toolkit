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

# 46 reglas del instrumento, sin red
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
