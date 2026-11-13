<!-- HUELLA-CASE-STUDY-ARCH-TWO-READINGS-20261113 -->
# Case study · an architecture graph has two readings, and the first one lies in both directions

Measured `2026-11-13` over five public Python libraries at their `HEAD`. Every number below was produced by the two commands at the end, on a checkout the commit names, and is bound to the bytes of the ingest by a SHA-256. Nothing here was estimated from a screenshot, a blog post or a memory.

Universe: the **importable package directory** of each library (`--source-root` = the package, `--package` = its name), tracked Python files only, one commit per row. Test suites, docs, benchmarks and every other directory are outside the universe — deliberately, so that the row measures the library and not the repository.
Commit: one per row, in the table.
Corpus SHA-256: one per row, in the table — the same value `--graph-sensitivity` prints as `graph_input_sha256`.
Command: the last two blocks of this page.

---

## 1 · A cyclic component is a projection, not a fact about your code

The index reports *cyclic strongly connected components* of the static import graph. That graph contains one kind of edge that is not a plain import: when `pkg/__init__.py` is a package, every `from .sub import X` inside the package also counts as an edge **back to `pkg`**. The root then joins any component that touches it, without any two of those modules importing each other.

In `click` that produces exactly **11** such edges, and every one of them has the same shape:

```
click._compat -> click            click.shell_completion -> click
click._termui_impl -> click       click.types -> click
click._textwrap -> click          click.utils -> click
click._winconsole -> click        click.decorators -> click
click.exceptions -> click         click.formatting -> click
click.parser -> click
```

Eleven edges, one direction, all into the root. The graph is not wrong — a package root really does become reachable from every submodule that imports another submodule — but **it is not a cycle in the source.** It is a property of the projection.

`--graph-sensitivity` re-projects *the same document* without that expansion. It does not re-ingest, does not re-read the checkout, and does not change the commit: the input SHA-256 is identical in both readings, so the difference cannot be an input difference.

## 2 · The two readings, five libraries

| library | commit | modules | internal edges (with / without expansion) | largest cyclic SCC, first reading | second reading | Δ cyclic SCC |
|---|---|---|---|---|---|---|
| `requests` | `3c7baaa05ab4aa49cc819ce3a819d260de19c157` | 19 | 74 / 65 | 1 × **13** | 1 × **7** | 0 |
| `click` | `e38188e9e205005d5af5f9e59df51904c984586a` | 17 | 70 / 59 | 1 × **14** | **3** × 8, 2, 2 | **+2** |
| `httpx` | `b5addb64f0161ff6bfe94c124ef76f6a1fba5254` | 23 | 104 / 81 | 1 × **19** | 1 × **2** | 0 |
| `attrs` | `9d9f94a043de7fc4012459853a4ed597a5577855` | 13 | 41 / 35 | 1 × **7** | 1 × **7** | 0 |
| `rich` | `3a109ccdffe5b2d0e30684a304fbd388e99ce57b` | 100 | 478 / 414 | 1 × **56** | 1 × **53** | 0 |

Corpus SHA-256, so any row can be reproduced and compared byte for byte:

| library | `graph_input_sha256` |
|---|---|
| `requests` | `641c94a7de297dfc58e7ba76180f76d8a26d19a0ca49b0d076361d40ed18709a` |
| `click` | `39da0a19132e82be05d34f5c24a90b7095e47e0a72eabbd52f744950ac00e0cf` |
| `httpx` | `4c9014514972ecff346057684b6ea2cbbb79ac696c2239f920b499d62b6402c3` |
| `attrs` | `573d4774dd100c7ca6d985ad7abfbe8ffb9ef8510aa6fbd4940c20176575034e` |
| `rich` | `de1ac7241e5e6b29fd8f3c66e9e8b347251157679f31153cb3e2a7c16b3b77be` |

Three of the five shrink but stay one component: the knot is real, part of it was not. `attrs` does not move at all — a small package whose root does not collect its own submodules the way the others do. And `click` does not shrink: it **splits**.

## 3 · The case that changes the decision: `click`

