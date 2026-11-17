# External kinase comparison and reusable verification

The comparison completed on a separate HCT116 genetic-perturbation study.
It **does not establish a biological gain from the source-cleaning rule or
graph pruning**. It did expose and resolve reusable integration defects,
recover substantially more compatible measurements, and show why direction
agreement alone can be misleading.

The completed original drug comparison and the app graph remain unchanged.
All three declared protein-kinase targets remain in this assessment, including
the target without enough measured signature sites.

## Fixed design and technical correction

The [author study](https://doi.org/10.1080/19768354.2026.2625524) compares stable
HCT116 knockouts with control cells and supplies paired protein/phosphosite
tables. MAPK1/ERK2, PLK1 and PAK4 were selected before quantitative access;
PIK3CA remains a separate pathway-context condition. This is an exploratory
external-study check, not a direct kinase-activity or catalytic-truth assay.

The original source-qualified SIGNOR prior has 6,114 binary links. A stricter
view excludes four unresolved source assertions, leaving 6,110 links and the
same 373-regulator catalogue. Five previously flagged literal assertions were
already excluded by the original source rules. The three target memberships
are unchanged. The separately typed iKiP arm is a partial three-target
signature diagnostic; it is never ranked against the full catalogue or merged
into SIGNOR by default.

The method is the published raw RoKAI z-score, with sample SD, no global-mean
subtraction and at least five finite distinct target sites. Contrasts use the
difference of mean log2 positive author-normalized intensities, requiring both
replicates in each group. Replicate pairing, imputation and pseudocounts are
not assumed. Conflicting duplicate-site contrasts remain aggregation-unresolved.
The prespecified sensitivity subtracts the same-qualified-host protein contrast,
with matched-support unadjusted controls and no missing-host fallback.
See the [RoKAI paper](https://doi.org/10.1038/s41467-021-21211-6) and
[2025 benchmark](https://doi.org/10.1038/s41467-025-59779-y).

Preflight first caught an integration mistake: the newer identifier audit had
inadvertently replaced the historical catalogue's admission policy. The
corrected runner explicitly uses the frozen catalogue correspondence check
and retains its separate SIK1 secondary-GeneID warning. No named-gene exception
was added, and that failed attempt opened no quantitative rows.

The first completed run then exposed a format defect. The author's redundant
`Other modification` field uses `N/A`; treating that unavailable marker as a
required modification expression rejected 8,609 rows. The correction declares
unavailable tokens per field and keeps this secondary corroboration unreported.
It does **not** interpret missing annotation as zero PTMs. Raw and processed
phosphorylation, site and peptide/reference consistency remain required;
present contradictions, ambiguous sites and multisite signals still fail.

Both completed versions are preserved. The corrected replay was explicitly
frozen **after data exposure**, with unchanged sources, targets, sample maps,
thresholds and numerical methods. It is a technical correction, not a fresh
unseen confirmation.

## Results

Coordinate-compatible phosphosite rows increased from **1,773 to 9,351 of
13,215 input rows**. These are transport/qualification counts, not independent
experiments or validated catalytic reactions. After duplicate and quantitative
eligibility checks, the corrected unadjusted contrasts have 7,046 finite site
groups for MAPK1/PAK4 conditions and 7,045 for PLK1. Protein qualification is
unchanged at 6,761 of 7,045 rows.

The original and strict SIGNOR arms produce **identical predictions and missing
masks everywhere**. The four source exclusions therefore provide no measured
functional gain in this panel. This does not independently validate those
assertions or imply that their curation is unnecessary for other questions.

The table uses the same matched site support before and after protein
adjustment. Negative scores match the declared knockout direction. Ranks are
shown against the **16 candidates with finite scores**, alongside a frozen
catalogue of 373 that retains missing candidates and worst-rank target penalties.

| Target | Matched measured SIGNOR sites | Unadjusted score on matched support | Protein-adjusted score | Signed rank before → after | Interpretation |
| --- | ---: | ---: | ---: | --- | --- |
| MAPK1 | 30 | +4.365 | −10.093 | 16/16 → 2/16 | Direction aligns after adjustment; relative rank improves. |
| PLK1 | 5 | +1.935 | −1.330 | 3/16 → 11/16 | Direction aligns, but relative rank worsens. |
| PAK4 | 2 | unavailable | unavailable | abstains | Below the fixed five-site requirement; absence of a score is not absence of activity. |

On the full unadjusted support, MAPK1/PLK1 have 32/5 measured signature sites,
scores +4.524/+1.953, and ranks 19/19 and 3/19 among the 19 finite candidates.
Both point opposite the declared knockout direction. PAK4 still abstains.
Target-score coverage is **2/3** before and after protein adjustment. Top-five
rank hits remain **1/3**, with a different gene supplying the hit. A rank hit
does not require the correct absolute direction; direction agreement is reported separately.
The all-case mean normalized rank is 0.352994 for the primary unadjusted arm,
0.350313 for matched-support unadjusted and 0.344951 after protein adjustment.
These small-panel descriptive values are not scientific-accuracy percentages.

The first incomplete-parser run had only one finite catalogue candidate,
making MAPK1's rank 1 automatic even with the wrong sign. The retained ranking
diagnostic now reports the number of available candidates. A count greater
than five alone still does not establish useful discrimination across ties.

### Background shifts limit the apparent direction gain

All 19 finite SIGNOR scores are positive in each of the three primary
unadjusted knockout conditions.
After protein adjustment, all 16 are negative in MAPK1/PAK4 conditions and
15 of 16 are negative in PLK1. On the same host-matched support, mean site
contrasts move from +0.316 to −0.519 for MAPK1 and +0.365 to −0.172 for PLK1.
These descriptive checks were added after sealed scoring;
they change no predictions or normalization.

Thus, the two matching target signs after adjustment cannot be taken as
target-specific biological validation. A broad background shift, shared
substrates and long-term compensation remain alternative explanations.
The data reviewed here do not establish whether the global shift is technical
or biological. PLK1's rank deterioration is a further reason not to promote
the sensitivity as a universally better method. The published benchmark also
found that host-protein normalization could reduce performance in its CPTAC
evaluation; that result and this small panel do not establish one rule for
every assay.

iKiP likewise scores two targets, with the same before/after direction pattern,
and does not rescue PAK4 at the fixed threshold. More matching substrate sites
for MAPK1 do not demonstrate additional target coverage or superior accuracy.
No complete-catalogue iKiP rank or default source union is reported.

## Mechanisms retained for other studies and questions

The optional code separates source contracts, measurement interpretation,
scoring and diagnostics instead of encoding HCT116 target or worksheet names
in the reusable functions.

| Issue | Reusable response |
| --- | --- |
| Hidden first sheet or repeated header labels | Require a declared visible sheet and positional column/sample map; reuse openpyxl for full transport. |
| Missing secondary corroboration | Preserve it as unavailable under an explicit field contract; require primary evidence and reject present contradictions. |
| Bad quantitative cell in one condition | Keep valid identity evidence and other groups; make only that cell/group unavailable. |
| Wrong source assertion or stale review | Bind review to release/file/record/ordinal/row digest; preserve alternative eligible support for a link and avoid global renaming. |
| Audit and admission policies differ | Declare the source correspondence policy explicitly and preserve additional audit warnings separately. |
| A partial catalogue or trivial rank | Block cross-catalogue rank comparisons and report finite-candidate competition alongside the full catalogue size. |
| Globally shifted scores | Report background means/sign counts without assuming their cause or automatically normalizing to the expected answer. |

Synthetic checks cover two workbook layouts, arbitrary sample/condition names,
single- and multi-condition designs, alternative unavailable tokens, source-key
layouts and retained competing support. The local numerical implementation also
reproduces archived author-code outputs from the consumed drug study within
3.56e−14, with identical missingness. A separate software-agent numerical
recount reproduced both completed comparisons. This is not external human
curation or a new experimental replication.

These checks demonstrate software reuse and prevent specific false conclusions.
They do not prove biological accuracy for every question. Kinase signatures,
physical-interaction evidence and clinical response claims need different
assay/context rules and their own references; a five-site kinase rule must not
be applied to PPI or clinical claims.

## Boundaries and retained artifacts

This study has three declared target cases in one stable cell model, two
biological samples per group in one TMT batch, unspecified independent-clone
replication/timing, and unverified site-localization/FDR thresholds. The source
methods support the declared normalized-intensity interpretation, but the
visible headers do not independently specify those units. A matching reference
sequence, source group-count 1 or a raw localization token does not establish
the exact experimental proteoform, group cardinality or calibrated confidence.
No other kinase is labelled a biological negative; no inferential precision
or general accuracy is estimated.

The **entire HCT116 parent study is now consumed** for this project. Future
changes on it are development or sensitivity analyses. A new independent
assessment is required for a stronger improvement claim.

Original workbooks, raw/derived source memberships and row ledgers remain
private and Git-ignored under their upstream terms, including CC BY-NC4.0.
The MIT software does not relicense those inputs. No app graph, source record
or human review state was automatically changed. No Brev/GPU/model inference
was required for this comparison.

See the [aggregate result](hct116_external_comparison_20261112_summary.json),
[optional tools](../../tools/kinase_utility/README.md) and the preserved local
artifacts under `runs/hct116_external_comparison_20261112/`.
