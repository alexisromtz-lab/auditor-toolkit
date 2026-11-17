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
| `HUELLA_PROPIA` | **121** | corridas de CI propias en la misma ventana: acotan `CLON` |
| `LECTOR_DEVTO` | `NO_MEDIDO` | `page_views_count` exige credencial de autor |
| `SENAL_DEVTO` | **0** | reacciones + comentarios del artículo |

## Tres trampas que el instrumento se niega a repetir

1. **Un clon no es un lector, y muchas veces es la huella del observador.**
   `architecture-audit.yml` corre en cada push y clona este mismo repositorio dos
   veces: una en `actions/checkout` y otra en el `git fetch --depth=1` que baja el
   motor. Medido el 17-11-2026, por día:

   | día | corridas | clones | uniques | clones/corrida |
   |---|---:|---:|---:|---:|
   | 13-11 | 63 | 211 | 62 | 3,35 |
   | 14-11 | 12 | 56 | 23 | 4,67 |
   | 15-11 | 4 | 136 | 56 | **34,0** |
   | 16-11 | 8 | 53 | 26 | 6,63 |

   Tres de cuatro días siguen al número de corridas. El día 15 **no** encaja y se
   declara sin explicación en vez de absorberlo: la huella del CI es una **cota
   inferior**, no una explicación total. Lo que sí queda establecido es que 456 de
   los 488 clones (93 %) ocurrieron **antes** de todo acto de publicación (tag
   `v0.1.0` el 16-11 a las 21:59, `v0.2.0` y el artículo el 17-11), y que en la
   misma ventana la portada del repositorio recibió **2 vistas**.

   Consecuencia para leer la tabla: `CLON` no se resta solo ni se interpreta como
   audiencia; se lee contra `runs_ci`. La hipótesis de la puerta —«la gente llega
   pero no encuentra el enlace»— **no queda refutada por este dato: queda sin
   probar**, porque no había población que llegara.
2. **En Zenodo, `downloads` de una versión hereda el total del concepto.** La cifra
   propia es `version_*`. Medido: v0.2.0 declara `downloads: 1` y
   `version_downloads: 0` — el zip nuevo no se descargó nunca, y el 1 es del v0.1.0.
3. **`clones` contiene `clones_unicos`.** Sumarlos inventa clones que no existen. El
   primer defecto de este instrumento fue exactamente ese: 656 donde había 488.

## Superficies distintas, clases distintas

`LECTOR_DEVTO` y `SENAL_DEVTO` **no se suman** a `LECTOR` / `SENAL`. Quien lee el
artículo no es quien vio el repositorio; sumarlos fabrica una audiencia. Y como
`page_views_count` exige llave de autor, sumarlo degradaría el `LECTOR` ya medido a
`NO_MEDIDO` y borraría la línea base.

## Reproducir

```bash
python3 instruments/medir_recepcion.py --self-test          # 16/16, sin red
python3 instruments/medir_recepcion.py \
  --recid 24323318 --repo alexisromtz-lab/auditor-toolkit --articulo 5059635 \
  --tsv data/RECEPCION.tsv
```

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

## Límites declarados

- GitHub entrega una **ventana móvil de 14 días**; esas cifras no son acumuladas.
- Los stats de Zenodo son acumulados por registro, no por descargador: no dicen
  *quién* descargó.
- `NO_MEDIDO` no es cero. Una clase pedida sin filas totaliza `NO_MEDIDO`, no `0`.
- Sólo dos superficies hablan de personas: dev.to y GitHub. El resto del tráfico del
  repositorio no es atribuible a un lector.
