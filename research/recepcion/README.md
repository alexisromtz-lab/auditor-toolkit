# Recepción — la cuarta etapa del embudo

El embudo que este repositorio publica tiene tres etapas medidas: **candidato**
(AST estático) → **ruptura** (ejecución real) → **consumidor** (búsqueda pública).
`research/frontera-import/` cerró la tercera con un número incómodo: 1 449 módulos,
2 rupturas reales, **0 consumidores**.

Falta la cuarta: **¿alguien leyó lo publicado?** Sin ella, «estamos ganando
presencia» es una opinión. Este directorio la convierte en un estado medible.

## La línea base (2026-11-17)

| clase | valor | qué cuenta |
|---|---|---|
| `LECTOR` | **2** | vistas de página del repo (14 d) + vistas de registro en Zenodo |
| `DESCARGA` | **1** | zip del DOI, todas las versiones |
| `SENAL` | **0** | estrellas + forks |
| `CLON` / `CLON_UNICO` | 488 / 168 | se publican aparte; **no** son lectores |
| `HUELLA_PROPIA` | **121** | corridas de CI propias en la misma ventana (lectura de `20:41Z`; la ventana es móvil y sube con cada corrida): **piso** del rastreo propio, no su explicación |
| `LECTOR_DEVTO` | `NO_MEDIDO` | `page_views_count` exige credencial de autor |
| `SENAL_DEVTO` | **0** | reacciones + comentarios del artículo |

## Cuatro trampas que el instrumento se niega a repetir

1. **Un clon no es un lector, y muchas veces es la huella del observador.**
   `architecture-audit.yml` clona este mismo repositorio dos veces por corrida: una
   en `actions/checkout` y otra en el `git fetch --depth=1` que baja el motor.
   `ci.yml` clona una por job, y tiene dos. Medido el 17-11-2026, por día:

   | día | corridas | de ellas clonan | clones | uniques | clones/corrida |
   |---|---:|---:|---:|---:|---:|
   | 13-11 | 63 | 42 | 211 | 62 | 3,35 |
   | 14-11 | 12 | 6 | 56 | 23 | 4,67 |
   | 15-11 | 4 | 2 | 136 | 56 | **34,0** |
   | 16-11 | 8 | 4 | 53 | 26 | 6,63 |

   «Clonan» son las corridas de `architecture-audit` (2 por corrida) y de `ci`
   (2 jobs); las de Pages y las omitidas no clonan. El dato que importa no es la
   correlación sino la **magnitud**: 54 corridas × 2 = **108** clones atribuibles
   contra **456** medidos, y aun contando las 87 como si todas clonaran dos veces,
   174. El CI cubre entre el **24 % y el 38 %**. Sobre los 14 días el techo es
   `2 × 121 = 242` contra 488 (50 %), y esa cuenta cruza ventanas: se publica como
   tope, no como cifra.

   Por eso no se dice «los clones siguen a las corridas»: el día 15, con 4
   corridas, produjo 136 clones. Un dato que no encaja se declara, no se absorbe.
   Lo que sí queda establecido, y no depende del dueño: 456 de los 488 clones
   ocurrieron **antes** de todo acto de publicación (tag `v0.1.0` el 16-11 a las
   21:59, `v0.2.0` y el artículo el 17-11), y en la misma ventana la portada del
   repositorio recibió **2 vistas**.

   Consecuencia para leer la tabla: `CLON` no se resta solo ni se interpreta como
   audiencia; se lee contra `runs_ci`. La hipótesis de la puerta —«la gente llega
   pero no encuentra el enlace»— **no queda refutada por este dato: queda sin
   probar**, porque no había población que llegara.
2. **En Zenodo, `downloads` de una versión hereda el total del concepto.** La cifra
   propia es `version_*`. Medido: v0.2.0 declara `downloads: 1` y
   `version_downloads: 0` — el zip nuevo no se descargó nunca, y el 1 es del v0.1.0.
3. **`clones` contiene `clones_unicos`.** Sumarlos inventa clones que no existen. El
   primer defecto de este instrumento fue exactamente ese: 656 donde había 488.
4. **La regla decidía sobre una cifra que la tabla no publicaba.** La enmienda 4
   sella que decide `vistas_pagina` **únicas**, y la tabla publicaba el **conteo**
   bajo ese mismo nombre. Medido el 17-11-2026 a las 20:41:39Z: la fila decía
   `github  vistas_pagina  2`, y ese `2` era `count`. Coincidía con `uniques`
   **sólo porque con dos visitas las dos cifras son la misma** — el defecto era
   invisible en la línea base y se activaba justo en el umbral, donde divergen.
   Ahora se publica `vistas_pagina_unicas` en clase `POBLACION`, que no se suma a
   `LECTOR`: sería contar dos veces al mismo lector. **El umbral no se movió**; se
   alineó el instrumento al nombre que la regla ya tenía.

## Superficies distintas, clases distintas

`LECTOR_DEVTO` y `SENAL_DEVTO` **no se suman** a `LECTOR` / `SENAL`. Quien lee el
artículo no es quien vio el repositorio; sumarlos fabrica una audiencia. Y como
`page_views_count` exige llave de autor, sumarlo degradaría el `LECTOR` ya medido a
`NO_MEDIDO` y borraría la línea base.

