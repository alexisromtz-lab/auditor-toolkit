<!-- HUELLA-PRE-WRITE-GATE-README-20261015 -->
<!-- HUELLA-SELLO-PASO2-README-20261015 · RC 17 autorizo · divergencia declarada: RC 13 = tracked-dirty · RC 17 = objeto-nuevo -->
# pre-write-gate (A2.1)

**Un gate que se corre ANTES de escribir.** No mide el resultado: mide si la escritura
tiene derecho a ocurrir. Si el destino ya cambió, si la huella ya habita el archivo, si
el blob declarado no es el blob en disco o si el árbol está sucio con cambios no
adjudicados, **la escritura no se autoriza** — y el código lo dice con una causa, no con
un adjetivo.

Instrumento de una sola pregunta, **contrato de cuatro parámetros**:

```
TARGET · BLOB_PRE · HUELLA · LINEAS_PRE
```

| parámetro | qué es | cómo se obtiene |
|---|---|---|
| `TARGET` | ruta **absoluta** del destino | tu ruta, resuelta |
| `BLOB_PRE` | blob git del contenido esperado | `git hash-object <archivo>` (o `git rev-parse HEAD:<ruta>`) |
| `HUELLA` | marcador único de ESTA operación | tu identificador (`HUELLA-MODULO-FECHA`) |
| `LINEAS_PRE` | líneas esperadas; `-` = **no declarado** | `wc -l` |

`BLOB_PRE` de una **creación** es el blob centinela de git (contenido 0 bytes):
`e69de29bb2d1d6434b8b29ae775ad8c2e48c5391`. Con `LINEAS_PRE = 0`.

---

## Tabla de causas (RC)

`RC` **y causa impresa** deben coincidir: un caso que devuelve el código esperado por
otro motivo no discrimina. El gate imprime `CAUSAS PRESENTES: {rc:N|CAUSA}` y en `--json`
el campo `"causa"`.

| RC | causa | significa | bloquea |
|---|---|---|---|
| `0` | `PRE_VUELO_OK` | edición sobre tracked limpio, identidad verificada | no |
| `10` | `OBJETO_INEXISTENTE` | el destino **no existe** ⇒ **creación autorizada** | no |
| `11` | `HUELLA_YA_HABITA` | la huella **ya está** en el destino ⇒ **cumplimiento pasivo: CERO escrituras** | no |
| `12` | `DESFASE_DE_OBJETO` | `blob(disco) != blob(contrato)` ⇒ **árbol en movimiento** | sí |
| `13` | `ESTADO_SUCIO` | el destino **tracked** tiene modificaciones **no adjudicadas** (no incluye objetos sin historia en el índice: eso es `17`) | sí |
| `14` | `SIN_REPO` | el destino no vive en un árbol git ⇒ **fail-closed** | sí |
| `15` | `LINEAS_DISTINTAS` | líneas medidas **≠** declaradas | sí |
| `17` | `OBJETO_NUEVO` | existe en disco con blob y líneas conformes, pero **sin historia en el índice** ⇒ **creación autorizada** *(divergencia declarada del referente bash, que lo leía como `13`)* | no |
| `20` | `CONTRATO_INCOMPLETO` | tupla ausente o `TARGET` no absoluto | sí |
| `30` | `MOTOR_INCOMPLETO` | `git` ausente ⇒ **fail-closed** *(solo el port)* | sí |
| `31` | `UNIVERSO_VACIO` | `--plan` con **0 tuplas útiles**: no hay nada que medir | sí |

Fuera de contrato y **declarado, no reparado** (referente bash): un `TARGET` relativo cae
en el paso de git con la ruta duplicada y git sale `128`. El port no lo reproduce: lo
resuelve como `20`. Un `RC` fuera de la tabla **no es una causa del contrato**.

**Orden de las guardas (importa):** `20 → 10 → 11 → 14 → 12 → 13 → 15 → 17 → 0`.
La sonda de huella corre **antes** de los pasos de git, así que `11` funciona incluso con
ruta relativa. `LINEAS_PRE = '-'` no enrojece: sale `RC 0` con
`VEREDICTO: PRE-VUELO OK (PARCIAL: lineas_pre no declarado)` — **el RC era correcto, la
palabra `VERDE` es la que mentía**.

---

## Dos caminos de descarga

### A) Copia del YAML (sin instalar nada)

`pre-write-gate/examples/pre-write-gate.yml` → cópialo a `.github/workflows/` de tu repo.
La action es **compuesta y vive en subdirectorio** (un repo tiene **un solo** `action.yml`
en la raíz; el de este repo ya estaba ocupado), así que se invoca por ruta:

```yaml
- uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
  with:
    fetch-depth: 0          # el gate lee git; sin historia no puede medir
- uses: ./pre-write-gate
  with:
    plan: pre-write-gate/tuplas.declaradas.tsv
    lineas-pre: "-"
    fail-on-red: "true"
```

Pinnea por **SHA-1 de 40 hex**, nunca por tag flotante: un tag flotante mueve el gate
bajo tus pies. En otro repo: `uses: <owner>/<repo>/pre-write-gate@<sha>`.

### B) `pip install` + hook de pre-commit

```bash
pip install ./pre-write-gate            # o: pip install git+<url>@<sha>#subdirectory=pre-write-gate
```

Instala el paquete **sin dependencias externas** (stdlib + `git`) y deja el ejecutable:

```bash
pre-write-gate TARGET BLOB_PRE HUELLA LINEAS_PRE
pre-write-gate --plan pre-write-gate/tuplas.declaradas.tsv
pre-write-gate --self-test          # banco must-fail, 12 casos
pre-write-gate --json               # salida cruda para máquinas
```

