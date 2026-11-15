# InterPro sequence-context qualification — 14 November 2026

**Decision: use the official hosted MCP for bounded MD5 lookup and retain an offline source packet.** This adds inspectable sequence features and annotation lineage to BioGraph Steward; it is not a new biological classifier or an independent accuracy reference. No GPU, Java server, API key or new Python dependency is needed.

## Established implementation and actual gaps

The [current InterPro paper](https://doi.org/10.1093/nar/gkag1114) describes precomputed sequence matches and the Matches API. The [official Matches documentation](https://interproscan6.readthedocs.io/stable/matches_api/) explicitly supports batches of up to 100 sequence MD5s. For a Pharos sequence this avoids silently replacing it with today's UniProt accession sequence. A lookup miss remains unknown; a scan of a new sequence would be a separate operation and is not implemented here.

We inspected the [official MCP repository](https://github.com/ebi-pf-team/interpro-mcp/tree/ceb9b2177a5f8861634972fb8b2eacff64702890) and [Matches API source](https://github.com/ProteinsWebTeam/interpro-matches-api/tree/8a085fd6bbc1909ffa0decb275e2de9498962411). The MCP's small Apache-2.0 Python client is vendored unchanged, including license and attribution. Its JSON/SSE parser is reused. Its convenience `call_tool` drops the full JSON-RPC envelope and tool-error flag, so our thin recording transport preserves and validates those fields rather than treating a text response as success. The deployed server's repository commit is not attested by its version string.

The producer permits only `matchSequences` with known sequence MD5s. It never sends raw sequences, invokes `analyzeSequence`, submits a scan job, changes the graph or invokes a model. Offline views read byte-pinned files and make no retrieval calls. Explicit registration fixes packet order; no biological score selects a source packet.

## Source contract and reuse

Live qualification observed Matches API **0.6.0**, InterPro **111.0** (5 November 2026), Pfam **39.0**, and InterPro-N **105.0**. Every packet captures `/info` before and after retrieval and rejects a changed API/release/analysis inventory. Individual signatures retain their own library version and method origin; the overall release does not overwrite those values.

All native records, null entries, location fragments, discontinuity labels and optional residue sites are retained. Matching signature accessions are not deduplicated across methods or library versions. The three previously selected Pharos examples returned 206 native match records in total; these include sequence features and site rules, not 206 independent domains or experiments. A prior public example also contains the same Pfam accession from conventional Pfam and InterPro-N with different versions and coordinates. This demonstrates why method and version must remain visible.

The actual Matches 0.6 schema supplies neither `goXRefs` nor a `representative` flag. Those fields exist in richer InterProScan output documentation and must not be invented in this response. [InterPro2GO](https://www.ebi.ac.uk/GOA/InterPro2GO) creates electronic GO annotations with **IEA**, **GO_REF:0000002**, and an InterPro With/From identifier. Comparing those identifiers with existing native GOA rows can expose reused annotation lineage; it does not create another independent evidence vote. Source grouping, NOT qualifiers and protein forms must remain intact.

Pharos already exposes InterPro/Pfam/PROSITE/SMART/PANTHER cross-references. The useful increment is access to the exact retrieved sequence, native coordinates/sites and provenance, not claiming those resources are absent from Pharos. MD5 establishes sequence equality, not taxon, canonical-isoform identity or the sequence underlying an older graph. The captured Pharos fields do not supply a UniProt sequence version. Current context therefore stays separate from frozen historical prediction comparisons.

An optional explicit entry lookup retains native current-entry metadata or the API's HTTP 410 deletion history. Qualification found a Pharos cross-reference whose current InterPro entry reports deletion in 2022. That establishes an entry-lifecycle mismatch, not a replacement accession or proof that an older biological assertion was false. Current `is_llm`, `is_reviewed_llm` and `is_updated_llm` flags are retained as editorial-method provenance; neither generated text nor human review alone establishes an assertion's scientific truth. No automatic remapping is performed.

InterPro-N predictions remain visibly distinct. The current paper states that its weights and inference code are not publicly distributed, and that its training has not been updated for the latest signatures. A current resource release therefore does not establish a current model or independent experimental support.

## Data and software licenses

Apache-2.0 covers the reused MCP client software. [InterPro's data license](https://interpro-documentation.readthedocs.io/en/latest/license.html) covers downloadable InterPro, Pfam, PRINTS and SFLD data under CC0; other included tools and signature collections can have separate terms. [EMBL-EBI's terms](https://www.ebi.ac.uk/about/terms-of-use/) retain original-owner terms and request attribution. This is not a blanket license for every field from every member resource.

[UniProt's static provider README](https://ftp.uniprot.org/pub/databases/uniprot/README) explicitly places copyrightable database parts under CC BY 4.0. Sequence attribution names the UniProt Consortium and Pharos as the delivery route, with accession, date and sequence hash retained. Full Pharos envelopes contain mixed-source information and native source-license fields; no software license is asserted for the complete data packet. Every packet includes `DATA_TERMS.md`. Real native payloads remain ignored operator data, separate from distributable code and synthetic fixtures.

## Verification and boundaries

The source producer's synthetic checks cover exact accessions and isoform suffixes, normalized sequence hashes, MD5-only requests, raw JSON/SSE preservation, repeated signature methods, nulls, fragments, sites and optional entry-lifecycle/editorial metadata. They reject missing/duplicate/unrequested MD5s, tool errors, HTTP failures, release drift, mismatched entry identities and coordinates outside the exact sequence. Missing sequence, missing lookup and known empty match lists remain distinct. The unchanged parser also accepted the three previously captured native responses offline. Subsequent app integration and independent reader tests are recorded separately.

A fresh generic-producer capture completed for the fixed EGFR, CCNO and TAS1R2 examples and three explicitly selected entry records. The offline reader verified all three proteins and all 22 source files; before/after Matches metadata agreed. The native response contains 143, 23 and 40 match records respectively. The entry records preserve one HTTP 410 deletion history and, separately, one current entry marked LLM-generated but not reviewed. The first sandbox DNS failure was retained in a separate failed packet; the subsequent network-enabled acquisition succeeded without a proxy override, retry loop or source substitution. This confirms the acquisition and replay path, not biological correctness.

The same unchanged producer then captured the remaining 98 exact primary targets from the verified source-faithful workspace, without expanding to neighbors or fetching additional entry metadata. Together with the existing EGFR packet, all **99 primary targets** have verified sequence-context packets and native lookup matches. Their 8051 native match records include correlated signatures, site rules and sequence features. The new packet contains 111 byte-pinned source files; the offline reader accepted every exact target, and the original snapshot, graph, run manifest and qualified-workspace files remained byte-identical. This is primary-workspace context coverage, not whole-graph biological validation.

These checks establish source fidelity and safer interpretation. They do not establish scientific truth, whole-graph accuracy, prediction gains, historical record identity or improved human comprehension. The latter still requires the reviewer walkthrough.

Operator receipts and public-source pins are under ignored `runs/interpro_qualification_20261114/`; the maintained source-only code and tests contain no real reference cases.