`POBLACION` tampoco se suma a nada. Es la clase de la cifra que **decide**
(`vistas_pagina_unicas`), y el conteo total (`vistas_pagina`, clase `LECTOR`) ya
cuenta a ese mismo lector: sumarlos daría el doble de la audiencia real.

## Reproducir

```bash
python3 instruments/medir_recepcion.py --self-test          # 34/34, sin red
python3 instruments/medir_recepcion.py \
  --recid 24323318 --repo alexisromtz-lab/auditor-toolkit --articulo 5059635 \
  --tsv data/RECEPCION.tsv
python3 instruments/medir_recepcion.py \
  --repo alexisromtz-lab/auditor-toolkit --canal           # nombra el canal, no escribe
python3 instruments/medir_recepcion.py \
  --repo alexisromtz-lab/auditor-toolkit --articulo 5059635 --veredicto   # la regla, no a mano
```

`--canal` es el lector de la rama C del pre-registro: cuando no hay población, el
acto siguiente no es escribir más ni empaquetar, es **nombrar de dónde vienen las
visitas que sí hubo**. Lee `traffic/popular/referrers` y `traffic/popular/paths`,
no toca el TSV, y sale con RC 0 si midió y RC 2 si no pudo leer. Medido el
17-11-2026: el único `referrer` es `github.com` (1 vista) — **cero referrers
externos**, que es el estado que P3 va a evaluar el 19-11.

`github.com` como `referrer` es **navegación dentro de GitHub**, no una puerta de
entrada: por eso el lector lo separa y publica una línea `puerta externa`. Sin esa
separación, la rama A se habría disparado con cero tráfico de fuera — es decir,
habría declarado «hay puerta» justo cuando la puerta es lo que falta.

`--veredicto` aplica la regla sellada y **no escribe nada**. Sale con RC 0 cuando
la rama es A, B o C, y con **RC 2 cuando la rama es D**: en este contrato 2 significa
`NO_MEDIDO`, y un fallo del instrumento no es un veredicto sobre el objeto. Imprime
las tres entradas con su umbral y su estado, distinguiendo `NO_PEDIDA` (no se pasó
`--articulo`) de `NO_MEDIDO` (se pidió y no se pudo leer): la rama es la misma, el
remedio no.

Sin `DEVTO_API_KEY` la superficie de vistas queda en `NO_MEDIDO`. Es el resultado
correcto, no un fallo: esa cifra sólo la tiene el autor.

## El pre-registro, y el defecto que lleva dentro

`PREDICCION_recepcion.txt` fija los umbrales a 48 h **antes** de que exista una sola
lectura de la recepción del artículo. También declara su propio defecto: se registró
**365 s después** de la publicación, no antes, y la frase original que afirmaba lo
contrario queda citada en la enmienda en vez de borrada.

De ahí sale la regla que ahora es una fila de la tabla: `ESTADO_PIEZA` publica
`publicado` y `horas_desde_publicacion`. La ventana de una predicción deja de vivir
en la prosa y pasa a ser un dato que se puede restar.

La **enmienda 4** cierra el hueco que quedaba: los umbrales estaban fijados, pero no
lo que se hace con cada resultado. Una consecuencia que se decide después del dato no
es una predicción, es una negociación. La regla sellada decide con **`vistas_pagina`
únicas**, nunca con `CLON`:

| rama | condición | acto siguiente |
|---|---|---|
| A | `P1 ≥ 15` y (`P3 ≥ 1` o `P4 ≥ 50`) | empaquetar la GitHub Action |
| B | `P1 ≥ 15` pero sin puerta (`P3 = 0`, `P4 < 50`) | la puerta, no el producto |
| C | `P1 < 15` | medir el canal (`--canal`), no escribir más |
| D | alguna entrada necesaria = `NO_MEDIDO` | no se decide: se reejecuta |

`P1` = `vistas_pagina_unicas` del repositorio (ventana de 14 d) · `P3` = referrers
**externos** (`github.com` no cuenta) · `P4` = vistas del artículo en dev.to.
`CLON` no decide en ninguna rama.

La regla **se ejecuta** con `decidir()` vía `--veredicto`; no se aplica a mano el día
del corte. Una consecuencia evaluada a mano sobre dos comandos y ocho columnas es una
consecuencia que se puede leer mal, y la rama D existe precisamente para no confundir
un fallo del instrumento con un veredicto sobre el objeto.

La regla trae su propio falsador: si el 19-11 hay ≥ 15 vistas y aun así `referrers`
vuelve vacío, quien falla es el instrumento, no el canal.

## Límites declarados

- GitHub entrega una **ventana móvil de 14 días**; esas cifras no son acumuladas.
- Los stats de Zenodo son acumulados por registro, no por descargador: no dicen
  *quién* descargó.
- `NO_MEDIDO` no es cero. Una clase pedida sin filas totaliza `NO_MEDIDO`, no `0`.
- Sólo dos superficies hablan de personas: dev.to y GitHub. El resto del tráfico del
  repositorio no es atribuible a un lector.
