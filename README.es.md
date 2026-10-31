<!-- HUELLA-README-AUDITOR-TOOLKIT-20261021 -->
# Auditor-Toolkit — verificación metrológica y falsadores

Instrumentos para auditar artefactos, manifiestos y CI **sin confiar en la palabra del autor**.

La mayoría de los benchmarks miden la media. Estos instrumentos miden **el límite del instrumento**:
qué puede ver, dónde es ciego, y qué devuelve cuando no alcanza a decidir.

Cada pieza cumple cuatro reglas, y el README las muestra en vez de jurarlas:

1. **Control negativo** — todo instrumento trae el mutante que *debe* fallar.
2. **Límite declarado** — se dice dónde el instrumento es ciego. Un instrumento sin límite declarado es otra caja negra.
3. **Procedencia** — cada cifra viaja con el comando que la produce.
4. **Reproducibilidad** — un comando, sin red, reproduce la tabla.

Si un número de este README no tiene comando, es un error del README: repórtalo con el `sha256` del archivo implicado.

---

## Pieza 1 · `pre-write-gate` (A2.1) — ¿esta escritura tiene derecho a ocurrir?

Un gate que se corre **antes** de escribir: no mide el resultado, mide si la escritura está autorizada.
Contrato de cuatro parámetros — `TARGET · BLOB_PRE · HUELLA · LINEAS_PRE`.

- **Pieza.** Autoriza o bloquea una escritura comparando el blob declarado contra el blob en disco, la huella contra el archivo y las líneas contra el contrato. Si no coincide, sale con **causa impresa**, no con un adjetivo.
- **Control negativo.** `--self-test` corre el banco: **20 casos**, de los cuales **12 tienen que enrojecer** (huella ya presente `11`, blob mutado `12`, árbol sucio `13`, líneas distintas `15`, contrato incompleto `20`, repo ausente `14`, resta no declarada `16`, retiro huérfano `18`) y **8 quedan verdes por diseño** (`0` ×5, `10` ×2, `17` ×1) — un banco sin verde es tan ciego como un test sin rojo. Medido, no afirmado: `pre-write-gate --self-test` el 2026-10-21 ⇒ `CASOS: 20, VERDES: 20, ROJOS: 0`, más **1 declarado no medido** (`RC 15` con `LINEAS_PRE` sin declarar). El motor embarcado declara **13** causas en `CAUSAS`; la cifra `n_ramas=8` pertenece al **referente bash** (`tools/gate_pre_escritura.sh`, 8 `exit N` distintos) y **no** es el denominador del puerto: no se funden. Uno de los 20 casos (`B20_PARIDAD`) mide el puerto **contra** ese referente: si falta el gemelo, el banco devuelve `ROJOS: 1`, `19/20`, `RC 2` — falla cerrado en vez de pasar sin gemelo.
<!-- HUELLA-CORRECCION-BANCO-20-CAUSAS-13-20261021 -->
<!-- HUELLA-EXTRACCION-GEMELO-B20-20261021 -->
- **Límite declarado.** **No escribe** y **no autoriza por sí mismo**: `RC 0` significa *la tupla es coherente con el objeto en este instante*, no *el contenido es correcto*. No mide intención. `LINEAS_PRE` cuenta bytes `0x0A`, no líneas lógicas. `RC 13` **no enrojece** sobre un objeto git-ignored: ahí el `RC 0` es *verde latente*. `RC 10` es etiqueta ancha (también dispara si `TARGET` es un directorio inexistente).
- **Comando.**

```bash
pre-write-gate TARGET BLOB_PRE HUELLA LINEAS_PRE   # una operación
pre-write-gate --plan tuplas.declaradas.tsv        # lote; 0 tuplas ⇒ RC 31, no verde
pre-write-gate --self-test                         # banco must-fail
```

Tabla de causas completa en [`pre-write-gate/README.md`](./pre-write-gate/README.md) (`0 · 10 · 11 · 12 · 13 · 14 · 15 · 16 · 17 · 18 · 20 · 30 · 31`). El hook de pre-commit es la **mitad commit** y tiene **vocabulario propio** (`10` `13` `16`): el mismo número no significa lo mismo en las dos tablas, y no se funden.

---

## Pieza 2 · `verify_claims` — ¿la prosa dice la cifra que el dato contiene?

El aparato de manifiesto prueba que un `.json` parsea y que un `.md` tiene líneas. **No** prueba que la cifra publicada sea la del dato. Este verificador mide eso y nada más: cada claim declara la afirmación, el dato del que sale y la expresión que la deriva; se compara **derivado contra afirmado** bajo una polaridad declarada.

