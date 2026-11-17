# Focused learned-combination comparison

Frozen before fitting weights or opening the new reference GO terms. The
executable specification is [protocol.py](../../tools/learned_combination/protocol.py).
This is an isolated research comparison; it changes no graph or app default.

## Established method and verified gap

[DeepGOPlus](https://doi.org/10.1093/bioinformatics/btz595) combines similarity
and neural scores with an aspect-specific fitted convex weight. Its
[official implementation](https://github.com/bio-ontology-research-group/deepgoplus/tree/8e8dcb1be7f1bfd5beed11893dacc4132213ea19)
was checked before adapting the arithmetic. Our components are full-context,
strict-alias LocalPlus and the published DeepGO-SE checkpoint ensemble. This
does not reproduce DeepGOPlus or introduce a new biological annotation method.
The verified remaining question is whether fitting a weight transfers better
than either parent or an equal mixture. Earlier truth-aware oracle headroom
and failed reciprocal-rank fusion do not answer that question.

Fit `alpha × LocalPlus + (1−alpha) × DeepGO-SE`, separately for MF, BP and CC.
Try exactly eleven weights, 0.0 to 1.0 by 0.1. Select the highest native
ordinary development micro-Fmax on thresholds .01–.99 by .01; break ties
with the smallest alpha. This objective and grid are declared adaptations,
not the original author's tuning settings. No further grid or conditional
expert-routing model follows this run.

## Data boundary

- Development: previously consumed CAFA5 PK primary and reserved frames,
  pooled only after excluding every accession in the later reference's entire
  7,401-protein target list. Start with 6,100 PK proteins, remove 1,135 exact
  accession overlaps and 17 additional identical-full-sequence matches:
  **4,948 development proteins** before per-aspect native eligibility.
- Later measurement: [LAFA September 2025–March 2026 release](https://github.com/FriedbergLab/CAFA_forever/tree/c3fd5b9a5226348d88b9efadddb3214c803b80c4/data/releases/Sep_2025_Mar_2026),
  intersected with the existing 6,437 human forecasts. All **1,163** intersection
  proteins have identical full sequences in Swiss-Prot 2023_03 and 2025_03.
  The author release also requires unchanged sequences across its own window.
- No new base inference. Original PK forecasts take precedence on overlapping
  PK/NK/LK targets; the non-PK files supply other accessions only. Do not MAX
  scores across overlapping forecast families.
- Canonicalize raw saved scores on each epoch's unchanged native ontology
  axes using its primary/alternative identifiers and duplicate MAX. Mix
  before this evaluator's `fill` propagation. Preserve original model
  internals, propagated training seeds and full-precision scores.
- Development uses the frozen 2023 ontology. The later measurement uses the
  exact [author T0 ontology, July 22, 2025](https://release.geneontology.org/2025-07-22/ontology/go-basic.obo).
  The future terms-of-interest mask is evaluation only. It cannot select
  forecast heads, mixture weights or candidate terms.

Accessions/full sequences are disjoint for fitting this combiner. This does
not establish homology separation, distinct truncated DeepGO inputs or
base-checkpoint training independence. The new reference is retrospective and
external, but not wholly developer-blind: later GOA source material was
previously processed for source quality checks. These proteins were selected
because annotations accumulated; they are not a random proteome sample.

## Controls and measurement

Seal all five complete final forecast arms before decoding LAFA's future GO
terms, PK-known rows or future terms-of-interest file:

1. DeepGO-SE parent.
2. Full-context strict-alias LocalPlus parent.
3. Fixed 50/50 mixture.
4. Development-fitted mixture.
5. The author's unchanged nonexperimental annotation baseline, using
   [human GOA September 4, 2025](https://ftp.ebi.ac.uk/pub/databases/GO/goa/old/HUMAN/goa_human.gaf.229.gz).

The contemporary baseline uses the original native admission and projection
rules: exact UniProtKB identifiers, no NOT, the author's nonexperimental
evidence-code groups, score1. No silent filtering of extension, form or
dual-taxon fields makes the control weaker. Its unchanged source is executed
in an isolated research environment and is not vendored into the app.

Use the pinned [CAFA-evaluator-PK](https://github.com/claradepaolis/CAFA-evaluator-PK/tree/e386b085e204ccfbd75a4f52c1a8b25987d8b465),
native `cafa` normalization, `no_orphans`, `fill`, PK-known exclusions and
evaluation-only TOI. The final metric grid is .001–.999 by .001, matching our
existing comparisons; it is denser than LAFA's published .01-step evaluation.
No exact IA file was obtained, so report ordinary unweighted metrics only.
This is not an exact IA-weighted leaderboard reproduction.

**Primary endpoint:** PK molecular-function ordinary native micro-Fmax.
Report all other eight setting/aspect strata as secondary, including failures
or unavailable coverage. Use the same 2,000 whole-protein bootstrap samples
for every arm, seed 20261113. Every ordinary curve column reconstructed from
per-protein counts must match the unchanged evaluator within 1e-12 first.
No fictitious IA channel is needed. Report unadjusted descriptive 95% intervals.

The declared success gate requires a positive primary point difference and a
paired interval entirely above zero against **all four** controls. A selected
endpoint weight is a selected parent, not an ensemble improvement. A missing
reference annotation is not a demonstrated biological negative. This measures
bounded curator agreement and cannot prove whole-graph biological accuracy.

## Execution receipts

Research code/runtime/source metadata and all 25 original forecast/reference
pins passed qualification. All 37 synthetic checks passed without skips on
Python 3.10.12, NumPy 1.26.4, SciPy 1.13.1 and Pandas 2.2.3. The latter exposed a
known chunk-boundary field-truncation behavior; an explicit extra-field guard
was qualified before real intake. No clipping or rescaling repairs scores.

The initial preparation freeze has SHA256
`d62371dcb63df71969ca98a670bcf2f142690f39b5afe75ca8a579f37848a1e2`.
The subsequent pre-fit freeze adds reviewed phase/provenance guards and the
final assessment implementation, preserving the same scientific protocol:
`926033e306b8e079d32cb582606333cc37c7eabdbfa15cf1e9df0b19327e9bb6`.
It pins 90 source, input and implementation files. Both precede fitting and
new GO-label decoding. Immutable operator receipts and complete raw inputs
remain under the ignored `runs/learned_combination_20261115` and isolated Brev
`/data/.../learned_combination_v1` research directories. Failed dependency and
transport attempts remain recorded and do not replace scientific outcomes.
