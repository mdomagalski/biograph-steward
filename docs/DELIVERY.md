# Delivery and reviewer access

The designated real example is `crc_biological_workspace_20261112`: **99 primary
Pharos targets, 9,865 entities, 16,985 evidence records and 16,980 assertions**.
It combines the saved Pharos/CIViC workspace with source-qualified STRING,
MAP-IT and SIGNOR records. The optional private BioPlex context workspace is
not part of this delivery. The [five-minute script](DEMO_SCRIPT.md) uses the
supported guided workflow, not the experimental model planner.

## Two separate packages

`scripts/prepare_judge_demo.py` reuses the existing committed-runtime release
builder and verified graph/decision interface. It retrieves no data, runs no
model and creates no cloud resources. Its output contains:

| Package | Contents and purpose |
| --- | --- |
| `biograph_steward_software.zip` | Core MIT runtime, launch instructions and an offline synthetic example recipe. No retrieved source data, credentials or Git history. The full repository also supplies tests, optional evaluation tools and documentation. |
| `biograph_steward_crc_local.zip` | The same runtime plus the complete saved CRC workspace, cited BRAF answer, site/context answer and full graph/decision handoff. Prepared and verified locally; redistribution is **not cleared**. |
| `delivery.json` | Code revision, source packet identity, graph counts, saved-answer hashes and archive byte inventories/checksums. It records source preservation, not scientific validation or data permission. |

The data package preserves these relationships:

- `runs/crc_judge_demo/` is the complete source workspace the app opens.
- `runs/question_judge_focus/` is a saved candidate answer about BRAF. Its diagram
  is a question-specific selection, not the whole graph.
- `handoff/retained_graph.json` retains the entire graph. Every original edge has
  an **abstain** disposition; none is silently accepted or pruned.
- `handoff/edge_dispositions.jsonl` accounts for every original evidence record.
- `handoff/baseline_packet/source/graph.json` is the original source graph;
  surrounding source files preserve replay and provenance.

The retained graph carries retention metadata. Its nodes, edges and assertions
match the reopened workspace; its entire JSON need not be byte-identical to the
original graph. The original source files remain byte-preserved.

## Build from an authorized saved workspace

Commit the intended runtime first: the software archive is built from Git,
not uncommitted working files. Use new output directories:

```sh
python3 app.py gold-export --run runs/crc_biological_workspace_20261112 \
  --out runs/my_crc_source_packet
python3 scripts/prepare_judge_demo.py --packet runs/my_crc_source_packet \
  --focus UniProtKB:P15056 --site Ser614 --ref HEAD \
  --out runs/my_crc_delivery
```

Preparation verifies the packet, writes all-abstain decisions, reopens the
complete source workspace, extracts each ZIP and checks its file inventory.
The final release check must also launch the extracted committed app and replay
its answer/site API. Synthetic builder tests do not establish compatibility
with an arbitrary older `--ref`.

The [November 12 v2 delivery check](evaluations/DELIVERY_READINESS_20261112.md)
completed this actual extracted-app replay for the full CRC graph and separate
software archive. Its aggregate summary binds the code revision and archive
checksums; locally generated archives are not stored in Git.

Unzip an authorized real package, open a terminal in that directory and run:

```sh
python3 app.py serve --runs-dir runs --host 127.0.0.1 --port 8765 --no-browser
```

Open `http://127.0.0.1:8765/?run=crc_judge_demo&question=question_judge_focus`.
The software-only package instead starts with:

```sh
python3 app.py demo --out runs/synthetic_demo
python3 app.py serve --runs-dir runs --host 127.0.0.1 --port 8765 --no-browser
```

Open `http://127.0.0.1:8765/?run=synthetic_demo`. Python 3.10+ is sufficient;
the core flow needs no package installation, model, GPU, account or cloud.
Keep the terminal running; Ctrl+C stops the local server.

## Real source availability and permissions

The full CRC graph contains **1,588 KEGG pathway membership records**. Pharos
provider metadata does not supply a blanket data redistribution license.
[KEGG's published terms](https://www.kegg.jp/kegg/legal.html) distinguish academic
use, service provision and non-academic licensing. Consequently, local package
verification does not authorize a public upload or controlled judge transfer.
Software MIT licensing does not relicense upstream data. Preserve the native
terms and attribution and resolve any applicable permissions before sharing
the real packet or hosting those data for others.

The independently usable route is the software-only archive/repository and
bounded retrieval by the user. In **Data & saved work → Pharos disease cohort**,
search `colorectal`, choose the exact returned disease and retrieve a bounded
cohort. Inspect coverage and upstream terms. This produces a new snapshot; it
does not reproduce the frozen graph byte-for-byte or automatically include
the separately qualified extension sources. See [scoped retrieval](SCOPED_RETRIEVAL.md)
and [source enrichment](BIOLOGICAL_SOURCE_UPDATE.md).

The [source repository](https://github.com/mdomagalski/biograph-steward) is private
during preparation and is intended to become public at final submission
(planned for November 17, 2026). Repository visibility, source permission and
the actual organizer handoff remain separate delivery actions. Do not claim an
official score while the organizer's final scoring contract is unavailable.
