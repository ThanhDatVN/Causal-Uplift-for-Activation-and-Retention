# Overlap boundary: where the DR interval stops covering

1,000 worlds per cell · N = 10,000 · seed 20260924 · 666 s

One mechanism, one policy, one estimator family. The boundary is where this evaluator stops covering on this generator; it is not a general theorem about doubly robust inference, and the effect is held at a constant fraction of the event rate so cells compare like with like. The asymmetry threshold is measured on this grid only: A has not been checked outside this generator family, and a design whose propensity varies with X is not covered by it at all.

## normal

| event rate | e=0.5 | e=0.6 | e=0.7 | e=0.8 | e=0.9 | e=0.95 |
|---|---|---|---|---|---|---|
| 0.5% | 0.948 | 0.951 | 0.944 | 0.934 ✗ | 0.907 ✗ | 0.830 ✗ |
| 1.0% | 0.960 | 0.953 | 0.945 | 0.934 ✗ | 0.924 ✗ | 0.886 ✗ |
| 3.5% | 0.957 | 0.947 | 0.948 | 0.955 | 0.939 | 0.927 ✗ |

## skewness_adjusted_t

| event rate | e=0.5 | e=0.6 | e=0.7 | e=0.8 | e=0.9 | e=0.95 |
|---|---|---|---|---|---|---|
| 0.5% | 0.942 | 0.946 | 0.949 | 0.953 | 0.937 | 0.811 ✗ |
| 1.0% | 0.955 | 0.947 | 0.945 | 0.954 | 0.957 | 0.937 |
| 3.5% | 0.955 | 0.947 | 0.946 | 0.954 | 0.949 | 0.965 |

## Boundary

| method | event rate | largest passing imbalance | smallest failing |
|---|---|---|---|
| normal | 0.5% | 0.20 | 0.30 |
| normal | 1.0% | 0.20 | 0.30 |
| normal | 3.5% | 0.40 | 0.45 |
| skewness_adjusted_t | 0.5% | 0.40 | 0.45 |
| skewness_adjusted_t | 1.0% | 0.45 | none |
| skewness_adjusted_t | 3.5% | 0.45 | none |

The imbalance boundary **moves with the event rate**, so imbalance is not a rule a gate can apply. The asymmetry index

> `A = |1 - 2e| / sqrt(n * h * rate * e * (1 - e))`

combines all four factors. Whether it orders these cells cleanly is measured, not assumed:

| method | cells failing | largest passing A | smallest failing A | separates? |
|---|---|---|---|---|
| normal | 7/18 | 0.202 | 0.212 | yes |
| skewness_adjusted_t | 1/18 | 0.584 | 0.826 | yes |

- `normal`: licensed up to **A = 0.202** -- the largest value actually measured as covering; the crossing is bracketed, not interpolated.
- `skewness_adjusted_t`: licensed up to **A = 0.584** -- the largest value actually measured as covering; the crossing is bracketed, not interpolated.
