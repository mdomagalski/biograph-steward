# Small data contract for future improvements

## A node

`id`, `name`, `category`, `data_kind`, `identifier_mapped`, and optional `sym`, `tdl`, `family`, `source_identifier`, `url`.

- Proteins use `UniProtKB:` plus the returned accession, never a gene symbol promoted into a protein identifier.
- A supplied MONDO ID is normalized without guessing equivalence from names.
- A missing disease ontology ID is represented with a clearly local `pharos.disease:` identifier and causes associated edges to need review.
- Explicit Reactome pathway source IDs are preserved as `REACT:` identifiers. Other pathway records retain local `pharos.pathway:` IDs pending a verified crosswalk.
- Demo nodes use `demo:` identifiers and cannot pass the normal live identifier parser.

## An evidence edge

`id`, `subject`, `predicate`, `object`, `status`, `review_reasons`, `record_kind`, `aggregator`, `primary_source_raw`, `reference_raw`, `publications`, `evidence_raw`, `source_scores_raw`, `evidence_record`, `record_locators`, `snapshot_sha256`, `data_kind`, `biologically_validated`.

There can be multiple edges for one protein-disease pair because different records carry different evidence. A later modeling pipeline must group these before splitting pairs; otherwise the same pair may leak into both training and test sets.

A raw locator such as `snapshot.json#/targets/0/diseaseAssociationDetails/1` identifies the precise transformed input. The snapshot contains query variables and raw successful API responses. A hash alone is not sufficient evidence provenance; it is paired with those records.

`primary_source_raw` retains the upstream string unchanged. `Pharos` is the aggregator, not an automatically substituted primary source. No claim of source independence is made.

## Status semantics

- `passed_structural_checks`: identifiers and implemented minimal record rules passed; **not** scientific validation.
- `needs_review`: an inspectable edge remains, with explicit reasons for caution.
- Quarantine log: a malformed or exact duplicate input is excluded from the graph, but preserved in the raw snapshot and log.

## Not model inputs yet

Do not train on all exported columns. Disease-association text, references, source scores, labels and inverse/equivalent edges may expose held-out answers. A future benchmark must deliberately select permissible features after pair-level splitting and leakage review.

The display order is alphabetical by symbol/identifier, not scientific priority. The source API order governs the bounded retrieval, not a model score. Scores on an evidence card are original source values, not output from this prototype.
