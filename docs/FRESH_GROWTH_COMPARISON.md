# Full-cohort Pharos retrieval and one fresh-gene comparison

This workflow follows the [development ablations and untouched-gene reservation](evaluations/CRC_GROWTH_DIAGNOSTICS_20261020.md). The 256 old genes are development data. The 256 reserved genes are the final test, with no gene/product overlap with development. The primary hypothesis is fixed **before reserved outcome access**: pathway-only minus full restricted Pharos in test-gene Spearman. It does not promote the best test arm after scoring.

## Cohort and consistent retrieval

```sh
python3 app.py fresh-cohort \
  --panel runs/matched_pharos_panel_20261020/frozen_panel \
  --reservation runs/crc_growth_diagnostics_20261020/published_reservation \
  --diagnostics runs/crc_growth_diagnostics_20261020/published_diagnostics \
  --out runs/crc_fresh_comparison_20261020/cohort

python3 app.py fresh-retrieve \
  --cohort runs/crc_fresh_comparison_20261020/cohort \
  --out runs/crc_fresh_comparison_20261020/retrieval_serial
```

The union contains 512 genes / 513 requested products. Every resolved product shares one PPI partner scope: the full resolved union, including links between development and reserve. IDs are explicit; no disease filter or outcome field is requested. The per-protein limits are identical: 5,000 pathways, 2,000 GO, 5,000 interactions and 5,000 expression records. Drugs/publications are not requested. These are ceilings, not a claim that all records exist. The full source envelope is retained before local tissue/cohort filtering.

All requests are refreshed, with a live database version before and after. Every requested family must reconcile to complete, without pagination issues. The verifier reconstructs scoped records from every retained raw page and rejects incomplete/capped families, changed identity/version, old cached HTTP envelopes and narrower PPI scope. Missing products remain in the panel without substitution. Offset retrieval is not an atomic upstream snapshot or an attestation of underlying study independence.

Pharos gateway errors from multi-protein expression pages prompted a transport-only retry: one protein per expression request, other families keep normal batches. Caps, family fields, genes and feature rules remain unchanged. The failed output is preserved separately; the successful attempt does not mix its older responses into the refreshed run.

## Freeze before reserved outcome access

```sh
python3 app.py fresh-freeze \
  --cohort runs/crc_fresh_comparison_20261020/cohort \
  --retrieval runs/crc_fresh_comparison_20261020/retrieval_serial \
  --mapping runs/crc_adjudication_mapping_20261020/published_cohort \
  --reference-protocol runs/crc_growth_protocol_20261020/frozen \
  --out runs/crc_fresh_comparison_20261020/frozen
```

The source-channel policy is unchanged: separate Reactome/WikiPathways memberships, qualified BioPlex binary adjacency and source-specific numeric/categorical expression; CPTAC adds the same signed median tumor/normal ratio. GO, integrated/unresolved dependency-related annotations and unqualified PPI components remain withheld. Evidence records are not deleted because a feature representation performed poorly.

Development genes formerly in train+validation (204) become training; the former test genes (52) become development validation. All are already exposed genes. The new 256 genes alone are test. Original model groups stay in their 36/12/13 train/validation/test assignments (38/12/13 models). Thus laboratory cohorts and upstream processing are reused. Whole reviewed-product components and sample groups stay together.

Train only on development training genes × training sample groups. Select alpha on development validation genes × validation sample groups. Refit selected models on all 256 development genes × the 50 train/validation models. Test only the 256 reserved genes × the 13 test models. No other reserved-gene values are parsed. Fit vocabularies, imputation and scaling on current fit genes only.

Exactly one primary contrast is **pathway-only minus full restricted Pharos**. It is motivated by the earlier exposed-data source audit, not selected using these reserved scores. The internal signal rule remains delta ≥ 0.05 and a positive paired 95% interval lower bound. The 2,000-draw paired gene/sample-group bootstrap uses fixed predictions and excludes fitting/selection uncertainty. Failure retains a negative/inconclusive result.

Predeclared secondary arms retain all six source ablations, Pharos+CPTAC, CPTAC-only, coverage-only and fixed half/half late combination. CPTAC-only keeps its prior validation nomination; the primary pathway hypothesis is not portrayed as that validation winner. Other arm comparisons are descriptive, with no confirmatory multiplicity-adjusted claims. Fixed fusion reuses two component budgets and fits no weight.

The complete budget is **200 ridge fits**: ten base ridge representations plus twenty CPTAC permutations and twenty pathway-block permutations, each with three alpha trials and one final refit. Permutations stay within each new gene role, use predeclared seeds 0–19 and preserve their donor mapping at refit. The pathway controls shuffle the entire source-qualified membership block; CPTAC controls shuffle the signed ratio. Also report an intercept and 100 fixed hash rankings. Controls are not replacement candidates selected on the final test.

## Execute once and replay without refitting

```sh
python3 app.py fresh-compare \
  --protocol runs/crc_fresh_comparison_20261020/frozen \
  --source runs/depmap_feasibility_20261020/source \
  --out runs/crc_fresh_comparison_20261020/result
```

The runner first verifies the freeze, exact implementation fingerprint and all pinned source bytes without parsing reserved effects. It loads only the development block, fits all declared models and controls, then saves models, preprocessing, donor maps and every prediction in `sealed_predictions.json`. Only then does it create an exclusive `.reserved_gene_test_access_*.json` ledger beside the pinned source directory, keyed by source and test-gene identities. Any overlapping gene set in another preserved ledger for that source is rejected, even under a different protocol identity. Preserve the ledger and partial output after a post-access failure; diagnose/recover from the same sealed predictions rather than rerunning model selection.

When moving or publishing a consumed test to another machine, preserve its exposure ledger beside that machine's pinned source directory too. The result export retains the byte-identical receipt as `test_access_receipt.json`; copy it under its source/test-gene digest ledger name. Merely importing a report is insufficient to protect another source location from a rerun. The recorded Brev deployment mirrors this prior exposure and tests that a repeat fails before source loading or fitting.

The report gives primary metrics/interval/decision, every secondary arm and control, and every reserved gene's ranks and source-linked pathway contributions. These are statistical explanations, not causal target validity. Attribution, source licenses, full feature input rows and source locators are retained. The full original source matrix and large Pharos response packet remain separate from the result export.

```python
from biograph_steward.fresh_growth import verify_fresh_protocol, verify_fresh_result
verify_fresh_protocol('runs/crc_fresh_comparison_20261020/frozen')
verify_fresh_result('runs/crc_fresh_comparison_20261020/result')
```

Offline result replay reconstructs the frozen views, sealed predictions, endpoint grouping, all metrics and control summaries, donor mappings, primary interval/decision and gene passports without fitting or reopening the original outcome matrix. The computation uses standard-library CPU code with zero model-service requests. AWS/GPU inference are unnecessary. A fresh gene holdout within a historical jointly processed release is not independent new laboratory validation, and the challenge's graph-link prediction/pruning benchmark remains a separate task.
