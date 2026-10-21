# Examples and what they establish

Run the readable [cache and composition tutorial](../../examples/formal/cache_and_composition.py):

```sh
.venv/bin/python examples/formal/cache_and_composition.py
```

It constructs source expressions, proposes plans, checks them and evaluates
the accepted result using the public API. It also checks two required refusals.
No Lean installation or native engine is needed for this runtime example.

The fitted-kernel fixture is

\[
F(a,g)=\exp(R-gb^2\log(Q/Q_A))\exp(-ab^2).
\]

With b=1.3, Q/Q_A=4, R=0.2 and reference (a,g)=(0.25,0.04), caching the
entire first factor matches the reference value 0.7289038134560686, but gives
zero g derivative instead of approximately −1.7077031664. The dependency
checker rejects that cache before any primitive evaluation. At g=0.05 the
correct value is about 0.7120252722; the frozen response stays at its reference.
These are an analytic fixture, not physical LL/NLL evolution or extracted data.

Declaring g fixed changes the model interface. The previously inadmissible
cache is now permitted, but evaluating it at a changed g is refused. The
composition example then transports (0.2,0.3) through f(x,y)=(x+2,y²) before
initializing g(u,v)=uv. Reusing an unrelated second reference is rejected.
Derivative and off-reference tests catch this particular error; the theorem
supplies an all-environments preservation result for accepted terms, without
claiming superiority to every possible unit test.

The full snapshot replay is:

```sh
.venv/bin/python scripts/replay_finite_plans.py --output results/finite-replay.json
```

It evaluates all nine finite-window outputs in each of two transported charts
at four parameter points (72 scalar comparisons), and all seven real-geometry
observation bins at four c0 values (28 comparisons). The finite-window budget
is `1e-13 + 1e-11*abs(target)`; the observation budget is
`2e-13*max(1,abs(target))`. The original targets and arrays are shipped unchanged.
The observation callback is `(1+c0*qT*qT)*(1+0.0001*Q+0.02*y)`, explicitly
analytic. It uses the actual seven-bin geometry, subdivisions, weights,
Jacobian and averaging, and does not execute arTeMiDe.

The [formal command](REPRODUCE.md) checks four complete positive selected roots
and one negative root. Counts are recomputed from the generated selected wires:

| Selected root | Expression nodes | Plan nodes |
|---|---:|---:|
| Cache fixture | 11 | 11 |
| Finite window chart A, output 0 | 4996 | 4228 |
| Finite window chart B, output 0 | 6148 | 5380 |
| Analytic observation, bin 0 | 7917 | 7170 |

The generic theorem is universal; literal checking here covers these four
roots. Other runtime-tested outputs are not counted as separately reduced
certificates. Repeating the same snapshot verification at publication does not
create a different set of eight certified roots.
