# Verification benchmarks — October 15, 2026

Use published labeled tasks to evaluate the proposed [source verifier](VERIFIER_PROTOCOL.md). They reduce the need for the project owner to create expert labels. They do not independently validate every CRC claim or the complete knowledge graph.

| Dataset | What it tests | Fit and limits |
|---|---|---|
| [SciFact paper](https://aclanthology.org/2020.emnlp-main.609/) and [author repository](https://github.com/allenai/scifact) | Expert-written scientific claims, supporting/contradicting abstracts and sentence rationales. | First choice for claim/paper verification. General scientific/biomedical scope; does not fully evaluate variant/regimen context or graph prediction. |
| [NLI4CT paper](https://aclanthology.org/2023.emnlp-main.1041/) and [organizer data](https://github.com/ai-systems/nli4ct) | Inference over clinical-trial reports and evidence selection, with 2,400 annotated statements. | Useful second test for trial context. Its inference task/labels differ from SciFact; it does not establish CRC-specific validity. |
| [Evidence Inference](https://aclanthology.org/N19-1371/) and [version 2 paper](https://aclanthology.org/2020.bionlp-1.13/) | Reported effects for an intervention versus a comparator on a specified outcome, with evidence. | Useful when adding comparative outcome extraction. Randomized-trial focus does not cover all observational and preclinical CIViC records. |

## Prepared SciFact data

The official [download script](https://github.com/allenai/scifact/blob/master/script/download-data.sh) identifies the authors' release. The downloaded archive SHA-256 is `11c621288d41ac144d29b13b0f8503b3820b7d6e8b1f6ff24dff335c196d76be`. Local raw data is in `runs/scifact_source_20261015/`; data is excluded from Git.

The release has 5,183 abstracts, 809 training claims and 300 development claims. The initial preparation uses the official development set and its cited documents to produce **339 unique claim/abstract pairs**. One repeated citation for claim 1245 is collapsed and recorded in the manifest; original source bytes are unchanged. Labels are 138 SUPPORT, 71 CONTRADICT and 130 NOT_ENOUGH_INFORMATION. All positive pairs have at least one annotated rationale of at most three sentences. These are data-readiness counts, not model results.

The official train/dev claim IDs are disjoint, but the prepared citation candidates share **181 document IDs** (565 unique training documents and 283 development documents). Therefore the official split alone does not establish generalization to unseen papers after training on the prepared training tasks. An additional subset excludes an entire development claim if any cited document appears in training. It contains **104 claims / 119 pairs**: 50 SUPPORT, 22 CONTRADICT and 47 NOT_ENOUGH_INFORMATION, in `runs/scifact_verification_document_holdout_20261015/`. This is a custom supplementary subset, not a replacement official benchmark split. Selection uses document IDs, not gold labels. Zero overlap within this project does not rule out foundation-model pretraining exposure.

`runs/scifact_verification_dev_20261015/inputs.jsonl` contains only task IDs, claim text and sentence-indexed abstracts. `gold.jsonl` separately contains the expert label and complete alternative rationale sets. An empty evidence annotation for a supplied cited abstract maps to insufficient information **within that abstract**, not biological falsity or absence from the literature. Unlabeled inputs are rejected rather than converted to negatives.

The [authors' schema](https://github.com/allenai/scifact/blob/master/doc/data.md) documents these annotations. The [official evaluation](https://github.com/allenai/scifact/blob/master/doc/evaluation.md) includes evidence-completeness requirements. Our prepared given-document task is a component test; its scores must not be called official full-pipeline or leaderboard scores. The original test release is unlabeled, so local preparation intentionally supports train/dev only. Foundation-model exposure to this public benchmark cannot be excluded.

Download and prepare with standard-library Python:

```bash
python3 scripts/prepare_verification_benchmark.py --download --out runs/scifact_source_02
python3 scripts/prepare_verification_benchmark.py --source runs/scifact_source_02 \
  --split train --out runs/scifact_verification_train_02
python3 scripts/prepare_verification_benchmark.py --source runs/scifact_source_02 \
  --split dev --out runs/scifact_verification_dev_02
python3 scripts/prepare_verification_benchmark.py --source runs/scifact_source_02 \
  --split dev --exclude-documents-from runs/scifact_verification_train_02/inputs.jsonl \
  --out runs/scifact_verification_document_holdout_02
```

The URL says `latest`, so pin and report the downloaded bytes; a future release may differ. The adapter verifies hashes before preparation and never supplies expert labels to model inputs. Read only `inputs.jsonl` into an isolated verifier turn. No verifier model was run as part of this preparation. A staged benchmark does not show that the proposed agent works.

The [authors' license](https://github.com/allenai/scifact/blob/master/LICENSE.md) distinguishes CC BY 4.0 claim/annotation data, ODC-By 1.0 corpus abstracts and Apache 2.0 code. Preserve attribution and the source manifest. Follow each additional dataset's own data terms; a participant implementation's software license is not a dataset license.

Preparation tests use invented records to check separation of labels, complete alternative rationales, unlabeled-input rejection, source byte hashes, citation deduplication, archive handling and whole-claim document exclusions. These software tests are not evidence-verifier performance measurements.

## CRC evidence audit

`runs/ai_source_verification_20261015/` contains an AI-prepared check of the ten G13D/cetuximab source items against the cached PubMed records. Checks bind the original CIViC descriptions and source-text hashes. They separate partial statement support, unresolved details and suspected context mismatches from scientific validation of CIViC's direction/significance labels. Two attempted PMC full-text fetches failed; those failures are access limitations. No human worksheet judgment, assertion acceptance or graph state was changed.

The next implementation is one bounded verifier using this contract and external answer keys. Evaluate its supplied-document reasoning before adding autonomous literature retrieval, graph updates or pruning. Source-grounded machine assessments can carry most routine checking, while disputed domain judgments remain explicitly unresolved.
