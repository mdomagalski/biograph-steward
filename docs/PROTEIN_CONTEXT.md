# Inspect protein sequence and domain context

In **Evidence & sources**, choose a saved claim and click **Guide me through
this source**. If an exact protein endpoint has registered source context,
expand **Protein sequence & domain context**, choose the protein and click
**Inspect saved domains and sites**. The initial section stays collapsed.
Inspection reads saved files; no Brev instance, model call or new source request
is needed.

A domain match places a sequence region against a source signature or model.
It supplies biological context, not an experiment confirming a function or
interaction. InterPro integrates several member databases; multiple signatures
can describe overlapping parts of the same protein. The view preserves every
method and library version rather than treating those matches as independent
votes. InterPro-N predictions remain distinguishable from conventional matches.

The view includes:

- Exact Pharos sequence length, hashes, retrieval time and source database label.
  Coordinates are 1-based and inclusive for this sequence. Split fragments stay
  split; their enclosing span is not substituted for the actual matched regions.
- Native signature positions and optional residue-site records. Missing sites,
  missing sequence and a missing precomputed lookup remain distinct unknowns.
- Existing Pharos InterPro/Pfam/PROSITE/SMART/PANTHER references and sequence
  annotation records. Their presence is recovered source context, not novel evidence.
- Currency and editorial-method flags for explicitly inspected InterPro entries.
  A retired identifier is preserved without inferring a replacement or pruning
  the graph. Missing editorial flags mean unknown review status.
- Native GOA mapping lineage when the existing verified GOA inspector covers the
  selected GO claim. NOT qualifiers, protein forms, references and With/From
  OR alternatives containing AND groups remain intact. Shared identifiers on
  other evidence codes are distinguished from an IEA/InterPro2GO reference chain.

The source sequence can differ from that underlying an older graph or today's
external accession page. Sequence equality does not prove taxon or canonical
isoform identity. This context does not establish historical record identity,
independent evidence, biological truth or prediction gains. See the
[source qualification](evaluations/INTERPRO_QUALIFICATION_20261114.md) and
[fixed example assessment](evaluations/PROTEIN_CONTEXT_20261114.md).

## Capture and register a bounded packet

From the repository root, use Python 3.10 or newer and a new direct child of
`runs/`. This requests current public Pharos context and sends only sequence
MD5s to the official InterPro MCP's precomputed `matchSequences` tool. It never
submits a scan job or changes the graph. No API key or paid compute is required.

```sh
python3 -m biograph_steward.protein_context_source \
  --protein P00533 --protein P22674 --protein Q8TE23 \
  --entry IPR028864 --entry IPR049328 --entry IPR050122 \
  --output runs/my_protein_context --register
```

Repeat `--protein` for up to 100 exact accessions. Preserve any isoform suffix;
an absent or differently resolved protein fails explicitly. `--entry` optionally
captures native lifecycle/editorial metadata for explicitly named InterPro
entries; it does not scan every linked entry. Without `--register`, acquisition
leaves the app's context selection unchanged.

`protein_context.json` pins native Pharos envelopes, InterPro JSON-RPC and raw
responses, tool schema, before/after release metadata, source requests and data
terms. Failed acquisitions retain their failure receipt and never become usable
context. `protein_context_index.json` explicitly orders registered packets; the
first covering an exact protein is used. A changed pin fails verification.

To move this optional inspector to another installation, transfer its registered
packet folders and index into that installation's runs directory, keeping the
folder names and bytes intact. Ordinary graph exports do not implicitly include
these separately acquired current-context packets. Review each packet's
`DATA_TERMS.md` and original-provider conditions before redistribution. Real
source packets stay outside Git; the included software license does not license
all aggregated source data.
