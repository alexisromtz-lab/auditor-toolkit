---
title: "My falsifier was measuring my laptop"
published: false
description: "Four engines, each run twice — a Python oracle and a JavaScript twin — with a bit-for-bit contract. Both defects came from a check that answered a question next to the one I asked: a fixture that recorded who measured, and a verifier that counted commented-out text as published."
tags: testing, python, javascript, ci
canonical_url: https://alexisromtz-lab.github.io/auditor-toolkit/
series: "Instruments that audit their author"
---

I ship small engines twice: once in Python as an oracle, once in JavaScript so a
stranger can play with one in a browser without installing anything. The rule is
that the port must agree with the oracle *exactly* — not approximately, not
within tolerance. Zero tolerance.

That rule needs a falsifier: a frozen fixture generated from the oracle and
committed, plus a script that recomputes everything and diffs it against the
frozen file. On the economic-threshold page that is **250 states and 4,270
compared values**, including a Monte Carlo bank (`n=8000`, `seed=20261113`).

It was green on my laptop every time I ran it. The first CI run after deploying
turned it red.

This post is about three checks that lied to me, and the one habit that caught
them: **measure the difference before naming the cause.**

---

## Defect 1 — the fixture recorded who measured

```
RC 5 · el oráculo se movió
```

CI runs Python 3.12.13; my laptop runs 3.9.6. The interesting conclusion is
also the wrong one: *the oracle is not deterministic across interpreters.* So I
measured instead of concluding.

- Oracle under 3.9.6 → fixture **102,715 bytes**
- Oracle under 3.12.13 → fixture **102,717 bytes**

Two bytes. A recursion over the two JSON trees puts both failures in one leaf:

```
/procedencia/python    "3.9.6"  ->  "3.12.13"
```

And the number that settles it: of the 4,270 values the fixture claims to
compare, **4,270 are identical, bit for bit.** Every boundary state, every
preset, every value on the frontier band. Nothing numeric moved.

The fixture recorded *who measured* inside the bytes it compared:

```json
{
  "estados": [ "... 250 states, 4270 values ..." ],
  "procedencia": { "python": "3.9.6" }
}
```

`procedencia.python` is a statement about the observer. The contract is about
the subject — the numbers. By putting the observer inside the compared region, a
*correct* oracle failed on a different interpreter.

This is worth naming precisely, because it is not "a flaky test". The oracle was
right. The page was right. The falsifier was answering the wrong question: it
asked *"did the environment change?"* and reported the answer as *"did the math
change?"*

### The fix, and the part that matters more

Split the compared region from the metadata:

```python
CAMPOS_DEL_OBSERVADOR = ("procedencia/python",)

def _sujeto(datos):
    """Lo que se compara: el sujeto, sin el estado del observador."""
    sujeto = copy.deepcopy(datos)
    sujeto.pop("procedencia", None)
    return sujeto

# --check compares the subject on both sides
if serializa(_sujeto(congelado)) != serializa(_sujeto(datos)):
    return RC_ORACULO_MOVIDO
```

The obvious version stops there, and that version has a second defect waiting: a
file that silently excludes a field is indistinguishable from a file that
silently excludes *the wrong* field. An unstated exemption is the same class of
error as a lie.

So `--check` prints its exemption on every run:

```
RC 0 · fixture congelado == oráculo (102715 bytes) · fuera del sujeto: procedencia/python=3.9.6
```

There is no state in which the tool excludes something and does not say so.

### Pin both halves

A fix tested only in the direction it was written is not tested. The test pins
the exemption **and** its boundary:

```python
def test_el_check_ignora_solo_al_observador(...):
    # 1) change the interpreter -> still RC 0, and the field is named
    # 2) change the Monte Carlo seed -> RC 5, naming the contract that moved
```

Change the observer and the check stays green. Change the subject and it goes
red, with a reason. Without that second assertion, "ignore `procedencia`" would
be indistinguishable from "ignore anything inconvenient".

---

## Defect 2 — a hang that had already printed its failure

The suite also drives the real page through a headless runtime and mutates it,
asserting that each mutation is caught. On macOS 26.5.2 / node 24.15.0, about 2%
of those runs never returned:

```
sample <pid>
  Builtins_JSEntryTrampoline
  node::Environment::Exit
  NodePlatform::Shutdown
  WorkerThreadsTaskRunner::Shutdown()      <- stuck here, after printing the failure
```

The failure had already been printed. The process just would not die. Measured:
**3 hangs in 150** runs of a mutated page, **0 in 200** of the pristine one, **0
in 200** of `node -e 'process.exit(1)'`.

The mitigation is one retry with a `UserWarning` — plus the check that keeps it
honest: **two consecutive timeouts still fail.** A retry that also swallows a
real hang is not a mitigation, it is a mute button.

The claim is not "it never hangs". The claim is "a hang costs one retry, not a
red build" — and since it has already fired once on a real run, the docs say
exactly that.

---

## The rule I added afterwards — and the false green inside it

Publishing four demos made the next gap obvious. Three of the four pages proved
their thesis and **never said what they do not prove**. For a project whose
whole argument is "publish the negative result as a result", that is a
credibility gap, not a rendering gap.

So the house rule became: no page ships without a block declaring its limits, in
both languages. Each page now carries two, and they are not decorative. This one
is from the field classifier:

