# R4 learner comparison: pre-run amendment 1

Written before the first nested-fold outcome comparison. The inherited
`docs/NEXT_RESEARCH_EXPERIMENTS_EN.md` describes development data but does not
specify a Lenta size. This run freezes a deterministic **60,000-row sample of
Lenta development** (`lenta-v4.1` hash split, `numpy.default_rng(20260921)`,
sample without replacement and sorted positions). The full Lenta development
frame is about 550,000 rows and the nested M07 fits would make this bounded
CPU study substantially larger. The Lenta branch is **exploratory** and cannot
be called the frozen full-development protocol or an independent replication.

Hillstrom Mens versus no email is primary development; Womens versus no email
is sensitivity development. Both use only the hashed development role. Lenta
uses only its hashed development role, its own SMS response outcome, and an
**assumed** constant `e=0.75` because an exact randomizer probability record
is unavailable. Lenta cannot license a causal claim or determine the primary
learner selection. The branches are never pooled.

The four fixed recipes are M01, M03, M05, M07. The inner three folds select
among M03/M05/M07 by mean paired DR policy value per 1,000 eligible customers,
with tie order M03/M05/M07. M01 is the fixed comparator. Three outer folds use
the same rows for every recipe, train-side preprocessing and nuisance fits,
20% hard cap, positive scores only, no cost assumption. An incomplete inner
candidate cannot win. The planning margin is one conversion per 1,000. The
outer-fold spread is descriptive; no interval or population significance is
claimed. The source hash, data hashes, roles and seed are in
`DRY_RUN_MANIFEST.json`, produced without indexing outcome labels. Planned
outputs are `hillstrom_mens.json`, `hillstrom_womens.json`, and `lenta_sms.json`
in this report directory. CSV parsing
still loads raw bytes, so the holdout is procedural rather than sealed.

No confirmation outcome is accessed by the runner. The three public domains
were already inspected in earlier work, so this is development only. A positive
score can prioritize future evaluation, never a measured telecom uplift or ROI.
