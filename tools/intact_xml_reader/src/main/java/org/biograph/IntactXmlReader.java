package org.biograph;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import psidev.psi.mi.jami.datasource.FileSourceContext;
import psidev.psi.mi.jami.datasource.FileSourceLocator;
import psidev.psi.mi.jami.model.*;
import psidev.psi.mi.jami.xml.io.parser.PsiXmlParser;
import psidev.psi.mi.jami.xml.listener.PsiXmlParserListener;
import psidev.psi.mi.jami.xml.model.extension.*;
import psidev.psi.mi.jami.xml.model.extension.datasource.XmlEvidenceStreamSource;

import java.io.*;
import java.lang.reflect.Proxy;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.*;

/** Bounded local-file projection of the official JAMI 3.9.4 PSI-MI XML reader. */
public final class IntactXmlReader {
    private static final String FORMAT = "biograph-steward.intact-xml-evidence.v1";
    private static final Gson JSON = new GsonBuilder().serializeNulls().disableHtmlEscaping().create();
    private static final int MAX_BYTES = 2 * 1024 * 1024;

    private static final class EvidenceSource extends XmlEvidenceStreamSource {
        EvidenceSource(InputStream input) { super(input); }
        PsiXmlParser<InteractionEvidence> parser() { return getParser(); }
    }