First reading: **one** cyclic component of **14** modules out of 17, 82 % of the package, index `1.0397` cyclic SCC per 10 000 LOC. The obvious decision that follows is "a large refactor of a knot of fourteen modules".

Second reading: **three** components of 8, 2 and 2. The eight:

```
click  click.core  click.decorators  click.formatting
click.parser  click.shell_completion  click.termui  click.types
```

and two pairs, `click._compat` ↔ `click._winconsole`, `click.exceptions` ↔ `click.utils`.

Twelve modules are in a real cycle. The other two that the first reading accused — **`click._termui_impl`** and **`click._textwrap`** — are in **no** cycle once the artifact is removed: they are reachable from the root, and the root is in a knot, so the first reading puts them in the knot too.

**The first number was wrong in both directions.** It overstated the size of the knot (14 instead of 8 for the largest) and it understated how many knots there are (one instead of three). A refactor sized from the first number addresses a shape that does not exist; three cuts sized from the second number address three shapes that do.

## 4 · The reading that can hide, not only exaggerate: `httpx`

The index also reports **exposure**: modules that are *not* themselves in a cycle but sit in a component that depends on one. That number is where the projection can turn a warning into an all-clear.

| library | exposed modules, first reading | exposed modules, second reading |
|---|---|---|
| `httpx` | **0** | **15** |
| `rich` | 29 | 8 |
| `attrs` | 3 | 3 |
| `click` | 1 | 3 |
| `requests` | 1 | 1 |

In `httpx` the first reading says **nothing is exposed to a cycle**. It says that because the root pulled fifteen modules into the same component as the knot: once you are inside the knot you are no longer "exposed" to it. Remove the artifact and fifteen modules are outside the real cycle and depend on it. Same document, same commit, same bytes — the reassuring number was a property of the projection.

This is why the tool ships two readings instead of one. A single number has no way to say which of the two things it measured.

## 5 · Correction to an earlier version of this table

The first version of this table, published in `README.md` on the same day, carried two rows measured over a **different universe** — `click` with 91 modules and `rich` with 212, that is, the whole repository rather than the package. The two rows that came from that universe read `click 1 × 14 → 3 × at most 7` and `rich 43 → 39`. Re-measured over the package, in the same convention as the other three rows, they are `click 1 × 14 → 3 × 8, 2, 2` and `rich 56 → 53`.

The three rows that were already measured over the package — `requests`, `httpx`, `attrs` — reproduced **exactly**, which is what made the defect findable: a table where three rows agree and two do not is not noise, it is two universes. Every row above now carries its module count and its corpus SHA-256, so a reader can tell a different measurement from a wrong one without trusting this page.

## 6 · What this does not measure

- It measures **static** imports of Python files in one commit. Runtime imports, dynamic imports, plugins and other languages are outside the universe.
- **The minimum set of edges that breaks each knot is not computed.** The second reading says how many knots there are and how big; it does not say which single import to move. That is the next piece, and it is not this one.
- A cycle is not a defect. `0 cyclic SCC` is an observation about one commit, not a score, a threshold or a verdict.
- The five libraries were chosen because they are public and small enough to read. They are not a sample of anything, and the percentages are not population estimates.

## 7 · The commands

Both readings come from the same ingest; the pipe keeps no intermediate file, so there is nothing to edit between them.

```bash
# first reading: the index, bound to the checkout it names
python3 tools/ingesta_ast_v2.py . "$(git rev-parse HEAD)" \
  --source-root src/click --package click \
| python3 tools/calculate_arch_index.py - --repo click --repo-root . \
    --commit "$(git rev-parse HEAD)"

# second reading: the same document, without initializer expansion
python3 tools/ingesta_ast_v2.py . "$(git rev-parse HEAD)" \
  --source-root src/click --package click \
| python3 tools/calculate_arch_index.py - --graph-sensitivity
```

Swap `src/click` / `click` for the package directory and name of the library you are auditing — `httpx`, `rich`, `src/requests`, `src/attr`. The `graph_input_sha256` of the second command must equal the `corpus_sha256` of the first; if it does not, the two readings describe different trees and neither may be quoted.
