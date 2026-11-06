# Does the asymmetry index transfer?

1,000 worlds per design · seed 20260926 · 1424 s · normal interval

Designs are matched on A and differ in frame size, acted fraction and event rate. The varying-propensity arm is a declared out-of-scope control: the index assumes a constant propensity, and this arm exists to show where that assumption fails rather than to be rescued by it.

## Designs matched on A

| target A | family | n | acted | rate | e | coverage | |
|---|---|---|---|---|---|---|---|
| 0.10 | baseline | 10,000 | 0.5 | 0.50% | 0.6213 | 0.943 |  |
| 0.10 | narrow_policy | 10,000 | 0.25 | 1.00% | 0.6213 | 0.945 |  |
| 0.10 | whole_frame | 10,000 | 1 | 0.25% | 0.6213 | 0.946 |  |
| 0.10 | small_frame | 2,500 | 0.5 | 2.00% | 0.6213 | 0.950 |  |
| 0.10 | sparse_frame | 5,000 | 0.5 | 0.40% | 0.5781 | 0.929 | ✗ |
| 0.10 | large_frame | 40,000 | 0.5 | 0.50% | 0.7236 | 0.939 |  |
| 0.10 | dense_frame | 20,000 | 0.8 | 1.00% | 0.7673 | 0.939 |  |
| 0.20 | baseline | 10,000 | 0.5 | 0.50% | 0.7236 | 0.943 |  |
| 0.20 | narrow_policy | 10,000 | 0.25 | 1.00% | 0.7236 | 0.936 | ✗ |
| 0.20 | whole_frame | 10,000 | 1 | 0.25% | 0.7236 | 0.943 |  |
| 0.20 | small_frame | 2,500 | 0.5 | 2.00% | 0.7236 | 0.935 | ✗ |
| 0.20 | sparse_frame | 5,000 | 0.5 | 0.40% | 0.6508 | 0.948 |  |
| 0.20 | large_frame | 40,000 | 0.5 | 0.50% | 0.8536 | 0.926 | ✗ |
| 0.20 | dense_frame | 20,000 | 0.8 | 1.00% | 0.8922 | 0.940 |  |
| 0.30 | baseline | 10,000 | 0.5 | 0.50% | 0.8000 | 0.940 |  |
| 0.30 | narrow_policy | 10,000 | 0.25 | 1.00% | 0.8000 | 0.925 | ✗ |
| 0.30 | whole_frame | 10,000 | 1 | 0.25% | 0.8000 | 0.935 | ✗ |
| 0.30 | small_frame | 2,500 | 0.5 | 2.00% | 0.8000 | 0.954 |  |
| 0.30 | sparse_frame | 5,000 | 0.5 | 0.40% | 0.7143 | 0.925 | ✗ |
| 0.30 | large_frame | 40,000 | 0.5 | 0.50% | 0.9160 | 0.941 |  |
| 0.30 | dense_frame | 20,000 | 0.8 | 1.00% | 0.9423 | 0.944 |  |
| 0.55 | baseline | 10,000 | 0.5 | 0.50% | 0.9044 | 0.894 | ✗ |
| 0.55 | narrow_policy | 10,000 | 0.25 | 1.00% | 0.9044 | 0.907 | ✗ |
| 0.55 | whole_frame | 10,000 | 1 | 0.25% | 0.9044 | 0.880 | ✗ |
| 0.55 | small_frame | 2,500 | 0.5 | 2.00% | 0.9044 | 0.893 | ✗ |
| 0.55 | sparse_frame | 5,000 | 0.5 | 0.40% | 0.8281 | 0.881 | ✗ |
| 0.55 | large_frame | 40,000 | 0.5 | 0.50% | 0.9699 | 0.890 | ✗ |
| 0.55 | dense_frame | 20,000 | 0.8 | 1.00% | 0.9805 | 0.889 | ✗ |

## Pre-registered predictions

| prediction | held? |
|---|---|
| **P1_transfer** — matched A agrees within 2 MCSE | **NO** |
| **P2_threshold** — designs at A <= 0.202 cover, designs above it do not | **NO** |
| **P3_out_of_scope** — a varying propensity under-covers relative to a constant one at the same nominal A, so the declared index understates the risk | **NO** |

## The declared out-of-scope arm

Same mean propensity, same nominal A, but the propensity varies by unit. The index is computed from the mean, which is what a caller would declare.

| target A | constant e | varying e | gap |
|---|---|---|---|
| 0.10 | 0.943 | 0.955 | -0.012 |
| 0.20 | 0.943 | 0.945 | -0.002 |
| 0.30 | 0.940 | 0.904 | +0.036 |
| 0.55 | 0.894 | 0.861 | +0.033 |
