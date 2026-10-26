# Checkpoint and historical replay — 2026-10-26

Commit `3f7c462d517ce5793c9af99fce65922a97f9159c`
(`feat: publish source-bound cohorts and qualified assay evidence`) preserves
the implementation used for the completed construction, reference interfaces
and assay publication. Its recorded local test baseline is **675 tests, 26
optional skips, no failures**. The assay publication was verified before the
commit; an independent replay from an exported copy of this commit also passed
on 2026-10-26 with Python **3.14.0**.

The verified assay publication is
`runs/lambourne_assay_evidence_20261025/`, with receipt content hash
`315f666f686736e86241dc802d68d09f69a35860d4d7ae91d053447e085e22e9`.
Replay reproduced 3,222 observations, 2,676 eligible observation edges and the
original 376 detected / 2,300 not-detected / 546 excluded accounting. This
checks preserved bytes and deterministic reconstruction. It neither opens a
fresh test panel nor establishes independent biological validity.

## Verify old publications with their recorded implementation

Assay and construction receipts bind implementation hashes. Subsequent
workbench integration legitimately changes some of those files, so an old
receipt can reject the current implementation. Preserve the receipt and use
the recorded code. Do not remove hash checks, edit historical source files or
reseal the old publication to make it pass.

From the repository root, export the checkpoint into a separate temporary
directory. This reads Git history without switching branches, modifying the
working tree, or creating a Git worktree:

```sh
BIOGRAPH_CHECKPOINT_DIR=$(mktemp -d /private/tmp/biograph-checkpoint-3f7c462-XXXXXX)
git archive 3f7c462d517ce5793c9af99fce65922a97f9159c | tar -x -C "$BIOGRAPH_CHECKPOINT_DIR"
(
  cd "$BIOGRAPH_CHECKPOINT_DIR"
  python3 -c 'import sys; assert sys.version_info[:3] == (3, 14, 0), sys.version'
  python3 scripts/publish_lambourne_evidence.py verify \
    --out /Users/42573/biograph-steward-pharos/runs/lambourne_assay_evidence_20261025
)
```

The absolute `--out` argument points to the existing publication; this
`verify` command reads it and does not publish or overwrite it. On another
computer, replace that path with the location of the transferred complete
publication. The saved `source/freeze` and `source/results` directories travel
inside it. The original external assessment directories are unnecessary for
this verifier. No model, GPU, network access or cloud account is used.

The code archive does **not** contain ignored `runs/` artifacts or an installed
Python runtime. Transfer the complete source publication separately and keep
its source license files. A Python version different from the recorded
3.14.0 is not a substitute for this exact replay.

The same archive can run a construction receipt verifier when that receipt's
implementation hashes match this checkpoint:

```sh
(
  cd "$BIOGRAPH_CHECKPOINT_DIR"
  python3 app.py construction-verify \
    --run /Users/42573/biograph-steward-pharos/runs/construction_crc_proteins_v3_20261023
)
```

Earlier construction versions may bind earlier implementation files. This
checkpoint must not be presented as a universal verifier for every archived
experiment. Retain each publication's receipt and the corresponding code
revision.

## Republish a construction using the current code

An offline republication is a separate operation. Run the current worktree's
command with the old, unchanged snapshot and a **new** directory outside the
old publication:

```sh
python3 app.py construct \
  --snapshot runs/construction_crc_proteins_v3_20261023/snapshot.json \
  --out runs/construction_crc_proteins_current_replay_20261026
```

Choose another unused output name if that directory already exists. The
current adapter replays the recorded source responses; it does not retrieve
new Pharos data. The new graph, answer and receipt describe the current
transformation of the same source snapshot. Preserve both publications and
their code versions. This is not a new biological evaluation or a refresh of
the upstream evidence. If recorded responses no longer fit the current
adapter, report the incompatibility instead of editing the old snapshot.

## Verification record

The exported checkpoint replay ran from
`/private/tmp/biograph-checkpoint-3f7c462-iht_2or1` and returned exit code 0,
empty stderr, the publication hash above, and the original population counts.
The construction command above also returned exit code 0 with
`construction_publication_verified` and `answer_status: answered`.
That temporary directory is a local verification artifact, not a required
distribution path. The reproducible identifier is the full Git commit and
the publication's preserved receipt.
