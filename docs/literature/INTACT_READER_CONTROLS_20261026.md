# Official-reader synthetic controls

These controls contain invented records only. No development or reserved IntAct
reference row was opened to design them. Their purpose is to test the installed
official evidence reader before source-fidelity projection; they do not measure
biological accuracy or independent interaction prediction.

The [fixture inventory](../../tests/fixtures/intact_reader/controls.json) binds each
isolated TSV by SHA-256, physical line count and raw column count. All ordinary
controls have the 42 columns required by the pinned
[MITAB 2.7 specification](https://github.com/HUPO-PSI/miTab/blob/301904541d716b767d02a67f3413907952844ea1/PSI-MITAB27Format.md).
The 15-, 41- and 43-column controls deliberately test the frozen protocol boundary.
The reader's support for other MITAB versions does not make those rows eligible.

Expected observations come from the format and PSI-JAMI 3.9.4 author source.
The exact sources JAR has SHA-256
`2ba7e3357a78f951eaa002d01b79c359ee2a79ffde7063b58981ebef984b7c99`;
its main Java files were independently compared with the pinned
[JAMI commit](https://github.com/MICommunity/psi-jami/tree/b66f63654d5878b918aad74af60054b1be0437a8).
The inventory binds both the original fidelity protocol and its mandatory
[expansion amendment](../evaluations/intact_fidelity_20261026_semantic_amendment.json).

The controls distinguish three things: raw source semantics, official-reader
objects and diagnostics, and the application's eligibility/projection duties.
They are not interchangeable. In particular:

- A negative cell `-` defaults to false by the format. An expansion cell `-`
  supplies no expansion annotation and leaves binary experimental origin unknown.
- Human participant taxonomy is separate from yeast, in-vitro or absent assay
  host context. Experimental bait/prey roles remain separate from biological roles
  and from side A/B.
- Missing source interactor type can produce a protein object through identifier
  inference. The explicit-type primary panel must still exclude that source row.
- Some multi-valued roles, types, detection methods, hosts and expansion terms are
  reduced by the evidence reader, with listener callbacks. Participant
  identification methods are retained as a collection. Raw cells and all
  callbacks must remain available; retained first values cannot imply lossless
  projection.
- Stoichiometric zero is meaningful in the specification. Missing `-` and zero
  remain distinct. A malformed numerical value can be recovered by the reader as
  zero with `onInvalidStoichiometry`; recovered zero is not an explicit source zero.

Source review identified another concrete limitation before reader execution.
`MitabLineParser.negative()` uses `Boolean.parseBoolean(safeFreeText())`.
Consequently a cell such as `maybe` becomes false without a syntax callback.
That behavior follows the released implementation but violates the format's
`true`/`false`/`-` value contract. The `negative_invalid_maybe` control therefore
expects the reader's false result **and** application quarantine. A minimal raw
literal check is needed; successful JAMI parsing alone is insufficient.

`reader_expected` contains conceptual projection aliases and callback method
counts. Tests must compare these with observations from the real Java reader
adapter. They must not implement a replacement biological parser. Minimum
callback counts permit additional legitimate diagnostics; generated log prose
is never the expected value. A null expected interaction count leaves malformed
line recovery observational while retaining the exact-column quarantine duty.
Expected observations in this inventory are source-derived controls, not a claim
that execution has passed.

The remaining controls exercise exact isoform retention, quoted reserved
characters and escaped quotes, malformed feature ranges, and missing optional
context. Invented source identifiers are visibly marked `EBI-SYNTHETIC-*`; neither
their identifiers nor the fabricated publication is a usable scientific citation.

The later [execution record](../evaluations/INTACT_READER_DEVELOPMENT_20261026.md)
reports the actual passing run of these unchanged controls and two separately
frozen recovery controls, including the preserved initial transport failure.
