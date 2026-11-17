# DPFunc pretrained qualification: hold before inference

**Decision: HOLD the pretrained comparison.** We found an unresolved, upstream-
reported feature/checkpoint mismatch before spending GPU time. No DPFunc weights
were downloaded, no benchmark annotation rows or protein-sequence members were
opened, and no prediction, runtime installation, graph change or application promotion occurred.
This is a source qualification result, not a negative biological benchmark.

[DPFunc's paper](https://doi.org/10.1038/s41467-024-54816-8) combines residue
language-model features, structure graphs and InterPro-guided attention. It is a
plausible complementary predictor. The current released workflow, however,
cannot yet establish the input contract of its downloadable pretrained weights.

## Verified source and artifact boundaries

We inspected the paper, the official repository at commit
[`c5faf4df4e29b7d264ccb14d88254a136b54f4b2`](https://github.com/CSUBioGroup/DPFunc/tree/c5faf4df4e29b7d264ccb14d88254a136b54f4b2)
(March 18, 2026), and selected source files from the immutable
[paper archive, Zenodo 13843028](https://doi.org/10.5281/zenodo.13843028).
The archive is 8,964,593 bytes with publisher MD5
`7f259de78699c5040e665cf9b1fabed5`. We used the unchanged MIT `remotezip` 0.12.6
range reader and standard `zipfile` CRC checks to inspect its 71-member index
and read only 13 source/configuration/license members. The whole archive was not
downloaded or its MD5 independently recomputed. Dataset members were not
opened. Selected source bodies and their hashes are preserved in the local
qualification record.

The repository and the actual archived `LICENSE` contain identical MIT text.
Zenodo's record metadata instead declares Apache-2.0; that discrepancy is retained
rather than silently treating the fields as equivalent. The official
[weight landing page](https://drive.google.com/file/d/1V0VTFTiB29ilbAIOZn0okBQWPlbOI3wN/view)
identifies `save_models.tar.gz`. We did not download or deserialize it; an exact
publisher checksum, feature manifest and separate weight-license statement were
not established by the inspected landing page.

## What is resolved, and what still blocks use

| Contract | Verified evidence | Consequence |
| --- | --- | --- |
| Encoder and representation layer | The paper specifies ESM-1b. Original archived graph code reads layer 31 from precomputed embeddings without identifying their encoder. The 2026 builder hardcodes `esm2_t33_650M_UR50D`, layer 31. | Matching 1,280-dimensional inputs and byte-identical old/current model architecture do not establish equivalent features. |
| Documented options | The pipeline README lists `--esm-model` and `--repr-layer`, but its actual argument parser exposes neither. | The documented flags cannot resolve the mismatch without a source change. We made none. |
| Structure graph | The paper describes C-alpha distances below 10 Å; archived graph code defaults to 12 Å and uses `<=`. The current builder also defaults to 12 Å. | The convention used for the exact published checkpoint remains unbound; we did not select a favorable interpretation. |
| InterPro axis | An author confirms a fixed 22,369-entry training map and says to ignore unseen entries. Current code retains that width. | Preserve the exact index order; do not fit a new vocabulary to query proteins. A matching width alone is insufficient. |
| Output classes | Released encoders exist; the new builder accepts `--mlb-source`. | Prediction must preserve the checkpoint's exact ordered class encoder. We have not established a checksum-bound checkpoint/encoder/ontology pairing. |

The encoder and GO-version uncertainty is already raised in official
[issue 11](https://github.com/CSUBioGroup/DPFunc/issues/11), which had no reply
at inspection. The current builder and its documented options can be checked
in the [pinned script](https://github.com/CSUBioGroup/DPFunc/blob/c5faf4df4e29b7d264ccb14d88254a136b54f4b2/DPFunc_demo_pipeline/scripts/build_data_demo.py)
and [guide](https://github.com/CSUBioGroup/DPFunc/blob/c5faf4df4e29b7d264ccb14d88254a136b54f4b2/DPFunc_demo_pipeline/README.md).
The fixed InterPro contract is supported by the
[author's reply](https://github.com/CSUBioGroup/DPFunc/issues/10#issuecomment-3816282448).
These are verified source differences and unresolved provenance, not evidence
that either encoder is biologically inferior or that the published method fails.

## Historical data and evaluation limits

The [author confirms](https://github.com/CSUBioGroup/DPFunc/issues/10#issuecomment-3737102114)
that the pretrained weights use the large-scale dataset and permit prediction
with empty annotation inputs. The
[dataset clarification](https://github.com/CSUBioGroup/DPFunc/issues/9#issuecomment-3625549567)
also states that `DataProcess/data_dpfunc` belongs to newer DPGOK research,
**not** the DPFunc paper benchmark. The replacement paper dataset omits the
AlphaFold structures and InterPro results. We did not read either annotation
dataset or use the newer one as historical training data.

The paper reports training before May 2020, validation from May 2020 through
April 2021, and testing from May 2021 through April 2022. Those dates do not
establish the actual checkpoint's row membership or homology separation from
our targets. Our existing CAFA5 outcomes have already been exposed; any later
comparison on them must remain development reuse. Dated sequences, structures
and InterPro inputs would need identity/version checks. InterPro features or
GO-derived context must not be counted as independent biological evidence.

The current author environment specifies Python 3.8.20, PyTorch 1.12.0/CUDA 11.3,
DGL 1.1.0.cu113, scikit-learn 1.3.0 and SciPy 1.10.1. An ESM package version is
not pinned there. We did not create that environment or substitute the existing
DeepGO runtime and call it an exact reproduction.

## Gates before reconsidering inference

1. Obtain an authoritative checkpoint-to-encoder/layer and graph-construction
   contract, or matching released feature artifacts. Do not infer compatibility
   from tensor dimensions or patch the pipeline to guess it.
2. Pin checkpoint bytes, all three epoch members per aspect, the exact InterPro
   index map, ordered GO encoder and ontology snapshot as one compatible bundle.
3. Qualify historical sequence/structure/domain coverage and training/time/
   homology overlap; preserve missing targets and the development exposure label.
4. Only then test an isolated runtime and unchanged-author prediction parity,
   followed by one fixed comparison. No retraining or alternative-feature sweep
   is authorized by this qualification.

The useful outcome is an upstream contract problem caught **before** another
experiment. Continue the already qualified comparisons while retaining this
hold and its source evidence.
