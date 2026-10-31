<!-- HUELLA-README-AUDITOR-TOOLKIT-EN-20261021 -->
# Auditor-Toolkit — metrological verification and falsifiers

<!-- PLATINO-LABS-ARCHITECTURE-AUDIT:START -->
[![Audited by Platino Labs](https://img.shields.io/badge/Audited%20by-Platino%20Labs-6C48B1)](https://github.com/alexisromtz-lab/auditor-toolkit/actions/runs/41233436179)

### Architecture snapshot · Python static analysis

| Observed metric | Value |
|---|---:|
| Python modules | 11 |
| Cyclic components (SCC) | 0 |
| Python source bytes | 371,813 bytes |

Commit: `6a4c87a3775bb5084cb47b22b8c85d7878bec83e` · Observed at: `2026-10-31T19:16:38Z` (UTC) · [Workflow run](https://github.com/alexisromtz-lab/auditor-toolkit/actions/runs/41233436179)

Scope: eligible Python source files tracked in this commit. SCC means component size > 1 or a self-loop. Metrics are observations, not a quality score or certification.
<!-- PLATINO-LABS-ARCHITECTURE-AUDIT:END -->
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
- **Declared limit.** It measures the **hook**, not the file system. It takes the **minimum** of the repetitions (declared with `--declaro-reps`), not the mean: the minimum is the reproducible cost, the mean carries machine noise. The `--force-*` flags (`--force-sello`, `--force-ventana`, `--force-curva`, `--force-regimen`) exist to **break** the curve on purpose, not to publish a prettier number. It **does not guess the hook**: if the hook is missing, or does not declare `LIMITE_BYTES=<cap>` exactly once, it fails closed (`RC 5`) instead of measuring something else. Here the hook ships at `tools/hooks/pre-commit`; `--hook` exists to measure a **copy** without touching the real one.
- **Command.**

```bash
python3 barrido_limite_bytes/barrido_limite_bytes_20261021.py --repo . --solo-pases
python3 barrido_limite_bytes/barrido_limite_bytes_20261021.py --repo . \
  --sizes 0.5,1,2,4,6,12 --reps 2 --json puntos.json
```
<!-- HUELLA-EXTRACCION-HOOK-DEFAULT-20261021 -->
<!-- HUELLA-EXTRACCION-RUTAS-AUDITOR-TOOLKIT-20261021 -->

---

## Piece 4 · `ci_sweep.py` — what do the current paginated PR checks say?

Inventories open PRs and classifies the configured CI shards against each PR's current head SHA.

- **Piece.** Paginated PR listing and check-run retrieval; records `ROJO`, `VERDE`, `PENDIENTE`, `SIN_CHECKS`, or `NO_VERIFICABLE` with the measured SHA and timestamp.
- **Negative control.** `--self-test` checks five synthetic outcomes, including missing checks and a cancelled run; neither can become green.
- **Declared limit.** `--limit` is a cap, not a census. The default cache is local and expires after 900 seconds; retry backoff is bounded. `CANDIDATA_FUERA_DEL_DIFF` means only that the case-study file is absent from the PR diff—it is not causal proof. The sweep does not download logs or recreate historical measurements.
- **Command.**

```bash
python3 ci_sweep.py --repo tenstorrent/tt-metal --out ci-sweep.json --limit 1000
python3 ci_sweep.py --self-test
```

<!-- HUELLA-CI-SWEEP-README-EN-20261021 -->

---

## Piece 5 · `auditar_supply_chain.py` — does a workflow grant more than it needs?

Reads GitHub Actions workflows and reports what the gate finds, one code per finding, grouped by policy: **SC-1** (what `permissions` grants at the workflow root — explicit scopes, inherited `write`), **SC-2** (remote action refs pinned to a full SHA), **SC-3** (`pull_request_target` / `workflow_run` reaching a privileged context with untrusted input). An empty universe is not a clean bill of health: a root with no workflows returns `UNIVERSO_VACIO`, never `PASS`.

- **Piece.** A rule table plus a caller: the verdicts come from `gate_workflows_ci.py`, a 711-line port of the private gate, vendored here so the auditor stands alone.
- **Negative control.** `--self-test` runs 19 synthetic workflows — one per code, plus the shapes that must stay silent — and fails if any expected code is missing or any unexpected code appears.
- **Declared limit.** It reads the workflow files of the checkout or repository you point it at; it does not authenticate against the GitHub API on its own, and it does not judge whether a job's code is trustworthy. A finding is a statement about the declared permission surface, not about runtime. An empty universe is **not** a clean bill of health: a root with no workflows returns `UNIVERSO_VACIO`, never `PASS`.
- **Dependency.** `PyYAML` (see `requirements.txt`). Without it the auditor does not guess: it stops with `UNVERIFIABLE` and `DEPENDENCIA_GATE_AUSENTE_RC_30`.
- **Command.**

```bash
python3 -m pip install -r requirements.txt
python3 auditar_supply_chain.py --self-test
python3 auditar_supply_chain.py --repo alexisromtz-lab/git-preflight-gate
```

<!-- HUELLA-PORT-SUPPLY-AUDITOR-TOOLKIT-20261031 -->

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
- **Full historical CI reproduction.** `ci_sweep.py` measures current checks and applies the absent-file criterion, but it does not download logs or regenerate the historical 2026-10-19 evidence.
<!-- HUELLA-CI-SWEEP-ROADMAP-EN-20261021 -->
- **D4B driver packaging.** It exists as a research driver with its seeds and declared blobs, **not** as a command-line instrument. Flags are not invented for it.

---

## Optional · Platino Labs architecture snapshot

Install the automated audit in about a minute:

1. Copy [`.github/workflows/architecture-audit.yml`](./.github/workflows/architecture-audit.yml) to the same path in your repository.
2. In **Settings → Actions → General**, allow the repository `GITHUB_TOKEN` to have **Read and write permissions**.
3. Push the workflow to your default branch. On its next run, it adds the badge and replaces the metrics block near the top of `README.md`.

The workflow reports observed **Python module count**, **cyclic strongly connected components (SCCs)**, and **bytes in eligible Python source files**, alongside the analyzed commit and UTC observation time. It does not assign a coupling level, score, or quality threshold. The badge links to the workflow run; it denotes an automated static snapshot, not a certification.

The badge text is built from the measured counts — `static scan: N modules · M cyclic SCC` — so it carries its own denominator and cannot be read as a generic quality or security claim. A badge without numbers is not produced by this workflow.

**Scope and limits:** tracked Python files in the default-branch snapshot; hidden directories and `__pycache__` are excluded. The engine uses Python 3.12 to parse imports and does not measure runtime/dynamic imports or other languages. The workflow writes only the aggregate snapshot to `README.md`. Repositories whose branch rules block GitHub Actions pushes must allow this workflow to update that file. The engine is fetched from `main` by default; for immutable supply-chain pinning, replace `TOOLKIT_REF: main` in the workflow with a reviewed full commit SHA.

## Collaboration principles

- We do not ask for bounties: we ask for **datasets** and **merges**.
- If you find a failure in this toolkit, attach the **`sha256` of the mutant** that proves it.
- A report without a declared limit reads as an opinion. A report with a declared limit can be re-audited — and that is all this repo offers.