- **Pieza.** Cotejo prosa↔dato, con la sonda de dígitos para detectar cifras que ningún cómputo sostiene.
- **Control negativo.** `--falsador-dato` inyecta el dato falseado; el verificador debe enrojecer el claim. Sin ese mutante, un verde no distingue "la cifra es correcta" de "no la estoy mirando".
- **Límite declarado.** Cuando no hay poder para decidir, **no firma rojo**: devuelve `PODER_INSUFICIENTE`. Los veredictos `DIGITO_MUERTO`, `SIN_DIGITO_VIVO` y `PODER_INSUFICIENTE` son estados distintos y se cuentan por separado: un cero de `DIGITO_MUERTO` no es un cero de todo.
- **Comando.**

```bash
python3 verify_claims/verify_claims.py REPO [REPO ...]
python3 verify_claims/verify_claims.py --sonda-digitos REPO [REPO ...] [--presupuesto N|todo]
python3 verify_claims/verify_claims.py --falsador-dato REPO [REPO ...]
python3 verify_claims/verify_claims.py --json
```

---

## Pieza 3 · `barrido_limite_bytes` — ¿el tope es prudencia medida o decreto?

Mide el coste real de un hook de contenido en función del tamaño del archivo indexado, para decidir si `LIMITE_BYTES = 2 MiB` es una frontera **medida** o un número redondo.

- **Pieza.** Cada punto se mide en **dos regímenes sobre el mismo archivo**: `TOPE` (el hook real, que **no escanea** por encima del límite) y `RSS`/pases (el escaneo efectivo). Tamaños por defecto: `0.5 · 1 · 2 · 4 · 6 · 12` MiB, mínimo de `--reps` repeticiones.
- **Control negativo.** El régimen `TOPE` **es** el control: cronometrar solo el hook real mide la rama de rechazo (constante, ~1 s) y concluiría "el coste es plano, el tope es superstición" — *el instrumento mediría su propia excepción*. `--solo-pases` y `--solo-rss` aíslan cada mitad para que la diferencia sea visible.
- **Límite declarado.** Mide el **hook**, no el sistema de archivos. Toma el **mínimo** de las repeticiones (declarado con `--declaro-reps`), no la media: el mínimo es el coste reproducible, la media incluye el ruido de la máquina. Los forzados (`--force-sello`, `--force-ventana`, `--force-curva`, `--force-regimen`) existen para **romper** la curva a propósito, no para publicar un número más bonito. **No adivina el hook**: si falta, o no declara `LIMITE_BYTES=<cap>` exactamente una vez, falla cerrado (`RC 5`) en vez de medir otra cosa. Aquí el hook vive en `tools/hooks/pre-commit`; `--hook` existe para medir una **copia** sin tocar el real.
- **Comando.**

```bash
python3 barrido_limite_bytes/barrido_limite_bytes_20261021.py --repo . --solo-pases
python3 barrido_limite_bytes/barrido_limite_bytes_20261021.py --repo . \
  --sizes 0.5,1,2,4,6,12 --reps 2 --json puntos.json
```
<!-- HUELLA-EXTRACCION-HOOK-DEFAULT-20261021 -->

---

## Pieza 4 · `ci_sweep.py` — ¿qué dicen los checks actuales de los PRs paginados?

Inventaría PRs abiertos y clasifica los shards configurados contra el SHA actual de cada PR.

- **Pieza.** Lista PRs y consulta check-runs con paginación; registra `ROJO`, `VERDE`, `PENDIENTE`, `SIN_CHECKS` o `NO_VERIFICABLE`, junto con SHA y fecha medidos.
- **Control negativo.** `--self-test` comprueba cinco resultados sintéticos, incluidos checks ausentes y una ejecución cancelada; ninguno se convierte en verde.
- **Límite declarado.** `--limit` es un tope, no un censo. La caché local predeterminada vence en 900 segundos; los reintentos usan backoff acotado. `CANDIDATA_FUERA_DEL_DIFF` solo significa que el archivo del caso no aparece en el diff: no es prueba causal. El barrido no descarga logs ni recrea mediciones históricas.
- **Comando.**

```bash
python3 ci_sweep.py --repo tenstorrent/tt-metal --out ci-sweep.json --limit 1000
python3 ci_sweep.py --self-test
```

<!-- HUELLA-CI-SWEEP-README-ES-20261021 -->

---

## Pieza 5 · `auditar_supply_chain.py` — ¿un workflow concede más de lo que necesita?

