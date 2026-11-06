# V09 — two-stage recruitment and treatment

1,000 worlds per cell · seed 20260921 · 114 s · status **PASS**

Recruitment-only intervals are scored as declared negative controls: they condition on the realised scores and must under-cover a target that also carries outcome and assignment noise. A pass means the superpopulation interval covered and the recruitment-only one did not.

| Study | Recruitment | Variance target | Coverage | Wilson 95% | CI width | Role |
|---|---|---|---:|---|---:|---|
| fixed_frame | q=0.6/0.1 | superpopulation | 0.941 | [0.925, 0.954] | 0.01387 | primary |
| fixed_frame | q=0.6/0.1 | finite_frame | 0.765 | [0.738, 0.790] | 0.00877 | negative control |
| fixed_frame | q=1 boundary | superpopulation | 0.947 | [0.931, 0.959] | 0.01073 | primary |
| fixed_frame | q=1 boundary | finite_frame | 0.000 | [0.000, 0.004] | 0.00000 | negative control |
| redrawn_frame | q=0.6/0.1 | superpopulation | 0.948 | [0.932, 0.960] | 0.01382 | primary |
| redrawn_frame | q=0.6/0.1 | finite_frame | 0.781 | [0.754, 0.806] | 0.00874 | negative control |
| redrawn_frame | q=1 boundary | superpopulation | 0.947 | [0.931, 0.959] | 0.01072 | primary |
| redrawn_frame | q=1 boundary | finite_frame | 0.000 | [0.000, 0.004] | 0.00000 | negative control |
