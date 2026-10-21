<!-- HUELLA-CASE-STUDY-TT-METAL-20261021 -->
# Case study · tt-metal CI (measured 2026-10-19T05:42Z)

`tenstorrent/tt-metal` · universe measured: **1000 open PRs** (pagination cap of the API — **declared, not presented as a census**).

This sweep does not look for culprits. It separates noise from signal using the Auditor-Toolkit principles: negative control, declared limit, provenance per number.

---

## 1 · The problem: a false zero printed by the tool

The GitHub API rollup **cuts at 100 entries**. In a 1000-PR universe that cut is not cosmetic: it **hides the red shard** and the PR reads green.

Measured: in **143 PRs** the cut was hiding the red shard. A sweep that reads only the first window reports a **false zero**.

> This is the failure mode the toolkit exists for. The first false zero was caught **in our own sweep**, not in theirs.

## 2 · The method

1. Download the rollup and **force pagination** past the 100-entry cut.
2. Isolate PRs with `sim_wh_n150` or `sim_bh_p150` in red.
3. Download the failing job logs.
4. **Independence criterion:** a PR counts as affected only if the blamed file is **absent from its own diff**. A red PR whose own diff contains the failure is *not* evidence of an external cause.

Step 4 is what turns a list of red PRs into a diagnosis. Steps 1–3 alone produce symptoms.

## 3 · The data

| medida | valor |
|---|---|
| PRs abiertos en el universo (tope de paginación) | **1000** |
| PRs inventariados | **229** |
| PRs con `sim_wh_n150` o `sim_bh_p150` en rojo | **12** |
| Confirmados con la causa **fuera de su propio diff** | **8** |
| Logs de job descargados | **6** |
| Logs con un único nodo culpable, idéntico en los seis | **6 de 6** |
| PRs donde el corte del rollup ocultaba el shard rojo | **143** |
| PRs competidores abiertos por mí | **0** |
| Merges | **0** |
| Bounties cobrados | **0** |

**Root cause: one, not twelve.** `tests/ttnn/unit_tests/operations/transformers/test_prefetcher_worker_pipes.py` is missing the `@skip_for_slow_dispatch` decorator. It landed with PR #59955 (2026-10-15) and blocks PRs whose diff never touches it. Twelve red PRs by shard, **one** cause.

Spot check on #61306, measured 2026-10-19T07:11Z (run `39200895879`): **9 failures in a single file**, `test_prefetcher_worker_pipes.py`, **absent from its diff**.

## 4 · The evidence — 12 diagnostic comments, one URL each

Each link is the comment published on that PR, not the PR front page: the anchor is the proof.

| # | PR | comment |
|---|---|---|
| 1 | [#61306](https://github.com/tenstorrent/tt-metal/pull/61306) | [`issuecomment-6261829912`](https://github.com/tenstorrent/tt-metal/pull/61306#issuecomment-6261829912) |
| 2 | [#59019](https://github.com/tenstorrent/tt-metal/pull/59019) | [`issuecomment-6258809358`](https://github.com/tenstorrent/tt-metal/pull/59019#issuecomment-6258809358) |
| 3 | [#61290](https://github.com/tenstorrent/tt-metal/pull/61290) | [`issuecomment-6259243763`](https://github.com/tenstorrent/tt-metal/pull/61290#issuecomment-6259243763) |
| 4 | [#60354](https://github.com/tenstorrent/tt-metal/pull/60354) | [`issuecomment-6260016747`](https://github.com/tenstorrent/tt-metal/pull/60354#issuecomment-6260016747) |
| 5 | [#61276](https://github.com/tenstorrent/tt-metal/pull/61276) | [`issuecomment-6260017042`](https://github.com/tenstorrent/tt-metal/pull/61276#issuecomment-6260017042) |
| 6 | [#61289](https://github.com/tenstorrent/tt-metal/pull/61289) | [`issuecomment-6260017401`](https://github.com/tenstorrent/tt-metal/pull/61289#issuecomment-6260017401) |
| 7 | [#60412](https://github.com/tenstorrent/tt-metal/pull/60412) | [`issuecomment-6260424917`](https://github.com/tenstorrent/tt-metal/pull/60412#issuecomment-6260424917) |
| 8 | [#60414](https://github.com/tenstorrent/tt-metal/pull/60414) | [`issuecomment-6260425266`](https://github.com/tenstorrent/tt-metal/pull/60414#issuecomment-6260425266) |
| 9 | [#61225](https://github.com/tenstorrent/tt-metal/pull/61225) | [`issuecomment-6260425564`](https://github.com/tenstorrent/tt-metal/pull/61225#issuecomment-6260425564) |
| 10 | [#61226](https://github.com/tenstorrent/tt-metal/pull/61226) | [`issuecomment-6260426082`](https://github.com/tenstorrent/tt-metal/pull/61226#issuecomment-6260426082) |
| 11 | [#61233](https://github.com/tenstorrent/tt-metal/pull/61233) | [`issuecomment-6260426487`](https://github.com/tenstorrent/tt-metal/pull/61233#issuecomment-6260426487) |
| 12 | [#61234](https://github.com/tenstorrent/tt-metal/pull/61234) | [`issuecomment-6260426921`](https://github.com/tenstorrent/tt-metal/pull/61234#issuecomment-6260426921) |

## 5 · What this report does NOT claim

Declared absences, so nobody has to audit the silence:

- **No merges.** The measured count is **0**. There is no patch of mine in `tt-metal`.
- **No bounty.** Five public bounties exist on that repo; **all five are assigned to other people**. None of them is claimed here.
- **#51655 is an issue, not a PR**, and it is assigned to `kinginu`. It is therefore not counted and not requested.
- **Not a census.** 229 PRs inventoried out of a 1000-PR pagination window. The 1000 is a **cap**, not a total.
- **Not the number of failures.** 12 is PRs red **by shard**; the cause is **one**. Anyone reading "12 failures" from this table is reading a number this document does not assert.

## 6 · Reproducing it

The sweep was run ad hoc; the packaged binary does not exist yet (see *Roadmap* in the [README](../README.md)). What **is** reproducible today is the criterion of §2, step 4: given a PR and its diff, "is the blamed file absent from the diff?" is a closed question with a yes/no answer that does not depend on who wrote the code.