Lee workflows de GitHub Actions y publica lo que el gate encuentra, un código por hallazgo, agrupado por política: **SC-1** (qué concede `permissions` en la raíz del workflow — alcances explícitos, `write` heredado), **SC-2** (refs de acciones remotas fijadas a un SHA completo), **SC-3** (`pull_request_target` / `workflow_run` que alcanza un contexto privilegiado con entrada no confiable). Un universo vacío no es un certificado de limpieza: una raíz sin workflows devuelve `UNIVERSO_VACIO`, nunca `PASS`.

- **Pieza.** Una tabla de reglas y un llamador: los veredictos los emite `gate_workflows_ci.py`, un port de 711 líneas del gate privado, vendorizado aquí para que el auditor se sostenga solo.
- **Control negativo.** `--self-test` corre 19 workflows sintéticos —uno por código, más las formas que deben quedarse calladas— y falla si falta un código esperado o aparece uno inesperado.
- **Límite declarado.** Lee los archivos de workflow del checkout o del repositorio que le señalas; no se autentica por su cuenta contra la API de GitHub ni juzga si el código de un job es confiable. Un hallazgo habla de la superficie de permisos declarada, no del runtime.
- **Dependencia.** `PyYAML` (ver `requirements.txt`). Sin ella el auditor no adivina: se detiene con `UNVERIFIABLE` y `DEPENDENCIA_GATE_AUSENTE_RC_30`.
- **Comando.**

```bash
python3 -m pip install -r requirements.txt
python3 auditar_supply_chain.py --self-test
python3 auditar_supply_chain.py --repo alexisromtz-lab/git-preflight-gate
```

<!-- HUELLA-PORT-SUPPLY-AUDITOR-TOOLKIT-20261031 -->

---

## Caso de estudio · tt-metal (CI) — el barrido que evitó un cero falso

Medido el 2026-10-19T05:42Z sobre `tenstorrent/tt-metal`.

**Lo que se midió, y lo que NO se mide:**

- Universo: **1000** PRs abiertos — **tope de paginación**, no censo total. Se declara el tope; no se presenta como universo.
- **12** PRs con `sim_wh_n150` o `sim_bh_p150` en rojo.
- **8** confirmados con la causa **fuera de su propio diff**.
- **6** logs de job descargados: en los 6, **un solo nodo** falla, y es el mismo.
- **229** PRs inventariados.

**La corrección que da valor al método:** el rollup de la API se corta a **100 entradas**, y en **143** PRs ese corte **ocultaba el shard rojo**. Un barrido que solo lee la primera ventana reporta un **cero falso**. Ese cero falso se detectó primero en casa.

**Causa raíz: una, no doce.** `tests/ttnn/unit_tests/operations/transformers/test_prefetcher_worker_pipes.py` no lleva `@skip_for_slow_dispatch`; entró con el PR #59955 y bloquea PRs cuyo diff no lo toca. Por eso este documento dice **12 PRs rojos por shard**, y no "12 fallos": doce síntomas, una causa.

**Lo que NO hay:** **0** PRs competidores abiertos, **0** merges, **0** bounties cobrados. El rastro público son **12** comentarios de diagnóstico, con URL por PR.

---

## Hoja de ruta — declarada ausente, no prometida

Lo que todavía **no existe** se dice aquí en vez de aparecer como "pieza" en la tabla de arriba:

- **Checkpoint atómico / guardián de objetos.** No hay implementación publicada. El requisito está claro: escritura `os.replace`, control negativo con `kill -9` a mitad de proceso, y el archivo resultante debe contener los ítems parciales (**no 0 bytes**). Hasta que exista el script y su `kill -9`, no hay pieza.
- **Reproducción histórica completa de CI.** `ci_sweep.py` mide checks actuales y aplica el criterio de archivo ausente del diff, pero no descarga logs ni reconstruye el barrido histórico de 2026-10-19 (229 PRs, 12 shards rojos, 8 casos fuera del diff y 6 logs).
- **Packaging del driver D4B.** Existe como driver de investigación con sus semillas y blobs declarados, **no** como instrumento de línea de comandos. No se le inventan flags.

---

## Principios de colaboración

- No pedimos bounties: pedimos **datasets** y **merges**.
- Si encuentras un fallo en este toolkit, adjunta el **`sha256` del mutante** que lo demuestra.
- Un reporte sin límite declarado se lee como opinión. Un reporte con límite declarado se puede re-auditar — y eso es todo lo que este repo ofrece.
