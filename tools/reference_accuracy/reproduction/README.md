# Reproduce public reference preparation

These are the successful preparation bodies used for the MitoCarta and HOU
assessments, adapted only to take checkout, output and dependency paths as
arguments. They prepare source eligibility, identifier coverage and explicit
ontology crosswalks. They do not score reference outcomes, fit models, edit a
graph or contact external services.

`source_manifest.json` records both the historical successful operator hashes
and these parameterized sources. It also pins the source data. No author code,
gold cases or protein sequences are copied into this directory.

## Inputs

Use Python 3.12 and the matching private captured-workspace/source bundle. Restore
its `runs/source_faithful_workspace_20261113`,
`runs/crc_go_context_qualification_v3_20261112` and
`runs/crc_go_ontology_qualification_20261112` directories at their original
repository-relative locations. Their graph, snapshot, reviewed human registry,
GO ontology and complete GAF hashes are in the manifest. The registry loader and
native GO inspector replay their existing source contracts. A Git checkout alone
does not contain those separately distributed data artifacts.

Keep the following public author artifacts in a separate ordinary directory,
using these filenames and the checksums recorded in `source_manifest.json`:

- `human.mitocarta3.0.xls`: [MitoCarta author workbook](https://sites.broadinstitute.org/files/mitocarta/files/documents/human.mitocarta3.0.xls).
- `HOU_hou_testset.csv` and
  `HOU_hierarchical_label_set.zenodo18435290.yaml`: the `hou_testset.csv` and
  `hierarchical_label_set.yaml` files from [Zenodo 18435290](https://doi.org/10.5281/zenodo.18435290).
- `uniprot_subcell.txt`: [UniProt subcellular vocabulary](https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/docs/subcell.txt),
  specifically the pinned 2026_04 bytes. A later release is a different input.
- `HOU_1-generating_datasets.ipynb`: the [author notebook at revision b7855525](https://github.com/CellProfiling/seq2loc_benchmark/blob/b7855525e49dbb430a0b9d4b365cd84b387a8e6b/notebooks/build_dataset/1-generating_datasets.ipynb).
  Preparation only hashes it; the notebook is not executed.

The HOU dataset is CC BY 4.0 and its author code is MIT. MitoCarta's paper is
CC BY-NC 4.0; its freely downloadable workbook has no separate permissive license
identified in the inspected documentation. Keep reference files local and retain
their attribution and terms. The application license does not relicense them.

## Metadata preparation

Choose an empty work directory outside the input directories. Install PyYAML
6.0.3 in an ordinary optional research environment, or provide its module
directory with `--yaml-module-dir`. Native GO replay for scoring uses the
existing dependency-free saved-sidecar reader; it does not require a new model.

Run from the repository root, replacing the illustrative absolute paths:

```sh
python3 tools/reference_accuracy/reproduction/prepare_source_eligibility.py \
  --repo /path/to/biograph-steward-pharos \
  --artifacts-dir /path/to/public-reference-artifacts \
  --work-dir /path/to/new-reference-metadata

python3 tools/reference_accuracy/reproduction/prepare_hou_metadata.py \
  --repo /path/to/biograph-steward-pharos \
  --artifacts-dir /path/to/public-reference-artifacts \
  --work-dir /path/to/new-reference-metadata

shasum -a 256 /path/to/new-reference-metadata/HOU_source_crosswalk_before_label_join.json

python3 tools/reference_accuracy/reproduction/prepare_hou_scope.py \
  --repo /path/to/biograph-steward-pharos \
  --artifacts-dir /path/to/public-reference-artifacts \
  --work-dir /path/to/new-reference-metadata \
  --source-readiness-sha256 THE_HASH_PRINTED_ABOVE
```

Expected source-only results are 99 eligible primary proteins representing 98
genes; 218 mapped workspace proteins; 31 exact primary HOU test identifiers; 160
literal official GO crosswalk entries; and 107 mappings retained after the fixed
compartment-containment qualification. All 53 excluded coarse mappings are
preserved in the output. No selection depends on a localization outcome.

Parameterization was executed against the same captured inputs and reproduced
the original eligibility rows, identifier mask, all hierarchy maps, 160-entry
crosswalk, 107-entry qualified crosswalk and all excluded/root records exactly.

## Freeze and score

Review and freeze the generated metadata and the declared arms before joining
reference outcomes. `tools/reference_accuracy/mitocarta.py` and `hou.py` take
`--contract`, `--contract-sha256`, `--context` and `--out`; each writes its
prediction seal before reading cohort reference labels. MitoCarta's XLS reader
requires optional `xlrd==2.0.2`. Existing frozen contracts and original execution
receipts are retained in the private assessment bundle.

A new checkout changes absolute paths and producer identities, so newly generated
metadata hashes differ. Pin those actual files in a reviewed contract; do not
pretend they have the historical execution hashes. Replaying this already opened
reference remains development evaluation, not fresh independent confirmation.

MitoCarta zero/unlisted genes stay unknown. HOU's unlisted compartments stay
unknown: the HOU adapter reports recovery of positive reference labels and
unresolved extra outputs, not biological precision, specificity or whole-graph
accuracy. The unchanged author dictionary is a separate coarse control; its
generic membrane/cytoplasm/nucleus mappings never enter the qualified profile.

## PPI source preparation

`ppi_sources.json` supplies the complete positive/negative Parquet release
locators, human canonical FASTA pin and original Negatome manual archive-member
names, sizes, CRCs and hashes. The unknown SNOOPPI split and complete multi-GB
archive are not required. The capture used the established `remotezip` reader
for the two small manual members; preparation itself reads ordinary local
files and makes no network requests.

Use the separate Python 3.12.4 environment pinned in
`../requirements-public-gold.txt`. Arrow reads the author Parquet files and
Biopython reads the FASTA. No upstream curation code is copied or executed.
Place source files and declared protein-frame files inside the checkout's
ignored data area. Adapt `ppi_preparation.example.json` to those paths and
their actual hashes; it deliberately contains placeholders, not a hidden
list of scientific truth labels. Keep its configuration directory separate
from the new output directory:

```sh
python -m tools.reference_accuracy.ppi_references \
  --root /path/to/biograph-steward-pharos \
  --configuration /path/to/biograph-steward-pharos/runs/gold-plan/configuration.json \
  --configuration-sha256 ACTUAL_CONFIGURATION_SHA256 \
  --out /path/to/biograph-steward-pharos/runs/gold-prepared-v1
```

The producer requires pinned complete source files and known frame sizes. It
emits canonical-sequence gold, separate experimental-state sensitivity rows,
all base-pair candidates and a manual-assay panel with conflicting curations
left unknown. Output admission files were checked byte for byte against all
12 consumed files across the 218-, 3,172- and 20,412-protein frames. Altered
inputs during a read are rejected before a successful receipt is written.

The two offline scoring commands accept separately fixed contracts:

```sh
python -m tools.reference_accuracy.ppi_gold --help
python -m tools.reference_accuracy.ppi_network_types --help
```

The current-network scorer additionally seals implementation and native
parser/metric versions before execution. It admits only reciprocal explicit
`UniProt_AC` aliases with identical complete sequences. Absent numeric scores
remain unavailable. Its fixed presence classifier may output zero for a
nonedge, but never uses that nonedge as negative gold. It retains every
reference frame, source conflict, identity failure and study-omission result.

Human curator labels can share studies or source resources with the scored
network. Negatome assay records do not establish universal canonical binding
absence. Keep those reference limits with every score and retain upstream
licenses; the compilation archive's license does not automatically relicense
its constituent datasets.
