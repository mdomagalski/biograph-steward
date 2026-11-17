# ProtNote qualification — 14 November 2026

**Completed: source/runtime qualification, native parity, full prediction and controlled evaluation.** All 547 original identities produced forecasts on the independently fixed GO axis, with no abstentions or reference-label input. The [complete comparison](PROTNOTE_COMPARISON_20261114.md) does not support replacement of the stronger controls: all four exploratory molecular-function intervals against the existing-annotation baseline favor that control. Valid execution did not establish a biological prediction gain.

## Why this candidate

[ProtNote](https://doi.org/10.1093/bioinformatics/btaf170) combines a sequence CNN with function-description embeddings and can score functions outside its trained label set. It supplies a different mechanism from our fixed-head DeepGO comparison. Its native masked CNN processes whole supplied test sequences, addressing the concrete 1,022-residue truncation in our existing DeepGO profile. Those additional capabilities did not produce an advantage over the stronger controls in the completed comparison.

The [official source](https://github.com/microsoft/protnote/tree/b29e17fa308d8c0fc1d9692f705b37dff3a8cf5e), model card and [released archive](https://zenodo.org/records/13897920) explicitly permit MIT reuse. We retain the author's `ProtNote` and `ProteInfer` classes and their scoring calculation. No replacement architecture or retraining is proposed.

## Completed artifact and runtime checks

The initial source-only stage read the archive's 82-member central directory in one 65,536-byte HTTP range. It opened no member bodies. Subsequently, the complete archive was staged on the existing Brev instance so its publisher checksum could be independently verified before extracting **only seed 42**:

- Archive: 17,594,525,298 bytes; recomputed MD5 `703141e8eb7a89c83190122f0adfde35`, matching the publisher.
- Selected checkpoint: 3,412,866,491 bytes; ZIP CRC verified; SHA256 `d855e6c40b986294f3f4c852020c58b362ec2d38d806f60ef78e2fef89ab0887`.
- Restricted CPU load used `torch.load(weights_only=True, map_location='cpu')`. Both frozen encoders are present, so no separate E5 model weights were downloaded.
- The native constructor strictly loaded all 523 state keys, with matching shapes and dtypes. At this CPU stage, all modules were in evaluation mode, parameters frozen, and CUDA remained uninitialized; the later explicitly authorized synthetic parity stage used the existing GPU.
- A separate runtime uses Python 3.10.12, PyTorch 2.0.1+cu117, torchvision 0.15.2 and transformers 4.32.1. The source environment specifies Python 3.10.13; this patch-version difference is recorded. Installed library dependencies pass `pip check`. The legacy obonet 1.0.0 import additionally needed its implicit `pkg_resources` provider; pinned setuptools 75.3.0 resolved this without changing the ontology parser or source.
- All 31 acquired official source files and five pinned E5 tokenizer/config files were checked against their expected hashes. Bulk archives and weights remain on Brev; local receipts contain metadata only.

The original default-curl transfer returned HTTP 403. [Zenodo's documented identifiable User-Agent policy](https://developers.zenodo.org/#user-agent) resolved this; the complete transfer then used bounded, verified HTTP ranges. Failed transfer and qualification receipts were retained.

## Integration gaps and their status

| Issue | Verified finding | Current handling |
|---|---|---|
| Label-derived prediction vocabulary | The native dataset builds its GO class universe from the union of FASTA header labels, ignoring its supplied vocabulary path. Forward itself does not receive each protein's positive labels. | The reviewed adapter supplies an explicit dated GO axis independently of target labels; its synthetic numerical parity has now passed. A dataset-defined universe may be appropriate for the original paper; it does not define our all-GO prediction task. |
| Conflicting package declarations | `environment.yml` specifies torch 2.0.1/transformers 4.32.1, while `setup.py` declares 2.2.0/4.38.0 and numerous training dependencies. | The new environment imports unchanged, hash-verified author source through an explicit source path. Only its conflicting editable distribution metadata was removed from that new environment; source and existing runtimes were preserved. |
| Text and cache identity | Default released descriptions/cache are from 2019/2024, and native hub loading does not pin a revision. | E5 config/tokenizer revision is pinned. The adapter uses the checkpoint's own frozen text encoder. The reviewed driver enforces source, ordered-axis, text, tokenizer and serialized-cache hashes. The complete GO 2023 cache was generated and its serialized body pinned before target inference. |
| Native preprocessing details | Obsolete-text cleanup applies to both name and definition; multi-batch cache generation changes encoder mode; inference averages name/definition probabilities. | The adapter retains native cleanup and aggregation, restores evaluation mode, and rejects an axis-order mismatch before forward. These changes passed independent source review and the synthetic execution gates. |
| Full target accounting | Native defaults deduplicate identical sequences. The 20-channel encoder documents no noncanonical-residue substitution. | Preserve every original target identity; explicitly abstain on missing/noncanonical/unscorable sequences. No inferred U/X substitution or silent denominator reduction. |

One manual CPU metadata probe initially expected the final layer at index 9. The author's zero-probability dropout modules place it at index 11. That probe was corrected and its earlier receipt preserved; the adapter always used the unchanged native constructor. This was our probe assumption, not a model defect.

## Completed execution and evaluation boundary

The reviewed GPU parity stage passed on one synthetic 1,200-residue sequence and 1,025 fixed GO classes split into native chunks of 1,024 and 1. Native dataset/collator features, forward logits and probabilities matched bitwise. Header removal, permutation and unrelated labels did not change predictions; reordered axes/caches and changed serialized cache bytes were rejected. Reusing the native sequence embedding across label chunks also matched bitwise. These are implementation checks, not biological accuracy results.

The complete pre-forward prediction scope is fixed to 547 original identities and 43,248 eligible nonobsolete GO 2023 terms, with 86,496 name/definition rows. Only 4,169 obsolete ontology nodes were excluded. The complete GO text cache contains 86,496 × 1,024 float32 values. Inference used predeclared text batch 8, label-pair chunk 1,024 and sequence batch 1. The scientific protocol was sealed before target forecasts. All 547 targets then completed in approximately 345 seconds, producing 23,656,656 protein/GO score rows. Independent admission checked the complete matrix against the frozen identity and GO axes. No target identity was removed or replaced.

The separate native evaluation is complete on the existing frozen 547-target NK/LK scope, seed 42 and unchanged comparison denominators. It retains all three GO aspects, 42 earlier outcomes and the 12 predeclared MFO paired contrasts against LocalPlus, DeepGO and the existing-annotation baseline. Molecular-function micro-Fmax is 0.4876/0.5313, versus DeepGO's 0.5589/0.5994 and the annotation control's 0.5216/0.5980. All four ordinary/IA intervals favor the annotation control; three favor DeepGO and its NK ordinary contrast crosses zero. All four LocalPlus intervals cross zero. No method, default, live graph or acceptance-policy promotion follows. These are exploratory, unadjusted, exposed-reference development results.

The existing NVIDIA L40S completed synthetic parity, text-cache generation and the frozen forecast without changing the model server or other services. After the GPU jobs exited, memory returned to its original 32,851 MiB used / 12,635 MiB free. Native CPU scoring and uncertainty are also complete. No further Brev compute is needed for this comparison.

The model card describes SwissProt/ProteInfer random 80/10/10 splits and GO 2019 descriptions; E5 was released in 2024. Target training-membership and homology overlap remain unaudited. Any ensuing comparison is **retrospective development transfer**, not an independent pre-2023 prospective result. A sequence-model gain would not establish a causal benefit of editing the Pharos graph.

## Additional reusable resource

[InterPro](https://doi.org/10.1093/nar/gkag1114) documents an official, no-key [MCP endpoint](https://www.ebi.ac.uk/interpro/mcp) for protein-domain and architecture inspection. Domain coordinates and sites could explain disagreements. However, [InterPro2GO](https://www.ebi.ac.uk/GOA/InterPro2GO) already enters GOA as IEA under `GO_REF:0000002`; adding those assertions again is not independent support. This endpoint was documented, not connected or called.

The PSB 2026 [GO-Agent paper](https://psb.stanford.edu/psb-online/proceedings/psb26/zhapa-camacho.pdf) is relevant to candidate-score refinement, but its repository currently lacks a code license and its live retrieval requires temporal qualification. We have not copied it or treated it as a qualified drop-in agent.

Stage receipts, preserved failures, source hashes, tokenizer pins and the reviewed adapter design are in ignored `runs/protnote_qualification_20261114/`. No training/test/reference dataset member was opened during artifact qualification. Existing app, model server, live graph and defaults remain unchanged.
