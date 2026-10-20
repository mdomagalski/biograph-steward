# Measured cohort mapping and source-context follow-up

The [recorded October 20 result](evaluations/CRC_CONTEXT_COHORT_20261020.md) accounts for every CPTAC matrix row and adjudicates the first pilot's context flag as a separate AI-authored overlay. Original source records, graph review states, machine verdicts and human review worksheets remain unchanged.

## Freeze the human identifier registries

```sh
python3 app.py identifier-registry \
  --out runs/crc_adjudication_mapping_20261020/registry
```

This retrieves the complete approved [HGNC dataset](https://www.genenames.org/download/statistics-and-files/) and a [UniProt REST](https://www.uniprot.org/help/uniprot_rest_tutorial) table of reviewed human entries, including gene names, synonyms, HGNC cross-references and NCBI Gene IDs. Raw TSVs, retrieval metadata, release headers and SHA-256 checksums are frozen. `--downloads <directory>` can reuse files with matching fixed-URL/hash receipts in `retrieval.json`; supplied receipt metadata remains caller-declared. The recorded run used downloads made earlier in the same task. No cloud account or key is required.

## Map every measured row

```sh
python3 app.py cptac-map \
  --cptac runs/crc_evidence_value_20261020/cptac \
  --pharos-run runs/planning_challenge_20261020/suite/sources/pharos \
  --registry runs/crc_adjudication_mapping_20261020/registry \
  --out runs/crc_adjudication_mapping_20261020/published_cohort
```

The output must be new and separate from its inputs. Exact approved HGNC symbols take precedence, with conflicting aliases still disclosed. Other exact previous symbols, aliases and UniProt gene names must identify one approved human HGNC gene across both registries. Collisions remain unresolved; the mapper does not rank candidates, guess spelling or silently convert case. Protein links retain agreement/conflict status against human UniProt HGNC and NCBI Gene cross-references. A missing entry in the reviewed subset does not prove that an accession is invalid or deleted.

The full `mappings.json` and `mapping_review.tsv` account for all source rows. The immutable `cohort.json` selects uniquely resolved genes with observed values and no duplicate gene rows, independently of disease labels. Identifier eligibility is not scientific validation. `protein_context_eligible` additionally requires a confirmed reviewed product and a protein-coding or complex-locus-constituent HGNC record. Even then, the assay remains gene-level: multiple products share one measurement and never become separate protein observations. Readthroughs and missing values are retained; nothing is imputed or relabeled as negative.

The export includes the original matrix, the frozen registry tables and manifest, and the 99 Pharos protein IDs/symbols used in the join. `verify_mapping(path)` rechecks checksums and reproduces the complete crosswalk and counts from these inputs without network access. These identifiers do not substitute for the original Pharos evidence snapshot, which remains separately preserved.

## Record a scoped source adjudication

```sh
python3 app.py source-adjudicate \
  --pilot runs/crc_evidence_value_20261020/live \
  --literature runs/crc_evidence_value_20261020/literature \
  --decision docs/evaluations/crc_947_context_decision_20261020.json \
  --mapping runs/crc_adjudication_mapping_20261020/published_cohort \
  --out runs/crc_adjudication_mapping_20261020/context_adjudication
```

The decision explicitly identifies its author as an AI assistant. It binds the original item hash, publication identity and each referenced source block's exact text hash. References must belong to the declared inspected text scope. The tool preserves original verifier traces byte for byte and exports original assessments alongside proposed scoped wording, findings, source passages and limits. It checks the original pilot and literature manifests without attempting to replay the old suite under changed code. Old code fingerprints are never rewritten.

This records source inspection performed by the assistant; it does not invoke a new verifier, attest an independent model identity, fill human review forms or score itself against its own decision. Relevant paper text and figure captions are distinct from figure-image, supplement or raw-data review. `verify_adjudication(path)` checks the overlay and its source bindings.

Both result directories contain protected-app-compatible `report.html` and `metrics.json`. When copied to the server's runs directory, view `/api/evaluation/<directory-name>/` and export `/api/download/<directory-name>`. These are inspection reports, not automatic graph review actions or a biological benchmark.
