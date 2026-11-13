# Historical WikiPathways source-content verification

This optional producer verifies source attribution and literal native content.
It does **not** create a biological gold standard, infer absent biology, prune
the graph, or run a prediction model. Original evidence rows, current-view
decisions, scientific reviews and frozen evaluation samples remain unchanged.

## Established upstream behavior

An important earlier assumption was incorrect: the `Version` XML attribute in
legacy GPML2013a is **not** the MediaWiki pathway revision. The released author
[GPML2013a schema](https://github.com/wikipathways/mediawiki-extensions-WikiPathways/blob/f9fbcb62995c3958154b129478342d428a499331/bin/GPML2013a.xsd)
describes it as optional GenMAPP export metadata. Empty or date-valued attributes
therefore do not disprove an exact historical source binding.

The official legacy
[BatchDownloader](https://github.com/wikipathways/mediawiki-extensions-WikiPathways/blob/f9fbcb62995c3958154b129478342d428a499331/src/BatchDownloader.php)
constructs an archive member from `getFilePrefix()`, `getIdentifier()` and
`getActiveRevision()`. For example, `Hs_Cell_Cycle_WP179_105448.gpml` binds
`WP179_r105448`. The monthly official
[release producer](https://github.com/wikipathways/scripts/blob/bde9de32e80fae48a65023eeef815d7d39d31676/data-release/wikipathways-data-release)
uses that exporter. Modern filenames ending in a valid `YYYYMMDD` date are
explicitly rejected as a legacy revision proof. Current-release content can be
inspected separately with `inspect_fields`; its XML `Version` is preserved as
author metadata without manufacturing an exact historical binding.

The public [human GPML archive concept](https://zenodo.org/records/7718815)
provides dated native ZIPs and publisher MD5 checksums, byte sizes, DOI and CC0
terms. The producer checks the exact file entry in captured native Zenodo
metadata and its actual MD5, size and SHA256. Multiple different model bytes
under one requested full revision cause abstention. A nearby date, a latest
redirect, a label match or an unversioned WP identifier never supplies an exact
historical model.

The publisher archive license and native author metadata are separate layers.
Some historical models retain `License="CC BY 2.0"` or other Creative Commons
strings, and others omit that attribute. Every literal value is preserved;
the Zenodo CC0 declaration is not used to erase native attribution or silently
clear all downstream redistribution obligations.

## Native content and identifier scope

The reviewed author GPML2013a XSD is executed with optional `lxml`; this is a
format check, not a biological curation algorithm. The core application only
uses the Python standard library for literal XML parsing. It preserves native
DataNodes, groups, attached states, xrefs, comments, BioPAX blocks and citation
owners. A publication attached to the whole pathway is separate from a native
node-attached reference. Neither automatically establishes paper support for a
member, direct binding or causation. The complete raw GPML remains authoritative.

The author's
[GMT generator](https://github.com/wikipathways/java-bots/blob/750c719e8427c5eb7aba8939ab883ce57bbdb4f9/org.wikipathways.bots/src/org/wikipathways/bots/utils/GenerateGMT.java)
reads native DataNode xrefs and uses BridgeDb mapping. The inspected code does
not justify custom family/group/linked-pathway expansion here. The exact
historical BridgeDb mapping release has not been recovered. Consequently,
failure of our deliberately narrower literal match remains unresolved.

Native database labels follow the captured official
[BridgeDb datasource declarations](https://bridgedb.github.io/datasources/datasources.tsv)
and [system-code documentation](https://www.bridgedb.org/pages/system-codes.html).
In particular, `HGNC`/`H` is the approved-symbol namespace; `HGNC Accession
number`/`Hac` is the accession namespace. An identifier that merely resembles an
Ensembl or gene ID under another database label is not repaired by its shape.

An exact native UniProt xref on a `Protein`/`GeneProduct` node yields
`explicitly_encoded_protein_xref`. Explicit gene xrefs can yield
`compatible_gene_level_xref` only through the existing frozen human
UniProt/HGNC/NCBI Gene agreement rule. This is a **gene-to-protein relationship,
not identity**, and does not establish historical identifier equivalence,
isoform/construct identity or protein-specific measurement. Matching references
on other entity types are exposed as diagnostics. Nonhuman/unvalidated models,
missing models, unknown identifiers, groups, families and linked pathways remain
`unresolved`; no source absence becomes a biological negative.

## Reproducible producer and portable consumer

The offline CLI requires explicit SHA256 pins for the sealed source inventory,
sealed archive-input manifest and existing human registry seal:

```sh
python tools/pathway_history/verify.py \
  --inventory /absolute/path/inventory.json --inventory-sha256 SHA256 \
  --sources /absolute/path/source_inputs.json --sources-sha256 SHA256 \
  --registry /absolute/path/registry --registry-sha256 REGISTRY_SEAL \
  --out /absolute/path/new_immutable_output
```

Only the optional producer requires `lxml` (the recorded execution used 6.1.1).
Core imports do not depend on `tools`, `lxml`, Pandas or an upstream full package.
No network requests or model calls occur during verification or consumption.

The packet contains:

- `historical_verification.json`: sealed input/method/output inventory, counts,
  cross-tabs, limitations, author-schema execution receipt and shared helper pins.
- `resource_coverage.jsonl`: every requested full source version, including
  missing/conflicting states and exact native archive/member proof.
- `native_models.jsonl` and `models/*.gpml`: literal parser output and raw native
  content for every verified model.
- `claim_assessments.jsonl`: every unique original subject/full-version
  connection, its literal match/unknown assessment and exact source/registry
  locators. `edge_assessments.jsonl` separately preserves every native row.
- `archives/`, `source_metadata/`, `source_documents/`: complete native ZIPs,
  publisher checksum/DOI/license metadata, reviewed exporter/schema/namespace
  documents and available capture receipts.
- `registry/`: both raw human registry tables and their original manifest.
- `inventory.json` and `source_inputs.json`: original sealed acquisition inputs.
  Their original acquisition paths are provenance; portable proof locations are
  explicitly recorded in the successful packet's own report/candidates.

```python
from biograph_steward.wiki_history import load_history_packet, query_history

packet = load_history_packet("/absolute/path/packet", expected_content_sha256=TRUSTED_SEAL)
proof = query_history(packet, "UniProtKB:P27986", "WP75_r105842")
```

The caller supplies the trusted report seal; self-consistent checksums alone
are not publisher authentication. The loader checks all portable proof bytes
and loads the original registry. A query checks selected ZIP/member bytes,
replays literal GPML and the exact registry bridge, and compares the resulting
status/bridge with the stored assessment. Its schema field explicitly reports
`executed=False`, `reexecuted=False` and attaches the byte-bound **producer**
validation receipt. It never claims the core consumer ran XML Schema validation.

## November 2026 scoped result

The original source contains 308 exact requested versions, 2,004 distinct
subject/version connections and 3,492 native rows. Eight examined official
archives establish **253/308 versions (82.1%)**, covering **1,621/2,004
connections** and **2,764/3,492 rows**. All 253 models pass the actual released
author XSD; the 761 archive occurrences have no conflicting model bytes. The
remaining 55 versions are unresolved, not failed biology. The preserved v1 run
and later fully portable v2 run are separate immutable artifacts.

The portable v2 has 59 literal protein-encoded, 996 gene-compatible and 949
unresolved **connections**. Repeated rows have a separate denominator: 64, 1,207
and 2,221 respectively. The source-encoding/current-GMT cross-tab is:

| Current-GMT view | Protein encoded | Gene compatible | Unresolved |
| --- | ---: | ---: | ---: |
| Keep: unique connections | 59 | 973 | 257 |
| Prune from current view: unique connections | 0 | 5 | 680 |
| Abstain: unique connections | 0 | 18 | 12 |
| Keep: native rows | 64 | 1,179 | 315 |
| Prune from current view: native rows | 0 | 5 | 1,887 |
| Abstain: native rows | 0 | 23 | 19 |

These are dependent source-content observations, **not independent scientific
accuracy**. They cannot be pooled with the frozen probability sample, treated
as 1,892 biologically false rows, or used as evidence of prediction improvement.

Five current-GMT-excluded connections are explicitly gene-encoded in exact
legacy models: PIK3R1/WP75_r105842, PIK3CA/WP75_r105842,
PIK3CA/WP2203_r105841, MAP2K7/WP3853_r105575 and PIK3R1/WP4255_r105677.
The same November 10 current native parents lack direct qualified target xrefs.
WP75 instead links PI3K family WP5472 and PI3K-Akt WP4172; those separate modules
each explicitly encode PIK3CA and PIK3R1. The current models therefore preserve
additional abstraction context. This is not proof of a GMT serialization bug,
nor a justification for silently inheriting module membership into a parent.
Historical positives should remain visible alongside current-source uncertainty.

## Source-faithful default decision ledger

`prepare_decisions.py` provides a separate, conservative Gold qualification:

```sh
python tools/pathway_history/prepare_decisions.py \
  --packet /absolute/path/original_Gold_packet \
  --history /absolute/path/portable_history_packet \
  --history-content-sha256 TRUSTED_HISTORY_SEAL \
  --out /absolute/path/new_immutable_output
```

The exact original graph file must match the historical packet. Every native
positive unique connection is replayed through the core archive/GPML/registry
consumer before its original Wiki rows receive `keep`. Every unresolved Wiki
row and every other evidence family receive `abstain`. Native absence **never**
produces `prune`. The complete Gold saver/loader preserves original source,
reviews, all nodes and all evidence rows. `keep` establishes source-content
eligibility, not scientific acceptance or protein-form identity. Source-supported
answer gating is separate from retaining unknown context in the workspace.

The source-faithful v1 run replayed all 1,055 native-positive connections,
marked 1,271 rows `keep`, zero `prune` and 15,714 `abstain`, retaining all 16,985
original edges. It does not change the frozen current-GMT ablation. The output
contains portable retained Gold plus pinned history metadata; the complete
native archives and registry proof remain in the separately portable history
packet, explicitly identified by its trusted content seal.

The next defensible evidence step is recovery of specific missing historical
models or their actual identifier mapping artifacts, and separate qualified
scientific/prediction assessment. Neither flattening family context nor adding
another aggregator resolves independence.