El hook (`pre-write-gate/hooks/pre-commit`) es la **mitad commit** del gate: el gate
responde *¿puedo escribir?*, el hook *¿el commit está cubierto por una tupla declarada?*
Cada ruta en el índice debe tener su tupla en `pre-write-gate/tuplas.declaradas.tsv`;
si el `BLOB_PRE` declarado ya no es el blob del commit padre, el hook sale `12` y **el
commit no pasa**. No colisiona con el hook de higiene en `tools/hooks/pre-commit`.

#### Vocabulario PROPIO del hook (no es el del gate)

El hook es la otra mitad y tiene **sus propias causas**: el **mismo número no significa lo
mismo** en las dos tablas, así que **no se funden**.

| RC hook | causa | significa |
|---|---|---|
| `10` | `ESCRITURA_NO_DECLARADA` | path staged **sin** tupla en el manifiesto *(causa PROPIA del hook)* |
| `13` | `MANIFIESTO_EN_MISMO_COMMIT` | la declaración se reescribe **junto a** lo declarado |
| `16` | `HUELLA_AUSENTE_EN_ESCRITO` | lo escrito **no contiene** la huella declarada *(causa PROPIA del hook)* |

Paths **exentos**: `pre-write-gate/**` — la herramienta escribe su propio código. El hook
imprime `PATHS STAGED MEDIDOS: N (exentos: pre-write-gate/**)`, de modo que un archivo de
la herramienta no se lee como escritura no declarada.

---

## Formato del manifiesto (`--plan`)

Una tupla por línea, cuatro campos, `-` donde no se declara. Líneas en blanco y `#` se
saltan. Una línea con ≠4 campos es `RC 20` **de esa línea**. Lote sin bloqueos ⇒ `RC 0`.

```
# TARGET	BLOB_PRE	HUELLA	LINEAS_PRE
/abs/ruta/a/modulo.py	8db0de859a6789bf5f341e0b593a1e9929e6525e	HUELLA-MODULO-20261015	508
/abs/ruta/a/nuevo.md	e69de29bb2d1d6434b8b29ae775ad8c2e48c5391	HUELLA-NUEVO-20261015	0
```

El veredicto del lote es el **mínimo** de los RC bloqueantes; sin bloqueantes, `0`.
`--plan` con `0` tuplas es `31`: **no se declara verde un lote que no midió nada**.

---

## Qué NO hace

- **No escribe.** Ni el gate ni la action ni el hook escriben en tu corpus. El banco
  escribe **solo** en un `tmpdir` fuera del repo y lo declara.
- **No autoriza por sí mismo.** El gate **reporta**; la escritura la decide quien lo
  invoca. `RC 0` significa *la tupla es coherente con el objeto en este instante*, no
  *el contenido es correcto*.
- **No sustituye al revisor.** Mide identidad y colisión; no mide intención.
- **No adivina.** `LINEAS_PRE` sin declarar sale `PARCIAL`, no verde pleno.

---

## Residuo declarado

- `LINEAS_PRE` cuenta **bytes `0x0A`**, no líneas lógicas: un archivo sin salto final
  declara una línea menos que su número de líneas. Divergencia **declarada** del
  referente bash, no error.
- **`RC 13` no puede enrojecer sobre un objeto git-ignored** (`.gitignore` lo saca del
  índice): ahí el `RC 0` es **verde latente**. Cobertura de ramas medida: `n_ramas=8`,
  8/8 ejercitadas cada una por su causa impresa.
- **`RC 10` es la etiqueta ANCHA**: también dispara si `TARGET` es un **directorio** que
  no existe. No se estrecha sin orden: se declara.
- El port **añade** `RC 15` (rama que el referente declaraba y **no tenía**) y el eco de
  éxito `PRE-VUELO OK` (el referente salía `0` en silencio). No se le quita nada.

## Archivos

| ruta | qué es |
|---|---|
| `pre-write-gate/gate_pre_escritura.py` | motor (port Python del referente bash) |
| `pre-write-gate/action.yml` | action compuesta (wrapper de CI) |
| `pre-write-gate/pyproject.toml` | paquete instalable + console script |
| `pre-write-gate/hooks/pre-commit` | hook de la mitad commit |
| `pre-write-gate/examples/pre-write-gate.yml` | ejemplo para copiar a `.github/workflows/` |
| `.github/workflows/pre-write-gate.yml` | workflow vivo de este repo |
| `tools/gate_pre_escritura.sh` | **referente** bash (no modificado) |

## Objetos Inmutables y el Ciclo de Vida de la Tupla

Cuando un archivo entra a `tuplas.declaradas.tsv`, adquiere el estatus de **Objeto Inmutable**. Esto implica dos reglas estrictas:

1. **La Huella es Permanente:** Una vez que una tupla cita una `HUELLA` y el archivo la contiene, cualquier intento de editar el archivo hará que el motor devuelva `rc=11 (HUELLA_YA_HABITA)`. Para modificarlo, es obligatorio declarar una nueva fila con una huella distinta.
2. **La Retirada es Auditable:** Si un Objeto Inmutable desaparece de `tuplas.declaradas.tsv`, el motor emitirá `RC 16 (RESTA_NO_DECLARADA)` a menos que se registre su retiro explícito en `tuplas.retiradas.tsv`.

*El manifiesto no es una lista de sugerencias; es un libro contable de la integridad.*

<!-- HUELLA-README-OBJETOS-INMUTABLES-20261018 -->
