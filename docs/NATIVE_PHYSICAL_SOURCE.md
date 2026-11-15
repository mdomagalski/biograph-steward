# Native STRING physical source

The existing STRING priority option reads a physical overlay within a functional
network. STRING documents `typed` as a functional-network flavor; the separate
physical network has a different source scope. This increment preserves that
older option and adds an explicit **Native STRING physical associations** choice
in the same guided question form. It does not replace functional evidence or
introduce another score model.

Source semantics follow the [official STRING API documentation](https://string-db.org/help/api/)
and [STRING's primary network paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC11701646/).
A physical association can mean co-complex proximity; it does not establish
direct binding. Missing rows and unresolved identities remain unknown.

The delivered combined example is a separately named source-profile workspace.
It preserves its captured Pharos baseline and adds candidate source records.
The qualified retained reviewer graph remains a separate example with its
recorded identifier-currency decisions; no new baseline replacement or universal
biological pruning is implied.

## Prepare and attach offline

`string-physical-publish` consumes a sealed live Pharos snapshot and a JSON
source manifest with `release: "12.5"`, `canonical_release`, and four `files`
entries: `canonical`, `aliases`, `sequences`, `physical`. Each entry contains
`path`, expected `sha256` and the original `url`. Inputs are the complete human
STRING 12.5 aliases, protein sequences and physical-link bulk files, plus the
complete reviewed human canonical UniProt FASTA. No selected protein identifiers
are sent externally. No assay labels, reference outcomes or model predictions
are loaded. The production intake supports a declared cohort of **2–250 exact
canonical human accessions**; the delivered example has 99. Other cohorts use
the same source replay and identity checks, rather than a KRAS-specific rule.

```sh
python3 app.py string-physical-publish --snapshot ORIGINAL/snapshot.json --sources SOURCE_INPUTS.json --out PHYSICAL_PUBLICATION
python3 app.py biological-update --run ORIGINAL --string-physical-publication PHYSICAL_PUBLICATION --out NEW_WORKSPACE
```

To preserve an existing native-location workspace and add this different source
kind into a new output:

```sh
python3 app.py biological-update --run NATIVE_LOCATION_WORKSPACE --string-physical-publication PHYSICAL_PUBLICATION --append-sources --out NEW_COMBINED_WORKSPACE
```

Appending replays all source publications against the original Pharos snapshot.
It requires identical existing projections, rejects replacing an existing source
kind, and refuses to rebind previous extension review decisions to a new source
collection. Inputs remain unchanged. Original Pharos review events are preserved.
Old capture profiles with additional exact baseline-file bindings can still
require their original baseline; append does not relax those checks.

Every publication retains the complete source files, pair ledger, mappings,
source URLs, hashes, release and provider license attribution. Full source replay
uses the same readers as the public-reference comparison, now shared in the
standard-library core. It requires unique reciprocal literal `UniProt_AC` aliases
and identical complete canonical/STRING amino-acid sequences. These checks do
not establish historical Pharos sequence or assay-construct identity.

Native bulk scores remain integer **0–1000** in `source_scores_raw` and the
ledger's `native_physical_score`. The separately named `physical_score_0_to_1`
is exactly the native integer divided by 1000. This rescaling introduces no
fitted score or confidence threshold. All source-listed eligible pairs are
candidate annotations; provider file inclusion limits remain explicit.

## Ask and inspect

Open the new workspace, select **Native STRING physical associations**, choose
a protein and **Inspect candidates**. The answer uses saved source records and
makes no live STRING or model request. The scope trace includes the selected
protein's exact identity admission and complete pair-state counts. Missing
identity is explained in the answer; it is not reported as biological absence.

Click a cited source to inspect native scores, sequence mapping proof and the
preserved pair ledger. Functional association and qualified assay workflows
remain available separately. Accepted-only answers stay empty until an explicit
review decision is recorded. Source records are not independent study counts.

The equivalent saved question is:

```sh
python3 app.py question --run NEW_COMBINED_WORKSPACE --protein KRAS --template native_string_physical.v1 --relations interactions --view candidates --max-results 30 --max-paths 1 --out SAVED_QUESTION
```

The ordinary workspace export includes all complete source material for offline
replay. A focused question export contains its answer and cited evidence, with
references to the full source workspace; it has a narrower scope.
