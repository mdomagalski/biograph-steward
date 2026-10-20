# Freeze the matched growth-dependency comparison

This increment turns the [matched Pharos pull](MATCHED_PHAROS_PANEL.md) into a reviewed feature packet and a frozen experiment specification. It does **not** load dependency scores, fit predictors or run the comparison. The first experiment tests whether CPTAC measurements add predictive information to a restricted Pharos representation; it does not test every feature available in Pharos or establish clinical response, disease selectivity or causal target validity.

```sh
python3 app.py comparison-freeze \
  --panel runs/matched_pharos_panel_20261020/frozen_panel \
  --retrieval runs/matched_pharos_panel_20261020/retrieval \
  --mapping runs/crc_adjudication_mapping_20261020/published_cohort \
  --pharos-code runs/pharos_coverage_20261014/TCRD.js \
  --repository-tree runs/pharos_coverage_20261014/repo_tree.json \
  --out runs/crc_growth_protocol_20261020/frozen
```

Verified parent hashes must agree, all requested Pharos families must have complete count reconciliation, and the Pharos database version must be unchanged across retrieval. The output must be new. This command has no dependency-matrix argument or model client. CPTAC measurements are predictor inputs and remain distinct from the withheld CRISPR endpoint.

## Source decisions

The [published Pharos implementation](https://github.com/ncats/pharos-graphql-server/blob/master/src/TCRD.js) shows that its confidence predicate removes low-score STRING-only rows; it does not apply that cutoff to every mixed-source interaction. The stored repository tree's Git blob identity is checked against the preserved implementation bytes. That binds the inspected public source, not the revision deployed behind the live API.

The [BioPlex documentation](https://bioplex.hms.harvard.edu/explorer/help) distinguishes its filtered network from subthreshold interactions. The feature policy accepts a reported BioPlex component only when its separate `p_int` is present exactly once, finite and between 0.75 and 1, including mixed BioPlex/STRING/Reactome rows. Only the binary BioPlex adjacency becomes a predictor. STRING scores, novelty/TDL, source-label mixtures and probability magnitude remain provenance. A mixed label without qualifying component evidence is withheld. The [BioPlex release catalogue](https://bioplex.hms.harvard.edu/interactions.php) also distinguishes assays and cell contexts; the retrieved records do not establish which underlying release or cell context produced each pair. These interactions are general context, not verified CRC-specific experiments.

All retrieved GO annotations remain in the source packet but are withheld from primary predictors. The [Pharos GO schema](https://github.com/ncats/pharos-graphql-server/blob/master/src/schema.graphql) does not expose study references or qualifiers for the inspected rows. The [GO evidence guide](https://geneontology.org/docs/guide-go-evidence-codes/) distinguishes direct assays, phenotypes, inference and other evidence; an assigning source or code alone cannot resolve overlap with held-out perturbation experiments. This exclusion defines a restricted baseline and must accompany every result claim.

Reactome and WikiPathways memberships require explicit stable identifiers. Binary membership is the union across verified products, collapsing repeated records and version suffixes within each source namespace. The sources stay separate; no unverified cross-source equivalence or independent-study count is inferred.

Expression inputs retain HPM Protein numeric observations for Adult Colon/Rectum, HPA RNA for colon/rectum and HPA Protein categories for exact colon/rectum cell-type labels. The [HPA scoring explanation](https://www.proteinatlas.org/about/help) supports preserving “Not detected” as an observed assay category. Missing observations stay distinct; conflicting categories remain sets. JensenLab TISSUES integrated scores and other sources are withheld. Exact repeated values collapse before source/tissue aggregation; observations are not independent replicate counts. Units are not pooled across assay sources.

The [LinkedOmics catalogue](https://linkedomics.org/data_download/CPTAC-COAD/) identifies the frozen 6,422-row, 96-column PNNL tumor/normal ratio matrix. The enriched arm adds one median available ratio per gene. It does not assume that a higher ratio means greater essentiality. LinkedOmics/PDC distributions of this study are not independent enrichment cohorts.

These are AI-authored source-contract decisions, not human scientific gold adjudication or proof of underlying-study independence. Raw metadata, source/popularity counts, disease labels, endpoint-derived fields, discovery text, unresolved shared products and CIViC therapy-response evidence stay outside the primary predictor definition.

## Frozen comparison

`specification.json` is the exact machine-readable policy. It defines:

- **Endpoint:** stronger growth dependency is negative processed gene effect. Aggregate by median within each recorded tissue-sample group, then median across groups with equal group weight. Missing or changed outcomes fail the run; no binary essential/nonessential labels are manufactured.
- **Splits:** deterministic 60/20/20 hash allocation on both axes. Genes sharing a requested protein accession form one component; models sharing PatientID/tissue-sample provenance form one group. Whole components/groups stay together. The tested task holds out both genes and model groups.
- **Inputs:** separate Reactome, WikiPathways, BioPlex adjacency, numeric expression and categorical expression blocks; the enriched arm adds the CPTAC summary. Training data alone determine vocabularies, scaling and imputation. Unknown held-out features cannot add columns. Gene and protein IDs are join keys, not identity predictor columns.
- **Model:** ridge regression with an unpenalized intercept and the identical three-value alpha budget in both arms. Select on validation Spearman; break ties toward stronger regularization. Refit preprocessing and the selected model on training plus validation before evaluating the held-out test block once.
- **Controls:** intercept, 100 deterministic random rankings, coverage-only and CPTAC-only baselines, and 20 fixed CPTAC permutation controls. A gain over restricted Pharos alone does not show that graph structure adds value beyond CPTAC alone; the control results must be reported.
- **Metrics:** primary paired change in test-gene Spearman; secondary MAE, per-group correlations and descriptive Recall@10. Undefined correlations remain null. A paired two-axis bootstrap resamples test genes and sample groups on the same draws, with fixed trained predictions. It does not include training or cohort-selection uncertainty.

The preset delta/interval rule is an internal pilot signal, not a universal biological significance threshold. Always report controls and limitations even if it passes. No outcome-based membership changes, extra tuning or post-test policy edits are allowed under this freeze. A changed experiment requires a new protocol and a fresh holdout.

The [Chronos methods paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC8686573/) describes processed fitness inference and corrections. These already processed outcomes retain upstream joint processing; downstream model splits do not create independent laboratory data. Modern Pharos annotations also postdate the historical outcome release. This is a retrospective pilot, not temporal validation, and general growth effects in colorectal models are not colorectal-selective dependencies.

## Artifacts and verification

`source_inputs.json` materializes the exact relevant source rows, gene/product identities, model inventory and CPTAC summaries. It contains no CRISPR values. `features.json` contains deduplicated memberships, source-specific observations, gene-level adjacency and CPTAC summaries. Support locators bind both the local source packet and the parent Pharos snapshot. `exclusions.json` records every withheld row and reason. `source_review.json` reports coverage and limitations. `partitions.json` fixes exact grouped assignments. Source references and the inspected public implementation/tree are preserved separately.

`metrics.json` binds all files, parents and the engine fingerprint. `report.html` presents the rules, review and assignments in the protected app. Offline verification reconstructs features, exclusions, partitions and policy:

```python
from biograph_steward.comparison_protocol import verify_protocol
verify_protocol('runs/crc_growth_protocol_20261020/frozen')
```

The next increment implements and tests the training/evaluation runner against this exact packet, then executes the first comparison. GPU inference and AWS provisioning are unnecessary for this CPU-sized experiment.
