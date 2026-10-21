<!-- HUELLA-README-AUDITOR-TOOLKIT-EN-20261021 -->
# Auditor-Toolkit — metrological verification and falsifiers

Instruments to audit artifacts, manifests and CI **without trusting the author's word**.

Most benchmarks measure the average. These instruments measure **the limit of the instrument**:
what it can see, where it is blind, and what it returns when it cannot decide.

Every piece follows four rules, and the README shows them instead of swearing them:

1. **Negative control** — every instrument ships the mutant that *must* fail.
2. **Declared limit** — it states where the instrument is blind. An instrument without a declared limit is just another black box.
3. **Provenance** — every number travels with the command that produces it.
4. **Reproducibility** — one command, no network, reproduces the table.

If a number in this README lacks its command, that is a README error: report it with the `sha256` of the file involved.

Spanish version: [`README.es.md`](./README.es.md).

---

## Piece 1 · `pre-write-gate` (A2.1) — does this write have the right to happen?

A gate that runs **before** writing: it does not measure the result, it measures whether the write is authorized.
Four-parameter contract — `TARGET · BLOB_PRE · HUELLA · LINEAS_PRE`.

- **Piece.** Authorizes or blocks a write by comparing the declared blob against the blob on disk, the marker against the file, and the lines against the contract. On mismatch it exits with an **imprinted cause**, not an adjective.
- **Negative control.** `--self-test` runs the bench: **20 cases**, of which **12 must redden** (marker already present `11`, mutated blob `12`, dirty tree `13`, different lines `15`, incomplete contract `20`, absent repo `14`, undeclared subtraction `16`, orphan retirement `18`) and **8 stay green by design** (`0` ×5, `10` ×2, `17` ×1) — a bench with no green is as blind as a test with no red. Measured, not asserted: `pre-write-gate --self-test` on 2026-10-21 ⇒ `CASOS: 20, VERDES: 20, ROJOS: 0`, plus **1 declared not measured** (`RC 15` with `LINEAS_PRE` undeclared). The shipped engine declares **13** causes in `CAUSAS`; the figure `n_ramas=8` belongs to the **bash referent** (`tools/gate_pre_escritura.sh`, 8 distinct `exit N`) and is **not** the port's denominator: the two are not merged. One of the 20 cases (`B20_PARIDAD`) measures the port **against** that referent: if the twin is absent the bench returns `ROJOS: 1`, `19/20`, `RC 2` — it fails closed instead of passing without a twin.
<!-- HUELLA-CORRECCION-BANCO-20-CAUSAS-13-20261021 -->
<!-- HUELLA-EXTRACCION-GEMELO-B20-20261021 -->
- **Declared limit.** It **does not write** and **does not authorize by itself**: `RC 0` means *the tuple is coherent with the object at this instant*, not *the content is correct*. It does not measure intent. `LINEAS_PRE` counts `0x0A` bytes, not logical lines. `RC 13` **does not redden** on a git-ignored object: there, `RC 0` is *latent green*. `RC 10` is a wide label (it also fires when `TARGET` is a non-existent directory).
- **Command.**

```bash
pre-write-gate TARGET BLOB_PRE HUELLA LINEAS_PRE   # one operation
pre-write-gate --plan tuplas.declaradas.tsv        # batch; 0 tuples ⇒ RC 31, not green
pre-write-gate --self-test                         # must-fail bench
```

Full cause table (`0 · 10 · 11 · 12 · 13 · 14 · 15 · 16 · 17 · 18 · 20 · 30 · 31`) in [`pre-write-gate/README.md`](./pre-write-gate/README.md) *(in Spanish)*. The pre-commit hook is the **commit half** and has its **own vocabulary** (`10` `13` `16`): the same number does not mean the same thing in the two tables, and they are not merged.

Blocking order of the guards: `20 → 10 → 11 → 14 → 12 → 13 → 15 → 17 → 0`.

---

## Piece 2 · `verify_claims` — does the prose say the number the data contains?

The manifest apparatus proves that a `.json` parses and that a `.md` has lines. It does **not** prove that the published number is the number the data holds. This verifier measures that and nothing else: each claim declares the statement, the datum it comes from, and the expression that derives it; **derived vs asserted** is compared under a declared polarity.

- **Piece.** Prose↔data cross-check, with a digit probe that detects numbers no computation supports.
- **Negative control.** `--falsador-dato` injects the falsified datum; the verifier must redden the claim. Without that mutant, a green does not distinguish "the number is correct" from "I am not looking at it".
- **Declared limit.** When there is not enough power to decide, **it does not sign red**: it returns `PODER_INSUFICIENTE`. `DIGITO_MUERTO`, `SIN_DIGITO_VIVO` and `PODER_INSUFICIENTE` are distinct states, counted separately: a zero of `DIGITO_MUERTO` is not a zero of everything.
- **Command.**

