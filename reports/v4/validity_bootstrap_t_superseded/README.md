# Superseded: measured under a seeding defect

This run scored the studentized bootstrap at B=499 over 1,000 worlds. It was
produced **before** the R01 suite's seeding was fixed: world seeds were keyed on
a scenario's position in the requested list, so this run drew different worlds
than any run made after the fix. Its numbers are not comparable with the
current artifacts and must not be quoted as a like-for-like comparison.

It is kept, rather than deleted, because the stage log cites its cost
(2,072 s) and its qualitative finding: the bootstrap fixed V05's asymmetry
while introducing failures elsewhere at B=499.

Current artifacts: `../validity/` (normal interval) and `../validity_confirm/`
(the confirmation run).
