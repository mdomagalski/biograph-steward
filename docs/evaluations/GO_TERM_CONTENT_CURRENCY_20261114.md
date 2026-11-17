# Historical and current GO term-content audit

This read-only audit compared the 36 displayed candidates from all six saved
historical queries, plus three post-outcome worked examples. It did not change
the frozen benchmark, predictions, current annotations, display index or notes.
The compared ontologies are the pinned **2023-01-01 go-basic OBO** and the
matching **2026-07-26 GO OBOGraphs JSON**.

| Scope | Literal name/definition changes | Other recorded differences |
|---|---|---|
| 36 displayed rows; 27 unique IDs | Four currently obsolete IDs gain obsolete markers; the other 32 rows have identical name and definition text | Four active IDs have different explicit parent records |
| Three worked examples | C1QBP / GO:0062153 changes active label and definition; CDK7 / GO:0001109 and ELOF1 / GO:0060090 retain both | C1QBP parent and synonym scopes differ; ELOF1 loses two related synonyms |

The four obsolete displayed IDs are `GO:0097159`, `GO:0005615`, `GO:0031323` and
`GO:1901564`. Active displayed IDs with different explicit `is_a`/`part_of`
records are `GO:1901363`, `GO:0019222`, `GO:0019538` and `GO:0051246`.
Matching labels/definitions do not establish complete semantic equivalence, and
hierarchies from the two versions must remain separate.

## C1QBP qualification

`GO:0062153` remains an active ID in both versions. The frozen January 2023 file
names it **C5-methylcytidine-containing RNA binding**; the July 2026 file names it
**C5-methylcytidine-containing RNA reader activity**. These snapshots do not date
the edit. The current definition adds an explicit protein-adaptor role. Its old
binding label is now a **RELATED**
synonym, not an EXACT synonym. The explicit parent changes from RNA binding
(`GO:0003723`) to protein–RNA adaptor activity (`GO:0140517`). Literal source
definitions, synonyms, lifecycle fields and parent records are retained in the
audit artifact rather than replaced with a generated semantic interpretation.

The [official GO curator discussion](https://github.com/geneontology/go-ontology/issues/25788)
requested this label/definition/parentage update in July 2023 and also discussed
an existing annotation whose demethylase role did not establish adaptor activity.
This is a documented curation issue. The discussion dates do not independently
establish the exact edit commit or first released version; it would be incorrect
to call reader activity a concept newly introduced in 2026.

The historical score should therefore retain its **January 2023 interpretation**.
The current C1QBP record can be shown as a separately qualified, post-outcome
source example. It must not imply that the historical model forecast the full
current reader/adaptor definition. No new predictive-gain claim follows from
matching the unchanged ID.

## Reused methods and evidence

The audit reused the CAFA authors' pinned OBO stanza reader, collecting metadata
instead of constructing its unused dense graph, and the project's existing
current OBOGraphs/lifecycle loader. Original stanzas and native current nodes
were retained. [ROBOT diff](https://robot.obolibrary.org/diff) and
[OAK diff](https://incatools.github.io/ontology-access-kit/cli.html#diff) were
checked as established comparison tools; no dependency installation or complete
OWL equivalence test was needed or claimed. Different source serializations also
limit what can be inferred from explicit parent-record differences.

The [GO overview](https://geneontology.org/docs/ontology-documentation/) documents
separate IDs, labels, definitions and synonym scopes, while the
[GO 2026 paper](https://academic.oup.com/nar/article/54/D1/D1779/8383826) describes
substantial release-tracked refactoring. These support recording versioned
content and lifecycle separately rather than treating an active ID as proof of
an unchanged definition or a correct biological annotation.

Local audit: `runs/agent_contribution_20261113/go_content_audit_v1/`.
The report covers 39 rows and 30 unique terms; it contains literal source
content and flags, with no semantic-equivalence or biological-falsehood verdict.
The [sanitized public summary](go_term_content_currency_20261114_summary.json)
provides aggregate counts, versioned term content and stanza/node provenance;
it excludes protein-to-future-outcome pairs, forecast scores and raw annotation
bodies. Historical stanza UTF-8 hashes and canonical JSON hashes are explicitly
distinguished.

- Historical ontology SHA256: `0c0062efbb1b199a6a54e62c0c48ff0038d39173aecc7edfab66a20090d5ec2d`
- Current ontology SHA256: `86c2e58bd639053cabfafd831afc4049e3da8457cb900879262d164a13ba0273`
- Report content seal: `d4cc906b419fee82a51192a6e845dd70efe28766221eba890e8c8fce75cb7530`
