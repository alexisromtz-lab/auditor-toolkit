# Contributing

## The rule for a pull request

One claim, one executable falsifier. A change that says "this is now correct"
without a test that fails before it and passes after it is not reviewable, and this
repository only accepts reviewable changes.

If you find a failure in one of the instruments, the most useful thing you can
attach is the smallest input that proves it — the mutant, the payload, the file
that makes the measurement wrong. A report without a reproducer reads as an
opinion.

## Sign-off (DCO), not a CLA

Every commit needs a `Signed-off-by` line:

```
git commit -s -m "your message"
```

That certifies you wrote the code or have the right to submit it
([Developer Certificate of Origin 1.1](https://developercertificate.org/)). It does
**not** transfer your copyright.

We do not ask for a CLA, and the reason is structural rather than generous: while
this repository is Apache 2.0 and its products are AGPL-3.0 from the first commit,
the project has no need for the right to relicense your contribution under other
terms. The licence already grants everyone — us, you, and whoever forks it — the
freedoms the project intends to grant. If that ever changes, it changes only for
code written after the change, never retroactively.

## Licence, and what it does not cover

| what | licence | why |
|---|---|---|
| the audit instruments (this repository) | Apache 2.0 — see [`LICENSE`](LICENSE) | adoption is the prize: a maintainer can run a measurement without a legal review |
| products built on them (network services) | AGPL-3.0, from the first commit | if it is offered over a network, its improvements stay open |
| published snapshots `v0.1.0`, `v0.2.0` | Apache 2.0, irrevocable | a deposit is dated evidence; it is not rewritten |

The split is one rule, not two: **instruments permissive, products copyleft**.
Nothing here is dual-licensed, and no contribution is accepted under terms other
than those above. Apache 2.0 grants no warranty, and it does not grant the right to
relicense this code under other terms.

## Copyright window (measured, not assumed)

Measured 2026-11-17 on `alexisromtz-lab/auditor-toolkit`: **0 forks**, **0 pull
requests from anyone other than the maintainer** (9 of 9 authored by the
maintainer), **1 human contributor**. The project is therefore still
sole-copyright and could still relicense as a whole.

The first externally merged pull request without a CLA closes that possibility for
good. This paragraph exists so the window can be *audited* instead of remembered.
Re-measure it with:

```
gh api repos/alexisromtz-lab/auditor-toolkit/forks --jq 'length'
gh api 'repos/alexisromtz-lab/auditor-toolkit/pulls?state=all' --jq '[.[].user.login] | unique'
```
