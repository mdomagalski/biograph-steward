# CRC evidence-value pilot

This workflow measures source coverage and performs advisory claim-to-passage checks on a frozen CRC evidence panel. It uses deterministic graph queries, the existing source-qualified CIViC records, primary publication text and one processed CPTAC colon-cancer matrix. It does not tune the question planner, manufacture biomedical gold labels, modify graph review states or measure predictive improvement.

The [first recorded pilot](evaluations/CRC_EVIDENCE_VALUE_20261020.md) includes the actual results, source-access gaps, measurement counts, unresolved mappings and complete experiment identities. Its executed packet is `runs/crc_evidence_value_20261020/final_packet/`; the initial unexecuted `packet/` preparation is retained separately after a pre-inference metadata-label correction.

The [subsequent context/cohort result](evaluations/CRC_CONTEXT_COHORT_20261020.md) preserves this pilot and adds an AI-assisted source-scope overlay plus a crosswalk accounting for every measured gene. Use the [mapping/follow-up commands](COHORT_MAPPING.md) for that increment; no historical verdict or packet fingerprint is rewritten.

## Frozen sources and selection

Use a Pharos-only run and its CIViC-enriched copy with the same primary snapshot and review events. The default six deterministic questions reuse KRAS/EGFR context, G13D/cetuximab, G12C/panitumumab, a complete complex profile and the locally accepted G13D counterpart. They are development examples, not an unseen evaluation. Custom specifications can be supplied with `--cases`.

The default 20-item source panel includes the previously inspected complete KRAS G13D profile records, then other CIViC records in ascending SHA-256 order of their IDs. Selection does not use machine verdicts or scientific labels. Excluded records remain in the panel with their original filter reasons; an editorial-revision exclusion is not a scientific negative. Every description, whole molecular profile, disease, complete treatment list, list semantics, direction and variant origin is preserved. The full source record and exact source hashes accompany each item.

Publication overlap is reported separately for explicit Pharos assertion citations and raw source/discovery mentions. A matching discovery PMID does not establish support for an assertion. No match does not establish novelty or experimental independence. Repeated CIViC records and distinct publications are not independent-study counts.

## Prepare and retrieve

These commands refer to the existing local frozen controls. Use new output directories for every preparation or run:

```sh
python3 app.py crc-pilot-prepare \
  --baseline runs/planning_challenge_20261020/suite/sources/pharos \
  --enriched runs/planning_challenge_20261020/suite/sources/enriched \
  --items 20 --out runs/crc_evidence_value_20261020/packet

python3 app.py crc-pilot-literature \
  --packet runs/crc_evidence_value_20261020/packet \
  --out runs/crc_evidence_value_20261020/literature

python3 app.py cptac-inspect \
  --pharos-run runs/planning_challenge_20261020/suite/sources/pharos \
  --out runs/crc_evidence_value_20261020/cptac
```

Preparation copies raw sources, freezes the current code and budgets, executes the deterministic arms and leaves scientific review worksheets blank. Literature retrieval uses bounded public NCBI E-Utilities requests. PMC IDs come from returned PubMed metadata rather than guessed mappings. Full text must match the requested publication identity. Abstracts, body paragraphs, tables, rights notices, access failures, requests and source bytes remain separately recorded. Missing abstracts or inaccessible full text are access gaps, not contradictions or absence from the literature. No cloud account or API key is required for these public downloads.

The selected CPTAC source is the PNNL gene-level tumor/normal log2-ratio matrix linked by the [LinkedOmics CPTAC-COAD catalogue](https://www.linkedomics.org/data_download/CPTAC-COAD/) and the [PDC000116 study](https://pdc.cancer.gov/pdc/study/PDC000116), associated with [Vasaikar et al., Cell 2019](https://doi.org/10.1016/j.cell.2019.03.030). The complete matrix and its missing values are preserved. The candidate population is the source's complete measured-gene list, rather than the disease-associated Pharos subset.

The original sidecar's mapping is limited to exact reported symbols in the frozen Pharos cohort. The separate [cohort mapper](COHORT_MAPPING.md) now accounts for all 6,422 measured rows using frozen human HGNC/UniProt registries, resolving 6,415 and retaining seven ambiguous names. It preserves gene/product granularity and does not replace this historical sidecar. The sidecar reports observed sample counts and descriptive median source ratios. Abundance is not a causal-disease or drug-response label. Pharos may already link to the same experiment through LinkedOmicsKB; quantitative detail is not automatically independent evidence. `--matrix` accepts a local file but records its source identity as caller-declared rather than independently verified.

## Advisory assessment

First render an offline report without model calls:

```sh
python3 app.py crc-pilot-run \
  --packet runs/crc_evidence_value_20261020/packet \
  --literature runs/crc_evidence_value_20261020/literature \
  --cptac runs/crc_evidence_value_20261020/cptac \
  --out runs/crc_evidence_value_20261020/offline
```

For an explicitly configured source verifier, add `--verifier codex --model <available-model-id>`, or use `--verifier configured` with the [shared provider configuration](PORTABILITY.md). Use a new output directory. The verifier role is independent of the question planner. Previous SciFact results from another prompt/model configuration do not transfer to this CRC task.

Each available abstract supplies one task. Where usable full text exists, a paired augmented task contains the abstract and up to 12 lexically selected body paragraphs/tables with immediate neighbors, bounded to 90 whole blocks and 28,000 source characters. Selection is deterministic and label-free but can omit crucial context or supplements. The assessment covers only that window, not the whole paper. Missing source views are recorded rather than replaced with synthetic evidence.

One tool-disabled model turn per task returns an advisory SUPPORT, CONTRADICT or NOT_ENOUGH_INFORMATION verdict. Material profile, regimen, population and statistical qualifications must be preserved. Decisive outputs require up to three exact supplied passages with valid indices; an exact quote check establishes reference fidelity, not scientific entailment. Errors remain cases with no repair, retry or alternate-model fallback. Prompts exclude review judgments and benchmark labels. Model identities and requested-turn counts are reported with provider limits; the Codex CLI does not independently attest served weights or expose internal HTTP retries.

## Inspect the result

`report.html` includes the source-view counts, deterministic query comparison, measured context and every source assessment, quote and passage locator. It identifies all judgments as machine assessments and displays human scientific labels as zero. `metrics.json` records controls, overlap, missing views and task/status counts. Scientific accuracy remains null and `scientific_improvement_established` remains false.

The directory also contains frozen tasks, source records, source rights/provenance, a prompt/schema contract, assessment traces, the deterministic reviewer worksheets and blank `scientific_reviews.json`. Edit copies for later independent review; keep the original packet and first run immutable. `verify_pilot_result()` rechecks result, input, assessment and trace hashes and exact quoted passages without another model call. Raw literature and the matrix remain in their separately hashed source directories; preserve those directories for complete reproduction.

The protected app can serve a copied result at `/api/evaluation/<result-directory-name>/` and export its ZIP. The first run should be retained even if its source assessments are disappointing. A further prediction experiment needs a defined measured relationship task, an adequately mapped comparison population, defensible labels and a leakage-controlled baseline/enriched comparison. This pilot does not supply those labels.
