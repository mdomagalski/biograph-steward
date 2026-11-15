# Optional temporal-reference reproduction recipe

This folder retains **our executed reference-construction drivers**, their public
input pins and the unchanged native command sequence for the April–November
2026 human protein-function comparison. It is separate from the supported core
app ZIP. It contains no source annotations, reference cases, model weights,
credentials or upstream helper bodies.

`executed/` preserves the three original driver files byte for byte. They contain
the historical Brev paths and interpreter checks: their `main()` entry points
are execution records, **not portable defaults**. `guard.py` is a separate,
portable input-verification wrapper; it does not download data, run native
helpers or score predictions. The command recipe below changes paths only.

## Source and runtime contract

Inspect the sanitized manifest without opening any reference input:

```sh
python3 -m tools.contextual_combination.reference_recipe.guard describe
```

[sources.json](sources.json) records the public URLs, exact sizes/SHA-256 values,
GAF dates, ontology content versions, native helper revision/file pins, executed
driver hashes and the actual construction runtime. The recorded runtime is
Python 3.10.12; NumPy 1.26.4; SciPy 1.13.1; Pandas 2.2.3; Biopython 1.85;
NetworkX 3.4.2; obonet 1.0.0; Requests 2.32.3. This is the reference builder's
runtime, distinct from the app's optional Biopython 1.88 native-source inspector.
The guard does not install or certify a new runtime.

Obtain the separately licensed author source from
[democafa_package at 0ab84ed](https://github.com/FriedbergLab/democafa_package/tree/0ab84edbaddf5fef11125dc8adbd19167c3cc038),
including its license. The guard checks its relevant files against the recorded
hashes. The construction follows the
[CAFA_forever source at c3fd5b9](https://github.com/FriedbergLab/CAFA_forever/tree/c3fd5b9a5226348d88b9efadddb3214c803b80c4).
The optional adapters retain their stated licenses; the core application has a
separate MIT license. No upstream source is relicensed here.

Put the six `required_for_reference` input files in an ordinary local directory,
using the manifest's `local_name` values. Matching operator-supplied archived
files are accepted. The T0 SwissProt FASTA can be recovered with the existing
allowlisted `tools.deepgo_reference.archive.index` / `extract` helpers from the
pinned `uniprot_sprot-only2026_01.tar.gz`; extract only
`uniprot_sprot.fasta.gz`, not DAT/XML. The original acquisition snapshot records
that exact call and the publisher's archive size/MD5. The archive itself is an
optional additional guard check.

**T1 download URLs are mutable.** The accepted GOA source is exactly 11,061,135
bytes with GAF generation date `2026-11-04 15:05` and the manifest's SHA-256.
SwissProt T1 is the pinned 2026_04 FASTA. If a URL serves newer bytes, use a
matching archived copy; never substitute the current release. A matching archive
URL for those T1 bytes has not been independently established by this delivery
increment.

The T1 GO-basic URL names the August 5 archive, whose recorded content header is
**July 26, 2026**. The GAF names a later GO-plus release. These are different
source versions; the fixed-T0 sensitivity below is retained explicitly.

## Verify supplied bytes

From the repository root, with your actual ordinary paths:

```sh
python3 -m tools.contextual_combination.reference_recipe.guard verify \
  --sources-root /absolute/path/to/reference-sources \
  --author-root /absolute/path/to/democafa_package \
  --output /absolute/path/to/verified_reference_inputs.json \
  --acknowledge-reference-access
```

The acknowledgement is a local access-order contract: **hashing reference inputs
already accesses them**. It is not another permission requirement for the
authorized study. The guard fails on changed size, hash, date/header, helper
source or preserved driver bytes. It writes no partial success receipt and
never overwrites an existing receipt. Add `--include-acquisition-archive` only if
you also want to verify the large T0 archive. Its successful result means input
bytes were verified; it does not mean the pipeline or scientific comparison ran.

## Exact native construction sequence

Use the recorded runtime, with the pinned author checkout on `PYTHONPATH`.
`PYTHON` below means that interpreter; `T0` and `T1` are fresh output directories;
each input name refers to the corresponding verified manifest source. Keep logs
closed during forecasting: native warnings may contain reference GO terms.
The original `run_native` helper in `executed/native_window_build_v1.py` records
commands and writes such logs without displaying them.

1. For each epoch, reuse `human_fasta(source, destination)` from that same
   executed snapshot. It selects the exact SwissProt `OX=9606` description token
   and preserves accession/sequence bytes. It reads no DAT/XML payloads.
2. For each epoch run, without changing evidence groups or ontology rules:

   ```text
   PYTHON -m democafa.datacollection.filter_gaf
     -a EPOCH_GAF -q EPOCH_HUMAN_FASTA -o EPOCH/filtered.gaf.gz
   PYTHON -m democafa.datacollection.retrieve_terms
     --annot EPOCH/filtered.gaf.gz -sgc Experimental,IC,TAS
     -g EPOCH_OBO --tsv EPOCH/train_terms.tsv
   PYTHON -m democafa.datacollection.propagate_and_ia
     --terms EPOCH/train_terms.tsv --graph EPOCH_OBO
     --tsv_propagated EPOCH/train_terms_propagated.tsv --output_tsv EPOCH/IA.tsv
   ```

3. Preserve the native unchanged-sequence intersection and reference classifier:

   ```text
   PYTHON -m democafa.datacollection.compare_fasta
     T0/human_swissprot.fasta T1/human_swissprot.fasta COMMON/differences.fasta
   PYTHON -m democafa.groundtruth.classify_ground_truth
     --annot_known T0/train_terms_propagated.tsv
     --annot2 T1/train_terms_propagated.tsv
     --query_file COMMON/differences_common.fasta
     --graph T0_OBO --graph2 T1_OBO --out_prefix NATIVE/groundtruth.tsv
   ```

4. For the declared fixed-T0 sensitivity, rerun `retrieve_terms` on the **same
   filtered T1 GAF** using `T0_OBO`, propagate on `T0_OBO`, then run the same
   classifier with `--graph T0_OBO --graph2 T0_OBO`. Preserve both output sets.
   Comparative scoring uses the originally declared native terms-of-interest
   for both views, not whichever TOI gives a better result.

`epoch_commands()` and `run_native()` in the preserved build snapshot contain
the exact executed argument arrays. The fixed-T0 snapshot contains its exact
three additional calls. A portable caller can import these functions and set
the module's `PYTHON` variable to its recorded-runtime interpreter; there is no
need to rewrite the native methods. Preserve fresh output directories and all
failure logs. The snapshots also retain the invented admission/classification
fixture used before the real data were processed.

## Scope and validation limits

The recorded native target union is 3,300; the fixed-T0 subset is 1,690. These
are reproduction checks, **not target selection quotas**. Unexpected counts
require investigation of inputs/runtime; do not discard targets to match them.
The 1,584 cached / 1,716 fresh-or-changed forecast split additionally requires
the earlier forecasts' full-sequence hash receipt. It is separate from reference
construction and is not needed to rerun the native label pipeline itself.

Reference admission includes experimental codes **plus IC and TAS**; do not
describe all admitted rows as direct experimental observations. Native handling
of NOT, aliases, forms, extensions and taxon remains unchanged. Missing later
annotations are not negative biology. The human-only IA output is a construction
byproduct, not the official global CAFA leaderboard IA.

This delivery increment checks the portable guard on invented files and verifies
the preserved source snapshots. It does **not** rerun acquisition, the native
helpers or the full scientific study. Base-model inference, fit/final identity
boundaries and scoring remain documented in the parent
[contextual-combination workflow](../README.md) and its retained source manifests.
