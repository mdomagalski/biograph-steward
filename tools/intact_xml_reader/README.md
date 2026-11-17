# Isolated official PSI-MI XML reader

This developer helper projects local PSI-MI XML through
`psidev.psi.mi.jami:jami-xml:3.9.4` and its declared `jami-core:3.9.4`
dependency. It is separate from the frozen MITAB reader. It performs no
retrieval, identifier enrichment, graph edits, provenance classification or
scientific-accuracy scoring. Input is one regular local file, at most 2 MiB.

## Upstream implementation checked

The official EBI Maven release and source JAR are under
`runs/intact_xml_validation_20261026/upstream/` with HTTP receipts and SHA-256
hashes. All 782 packaged XML Java source files match the main-source Git blobs
at commit `b66f63654d5878b918aad74af60054b1be0437a8`; see
`upstream/source_commit_comparison.json`. The JAMI modules are Apache-2.0;
Gson 2.13.2 is Apache-2.0. Their transitive artifacts and licenses remain
separate upstream components; the recorded resolved dependency tree is the
runtime inventory.

Version-specific source references:

- [XML versions](https://github.com/MICommunity/psi-jami/blob/b66f63654d5878b918aad74af60054b1be0437a8/jami-xml/src/main/java/psidev/psi/mi/jami/xml/PsiXmlVersion.java)
  and [JAXB dispatch](https://github.com/MICommunity/psi-jami/blob/b66f63654d5878b918aad74af60054b1be0437a8/jami-xml/src/main/java/psidev/psi/mi/jami/xml/io/parser/JaxbUnmarshallerFactory.java)
  support 2.5.3, 2.5.4 and 3.0.0 at source level. A runtime control result is
  still required for the exact version used by a publication.
- [XmlEvidenceStreamSource](https://github.com/MICommunity/psi-jami/blob/b66f63654d5878b918aad74af60054b1be0437a8/jami-xml/src/main/java/psidev/psi/mi/jami/xml/model/extension/datasource/XmlEvidenceStreamSource.java)
  constructs the official evidence parser. This helper exposes the protected
  parser using a small subclass and calls its public `hasFinished()` and
  `parseNextInteraction()` methods. No XML biology parser is implemented here.
- [AbstractXmlIterator](https://github.com/MICommunity/psi-jami/blob/b66f63654d5878b918aad74af60054b1be0437a8/jami-xml/src/main/java/psidev/psi/mi/jami/xml/io/iterator/AbstractXmlIterator.java)
  calls `processNextBinary()` inside `next()` before returning the current
  object. Direct official-parser calls avoid that whole-next-object iterator
  prefetch and emit only objects the official parser actually returns. The
  parser's own flush/lookahead can still fail before returning an object;
  this is not universal malformed-tail recovery. Any terminal parse failure
  invalidates the whole file, including any emitted prefix. No upstream code
  is patched.
- [ExtendedPsiXmlInteractionEvidence](https://github.com/MICommunity/psi-jami/blob/b66f63654d5878b918aad74af60054b1be0437a8/jami-xml/src/main/java/psidev/psi/mi/jami/xml/model/extension/ExtendedPsiXmlInteractionEvidence.java),
  [ExtendedPsiXmlExperiment](https://github.com/MICommunity/psi-jami/blob/b66f63654d5878b918aad74af60054b1be0437a8/jami-xml/src/main/java/psidev/psi/mi/jami/xml/model/extension/ExtendedPsiXmlExperiment.java)
  and [ExtendedPsiXmlParticipantEvidence](https://github.com/MICommunity/psi-jami/blob/b66f63654d5878b918aad74af60054b1be0437a8/jami-xml/src/main/java/psidev/psi/mi/jami/xml/model/extension/ExtendedPsiXmlParticipantEvidence.java)
  expose the complete experiment, host and role lists. The helper avoids their
  lossy singular convenience getters.

`AbstractPsiXmlParser` privately creates a factory using the standard
`XMLInputFactory` provider mechanism, without a public factory-injection
option. The helper supplies a subclass of JAMI's declared Woodstox 4.4.1
provider through the standard `javax.xml.stream.XMLInputFactory` property.
That provider sets the standard `SUPPORT_DTD` and
`IS_SUPPORTING_EXTERNAL_ENTITIES` properties to false and installs a resolver
that throws on every external request. It never calls JAMI's separate
`validateSyntax()` path, which can perform schema resolution. These are
transport settings, with no change to PSI-MI field interpretation. A DTD
declaration is not itself classified as biological data; attempted external
entity use must fail without reading the resource. The synthetic security
control is recorded separately from biological field controls.

## Build and run

With Maven 3.10.0 and JDK 21.0.1 (compiling for Java 11):

```sh
export JAVA_HOME=/Library/Java/JavaVirtualMachines/temurin-21.jdk/Contents/Home
runs/intact_reader_validation_20261026/tooling/apache-maven-3.10.0/bin/mvn \
  -B -f tools/intact_xml_reader/pom.xml \
  -Dmaven.repo.local="$PWD/runs/intact_xml_validation_20261026/m2" \
  package org.apache.maven.plugins:maven-dependency-plugin:3.8.1:build-classpath \
  -DincludeTypes=jar \
  -Dmdep.outputFile="$PWD/runs/intact_xml_validation_20261026/classpath-jars.txt"
"$JAVA_HOME/bin/java" \
  -cp "tools/intact_xml_reader/target/classes:$(cat runs/intact_xml_validation_20261026/classpath-jars.txt)" \
  org.biograph.IntactXmlReader LOCAL_XML_FILE > evidence.jsonl 2> reader.stderr.txt
```

Use the recorded absolute classpath for replay. No model or GPU is involved.
Build logs, runtime versions, resolved artifacts and file hashes belong in
the separate validation run. Never repoint this helper at reserved material
without the parent protocol's access gate.

JAMI's declared `jaxws-ri` aggregate also resolves POM/documentation/sample
ZIP artifacts. Maven dependency plugin 3.8.1's supported `includeTypes=jar`
filter selects executable JARs for the runtime classpath; the full dependency
tree and unfiltered classpath are retained as receipts. No dependency version
is replaced. This plugin capability is specified in its packaged
`META-INF/maven/plugin.xml` and [official parameter documentation](https://maven.apache.org/plugins/maven-dependency-plugin/build-classpath-mojo.html#includeTypes).

## Output contract

Stdout is JSONL with `format: biograph-steward.intact-xml-evidence.v1`.
Upstream stdout is routed to stderr without filtering while parsing. Keep
both streams. A successful parse emits an `evidence` record for each official
object, in source traversal order, with a one-based `evidence_sequence`.
Different evidence objects remain separate even when participants match.

Every evidence contains:

- `xml_id`, official `model_class` and `source_locator` (line/column);
  `identifiers`, qualified `xrefs`, `annotations`, aliases, `imex_id`,
  reader-valued `negative`, all `interaction_types` and confidences.
- `experiments[]`, each preserving local XML ID, names, qualified xrefs,
  annotations, detection method, identification/feature methods, all hosts
  and its publication. Publication identifiers are separate from generic
  qualified xrefs and annotations; PMID/DOI/IMEx convenience values are
  also retained. `original_experiment_ids[]` records the official model's
  original experiment list separately, without inventing associations.
- `participants[]`, in source model order with a one-based `source_index`,
  local XML participant ID, qualified xrefs, annotations, biological role,
  all experimental roles, identification/preparation methods and hosts.
  Role/method/host `experiments[]` retain their explicit official experiment
  associations. Empty associations stay empty. Each interactor retains its
  local XML ID, all identifiers/xrefs, type, organism/labels and aliases.
  `reader_preferred_identifier` is explicitly named as a reader choice.
  Stoichiometry retains the reader's minimum/maximum when provided.

Terms contain `mi_id`, `name`, `full_name`. Xrefs contain database term, ID,
version and qualifier term; XML extension secondary values and annotations
are retained where exposed. Annotations contain their topic term and value.
Organisms retain taxid, scientific/common names, aliases and cell/tissue/
compartment terms without translating those labels into mechanisms.

All listener callbacks are kept with method name, argument classes, public
primitive values, structured terms/organisms and source locators when
available. Error arguments include the complete stack trace. Per-record
diagnostics are those observed during that parse/projection call; entry-level
callbacks and the authoritative complete list remain in the terminal summary.
Callback proximity is not an asserted biological attachment.

Exactly one final `file_summary` gives input bytes/SHA-256, official reader
version, detected XML version, `evidence_count` (emitted records),
`parsed_evidence_count` (official objects returned), all diagnostics, security
settings and a full terminal error. `status` is `completed`,
`completed_with_diagnostics`, or `failed`. A terminal failure exits 2; any
emitted prefix is incomplete and must not be scored as a complete file.
Security includes the denying resolver's invocation count and attempted system
IDs. Zero means that resolver was never called in that process; it is not a
general operating-system network monitor. Any invocation is refused before
resource access, and external-entity support is independently disabled.
Diagnostics do not establish source validity. A caller must explicitly gate
unresolved references, syntax errors or other qualifications as required by
its frozen protocol.

This is a bounded **reader model projection**, not a lossless XML serializer,
an XSD validator or a study-independence classifier. Raw XML and its receipt
remain required. JAMI can supply defaults (including roles, method or
negative values) and prefer identifiers; those values do not prove explicit
markup. Generic `see-also` links, matching pairs, shared participants or
an IMEx identifier alone do not establish independent/shared studies.
