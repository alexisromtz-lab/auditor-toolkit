# Alcance — ¿la pieza abre la puerta al objeto?

La etapa 0 del embudo. Las otras cuatro (candidato, ruptura, consumidor, recepción)
suponen algo que nadie medía: que el lector **pueda llegar**. Una pieza puede
describir un objeto con precisión perfecta y no ofrecer ninguna puerta.

## El hallazgo que creó este instrumento

Medido el 17-Nov-2026 sobre el artículo `dev.to/5059635`:

| superficie | huella | estado | detalle | veredicto |
|---|---|---|---|---|
| `devto/5059635` (vivo) | `287e6b023274` | `SOLO_TEXTO` | `code_span` | **SIN_ALCANCE** |
| `archivo:devto-articulo-final.md` (original) | `ab0eff5a1ab9` | `ENLACE` | `markdown` | **ALCANZABLE** |

`ORIGEN_DIVERGE: 1` — el original enlaza el repositorio y la pieza publicada **no**.
En el cuerpo vivo, `github.com` aparece **0 veces** y el repositorio se nombra una
sola vez, entre acentos graves: `` `auditor-toolkit` ``.

El defecto no fue de cifras. El autor había auditado las cifras de esa pieza tres
veces. Nunca auditó si era alcanzable. **Un instrumento puede medir el objeto con
precisión y no medir su puerta.**

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

## Tres trampas que el instrumento no negocia

1. **URL desnuda no es `ENLACE`.** Se reporta `url_desnuda`. Un falso rojo se
   corrige añadiendo corchetes; un falso verde autoriza publicar una pieza
   huérfana creyendo que tiene puerta. La asimetría es deliberada.
2. **Nombrar no es enlazar.** `` `auditor-toolkit` `` describe el objeto y no lo
   alcanza. Es el defecto medido, con nombre propio.
3. **Una imagen no es una puerta.** `![portada](url)` no se pincha hacia el
   objeto, y su URL no la ve el lector. Mismo criterio que `cover_image: None`
   frente a `social_image`: una portada no es un enlace.

## Reproducir

```bash
# la pieza viva contra su original: aquí vive el RC 1
python3 research/alcance/instruments/medir_alcance.py --pieza 5059635 \
  --debe https://github.com/alexisromtz-lab/auditor-toolkit \
  --origen ~/Desktop/devto-articulo-final.md

# control positivo: el original corregido debe dar RC 0
python3 research/alcance/instruments/medir_alcance.py \
  --pieza ~/Desktop/devto-articulo-final.md \
  --debe https://github.com/alexisromtz-lab/auditor-toolkit

# control negativo: pieza ilegible => NO_MEDIDO, RC 2, nunca HUERFANO
python3 research/alcance/instruments/medir_alcance.py --pieza 999999999 \
  --debe https://github.com/alexisromtz-lab/auditor-toolkit

# 30 reglas del instrumento, sin red
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