    private static Map<String, Object> map(Object... pairs) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int i = 0; i < pairs.length; i += 2) result.put((String)pairs[i], pairs[i+1]);
        return result;
    }

    private static Map<String, Object> locator(Object value) {
        FileSourceLocator loc = value instanceof FileSourceLocator ? (FileSourceLocator)value
                : value instanceof FileSourceContext ? ((FileSourceContext)value).getSourceLocator() : null;
        return loc == null ? null : map("line", loc.getLineNumber(), "column", loc.getCharNumber());
    }

    private static Map<String, Object> term(CvTerm value) {
        return value == null ? null : map("mi_id", value.getMIIdentifier(),
                "name", value.getShortName(), "full_name", value.getFullName());
    }

    private static List<Object> terms(Collection<? extends CvTerm> values) {
        List<Object> result = new ArrayList<>();
        for (CvTerm value : values) result.add(term(value));
        return result;
    }

    private static List<Object> annotations(Collection<? extends Annotation> values) {
        List<Object> result = new ArrayList<>();
        for (Annotation value : values) result.add(map("topic", term(value.getTopic()),
                "value", value.getValue(), "source_locator", locator(value)));
        return result;
    }

    private static Map<String, Object> xref(Xref value) {
        if (value == null) return null;
        Map<String, Object> result = map("database", term(value.getDatabase()), "id", value.getId(),
                "version", value.getVersion(), "qualifier", term(value.getQualifier()), "source_locator", locator(value));
        if (value instanceof ExtendedPsiXmlXref) {
            ExtendedPsiXmlXref extended = (ExtendedPsiXmlXref)value;
            result.put("secondary", extended.getSecondary());
            result.put("annotations", annotations(extended.getAnnotations()));
        }
        return result;
    }

    private static List<Object> xrefs(Collection<? extends Xref> values) {
        List<Object> result = new ArrayList<>();
        for (Xref value : values) result.add(xref(value));
        return result;
    }

    private static List<Object> aliases(Collection<? extends Alias> values) {
        List<Object> result = new ArrayList<>();
        for (Alias value : values) result.add(map("type", term(value.getType()), "name", value.getName()));
        return result;
    }

    private static Integer experimentId(Experiment value) {
        return value instanceof ExtendedPsiXmlExperiment ? ((ExtendedPsiXmlExperiment)value).getId() : null;
    }

    /** Public, version-specific JAMI getters preserve experiment-scoped roles and hosts. */
    private static Collection<Experiment> associatedExperiments(Object value) {
        if (value instanceof psidev.psi.mi.jami.xml.model.extension.xml253.ExperimentalCvTerm)
            return ((psidev.psi.mi.jami.xml.model.extension.xml253.ExperimentalCvTerm)value).getExperiments();
        if (value instanceof psidev.psi.mi.jami.xml.model.extension.xml254.ExperimentalCvTerm)
            return ((psidev.psi.mi.jami.xml.model.extension.xml254.ExperimentalCvTerm)value).getExperiments();
        if (value instanceof psidev.psi.mi.jami.xml.model.extension.xml300.ExperimentalCvTerm)
            return ((psidev.psi.mi.jami.xml.model.extension.xml300.ExperimentalCvTerm)value).getExperiments();
        if (value instanceof psidev.psi.mi.jami.xml.model.extension.xml253.HostOrganism)
            return ((psidev.psi.mi.jami.xml.model.extension.xml253.HostOrganism)value).getExperiments();
        if (value instanceof psidev.psi.mi.jami.xml.model.extension.xml254.HostOrganism)
            return ((psidev.psi.mi.jami.xml.model.extension.xml254.HostOrganism)value).getExperiments();
        if (value instanceof psidev.psi.mi.jami.xml.model.extension.xml300.HostOrganism)
            return ((psidev.psi.mi.jami.xml.model.extension.xml300.HostOrganism)value).getExperiments();
        return Collections.emptyList();
    }

    private static List<Object> experimentIds(Collection<? extends Experiment> values) {
        List<Object> result = new ArrayList<>();
        for (Experiment value : values) result.add(map("xml_id", experimentId(value),
                "model_class", value.getClass().getName(), "source_locator", locator(value)));
        return result;
    }

    private static List<Object> experimentalTerms(Collection<? extends CvTerm> values) {
        List<Object> result = new ArrayList<>();
        for (CvTerm value : values) result.add(map("term", term(value),
                "experiments", experimentIds(associatedExperiments(value)), "source_locator", locator(value)));
        return result;
    }

    private static Map<String, Object> organism(Organism value) {
        return value == null ? null : map("taxid", value.getTaxId(), "scientific_name", value.getScientificName(),
                "common_name", value.getCommonName(), "aliases", aliases(value.getAliases()),
                "cell_type", term(value.getCellType()), "tissue", term(value.getTissue()),
                "compartment", term(value.getCompartment()), "experiments", experimentIds(associatedExperiments(value)),
                "source_locator", locator(value));
    }

    private static List<Object> organisms(Collection<? extends Organism> values) {
        List<Object> result = new ArrayList<>();
        for (Organism value : values) result.add(organism(value));
        return result;
    }

    private static Map<String, Object> publication(Publication value) {
        return value == null ? null : map("identifiers", xrefs(value.getIdentifiers()), "xrefs", xrefs(value.getXrefs()),
                "annotations", annotations(value.getAnnotations()), "pubmed_id", value.getPubmedId(),
                "doi", value.getDoi(), "imex_id", value.getImexId(), "title", value.getTitle(),
                "journal", value.getJournal(), "authors", value.getAuthors(), "source_locator", locator(value));
    }

    private static List<Object> confidences(Collection<? extends Confidence> values) {
        List<Object> result = new ArrayList<>();
        for (Confidence value : values) result.add(map("type", term(value.getType()), "value", value.getValue()));
        return result;
    }

    private static Map<String, Object> experiment(Experiment value) {
        Map<String, Object> result = map("xml_id", experimentId(value), "model_class", value.getClass().getName(),
                "source_locator", locator(value), "xrefs", xrefs(value.getXrefs()),
                "annotations", annotations(value.getAnnotations()), "publication", publication(value.getPublication()),
                "detection_method", term(value.getInteractionDetectionMethod()), "confidences", confidences(value.getConfidences()));
        if (!(value instanceof ExtendedPsiXmlExperiment))
            throw new IllegalStateException("Official XML experiment does not expose the full-list XML API: " + value.getClass().getName());
        ExtendedPsiXmlExperiment extended = (ExtendedPsiXmlExperiment)value;
        result.put("short_name", extended.getShortName());
        result.put("full_name", extended.getFullName());
        result.put("aliases", aliases(extended.getAliases()));
        result.put("host_organisms", organisms(extended.getHostOrganisms()));
        result.put("participant_identification_method", term(extended.getParticipantIdentificationMethod()));
        result.put("feature_detection_method", term(extended.getFeatureDetectionMethod()));
        return result;
    }

    private static Map<String, Object> interactor(Interactor value) {
        if (value == null) return null;
        return map("xml_id", value instanceof ExtendedPsiXmlInteractor ? ((ExtendedPsiXmlInteractor)value).getId() : null,
                "model_class", value.getClass().getName(), "source_locator", locator(value),
                "identifiers", xrefs(value.getIdentifiers()), "xrefs", xrefs(value.getXrefs()),
                "reader_preferred_identifier", xref(value.getPreferredIdentifier()), "short_name", value.getShortName(),
                "full_name", value.getFullName(), "type", term(value.getInteractorType()),
                "organism", organism(value.getOrganism()), "aliases", aliases(value.getAliases()),
                "annotations", annotations(value.getAnnotations()));
    }

    private static Map<String, Object> participant(ParticipantEvidence value, int index) {
        if (!(value instanceof ExtendedPsiXmlParticipantEvidence))
            throw new IllegalStateException("Official XML participant does not expose the full-list XML API: " + value.getClass().getName());
        ExtendedPsiXmlParticipantEvidence extended = (ExtendedPsiXmlParticipantEvidence)value;
        Stoichiometry stoich = value.getStoichiometry();
        return map("source_index", index, "xml_id", extended.getId(), "model_class", value.getClass().getName(),
                "source_locator", locator(value), "xrefs", xrefs(value.getXrefs()),
                "annotations", annotations(value.getAnnotations()), "aliases", aliases(value.getAliases()),
                "interactor", interactor(value.getInteractor()), "biological_role", term(value.getBiologicalRole()),
                "experimental_roles", experimentalTerms(extended.getExperimentalRoles()),
                "identification_methods", experimentalTerms(value.getIdentificationMethods()),
                "experimental_preparations", experimentalTerms(value.getExperimentalPreparations()),
                "host_organisms", organisms(extended.getHostOrganisms()),
                "stoichiometry", stoich == null ? null : map("min", stoich.getMinValue(), "max", stoich.getMaxValue()));
    }

    private static Map<String, Object> evidence(InteractionEvidence value) {
        if (!(value instanceof ExtendedPsiXmlInteractionEvidence))
            throw new IllegalStateException("Official XML evidence does not expose the full-list XML API: " + value.getClass().getName());
        ExtendedPsiXmlInteractionEvidence extended = (ExtendedPsiXmlInteractionEvidence)value;
        List<Object> experiments = new ArrayList<>();
        for (Experiment exp : extended.getExperiments()) experiments.add(experiment(exp));
        List<Object> participants = new ArrayList<>();
        int index = 0;
        for (ParticipantEvidence item : value.getParticipants()) participants.add(participant(item, ++index));
        return map("xml_id", extended.getId(), "model_class", value.getClass().getName(),
                "source_locator", locator(value), "identifiers", xrefs(value.getIdentifiers()),
                "xrefs", xrefs(value.getXrefs()), "annotations", annotations(value.getAnnotations()),
                "aliases", aliases(extended.getAliases()), "imex_id", value.getImexId(), "negative", value.isNegative(),
                "interaction_types", terms(extended.getInteractionTypes()), "experiments", experiments,
                "original_experiment_ids", experimentIds(extended.getOriginalExperiments()),
                "participants", participants, "confidences", confidences(value.getConfidences()),
                "reader_inferred", value.isInferred(), "reader_modelled", extended.isModelled(),
                "reader_intramolecular", extended.isIntraMolecular(), "availability", value.getAvailability());
    }

    private static Map<String, Object> error(Throwable error) {
        StringWriter stack = new StringWriter();
        error.printStackTrace(new PrintWriter(stack));
        return map("class", error.getClass().getName(), "message", error.getMessage(), "stacktrace", stack.toString());
    }

    private static Object diagnosticArgument(Object value) {
        if (value == null || value instanceof String || value instanceof Number || value instanceof Boolean) return value;
        if (value instanceof Throwable) return error((Throwable)value);
        if (value instanceof CvTerm) return term((CvTerm)value);
        if (value instanceof Organism) return organism((Organism)value);
        if (value instanceof Collection) {
            List<Object> values = new ArrayList<>();
            for (Object item : (Collection<?>)value) values.add(diagnosticArgument(item));
            return values;
        }
        return map("class", value.getClass().getName(), "source_locator", locator(value));
    }

    private static PsiXmlParserListener listener(List<Object> diagnostics) {
        return (PsiXmlParserListener)Proxy.newProxyInstance(IntactXmlReader.class.getClassLoader(),
                new Class<?>[]{PsiXmlParserListener.class}, (proxy, method, args) -> {
                    if (method.getDeclaringClass() == Object.class) {
                        if (method.getName().equals("toString")) return "IntactXmlReader diagnostic listener";
                        if (method.getName().equals("hashCode")) return System.identityHashCode(proxy);
                        if (method.getName().equals("equals")) return proxy == args[0];
                    }
                    List<Object> values = new ArrayList<>();
                    List<Object> classes = new ArrayList<>();
                    if (args != null) for (Object arg : args) {
                        classes.add(arg == null ? null : arg.getClass().getName());
                        values.add(diagnosticArgument(arg));
                    }
                    diagnostics.add(map("callback", method.getName(), "arg_classes", classes, "arguments", values));
                    return null;
                });
    }

    private static String sha256(byte[] input) throws Exception {
        StringBuilder value = new StringBuilder();
        for (byte b : MessageDigest.getInstance("SHA-256").digest(input)) value.append(String.format("%02x", b & 255));
        return value.toString();
    }

    public static void main(String[] args) {
        PrintStream transport = System.out;
        List<Object> diagnostics = new ArrayList<>();
        EvidenceSource source = null;
        Throwable failure = null;
        int count = 0;
        int parsedCount = 0;
        String version = null;
        String digest = null;
        Long bytes = null;
        String input = args.length == 1 ? args[0] : null;
        try {
            if (input == null) throw new IllegalArgumentException("Usage: org.biograph.IntactXmlReader LOCAL_XML_FILE (maximum 2 MiB)");
            Path path = Path.of(input);
            if (!Files.isRegularFile(path)) throw new IllegalArgumentException("Input must be a regular local file");
            bytes = Files.size(path);
            if (bytes > MAX_BYTES) throw new IllegalArgumentException("Input exceeds fixed maximum of " + MAX_BYTES + " bytes");
            byte[] body = Files.readAllBytes(path);
            if (body.length > MAX_BYTES) throw new IllegalArgumentException("Input grew beyond fixed maximum");
            digest = sha256(body);
            System.setProperty("javax.xml.stream.XMLInputFactory", OfflineXmlInputFactory.class.getName());
            // Keep upstream prose on stderr; stdout remains exactly JSONL, with no filtering.
            System.setOut(System.err);
            source = new EvidenceSource(new ByteArrayInputStream(body));
            source.setFileParserListener(listener(diagnostics));
            PsiXmlParser<InteractionEvidence> parser = source.parser();
            while (!parser.hasFinished()) {
                int before = diagnostics.size();
                InteractionEvidence item = parser.parseNextInteraction();
                version = parser.getVersion() == null ? null : parser.getVersion().name();
                if (item == null) continue;
                ++parsedCount;
                Map<String, Object> projected = evidence(item);
                ++count;
                transport.println(JSON.toJson(map("format", FORMAT, "record_kind", "evidence",
                        "evidence_sequence", count, "xml_version", version, "evidence", projected,
                        "diagnostics", new ArrayList<>(diagnostics.subList(before, diagnostics.size())))));
            }
        } catch (Exception | LinkageError problem) {
            failure = problem;
            problem.printStackTrace(System.err);
        } finally {
            if (source != null) {
                try { source.close(); }
                catch (Exception | LinkageError problem) {
                    diagnostics.add(map("callback", "bridge_close_failure", "error", error(problem)));
                    problem.printStackTrace(System.err);
                    if (failure == null) failure = problem;
                }
            }
            System.setOut(transport);
        }
        transport.println(JSON.toJson(map("format", FORMAT, "record_kind", "file_summary",
                "status", failure != null ? "failed" : diagnostics.isEmpty() ? "completed" : "completed_with_diagnostics",
                "input_file", input, "input_sha256", digest, "input_bytes", bytes,
                "xml_version", version, "evidence_count", count, "parsed_evidence_count", parsedCount,
                "diagnostics", diagnostics,
                "error", failure == null ? null : error(failure), "reader", "psidev.psi.mi.jami:jami-xml:3.9.4",
                "security", map("provider", OfflineXmlInputFactory.class.getName(), "support_dtd", false,
                        "support_external_entities", false, "external_resolver", "deny", "schema_validation_invoked", false,
                        "resolver_attempt_count", OfflineXmlInputFactory.resolverAttempts().size(),
                        "resolver_attempted_system_ids", OfflineXmlInputFactory.resolverAttempts()),
                "limitations", Arrays.asList("Official reader model projection; not raw XML or XSD validation.",
                        "Reader defaults and preferred identifiers are not proof of explicit source markup.",
                        "No study-independence or scientific-truth inference; qualified citations remain citations."))));
        if (failure != null) System.exit(2);
    }
}
