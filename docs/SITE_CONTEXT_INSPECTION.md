# Inspect reported sites and experimental context

The **Sites & context** view separates a source-reported phosphate change from
the source's net effect on the target protein. It reads the saved SIGNOR layer;
it retrieves no new evidence, calls no model and changes no graph or review
decision. Original records, citations and local review states remain available.

This follows the distinction described by [SIGNOR 4.0 / PhosphoSIGNOR](https://doi.org/10.1093/nar/gkaf1237).
Our view is deliberately source-scoped: it does not infer a causal effect of
phosphate occupancy from the source's net protein effect. A phosphorylation
record can report inhibition of the protein while still describing phosphate
addition. Dephosphorylation describes phosphate removal; its net protein effect
is displayed separately.

## In the workbench

Open a workspace with a verified SIGNOR extension, then choose **Evidence &
sources → Regulation and experimental context**. Set **View** to **Sites &
context**, choose a cohort protein and direction, and optionally enter one
reported position such as `S614` or `Ser614`.

The **Inhibitory BRAF phosphorylation** example uses the saved BRAF/Ser614
record. It shows phosphate addition beside the source-reported reduction in
protein activity. This is an interpretation of preserved source fields, not a
new activity measurement.

Context dropdowns show saved cell/tissue labels while matching their exact
source tokens. **Context availability** means:

- **All:** retain records with and without context.
- **Reported:** either cell or tissue context is supplied.
- **Unreported:** both fields are blank.

Missing context stays unknown. No ontology expansion or colorectal-cancer
applicability is inferred. Available choices and scope counts precede filtering
and pagination. The download button saves the displayed answer page.

## CLI and API

The existing example workspace must be supplied separately; source data are not
bundled with the software. Choose a new output directory:

```sh
python -m biograph_steward regulatory-sites \
  --run runs/crc_biological_workspace_20261112 \
  --protein UniProtKB:P15056 --direction outgoing --site Ser614 \
  --context-reporting all --out runs/my_braf_site_context
```

This writes `answer.json`. Optional `--cell-context` and `--tissue-context`
arguments accept one exact saved token each. CLI output uses the first page;
the API supports explicit pagination. Through the workspace's normal
authenticated, same-origin API, send `POST /api/regulatory-sites` with:

```json
{
  "run_id": "crc_biological_workspace_20261112",
  "protein": "UniProtKB:P15056",
  "direction": "outgoing",
  "site": "S614",
  "cell_context": "",
  "tissue_context": "",
  "context_reporting": "all",
  "offset": 0,
  "limit": 25
}
```

The response preserves source bindings and adds `site_view` to each record.
`summary.available_filters` supplies the position and context choices;
`summary.next_offset` identifies the next page. The endpoint accepts exact
primary cohort protein identifiers and page sizes from 1 to 25.

## Interpretation and verification

Single explicit residue positions are displayed as **source-reported**.
Histidine and other recognized amino-acid positions are retained. Multisite,
unlocalized or unrecognized descriptions remain unresolved; non-phosphate
mechanisms receive no phosphate projection. Nothing is silently split or
converted into a canonical site.

Display identities are scoped to the source observation. They are not new
phosphosite entities in the saved graph. A valid coordinate label, matching
protein identifier or source `DIRECT` flag does not verify an experimental
proteoform, purified catalysis or biological truth. The experimental organism
also remains distinct from SIGNOR's human participant identifiers.

Synthetic tests cover these distinctions, exact filters, pagination, source
tampering and absence of retrieval/mutation. A saved-workspace check recovered
the BRAF Ser614 example with unchanged graph bytes. These checks establish
source-preserving behavior, not a new biological improvement result. See the
[source enrichment](BIOLOGICAL_SOURCE_UPDATE.md) and
[curated-signature comparison](evaluations/CURATED_SIGNATURE_RECOVERY_20261112.md)
for their separate scopes and evidence limits.