> `reader drift` compares two readers of this same code. If both share the same
> wrong definition of the invariant, the drift is zero and the error stays
> invisible: zero drift proves the two paths agree, not that the class is right.

And the rule is enforced, not requested:

```
$ python3 tools/verificar_limites.py
demo/clasificador-de-campos            limites=2  OK
demo/nulo-con-dientes                  limites=2  OK
demo/piso-de-deteccion                 limites=2  OK
demo/umbral-economico                  limites=2  OK
README.md                              cita la regla
README.es.md                           cita la regla
RC 0 · 4 páginas declaran lo que no prueban, en todos sus idiomas
```

Delete a limit while still declaring `data-limites="2"` and it fails closed:

```
  ✗ demo/piso-de-deteccion: declara 2 límites y publica 1
  ✗ demo/piso-de-deteccion: publica 1 límite(s) y el mínimo es 2: un límite único no distingue el alcance de la excusa
RC 1 · 2 fallo(s): una página que no declara su límite no es un instrumento
```

### Then I tried to write this paragraph, and the paragraph was false

I was about to publish "the limits contract fails closed", which is a claim, not
an observation. So I ran the mutation that the sentence depends on:

```html
<!-- <li data-t="lim1">The floats are not bit-exact and this page does not
     claim they are: x**2 in CPython routes to the system libm …</li> -->
```

```
$ python3 tools/verificar_limites.py
...
RC 0 · 4 páginas declaran lo que no prueban, en todos sus idiomas
```

**RC 0.** A limit wrapped in an HTML comment — present in the file, invisible to
every reader — counted as published. The verifier extracted `<li>` elements from
the raw body, and the comment markers sat *outside* the `<li>`, so the element
was still there and its text was still substantive. Commenting the whole
`<section id="limites">` did not register either.

The cause is embarrassingly simple, and it is the same cause as defect 1: the
check was reading the observer's view of the document (what a `findall` sees)
instead of the reader's view (what a person sees). Stripping `<!-- … -->` from
the whole document *before* counting anything closed all three shapes.

The other half of the defect is in the test bank: it covered commenting the text
*inside* a `<li>` — the half of the problem that was easy to imagine. The half
that mattered was the one outside the quote marks.

Two new mutations, and I checked that each one is a real falsifier by reverting
the fix in a throwaway copy:

```
FAILED tests/test_limites.py::MutacionesTests::test_la_seccion_entera_comentada_no_cuenta
FAILED tests/test_limites.py::MutacionesTests::test_un_limite_entero_comentado_no_cuenta
2 failed, 15 passed
```

Green with the fix, red without it. Without that second run, "the test passes"
would have meant nothing more than "the test agrees with the code I just wrote".

---

## What generalises

1. **A fixture that fails on a correct implementation teaches people to ignore
   fixtures.** The cost of a false red is not the red — it is the credibility you
   spend next time.
2. **Separate the observer from the subject, and print what you excluded.**
   Compiler versions, OS, machine, timestamp, user: all of them describe who
   measured, not what was measured. HTML comments, rendering, and scroll
   position are observers too.
3. **If you cannot make a check fail on purpose, it is not a check.** Every
   verifier here is paired with a mutation that must produce a non-zero exit —
   and the mutation is re-run with the fix removed, because a mutation that
   passes in both directions is measuring nothing.
4. **A test bank covers exactly the failures its author imagined.** The gap is
   never in the case you wrote; it is in the neighbouring one. Enumerate the
   shapes the defect can take — text inside the tag, tag inside the comment,
   comment around the section — not just the one in front of you.
5. **Measure the difference before naming the cause.** "Not deterministic across
   interpreters" was one command away from being refuted. If I had written it in
   the commit message first, it would have become the story.

---

## Go try to break them

Four engines. Each page ships its frozen fixture — every state, every compared
value — plus a script that recomputes the browser engine and diffs it against
that file. The check runs in the public repo, against a fixture generated from
the Python oracle. The oracle itself lives in a private repository for three of
the four, and those fixtures say `fuente_publica: false` with a reproducible
local command rather than a link that would 404:

- **[Classifier of electromagnetic fields](https://alexisromtz-lab.github.io/auditor-toolkit/demo/clasificador-de-campos/)** —
  six components of an antisymmetric tensor, classified into the algebraic types
  of Cl(1,3), with the invariants that do not move under a frame change.
- **[Does your null have teeth?](https://alexisromtz-lab.github.io/auditor-toolkit/demo/nulo-con-dientes/)** —
  a permutation test is a null only for the invariant it destroys: which
  invariant dies, and which one survives, under each of five resamplers.
- **[The detection floor](https://alexisromtz-lab.github.io/auditor-toolkit/demo/piso-de-deteccion/)** —
  a gate that judges a field with a constant ε is not choosing a precision, it
  is choosing between two blindnesses; the operator's truncation floor depends
  on the node and is measured without ground truth.
- **[The threshold](https://alexisromtz-lab.github.io/auditor-toolkit/demo/umbral-economico/)** —
  `p_min = C/V` and expected value for repeated attempts, with the Monte Carlo
  bank behind the closed form.

**Hub: [alexisromtz-lab.github.io/auditor-toolkit](https://alexisromtz-lab.github.io/auditor-toolkit/)**

Each page also tells you, in English and Spanish, what it does *not* prove — and
a script fails the build if that block ever disappears. If you find a state where
the browser and the oracle disagree, that is the bug report I want.
