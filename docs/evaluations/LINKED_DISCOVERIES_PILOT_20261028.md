# Linked Discoveries pilot

The documented Linked Discoveries interface successfully returned two unfiltered, default 50-record neighborhoods around PMIDs 20619739 and 19223544, the two publications cited in the saved KRAS G12D example. After deduplication, the exports contain **90 distinct papers**: **eight already retrieved in the saved workspace and 82 absent from its explicit PMID inventory**. This demonstrates usable literature discovery in this example, not improved biological accuracy or prediction.

## Source and comparison scope

The original CSV downloads are preserved unchanged under `runs/linked_discoveries_pilot_20261028/retrieval/`. Each contains the seed and 49 neighbors. The two neighborhoods share ten papers. The documented Download CSV buttons were used, with the UI confirming no active filters. No undocumented service endpoint, model inference or paid compute was used.

| Seed PMID | Exported records | Already retrieved, including excluded items | Absent from saved inventory |
| --- | ---: | ---: | ---: |
| 20619739 | 50 | 7 | 43 |
| 19223544 | 50 | 4 | 46 |

These per-seed populations overlap. The eight distinct existing papers comprise seven normalized CIViC source publications and one additional publication already present among retrieved but excluded CIViC items. Neither discovery nor source editorial acceptance accepts an assertion locally.

The baseline is the complete **saved 99-target Pharos/CIViC workspace**, not the complete Pharos database. It contains 2,161 distinct target-linked Pharos discovery PMIDs and 22 retrieved CIViC source PMIDs, with a union of 2,182. Target-discovery references remain separate from supporting citations. Ninety of the 99 Pharos publication lists were capped at 25 records per target, and the saved graph does not enumerate all upstream STRING studies. No IntAct attachment is present in this workspace; separate assay cohorts were not pooled.

The CSV stores plain PMID strings; the project uses `PMID:` CURIEs. Exact comparisons use the same representation and assert known existing seed references before calculating overlap. “Absent from this saved inventory” does not establish absence from Pharos, a new discovery, an independent experiment or new supporting evidence.

## Bounded relevance inspection

Assistant inspection of the first five nonseed rows per neighborhood gives ten distinct papers. Seven are absent from the saved inventory, two already support normalized CIViC records, and one was already retrieved but excluded from normalized assertions. All ten concern broader colorectal-cancer, RAS/PIK3CA or anti-EGFR context; none explicitly identifies G12D-specific response evidence in its title or abstract. This does not exclude relevant details in full-text tables. It is not independent expert adjudication, a systematic review or an accuracy benchmark. The remaining 80 papers have not been assessed for exact-claim relevance.

For example, PMID 19366826 reports a different abstract-level PIK3CA finding from seed PMID 19223544. Population, treatment, mutation definitions, methods and possible cohort reuse need examination before treating this as a contradiction or failed replication. G13D-specific and KRAS-wild-type studies must not be transferred to G12D solely because they are nearby in the graph.

## Publication-status information

Twelve distinct records have exported publication-update metadata: eleven have Comment entries and one has an Erratum entry. Comments are not retractions, and blank fields do not establish clearance. The Erratum entry on PMID 18339877 links back to the same PMID. A bounded, documented NCBI EFetch verification failed with DNS resolution error, leaving the distinct correction relationship unverified. The exported value is preserved as unresolved metadata; no automatic exclusion or retraction action is taken.

## Product behavior and limits

The existing collapsed CIViC source details and source passport now offer a safe external Linked Discoveries link for exact positive PMIDs. There is no automatic retrieval, source import, change to answer content, graph mutation or review decision. Focused DOM checks cover both render locations, identifier handling and immutability.

Keep the optional links. This pilot does not compare Linked Discoveries against PubMed Similar Articles, measure systematic-review recall, establish study independence or provide gold scientific labels. No neighborhood similarity or citation edge was imported as a biological relationship.

Artifacts: `runs/linked_discoveries_pilot_20261028/report.html`, `comparison.json`, `plan.json`, `baseline/baseline.json`, unchanged raw CSVs and `retrieval/downloads.json`. Reproduce the saved-data analysis with `python3 runs/linked_discoveries_pilot_20261028/analyze.py`; this does not retrieve new data. A compact record and artifact hashes are in `linked_discoveries_pilot_20261028_summary.json`.

## Primary references

- [NLM Linked Discoveries user guide](https://linkeddiscoveries.ncbi.nlm.nih.gov/userguide/): neighborhood generation, filters, export contents and interpretation limits.
- [NIH launch statement](https://www.nih.gov/news-events/news-releases/nih-launches-new-pubmed-tool-strengthen-research-replication-reproducibility): the tool does not determine study quality or successful replication.
- [PMID 19366826](https://pubmed.ncbi.nlm.nih.gov/19366826/) and [PMID 19223544](https://pubmed.ncbi.nlm.nih.gov/19223544/): primary abstracts for the PIK3CA context example.
