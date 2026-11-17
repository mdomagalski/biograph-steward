# Portable native GO context and saved QC

The optional native GO inspector now has a **separate source-packet download**.
It makes the same preserved annotation and quality-check context portable
without changing the strict saved workspace or its ordinary ZIP export.
Fresh checkouts still contain neither the private workspace nor this packet.

## Choose the right download

| Download | What it contains |
|---|---|
| **Download run ZIP** | The complete selected saved workspace, including its graph, preserved baseline and decision package. |
| **Download summary, paths and evidence ZIP** | One saved answer and its supporting question-specific exports. |
| **Download native GO + QC packet** | The full supplied native GO/QC packet: 12 unchanged source files, plus `manifest.json` and `README.txt`. It contains neither the workspace nor the answer. |

The source download includes the preserved GAF's broader source scope, not just
the selected claim's displayed rows. Selection checks that the packet belongs
to this workspace; it does not filter the exported rows. Original source
headers, references, provenance and saved QC remain intact.

## Download and reopen

1. Select a GO claim in **Evidence & sources** and choose **Guide me through
   this source > Inspect preserved native GO annotations**.
2. When the source and saved QC verify, choose **Download native GO + QC
   packet**. Obtain the matching complete workspace ZIP separately.
3. Extract the native packet **outside** the saved workspace. Keep its
   `context/` and `qc/` directories separate and unchanged. Do not put the
   manifest, README or other files inside either strict source directory.
4. With software supporting this increment, set the two operator paths and
   start the app. For example:

```sh
export BIOGRAPH_GO_CONTEXT_DIR="/absolute/path/native_go_context_qc/context"
export BIOGRAPH_GO_QC_DIR="/absolute/path/native_go_context_qc/qc"
python3 app.py serve --runs-dir /absolute/path/runs --host 127.0.0.1 --port 8765 --no-browser
```

Open the matching saved workspace and inspect the GO claim again. The app
rechecks the original source frame, selected claim and saved QC. Both packets
are required for this download; missing configuration reports unavailable,
and invalid source bindings fail closed. The browser cannot select filesystem
paths. Downloads use the existing sign-in and origin checks.

This replay needs only Python/CPU. It does not fetch data, run a model, or
rerun Biopython, GO rules or the reasoner. The manifest lists every source
file's size and SHA256 and keeps the current graph, original baseline,
source-report content seals and file-byte hashes distinct.

## Verified with the preserved real packet

The [local replay receipt](evaluations/native_go_portable_export_20261113_summary.json)
records a 16,635,274-byte ZIP with 14 members. Its 12 source files reproduce
all 79,181,773 source bytes. After extraction outside the workspace, both NRAS
inspections returned exactly the same results as the original source packet:

| Selected claim | Preserved finding and interpretation boundary |
|---|---|
| **NRAS / GO:0005794 — Golgi apparatus** | One native row matches all five available Pharos fields. Its original `part_of` relation and the saved GORULE:0000061 normalization to `located_in` remain separately visible. Even this unique match does not establish historical row identity. |
| **NRAS / GO:0070062 — extracellular exosome** | One native row is present, but none matches all five available Pharos fields. The saved check reports an unsatisfiable context conjunction with no taxon problem; it does not declare the base annotation false. Other context alternatives can differ. |

All 406 original workspace/context/QC files remained unchanged. No graph edit,
review decision, new scientific label or biological outcome was created. This
receipt verifies local export, extraction and reader replay; it is not a new
hosted acceptance or browser walkthrough. Deployment availability follows the
software and source configuration supplied by the operator.

## Limits and source permissions

This packet makes existing source qualifications reproducible. It does not
prove whole-graph biological accuracy, source independence, prediction gains
or automatic biological pruning. Its QC findings concern separately preserved
native annotations and derivatives, not repairs of historical Pharos evidence.
Hashes detect changed bytes relative to a receipt; they do not authenticate
the publisher or establish scientific truth.

The packet is not a complete application backup and does not contain the
ontology, reasoner/runtime dependencies or application code. Preserve original
attribution and consult upstream terms before sharing; private access and the
project's MIT code license do not grant blanket redistribution rights over
source data. Original producer receipts can retain original operator paths;
the consumer does not follow those paths.

See the [workbench guide](NATIVE_GO_CONTEXT_WORKBENCH.md) for the source/QC
interpretation and [native GO methods](GO_NATIVE_QUALITY.md) for the earlier
executed pipeline and its scientific boundaries.