```bash
python3 verify_claims/verify_claims.py REPO [REPO ...]
python3 verify_claims/verify_claims.py --sonda-digitos REPO [REPO ...] [--presupuesto N|todo]
python3 verify_claims/verify_claims.py --falsador-dato REPO [REPO ...]
python3 verify_claims/verify_claims.py --json
```

---

## Piece 3 · `barrido_limite_bytes` — is the cap measured prudence or decree?

Measures the real cost of a content hook as a function of the indexed file size, to decide whether `LIMITE_BYTES = 2 MiB` is a **measured** boundary or a round number.

- **Piece.** Each point is measured in **two regimes over the same file**: `TOPE` (the real hook, which **does not scan** above the limit) and `RSS`/passes (the effective scan). Default sizes: `0.5 · 1 · 2 · 4 · 6 · 12` MiB, minimum of `--reps` repetitions.
- **Negative control.** The `TOPE` regime **is** the control: timing only the real hook measures the rejection branch (constant, ~1 s) and would conclude "cost is flat, the cap is superstition" — *the instrument would be measuring its own exception*. `--solo-pases` and `--solo-rss` isolate each half so the difference is visible.
- **Declared limit.** It measures the **hook**, not the file system. It takes the **minimum** of the repetitions (declared with `--declaro-reps`), not the mean: the minimum is the reproducible cost, the mean carries machine noise. The `--force-*` flags (`--force-sello`, `--force-ventana`, `--force-curva`, `--force-regimen`) exist to **break** the curve on purpose, not to publish a prettier number. It **does not guess the hook**: if it does not find it, it fails closed. The default path is `tools/hooks/pre-commit`, which is the layout of the corpus this piece came from and **not** the layout of this repo: here the hook lives at `pre-write-gate/hooks/pre-commit`, so it must be named with `--hook`. A command copied without `--hook` fails closed — it does not fall back to a silent default.
- **Command.**

```bash
python3 barrido_limite_bytes/barrido_limite_bytes_20261021.py --repo . \
  --hook pre-write-gate/hooks/pre-commit --sizes 0.5,1,2,4,6,12 --reps 2 --json puntos.json
python3 barrido_limite_bytes/barrido_limite_bytes_20261021.py --repo . \
  --hook pre-write-gate/hooks/pre-commit --solo-pases   # only the half that scans
```
<!-- HUELLA-EXTRACCION-RUTAS-AUDITOR-TOOLKIT-20261021 -->

---

## Case study · tt-metal (CI) — the sweep that avoided a false zero

Measured on 2026-10-19T05:42Z over `tenstorrent/tt-metal`. Full evidence, with one URL per PR: [`case_studies/tt-metal.md`](./case_studies/tt-metal.md).

**What was measured, and what was NOT:**

- Universe: **1000** open PRs — **pagination cap**, not a total census. The cap is declared, not presented as the universe.
- **12** PRs with `sim_wh_n150` or `sim_bh_p150` in red.
- **8** confirmed with the cause **outside their own diff**.
- **6** job logs downloaded: in all 6, **a single node** fails, and it is the same one.
- **229** PRs inventoried.

**The correction that gives the method its value:** the API rollup cuts at **100 entries**, and in **143** PRs that cut **hid the red shard**. A sweep that reads only the first window reports a **false zero**. That false zero was caught at home first.

**Root cause: one, not twelve.** `tests/ttnn/unit_tests/operations/transformers/test_prefetcher_worker_pipes.py` lacks `@skip_for_slow_dispatch`; it landed with PR #59955 and blocks PRs whose diff does not touch it. That is why this document says **12 PRs red by shard**, not "12 failures": twelve symptoms, one cause.

**What is NOT there:** **0** competing PRs opened, **0** merges, **0** bounties collected. The public trail is **12** diagnostic comments, each with its URL.

---

## Roadmap — declared absent, not promised

What **does not exist yet** is said here instead of appearing as a "piece" in the tables above:

- **Atomic checkpoint / object guardian.** No published implementation. The requirement is clear: `os.replace` write, negative control with `kill -9` mid-process, and the resulting file must hold the partial items (**not 0 bytes**). Until the script and its `kill -9` exist, there is no piece.
- **Packaged CI sweep.** The tt-metal sweep was run ad hoc; packaging it (log download, independence criterion *blamed file absent from the diff*) is pending work. The criterion is already written above; the binary is not.
- **D4B driver packaging.** It exists as a research driver with its seeds and declared blobs, **not** as a command-line instrument. Flags are not invented for it.

---

## Collaboration principles

- We do not ask for bounties: we ask for **datasets** and **merges**.
- If you find a failure in this toolkit, attach the **`sha256` of the mutant** that proves it.
- A report without a declared limit reads as an opinion. A report with a declared limit can be re-audited — and that is all this repo offers.
