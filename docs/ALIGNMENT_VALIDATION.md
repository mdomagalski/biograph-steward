# Assertion and review workflow validation — October 14, 2026

This increment advances BioGraph Steward from a source-record inspector to a qualified-assertion workbench. It does not implement biological evidence verification, a natural-language planner, external enrichment or model training.

## Verified behavior

- A record naming another disease attaches to a separate local disease node with its actual label. It cannot be counted as evidence for the selected disease.
- A missing disease context creates an input-quarantine record, preserving the original record without fabricating an association.
- Multiple supporting records can belong to one assertion. Qualifiers and relation kind distinguish claims; changes to supporting records change the evidence revision.
- Structural checks do not accept assertions. A reviewer, reason and valid lifecycle transition are required. Membership alone and assertions without structurally usable evidence cannot be accepted.
- Every saved decision creates a new run. The original snapshot and run files remain unchanged. Old-snapshot, unknown-revision, invalid-sequence and invalid-transition events are rejected.
- The accepted view hides candidate/provisional/rejected assertions. Inspection mode retains them. Graph lines open the complete assertion passport, including all contributing records.
- A saved run URL reopens review history. CLI replay with `--reviews` preserves the same derived graph.
- Review decisions do not become experimental positive or negative labels.

## Automated checks

**69 tests passed**, covering the original connector, snapshots, normalization, HTTP endpoints, benchmark preparation and the new assertion/review behavior. Run from the repository root:

```bash
NO_PROXY=127.0.0.1,localhost,::1 no_proxy=127.0.0.1,localhost,::1 \
  python3 -m unittest discover -s tests -v
```

Loopback socket permission was needed for the HTTP tests. Python emitted resource-cleanup warnings from mocked HTTP error fixtures; the suite completed successfully. The UI JavaScript also passed Node syntax checking.

## Browser verification

Using the local app and explicitly synthetic data:

1. Built a demo; the default accepted view contained zero assertions.
2. Switched to inspection and opened the DEMO_P1 disease assertion; its passport showed both synthetic source records.
3. Saved a test acceptance with a reviewer explicitly identified as software QA and a reason stating no biological validation.
4. Switched to accepted view; only that assertion appeared.
5. Reopened the saved run URL and verified that the acceptance and review history persisted.

The local screenshot and test runs remain under ignored `runs/`; they are not biomedical evaluation data. No live biological assertion was accepted during software testing.

## Replay of the existing live snapshot

The saved 99-protein colorectal adenocarcinoma snapshot was replayed locally into `runs/crc_aligned_20261014/`. Its raw snapshot bytes are unchanged. The new graph contains:

- 97 association records and 97 pairs for the exact selected disease;
- 3 association records for other disease labels, preserved separately;
- 2 retrieved proteins without exact selected-disease evidence;
- 906 candidate assertions and zero human-accepted assertions.

The previous v1 audit counted all 100 association records under the selected disease before flagging three context mismatches. Audit v2 fixes the underlying relationship mapping and reports those three separately. The original audit and snapshot remain available.

## Remaining limitations

Pharos retrieval is still capped, and the larger pathway audit is not yet imported into the app. Non-Reactome pathway mappings, study-level evidence deduplication, variant/therapy retrieval, formal schema validation, authenticated multi-user review, update reconciliation and experimental evaluation remain future work. Local review files are inspectable records, not signed attestations. Human acceptance does not establish scientific truth.
