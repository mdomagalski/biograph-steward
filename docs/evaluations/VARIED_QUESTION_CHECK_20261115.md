# Three additional source-aware questions

Three task definitions were fixed before opening their results, using the
existing query engines and source readers. All completed without a model,
new retrieval, graph edits or new acceptance decisions. They extend the KRAS
walkthrough to three supported question types within the **same captured
99-target cohort**; they do not test a new cohort or establish scientific accuracy.

| Question | Result | Interpretation retained |
|---|---|---|
| Which proteins have native STRING physical associations with **EGFR**? | 35 matching partners; 30 displayed and 5 explicitly omitted by the supported cap. | Physical proximity or shared-complex association, not proof of direct binding or cancer mechanism. Missing pairs and unavailable participant identities remain distinct unknowns. |
| Which native GO cell-location annotations describe **TP53**? | 12 location concepts, represented by 191 native rows; all rows returned. | Original relations, evidence codes, assigning databases and references remain available. Rows and overlapping concepts are not independent experiments. |
| Which proteins share native-supported exact-revision pathway context with **BRAF**? | 50 matching proteins; 30 displayed and 20 explicitly omitted. | Shared archived-model context, not direct interaction or pathway activation. Displayed source groups distinguish 110 compatible gene-level matches from 4 explicit protein references. |

Every accepted-only control returned zero while candidate evidence remained
inspectable. This reflects the preserved local review state, rather than an
absence of source evidence or a biological rejection. No parameters or seeds
were replaced after opening results, and source passports were inspected through
the existing implementation.

The complete before/after inventories of the 207-file native workspace and
394-file retained workspace were identical, as were both graph hashes. The
two graph products have different source collections; their totals are not a
before/after comparison. Execution took 74 seconds on local CPU using the
recorded `4c91681` software. The subsequent source-display change affects no
answer engine or scientific result.

The [aggregate receipt](reviewer_journey_delivery_20261115/varied_question_check.json)
records the fixed-plan hash, exact parameters, answer/source commitments,
coverage and preserved empty controls. This is a source-aware applicability
check, separate from the public-reference biological measurements and the
same-learner graph-prediction comparison.
